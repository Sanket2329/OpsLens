import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Protected } from "@/components/protected";
import { SeverityBadge, StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { api, type Incident } from "@/lib/api";

export const Route = createFileRoute("/investigate/")({
  ssr: false,
  component: () => (
    <Protected>
      <InvestigateIndex />
    </Protected>
  ),
});

function InvestigateIndex() {
  const { data = [], isLoading } = useQuery({
    queryKey: ["incidents"],
    queryFn: () => api.get<Incident[]>("/api/v1/incidents"),
  });
  return (
    <AppShell title="Investigation">
      <div className="mx-auto max-w-4xl space-y-4">
        <div className="rounded-lg border border-border bg-card p-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/15">
              <Sparkles className="h-4 w-4 text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-semibold">
                Pick an incident to investigate
              </h2>
              <p className="text-xs text-muted-foreground">
                Run AI-powered root cause analysis with your indexed
                documentation.
              </p>
            </div>
          </div>
        </div>
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          {isLoading && (
            <div className="p-6 text-sm text-muted-foreground">Loading…</div>
          )}
          {!isLoading && data.length === 0 && (
            <div className="p-6 text-sm text-muted-foreground">
              No incidents yet.
            </div>
          )}
          <ul className="divide-y divide-border">
            {data.map((i) => (
              <li
                key={i.id}
                className="flex items-center justify-between px-5 py-3"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{i.title}</div>
                  <div className="mt-1 flex items-center gap-2">
                    <SeverityBadge severity={i.severity} />
                    <StatusBadge status={i.status} />
                    <span className="text-xs text-muted-foreground">
                      {i.service}
                    </span>
                  </div>
                </div>
                <Button asChild size="sm">
                  <Link
                    to="/investigate/$incident_id"
                    params={{ incident_id: i.id }}
                  >
                    Investigate
                  </Link>
                </Button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </AppShell>
  );
}
