import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Brain, CheckCircle, Loader2, Sparkles, Zap } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/app-shell";
import { Protected } from "@/components/protected";
import { Button } from "@/components/ui/button";
import { SeverityBadge, StatusBadge } from "@/components/badges";
import { ReportView } from "@/components/report-view";
import {
  api,
  getToken,
  type Incident,
  type InvestigationHistoryItem,
  type InvestigationReport,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/investigate/$incident_id")({
  ssr: false,
  component: () => (
    <Protected>
      <InvestigationPage />
    </Protected>
  ),
});

type InvestigationMode = "standard" | "crew";

// ─── Mode selector card ───────────────────────────────────────────────────────
function ModeCard({
  mode,
  selected,
  onSelect,
}: {
  mode: InvestigationMode;
  selected: boolean;
  onSelect: () => void;
}) {
  const isStandard = mode === "standard";

  return (
    <button
      onClick={onSelect}
      className={cn(
        "flex flex-1 flex-col items-start rounded-lg border-2 p-5 text-left transition-all",
        selected
          ? "border-primary bg-primary/5"
          : "border-border bg-card hover:border-primary/40 hover:bg-card-elevated/50",
      )}
    >
      <div className="flex items-center gap-2">
        <div
          className={cn(
            "flex h-9 w-9 items-center justify-center rounded-lg",
            isStandard ? "bg-primary/15" : "bg-warning/15",
          )}
        >
          {isStandard ? (
            <Zap className={cn("h-4 w-4", selected ? "text-primary" : "text-muted-foreground")} />
          ) : (
            <Brain className={cn("h-4 w-4", selected ? "text-warning" : "text-muted-foreground")} />
          )}
        </div>
        <div>
          <p className="text-sm font-semibold">
            {isStandard ? "Quick Investigation" : "Deep Investigation"}
          </p>
          <p className="text-[11px] text-muted-foreground">
            {isStandard ? "RAG + Gemini · ~10s" : "CrewAI · 4 agents · ~60-90s"}
          </p>
        </div>
        {selected && <CheckCircle className="ml-auto h-4 w-4 text-primary" />}
      </div>
      <p className="mt-3 text-xs text-muted-foreground leading-relaxed">
        {isStandard
          ? "Single LLM call. Fast, cheap, great for most incidents. Uses your indexed documentation for grounded evidence."
          : "4 specialised agents: Retriever (Python, 0 tokens) → Analyst → Recommender → Reporter. Better reasoning for complex incidents. 3 LLM calls."}
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {isStandard ? (
          <>
            <Chip label="1 LLM call" color="primary" />
            <Chip label="~5-15s" color="muted" />
            <Chip label="Streaming" color="muted" />
          </>
        ) : (
          <>
            <Chip label="3 LLM calls" color="warning" />
            <Chip label="~60-90s" color="muted" />
            <Chip label="CrewAI agents" color="warning" />
            <Chip label="Deeper reasoning" color="muted" />
          </>
        )}
      </div>
    </button>
  );
}

