import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  FileText,
  Flame,
  Sparkles,
  ArrowRight,
  Plus,
  Upload,
  MessageSquare,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Protected } from "@/components/protected";
import { SeverityBadge, StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import {
  api,
  type Incident,
  type DocumentItem,
  type InvestigationHistoryItem,
} from "@/lib/api";
import { formatRelative } from "@/lib/format";

export const Route = createFileRoute("/dashboard")({
  ssr: false,
  component: () => (
    <Protected>
      <DashboardPage />
    </Protected>
  ),
});

function DashboardPage() {
  const incidents = useQuery({
    queryKey: ["incidents"],
    queryFn: () => api.get<Incident[]>("/api/v1/incidents"),
  });
  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.get<DocumentItem[]>("/api/v1/documents"),
  });
  const history = useQuery({
    queryKey: ["history"],
    queryFn: () => api.get<InvestigationHistoryItem[]>("/api/v1/investigate/history"),
  });

  const list = incidents.data ?? [];
  const open = list.filter((i) => i.status === "Open").length;
  const critical = list.filter((i) => i.severity === "Critical").length;
  const recent = [...list]
    .sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))
    .slice(0, 5);
  const recentInv = [...(history.data ?? [])]
    .sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))
    .slice(0, 5);

  const stats = [
    {
      label: "Open Incidents",
      value: open,
      icon: AlertOctagon,
      tone: open > 0 ? "text-danger" : "text-muted-foreground",
    },
    {
      label: "Critical Incidents",
      value: critical,
      icon: Flame,
      tone: critical > 0 ? "text-danger" : "text-muted-foreground",
    },
    {
      label: "Total Documents",
      value: documents.data?.length ?? 0,
      icon: FileText,
      tone: "text-muted-foreground",
    },
    {
      label: "Investigations Run",
      value: history.data?.length ?? 0,
      icon: Sparkles,
      tone: "text-muted-foreground",
    },
  ];

  return (
    <AppShell title="Dashboard">
      <div className="mx-auto max-w-7xl space-y-6">
        {/* Stat cards */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="rounded-lg border border-border bg-card p-5">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-wider text-muted-foreground">
                  {s.label}
                </span>
                <s.icon className={`h-4 w-4 ${s.tone}`} />
              </div>
              <div className="mt-3 text-3xl font-semibold tabular-nums">{s.value}</div>
            </div>
          ))}
        </div>

        {/* Quick actions */}
        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm">
            <Link to="/incidents">
              <Plus className="h-3.5 w-3.5" />New Incident
            </Link>
          </Button>
          <Button asChild size="sm" variant="secondary">
            <Link to="/documents">
              <Upload className="h-3.5 w-3.5" />Upload Document
            </Link>
          </Button>
          <Button asChild size="sm" variant="secondary">
            <Link to="/chat">
              <MessageSquare className="h-3.5 w-3.5" />Open Chat
            </Link>
          </Button>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Recent incidents */}
          <section className="rounded-lg border border-border bg-card">
            <header className="flex items-center justify-between border-b border-border px-5 py-3">
              <h2 className="text-sm font-semibold">Recent Incidents</h2>
              <Link
                to="/incidents"
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              >
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </header>
            <div className="divide-y divide-border">
              {incidents.isLoading && (
                <div className="p-6 text-sm text-muted-foreground">Loading…</div>
              )}
              {!incidents.isLoading && recent.length === 0 && (
                <div className="p-6 text-sm text-muted-foreground">No incidents yet.</div>
              )}
              {recent.map((i) => (
                <div
                  key={i.id}
                  className="flex items-center justify-between gap-4 px-5 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{i.title}</div>
                    <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                      <SeverityBadge severity={i.severity} />
                      <StatusBadge status={i.status} />
                      <span>{i.service}</span>
                      <span>·</span>
                      <span>{formatRelative(i.created_at)}</span>
                    </div>
                  </div>
                  <Button asChild size="sm" variant="secondary">
                    <Link
                      to="/investigate/$incident_id"
                      params={{ incident_id: String(i.id) }}
                    >
                      Investigate
                    </Link>
                  </Button>
                </div>
              ))}
            </div>
          </section>

          {/* Recent investigations */}
          <section className="rounded-lg border border-border bg-card">
            <header className="flex items-center justify-between border-b border-border px-5 py-3">
              <h2 className="text-sm font-semibold">Recent Investigations</h2>
              <Link
                to="/history"
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              >
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </header>
            <div className="divide-y divide-border">
              {history.isLoading && (
                <div className="p-6 text-sm text-muted-foreground">Loading…</div>
              )}
              {!history.isLoading && recentInv.length === 0 && (
                <div className="p-6 text-sm text-muted-foreground">No investigations yet.</div>
              )}
              {recentInv.map((r) => {
                const conf = r.confidence; // 0-100 from backend
                const color =
                  conf >= 80 ? "bg-success" : conf >= 50 ? "bg-warning" : "bg-danger";
                return (
                  <Link
                    key={r.id}
                    to="/history/$investigation_id"
                    params={{ investigation_id: String(r.id) }}
                    className="flex items-center gap-4 px-5 py-3 hover:bg-card-elevated/50"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">
                        {r.incident_title ?? `Incident #${r.incident_id}`}
                      </div>
                      <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                        <span>{r.source_count} sources</span>
                        <span>·</span>
                        <span>{formatRelative(r.created_at)}</span>
                      </div>
                    </div>
                    <div className="flex w-32 items-center gap-2">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                        <div
                          className={`h-full ${color}`}
                          style={{ width: `${conf}%` }}
                        />
                      </div>
                      <span className="w-10 text-right text-xs tabular-nums">{conf}%</span>
                    </div>
                  </Link>
                );
              })}
            </div>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
