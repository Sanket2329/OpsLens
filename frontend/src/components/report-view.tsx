import {
  AlertTriangle,
  BookOpen,
  CheckCircle,
  Copy,
  Download,
  FileText,
  GitCompare,
  HelpCircle,
  Info,
  Lightbulb,
  Loader2,
  Shield,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ConfidenceGauge, SimilarityBar } from "@/components/confidence-gauge";
import {
  api,
  getToken,
  type InvestigationReport,
  type RootCauseStatus,
  type RunbookResult,
  type SimilarInvestigation,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatRelative } from "@/lib/format";

// ─── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: RootCauseStatus }) {
  const map: Record<
    RootCauseStatus,
    { color: string; icon: React.ReactNode; label: string }
  > = {
    Confirmed: {
      color: "bg-success/15 text-success border-success/30",
      icon: <CheckCircle className="h-3 w-3" />,
      label: "Confirmed",
    },
    Likely: {
      color: "bg-warning/15 text-warning border-warning/30",
      icon: <AlertTriangle className="h-3 w-3" />,
      label: "Likely",
    },
    "Unable to Determine": {
      color: "bg-danger/15 text-danger border-danger/30",
      icon: <HelpCircle className="h-3 w-3" />,
      label: "Unable to Determine",
    },
  };
  const s = map[status] ?? map["Likely"];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-semibold",
        s.color,
      )}
    >
      {s.icon}
      {s.label}
    </span>
  );
}

// ─── Confidence level badge ────────────────────────────────────────────────────
function ConfidenceBadge({ level, pct }: { level: string; pct: number }) {
  const color =
    level === "High"
      ? "bg-success/15 text-success border-success/30"
      : level === "Medium"
        ? "bg-warning/15 text-warning border-warning/30"
        : "bg-danger/15 text-danger border-danger/30";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-semibold",
        color,
      )}
    >
      {level} — {pct}%
    </span>
  );
}

// ─── Section wrapper ───────────────────────────────────────────────────────────
function Section({
  title,
  icon,
  children,
  className,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn("rounded-lg border border-border bg-card p-5", className)}
    >
      <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {icon}
        {title}
      </h3>
      {children}
    </div>
  );
}

