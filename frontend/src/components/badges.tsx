import { cn } from "@/lib/utils";
import type { Severity, IncidentStatus } from "@/lib/api";

const sevMap: Record<Severity, string> = {
  Critical: "bg-danger/15 text-danger border-danger/30",
  High: "bg-warning/15 text-warning border-warning/30",
  Medium: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  Low: "bg-blue-500/15 text-blue-400 border-blue-500/30",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium",
        sevMap[severity] ?? sevMap.Low,
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {severity}
    </span>
  );
}

const statusMap: Record<IncidentStatus, string> = {
  Open: "bg-danger/15 text-danger border-danger/30",
  Investigating: "bg-warning/15 text-warning border-warning/30",
  Resolved: "bg-success/15 text-success border-success/30",
};

export function StatusBadge({ status }: { status: IncidentStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium",
        statusMap[status] ?? statusMap.Open,
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status}
    </span>
  );
}