function Chip({ label, color }: { label: string; color: "primary" | "warning" | "muted" }) {
  return (
    <span
      className={cn(
        "rounded-full border px-2 py-0.5 text-[10px] font-medium",
        color === "primary" && "border-primary/30 bg-primary/10 text-primary",
        color === "warning" && "border-warning/30 bg-warning/10 text-warning",
        color === "muted" && "border-border bg-card-elevated text-muted-foreground",
      )}
    >
      {label}
    </span>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────
function InvestigationPage() {
  const { incident_id } = Route.useParams();
  const incidentIdNum = Number(incident_id);

  const qc = useQueryClient();
  const navigate = useNavigate();

  const incidentsQuery = useQuery({
    queryKey: ["incidents"],
    queryFn: () => api.get<Incident[]>("/api/v1/incidents"),
  });

  const historyQuery = useQuery({
    queryKey: ["history"],
    queryFn: () => api.get<InvestigationHistoryItem[]>("/api/v1/investigate/history"),
  });

  const existingHistoryItem = historyQuery.data?.find(
    (r) => r.incident_id === incidentIdNum,
  );

  const [mode, setMode] = useState<InvestigationMode>("standard");
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState("");
  const [output, setOutput] = useState("");
  const [report, setReport] = useState<InvestigationReport | null>(null);
  const terminalRef = useRef<HTMLDivElement>(null);

  // Load existing report on mount
  useEffect(() => {
    if (existingHistoryItem && !report && !running) {
      api
        .get<InvestigationReport>(`/api/v1/investigate/history/${existingHistoryItem.id}`)
        .then((r) => setReport(r))
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingHistoryItem?.id]);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [output]);

  // ── Standard (streaming SSE) ────────────────────────────────────────
  async function runStandard() {
    setRunning(true);
    setOutput("");
    setReport(null);
    setStage("Retrieving documentation…");

    try {
      const res = await fetch(
        `${api.baseUrl}/api/v1/investigate/${incidentIdNum}/stream`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getToken() ?? ""}`,
          },
        },
      );

      if (!res.ok || !res.body) throw new Error(`Failed (${res.status})`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let charCount = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const evt of events) {
          const dataLine = evt.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          const payload = dataLine.slice(5).trim();
          if (!payload) continue;

          try {
            const parsed = JSON.parse(payload);
            if (parsed.type === "token") {
              setOutput((o) => o + (parsed.content ?? ""));
              charCount += (parsed.content ?? "").length;
              if (charCount < 100) setStage("Analysing incident…");
              else if (charCount < 500) setStage("Generating report…");
              else setStage("Finalising…");
            } else if (parsed.type === "done") {
              setReport(parsed.report as InvestigationReport);
              setStage("Complete ✓");
              qc.invalidateQueries({ queryKey: ["history"] });
            } else if (parsed.type === "error") {
              throw new Error(parsed.detail ?? "Investigation failed");
            }
          } catch (parseErr) {
            if (parseErr instanceof SyntaxError) {
              setOutput((o) => o + payload);
            } else {
              throw parseErr;
            }
          }
        }
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Investigation failed");
    } finally {
      setRunning(false);
    }
  }

  // ── Deep (CrewAI — blocking REST call) ─────────────────────────────
  async function runCrew() {
    setRunning(true);
    setOutput("");
    setReport(null);

    // Simulate progress stages while waiting for the blocking crew response
    const stages = [
      "🔍 Retrieving documentation from knowledge base…",
      "🧠 Analyst diagnosing root cause…",
      "🔧 Recommender producing remediation steps…",
      "📝 Reporter formatting final report…",
      "⏳ Finalising investigation…",
    ];
    let stageIdx = 0;
    setStage(stages[0]);

    const stageInterval = setInterval(() => {
      stageIdx = Math.min(stageIdx + 1, stages.length - 1);
      setStage(stages[stageIdx]);
    }, 15000); // advance stage every 15s

    try {
      const result = await api.post<InvestigationReport>(
        `/api/v1/investigate/${incidentIdNum}/crew`,
      );
      setReport(result);
      setStage("Complete ✓");
      qc.invalidateQueries({ queryKey: ["history"] });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Deep investigation failed");
    } finally {
      clearInterval(stageInterval);
      setRunning(false);
    }
  }

  function startInvestigation() {
    if (mode === "standard") runStandard();
    else runCrew();
  }

  const incident = incidentsQuery.data?.find((i) => i.id === incidentIdNum);

  return (
    <AppShell title="Investigation">
      <div className="mx-auto max-w-7xl space-y-6">

        {/* Incident details */}
        {incident && (
          <div className="rounded-lg border border-border bg-card p-5">
            <h2 className="text-lg font-semibold">{incident.title}</h2>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <SeverityBadge severity={incident.severity} />
              <StatusBadge status={incident.status} />
              <span>Service: {incident.service}</span>
            </div>
            <p className="mt-3 max-w-3xl text-sm text-muted-foreground">
              {incident.description}
            </p>
          </div>
        )}

        {/* Mode selection + launch */}
        {!report && !running && (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold">Choose investigation mode</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Both modes use your indexed documentation as evidence.
              </p>
            </div>

            <div className="flex gap-4">
              <ModeCard mode="standard" selected={mode === "standard"} onSelect={() => setMode("standard")} />
              <ModeCard mode="crew" selected={mode === "crew"} onSelect={() => setMode("crew")} />
            </div>

            {existingHistoryItem && (
              <p className="text-xs text-muted-foreground">
                A previous investigation exists — starting a new one creates an additional history entry.
              </p>
            )}

            <div className="flex items-center gap-3">
              <Button
                size="lg"
                onClick={startInvestigation}
                className={cn(
                  "min-w-56",
                  mode === "crew" && "bg-warning text-warning-foreground hover:bg-warning/90",
                )}
              >
                {mode === "standard" ? (
                  <><Zap className="h-4 w-4" />Quick Investigation</>
                ) : (
                  <><Brain className="h-4 w-4" />Deep Investigation (CrewAI)</>
                )}
              </Button>
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <AlertTriangle className="h-3 w-3 text-warning" />
                {mode === "standard" ? "~1 AI credit" : "~3 AI credits · takes 60-90s"}
              </p>
            </div>
          </div>
        )}

        {/* Running state */}
        {running && (
          <div className="rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 border-b border-border px-4 py-3 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
              <span>{stage || "Working…"}</span>
              {mode === "crew" && (
                <span className="ml-auto rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 text-[10px] font-medium text-warning">
                  CrewAI
                </span>
              )}
            </div>
            {/* Standard mode shows streaming tokens; crew mode shows a spinner */}
            {mode === "standard" ? (
              <div
                ref={terminalRef}
                className="max-h-96 overflow-auto whitespace-pre-wrap p-4 text-xs text-foreground/90"
                style={{ fontFamily: "'JetBrains Mono', ui-monospace, monospace" }}
              >
                {output || <span className="text-muted-foreground">Awaiting output…</span>}
                <span className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-primary" />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center gap-4 py-16">
                <div className="relative flex h-16 w-16 items-center justify-center">
                  <div className="absolute h-16 w-16 animate-spin rounded-full border-2 border-transparent border-t-warning" />
                  <Brain className="h-6 w-6 text-warning" />
                </div>
                <div className="text-center">
                  <p className="text-sm font-medium">CrewAI agents are working…</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    3 agents collaborating in sequence. This takes 60–90 seconds.
                  </p>
                </div>
                <div className="flex gap-2 text-xs text-muted-foreground">
                  {["Retriever", "Analyst", "Recommender", "Reporter"].map((a, i) => (
                    <span key={a} className="flex items-center gap-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-warning/60 animate-pulse"
                        style={{ animationDelay: `${i * 300}ms` }} />
                      {a}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Report */}
        {report && !running && (
          <>
            {report.investigation_mode === "crew" && (
              <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 px-4 py-2.5 text-xs text-warning">
                <Brain className="h-3.5 w-3.5" />
                This report was generated by the CrewAI deep investigation (3 specialised agents).
              </div>
            )}
            <ReportView
              report={report}
              onReinvestigate={() => {
                setReport(null);
                setOutput("");
              }}
            />
          </>
        )}
      </div>
    </AppShell>
  );
}