// ─── Main ReportView ───────────────────────────────────────────────────────────
export function ReportView({
  report,
  onReinvestigate,
}: {
  report: InvestigationReport;
  onReinvestigate?: () => void;
}) {
  const confPct = Math.max(0, Math.min(100, report.confidence));
  const rootCauseStatus = report.root_cause_status ?? "Likely";
  const retrievedChunks = report.retrieved_chunks?.length
    ? report.retrieved_chunks
    : (report.sources ?? []);

  // Runbook generation state
  const [runbookLoading, setRunbookLoading] = useState(false);
  const [runbookDone, setRunbookDone] = useState(false);

  // Similar investigations state
  const [similar, setSimilar] = useState<SimilarInvestigation[] | null>(null);
  const [similarLoading, setSimilarLoading] = useState(false);

  async function generateRunbook() {
    if (!report.id) return;
    setRunbookLoading(true);
    try {
      const result = await api.post<RunbookResult>(
        `/api/v1/investigate/history/${report.id}/runbook`,
      );
      setRunbookDone(true);
      toast.success(
        `Runbook generated and indexed (${result.chunks_indexed} chunks). Future investigations will use it.`,
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Runbook generation failed");
    } finally {
      setRunbookLoading(false);
    }
  }

  async function loadSimilar() {
    if (!report.id || similarLoading) return;
    setSimilarLoading(true);
    try {
      const result = await api.get<{
        similar_investigations: SimilarInvestigation[];
      }>(`/api/v1/investigate/history/${report.id}/similar`);
      setSimilar(result.similar_investigations);
    } catch {
      setSimilar([]);
    } finally {
      setSimilarLoading(false);
    }
  }

  async function downloadMd() {
    try {
      const md = await api.get<string>(
        `/api/v1/investigate/history/${report.id}/report.md`,
      );
      _triggerDownload(
        new Blob([md], { type: "text/markdown" }),
        `investigation-${report.id}.md`,
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Download failed");
    }
  }

  async function downloadPdf() {
    try {
      const token = getToken();
      const res = await fetch(
        `${api.baseUrl}/api/v1/investigate/history/${report.id}/report.pdf`,
        { headers: { Authorization: `Bearer ${token ?? ""}` } },
      );
      if (!res.ok) throw new Error(`PDF generation failed (${res.status})`);
      _triggerDownload(
        new Blob([await res.arrayBuffer()], { type: "application/pdf" }),
        `investigation-${report.id}.pdf`,
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "PDF download failed");
    }
  }

  function _triggerDownload(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      {/* ── Header bar ─────────────────────────────────────────────────────── */}
      {report.incident_summary && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold">
                {report.incident_summary.title}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {report.incident_summary.affected_service} ·{" "}
                {report.incident_summary.severity}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={rootCauseStatus} />
              <ConfidenceBadge
                level={report.confidence_level ?? "Medium"}
                pct={confPct}
              />
            </div>
          </div>
          {report.incident_summary.business_impact && (
            <p className="mt-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">
                Business impact:
              </span>{" "}
              {report.incident_summary.business_impact}
            </p>
          )}
        </div>
      )}

      {/* ── Main 2-col layout ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_300px]">
        {/* LEFT COLUMN */}
        <div className="space-y-4">
          {/* Executive Summary */}
          {report.executive_summary && (
            <Section
              title="Executive Summary"
              icon={<Info className="h-3.5 w-3.5" />}
            >
              <p className="text-sm leading-relaxed text-foreground/90">
                {report.executive_summary}
              </p>
            </Section>
          )}

          {/* Observed Evidence */}
          {(report.observed_evidence?.length ?? 0) > 0 && (
            <Section
              title="Observed Evidence"
              icon={<Shield className="h-3.5 w-3.5" />}
            >
              <ul className="space-y-1.5">
                {report.observed_evidence!.map((e, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <CheckCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
                    <span>{e}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {/* Root Cause */}
          <Section
            title="Root Cause Analysis"
            icon={<AlertTriangle className="h-3.5 w-3.5" />}
          >
            <div className="mb-2">
              <StatusBadge status={rootCauseStatus} />
            </div>
            <p className="text-sm leading-relaxed">{report.root_cause}</p>
          </Section>

          {/* Alternative Hypotheses */}
          {(report.alternative_hypotheses?.length ?? 0) > 0 && (
            <Section
              title="Alternative Hypotheses"
              icon={<Lightbulb className="h-3.5 w-3.5" />}
            >
              <div className="space-y-3">
                {report.alternative_hypotheses!.map((h, i) => (
                  <div
                    key={i}
                    className="rounded-md border border-border bg-card-elevated/40 p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium">{h.hypothesis}</p>
                      <span
                        className={cn(
                          "shrink-0 rounded px-1.5 py-0.5 text-xs font-semibold tabular-nums",
                          h.confidence_pct >= 75
                            ? "bg-success/15 text-success"
                            : h.confidence_pct >= 50
                              ? "bg-warning/15 text-warning"
                              : "bg-muted text-muted-foreground",
                        )}
                      >
                        {h.confidence_pct}%
                      </span>
                    </div>
                    {h.reasoning && (
                      <p className="mt-1.5 text-xs text-muted-foreground">
                        {h.reasoning}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Immediate Actions */}
          <Section title="Immediate Actions">
            {(report.immediate_actions?.length ?? 0) > 0 ? (
              <ol className="space-y-2 text-sm">
                {report.immediate_actions!.map((a, i) => (
                  <li
                    key={i}
                    className="group flex items-start gap-3 rounded-md border border-border bg-card-elevated/40 p-3"
                  >
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-primary/20 text-xs font-medium text-primary">
                      {i + 1}
                    </span>
                    <span className="flex-1">{a}</span>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(a);
                        toast.success("Copied");
                      }}
                      className="opacity-0 transition group-hover:opacity-100"
                    >
                      <Copy className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
                    </button>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-xs text-muted-foreground">None recommended.</p>
            )}
          </Section>

          {/* Long-term Prevention */}
          <Section title="Long-term Prevention">
            {(report.long_term_prevention?.length ?? 0) > 0 ? (
              <ol className="list-decimal space-y-2 pl-5 text-sm text-muted-foreground marker:text-primary">
                {report.long_term_prevention!.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ol>
            ) : (
              <p className="text-xs text-muted-foreground">None recommended.</p>
            )}
          </Section>

          {/* AI Reasoning Notes */}
          {report.ai_reasoning_notes && (
            <Section
              title="AI Reasoning Notes"
              icon={<Info className="h-3.5 w-3.5" />}
            >
              <p className="text-sm italic text-muted-foreground leading-relaxed">
                {report.ai_reasoning_notes}
              </p>
            </Section>
          )}
        </div>

        {/* RIGHT COLUMN */}
        <div className="space-y-4">
          {/* Confidence gauge */}
          <div className="flex flex-col items-center rounded-lg border border-border bg-card p-6">
            <ConfidenceGauge value={confPct} />
            {report.confidence_reasoning && (
              <p className="mt-3 text-center text-xs text-muted-foreground leading-relaxed">
                {report.confidence_reasoning}
              </p>
            )}
          </div>

          {/* Retrieved Evidence */}
          <Section title="Retrieved Evidence">
            {retrievedChunks.length > 0 ? (
              <div className="space-y-3">
                {retrievedChunks.map((c, i) => (
                  <div
                    key={i}
                    className="rounded-md border border-border bg-card-elevated/30 p-3 space-y-1.5"
                  >
                    <div className="flex items-start justify-between gap-2 text-xs">
                      <span className="truncate font-medium text-primary/90">
                        {c.filename ?? `doc_${c.document_id}`}
                      </span>
                      <span className="shrink-0 text-muted-foreground">
                        #{c.chunk_index}
                      </span>
                    </div>
                    <SimilarityBar value={c.score ?? 0} />
                    {c.snippet && (
                      <p className="border-l-2 border-border pl-2 text-[11px] text-muted-foreground italic leading-relaxed line-clamp-3">
                        {c.snippet}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                No documentation retrieved.
              </p>
            )}
          </Section>

          {/* Evidence Coverage */}
          {report.evidence_coverage && (
            <Section title="Evidence Coverage">
              <div className="space-y-3 text-xs">
                {(report.evidence_coverage.evidence_used?.length ?? 0) > 0 && (
                  <div>
                    <p className="mb-1 font-semibold text-success">Used</p>
                    {report.evidence_coverage.evidence_used!.map((e, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-1.5 text-muted-foreground"
                      >
                        <CheckCircle className="h-3 w-3 text-success" />
                        {e}
                      </div>
                    ))}
                  </div>
                )}
                {(report.evidence_coverage.missing_evidence?.length ?? 0) >
                  0 && (
                  <div>
                    <p className="mb-1 font-semibold text-danger">Missing</p>
                    {report.evidence_coverage.missing_evidence!.map((m, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-1.5 text-muted-foreground"
                      >
                        <XCircle className="h-3 w-3 text-danger" />
                        {m}
                      </div>
                    ))}
                  </div>
                )}
                {(report.evidence_coverage.unknowns?.length ?? 0) > 0 && (
                  <div>
                    <p className="mb-1 font-semibold text-warning">Unknowns</p>
                    {report.evidence_coverage.unknowns!.map((u, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-1.5 text-muted-foreground"
                      >
                        <HelpCircle className="h-3 w-3 text-warning" />
                        {u}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Section>
          )}

          {/* Download actions */}
          {report.id && (
            <div className="space-y-2">
              <Button
                variant="secondary"
                className="w-full"
                onClick={downloadMd}
              >
                <Download className="h-3.5 w-3.5" />
                Download Markdown
              </Button>
              <Button
                variant="secondary"
                className="w-full"
                onClick={downloadPdf}
              >
                <FileText className="h-3.5 w-3.5" />
                Download PDF
              </Button>

              {/* Generate Runbook — 1 Gemini call, opt-in */}
              <Button
                variant="secondary"
                className="w-full"
                onClick={generateRunbook}
                disabled={runbookLoading || runbookDone}
              >
                {runbookLoading ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Generating runbook…
                  </>
                ) : runbookDone ? (
                  <>
                    <CheckCircle className="h-3.5 w-3.5 text-success" />
                    Runbook indexed
                  </>
                ) : (
                  <>
                    <BookOpen className="h-3.5 w-3.5" />
                    Generate Runbook (1 AI call)
                  </>
                )}
              </Button>

              {/* Find similar investigations — 0 tokens */}
              <Button
                variant="secondary"
                className="w-full"
                onClick={loadSimilar}
                disabled={similarLoading || similar !== null}
              >
                {similarLoading ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Finding similar…
                  </>
                ) : (
                  <>
                    <GitCompare className="h-3.5 w-3.5" />
                    Find Similar Incidents
                  </>
                )}
              </Button>

              {/* Similar results panel */}
              {similar !== null && (
                <div className="rounded-lg border border-border bg-card p-4 space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Similar Past Incidents
                  </p>
                  {similar.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      No similar incidents found.
                    </p>
                  ) : (
                    similar.map((s) => (
                      <a
                        key={s.id}
                        href={`/history/${s.id}`}
                        className="block rounded-md border border-border bg-card-elevated/40 p-3 hover:bg-card-elevated transition"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs font-medium truncate">
                            {s.incident_title}
                          </p>
                          <span className="shrink-0 text-[10px] font-semibold text-primary">
                            {Math.round(s.similarity * 100)}% match
                          </span>
                        </div>
                        <p className="mt-1 text-[11px] text-muted-foreground line-clamp-2">
                          {s.root_cause_snippet}
                        </p>
                        <p className="mt-1 text-[10px] text-muted-foreground">
                          {formatRelative(s.created_at ?? "")} · Confidence:{" "}
                          {s.confidence}%
                        </p>
                      </a>
                    ))
                  )}
                </div>
              )}

              {onReinvestigate && (
                <Button className="w-full" onClick={onReinvestigate}>
                  Re-investigate
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
