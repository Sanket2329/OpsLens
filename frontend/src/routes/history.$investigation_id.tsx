import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Trash2 } from "lucide-react";
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
import { ReportView } from "@/components/report-view";
import { api, type InvestigationReport } from "@/lib/api";

export const Route = createFileRoute("/history/$investigation_id")({
  ssr: false,
  component: () => (
    <Protected>
      <HistoryDetail />
    </Protected>
  ),
});

function HistoryDetail() {
  const { investigation_id } = Route.useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["history", investigation_id],
    queryFn: () =>
      api.get<InvestigationReport>(
        `/api/v1/investigate/history/${investigation_id}`,
      ),
  });

  const deleteMutation = useMutation({
    mutationFn: () =>
      api.del(`/api/v1/investigate/history/${investigation_id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["history"] });
      toast.success("Investigation deleted");
      navigate({ to: "/history" });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <AppShell
      title="Investigation Report"
      actions={
        data ? (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 text-muted-foreground hover:text-danger"
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </Button>
        ) : undefined
      }
    >
      <div className="mx-auto max-w-7xl">
        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-muted border-t-primary" />
            Loading investigation…
          </div>
        )}
        {data && (
          <ReportView
            report={data}
            onReinvestigate={() =>
              navigate({
                to: "/investigate/$incident_id",
                params: { incident_id: String(data.incident_id) },
              })
            }
          />
        )}
      </div>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this investigation?</AlertDialogTitle>
            <AlertDialogDescription>
              Investigation #{investigation_id} will be permanently deleted. The
              incident and documents are not affected.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-danger text-white hover:bg-danger/90"
              onClick={() => deleteMutation.mutate()}
            >
              {deleteMutation.isPending ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  );
}
