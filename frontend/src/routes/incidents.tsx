import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Plus, Search, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/app-shell";
import { Protected } from "@/components/protected";
import { SeverityBadge, StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, type Incident, type IncidentStatus, type Severity, type SeverityDetection } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/incidents")({
  ssr: false,
  component: () => (
    <Protected>
      <IncidentsPage />
    </Protected>
  ),
});

function IncidentsPage() {
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const { data = [], isLoading } = useQuery({
    queryKey: ["incidents"],
    queryFn: () => api.get<Incident[]>("/api/v1/incidents"),
  });

  const filtered = useMemo(
    () =>
      data.filter(
        (i) =>
          i.title.toLowerCase().includes(query.toLowerCase()) ||
          i.service.toLowerCase().includes(query.toLowerCase()),
      ),
    [data, query],
  );

  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: IncidentStatus }) =>
      api.patch(`/api/v1/incidents/${id}`, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["incidents"] });
      toast.success("Status updated");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <AppShell
      title="Incidents"
      actions={
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="h-3.5 w-3.5" />New Incident
            </Button>
          </DialogTrigger>
          <NewIncidentDialog onDone={() => setOpen(false)} />
        </Dialog>
      }
    >
      <div className="mx-auto max-w-7xl space-y-4">
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search by title or service…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-card-elevated/50 text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left font-medium">ID</th>
                <th className="px-4 py-3 text-left font-medium">Title</th>
                <th className="px-4 py-3 text-left font-medium">Severity</th>
                <th className="px-4 py-3 text-left font-medium">Service</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Created</th>
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    Loading…
                  </td>
                </tr>
              )}
              {!isLoading && filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-muted-foreground">
                    No incidents found
                  </td>
                </tr>
              )}
              {filtered.map((i) => (
                <tr key={i.id} className="hover:bg-card-elevated/40">
                  {/* id is a number — display directly */}
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">#{i.id}</td>
                  <td className="px-4 py-3 font-medium">{i.title}</td>
                  <td className="px-4 py-3">
                    <SeverityBadge severity={i.severity} />
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{i.service}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={i.status} />
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {formatRelative(i.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <Select
                        value={i.status}
                        onValueChange={(v) =>
                          updateStatus.mutate({ id: i.id, status: v as IncidentStatus })
                        }
                      >
                        <SelectTrigger className="h-8 w-36 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Open">Open</SelectItem>
                          <SelectItem value="Investigating">Investigating</SelectItem>
                          <SelectItem value="Resolved">Resolved</SelectItem>
                        </SelectContent>
                      </Select>
                      <Button asChild size="sm">
                        <Link
                          to="/investigate/$incident_id"
                          params={{ incident_id: String(i.id) }}
                        >
                          Investigate
                        </Link>
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
}

function NewIncidentDialog({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    title: "",
    description: "",
    severity: "Medium" as Severity,
    service: "",
  });
  const [loading, setLoading] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [detection, setDetection] = useState<SeverityDetection | null>(null);

  async function detectSeverity() {
    if (form.title.length < 3 || form.description.length < 10) return;
    setDetecting(true);
    try {
      const result = await api.post<SeverityDetection>("/api/v1/incidents/detect-severity", {
        title: form.title,
        description: form.description,
      });
      setDetection(result);
      setForm((f) => ({ ...f, severity: result.suggested_severity as Severity }));
    } catch {
      // Silent — user can still pick manually
    } finally {
      setDetecting(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (form.description.trim().length < 10) {
      toast.error("Description must be at least 10 characters");
      return;
    }
    setLoading(true);
    try {
      await api.post("/api/v1/incidents", form);
      qc.invalidateQueries({ queryKey: ["incidents"] });
      toast.success("Incident created");
      onDone();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  const confColor = detection
    ? detection.confidence >= 0.7 ? "text-success" : detection.confidence >= 0.4 ? "text-warning" : "text-muted-foreground"
    : "";

  return (
    <DialogContent className="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>New Incident</DialogTitle>
      </DialogHeader>
      <form onSubmit={submit} className="space-y-3">
        <div className="space-y-1.5">
          <Label>Title</Label>
          <Input
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            required
            minLength={3}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Description</Label>
          <Textarea
            rows={4}
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            required
            minLength={10}
            placeholder="Describe what's happening and its impact…"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label>Severity</Label>
              <button
                type="button"
                onClick={detectSeverity}
                disabled={detecting || form.title.length < 3 || form.description.length < 10}
                className={cn(
                  "flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium transition",
                  "border border-primary/30 bg-primary/10 text-primary hover:bg-primary/20",
                  "disabled:opacity-40 disabled:cursor-not-allowed",
                )}
                title="Auto-detect severity (0 AI tokens)"
              >
                <Wand2 className="h-2.5 w-2.5" />
                {detecting ? "Detecting…" : "Auto-detect"}
              </button>
            </div>
            <Select
              value={form.severity}
              onValueChange={(v) => { setForm({ ...form, severity: v as Severity }); setDetection(null); }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Critical">Critical</SelectItem>
                <SelectItem value="High">High</SelectItem>
                <SelectItem value="Medium">Medium</SelectItem>
                <SelectItem value="Low">Low</SelectItem>
              </SelectContent>
            </Select>
            {detection && (
              <p className={cn("text-[10px] leading-relaxed", confColor)}>
                {Math.round(detection.confidence * 100)}% confident · {detection.signals.slice(0, 2).join(", ")}
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label>Service</Label>
            <Input
              value={form.service}
              onChange={(e) => setForm({ ...form, service: e.target.value })}
              required
              placeholder="e.g. payment-api"
            />
          </div>
        </div>

        <DialogFooter>
          <Button type="submit" disabled={loading}>
            {loading ? "Creating…" : "Create"}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}
