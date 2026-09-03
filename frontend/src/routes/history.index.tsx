import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AlertTriangle, CheckCircle, HelpCircle, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/app-shell";
import { Protected } from "@/components/protected";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { api, type InvestigationHistoryItem } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/history/")({
  ssr: false,
  component: () => (
    <Protected>
      <HistoryPage />
    </Protected>
  ),
});

function RootCauseStatusBadge({ status }: { status: string }) {
  const map: Record<string, { color: string; icon: React.ReactNode }> = {
    Confirmed: {
      color: "text-success",
      icon: <CheckCircle className="h-3 w-3" />,
    },
    Likely: {
      color: "text-warning",
      icon: <AlertTriangle className="h-3 w-3" />,
    },
    "Unable to Determine": {
      color: "text-danger",
      icon: <HelpCircle className="h-3 w-3" />,
    },
  };
  const s = map[status] ?? map["Likely"];
  return (
    <span
      className={cn("flex items-center gap-1 text-xs font-medium", s.color)}
    >
      {s.icon}
      {status}
    </span>
  );
}

function HistoryPage() {
  const qc = useQueryClient();
  const [toDelete, setToDelete] = useState<InvestigationHistoryItem | null>(
    null,
  );

  const { data = [], isLoading } = useQuery({
    queryKey: ["history"],
    queryFn: () =>
      api.get<InvestigationHistoryItem[]>("/api/v1/investigate/history"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.del(`/api/v1/investigate/history/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["history"] });
      toast.success("Investigation deleted");
      setToDelete(null);
    },
    onError: (e: Error) => {
      toast.error(e.message);
      setToDelete(null);
    },
  });

  return (
    <AppShell title="Investigation History">
      <div className="mx-auto max-w-7xl">
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-card-elevated/50 text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left font-medium">ID</th>
                <th className="px-4 py-3 text-left font-medium">Incident</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Confidence</th>
                <th className="px-4 py-3 text-left font-medium">Sources</th>
                <th className="px-4 py-3 text-left font-medium">Date</th>
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading && (
                <tr>
                  <td
                    colSpan={7}
                    className="p-6 text-center text-muted-foreground"
                  >
                    Loading…
                  </td>
                </tr>
              )}
              {!isLoading && data.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="p-12 text-center text-muted-foreground"
                  >
                    No investigations yet. Run your first investigation from the
                    Incidents page.
                  </td>
                </tr>
              )}
              {data.map((r) => {
                const conf = r.confidence;
                const confColor =
                  conf >= 75
                    ? "text-success"
                    : conf >= 50
                      ? "text-warning"
                      : "text-danger";
                const confLevel =
                  r.confidence_level ??
                  (conf >= 75 ? "High" : conf >= 50 ? "Medium" : "Low");
                return (
                  <tr key={r.id} className="hover:bg-card-elevated/40">
                    <td className="px-4 py-3">
                      <Link
                        to="/history/$investigation_id"
                        params={{ investigation_id: String(r.id) }}
                        className="font-mono text-xs text-muted-foreground hover:text-primary"
                      >
                        #{r.id}
                      </Link>
                    </td>
                    <td className="max-w-xs px-4 py-3">
                      <Link
                        to="/history/$investigation_id"
                        params={{ investigation_id: String(r.id) }}
                        className="block truncate font-medium hover:text-primary"
                      >
                        {r.incident_title ?? `Incident #${r.incident_id}`}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <RootCauseStatusBadge
                        status={r.root_cause_status ?? "Likely"}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "text-xs font-semibold tabular-nums",
                          confColor,
                        )}
                      >
                        {confLevel} — {conf}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {r.source_count > 0 ? r.source_count : "—"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatRelative(r.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-danger"
                        onClick={(e) => {
                          e.stopPropagation();
                          setToDelete(r);
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Delete confirmation */}
      <AlertDialog
        open={!!toDelete}
        onOpenChange={(open) => !open && setToDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete investigation?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete investigation #{toDelete?.id} for{" "}
              <strong>
                {toDelete?.incident_title ??
                  `Incident #${toDelete?.incident_id}`}
              </strong>
              . This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-danger text-white hover:bg-danger/90"
              onClick={() => toDelete && deleteMutation.mutate(toDelete.id)}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  );
}
