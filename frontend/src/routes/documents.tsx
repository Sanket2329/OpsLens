import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  RefreshCw,
  Trash2,
  Upload,
  AlertTriangle,
} from "lucide-react";
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
import { api, getToken, type DocumentItem } from "@/lib/api";
import { formatBytes, formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/documents")({
  ssr: false,
  component: () => (
    <Protected>
      <DocumentsPage />
    </Protected>
  ),
});

const ACCEPT = ".pdf,.txt,.md";
const MAX = 20 * 1024 * 1024;

// ─── Index status badge ────────────────────────────────────────────────────────
function IndexStatusBadge({ status }: { status: string }) {
  const map: Record<
    string,
    { label: string; color: string; icon: React.ReactNode }
  > = {
    pending: {
      label: "Pending",
      color: "text-muted-foreground bg-muted/30 border-border",
      icon: <Clock className="h-3 w-3" />,
    },
    indexing: {
      label: "Indexing",
      color: "text-warning bg-warning/10 border-warning/30",
      icon: <Loader2 className="h-3 w-3 animate-spin" />,
    },
    indexed: {
      label: "Indexed",
      color: "text-success bg-success/10 border-success/30",
      icon: <CheckCircle2 className="h-3 w-3" />,
    },
    partial: {
      label: "Partial",
      color: "text-warning bg-warning/10 border-warning/30",
      icon: <AlertTriangle className="h-3 w-3" />,
    },
    failed: {
      label: "Failed",
      color: "text-danger bg-danger/10 border-danger/30",
      icon: <AlertCircle className="h-3 w-3" />,
    },
  };
  const s = map[status] ?? map["pending"];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium",
        s.color,
      )}
    >
      {s.icon}
      {s.label}
    </span>
  );
}

// ─── Upload state ──────────────────────────────────────────────────────────────
interface UploadState {
  phase: "uploading" | "indexing" | "done" | "error";
  uploadPct: number;
  chunksDone: number;
  chunksTotal: number;
  filename: string;
}

function DocumentsPage() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadState, setUploadState] = useState<UploadState | null>(null);
  const [toDelete, setToDelete] = useState<DocumentItem | null>(null);

  const { data = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.get<DocumentItem[]>("/api/v1/documents"),
  });

  const reindex = useMutation({
    mutationFn: (id: number) =>
      api.post<{
        new_chunks_indexed: number;
        total_chunks: number;
        index_status: string;
      }>(`/api/v1/documents/${id}/reindex`),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      toast.success(
        `Re-indexed: ${result.total_chunks} chunks (${result.index_status})`,
      );
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const del = useMutation({
    mutationFn: (id: number) => api.del(`/api/v1/documents/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      toast.success("Document deleted");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function upload(file: File) {
    if (file.size > MAX) return toast.error("Max file size is 20MB");

    setUploadState({
      phase: "uploading",
      uploadPct: 0,
      chunksDone: 0,
      chunksTotal: 0,
      filename: file.name,
    });

    try {
      // Phase 1: upload via XHR to track upload progress
      const token = getToken();
      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${api.baseUrl}/api/v1/documents/upload/stream`);
        if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

        // XHR doesn't support streaming response — use fetch SSE below
        // Just track upload progress here, then close
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            setUploadState((s) =>
              s
                ? { ...s, uploadPct: Math.round((e.loaded / e.total) * 100) }
                : null,
            );
          }
        };
        xhr.onload = () => resolve();
        xhr.onerror = () => reject(new Error("Upload failed"));

        const fd = new FormData();
        fd.append("file", file);
        xhr.send(fd);
      });
    } catch {
      // Fall through to SSE approach
    }

    // Phase 2: Use fetch + SSE for the streaming upload+index endpoint
    setUploadState({
      phase: "uploading",
      uploadPct: 100,
      chunksDone: 0,
      chunksTotal: 0,
      filename: file.name,
    });

    try {
      const token = getToken();
      const fd = new FormData();
      fd.append("file", file);

      const res = await fetch(`${api.baseUrl}/api/v1/documents/upload/stream`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });

      if (!res.ok || !res.body)
        throw new Error(`Upload failed (${res.status})`);

      setUploadState((s) => (s ? { ...s, phase: "indexing" } : null));

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const evt of events) {
          const line = evt.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          const payload = line.slice(5).trim();
          if (!payload) continue;
          try {
            const data = JSON.parse(payload);
            if (data.type === "progress") {
              setUploadState((s) =>
                s
                  ? {
                      ...s,
                      phase: "indexing",
                      chunksDone: data.chunks_done,
                      chunksTotal: data.chunks_total,
                    }
                  : null,
              );
            } else if (data.type === "done") {
              setUploadState((s) =>
                s
                  ? {
                      ...s,
                      phase: "done",
                      chunksDone: data.chunk_count ?? data.chunks_total,
                      chunksTotal: data.chunks_total,
                    }
                  : null,
              );
              toast.success(
                `${file.name} — ${data.chunk_count ?? 0} chunks indexed`,
              );
              qc.invalidateQueries({ queryKey: ["documents"] });
            } else if (data.type === "error") {
              throw new Error(data.detail ?? "Indexing failed");
            }
          } catch (parseErr) {
            if (
              parseErr instanceof Error &&
              parseErr.message !== "Unexpected token"
            ) {
              throw parseErr;
            }
          }
        }
      }
    } catch (e) {
      setUploadState((s) => (s ? { ...s, phase: "error" } : null));
      toast.error(e instanceof Error ? e.message : "Upload failed");
      qc.invalidateQueries({ queryKey: ["documents"] });
    } finally {
      setTimeout(() => setUploadState(null), 2000);
    }
  }

  return (
    <AppShell title="Documents">
      <div className="mx-auto max-w-6xl space-y-6">
        {/* Upload zone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files?.[0];
            if (f) void upload(f);
          }}
          onClick={() => !uploadState && inputRef.current?.click()}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-10 text-center transition",
            dragOver
              ? "border-primary bg-primary/5"
              : "border-border bg-card hover:bg-card-elevated/50",
            uploadState && "cursor-default opacity-80",
          )}
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15">
            {uploadState?.phase === "indexing" ? (
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
            ) : (
              <Upload className="h-4 w-4 text-primary" />
            )}
          </div>

          {!uploadState && (
            <>
              <div className="text-sm font-medium">
                Drag & drop a document here
              </div>
              <div className="text-xs text-muted-foreground">
                or click to browse — PDF, TXT, MD · max 20MB
              </div>
            </>
          )}

          {uploadState && (
            <div className="w-full max-w-md space-y-2">
              <div className="text-sm font-medium truncate">
                {uploadState.filename}
              </div>

              {/* Upload progress */}
              {uploadState.phase === "uploading" && (
                <>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full bg-primary transition-[width] duration-300"
                      style={{ width: `${uploadState.uploadPct}%` }}
                    />
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Uploading… {uploadState.uploadPct}%
                  </div>
                </>
              )}

              {/* Indexing progress */}
              {uploadState.phase === "indexing" && (
                <>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full bg-success transition-[width] duration-300"
                      style={{
                        width:
                          uploadState.chunksTotal > 0
                            ? `${Math.round((uploadState.chunksDone / uploadState.chunksTotal) * 100)}%`
                            : "5%",
                      }}
                    />
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Indexing chunks…{" "}
                    {uploadState.chunksTotal > 0
                      ? `${uploadState.chunksDone} / ${uploadState.chunksTotal}`
                      : "starting…"}
                  </div>
                </>
              )}

              {/* Done */}
              {uploadState.phase === "done" && (
                <div className="flex items-center justify-center gap-1.5 text-xs text-success">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Indexed {uploadState.chunksDone} chunks
                </div>
              )}

              {/* Error */}
              {uploadState.phase === "error" && (
                <div className="flex items-center justify-center gap-1.5 text-xs text-danger">
                  <AlertCircle className="h-3.5 w-3.5" />
                  Upload failed
                </div>
              )}
            </div>
          )}

          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void upload(f);
              e.target.value = "";
            }}
          />
        </div>

        {/* Documents table */}
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          {isLoading ? (
            <div className="p-6 text-sm text-muted-foreground">Loading…</div>
          ) : data.length === 0 ? (
            <div className="flex flex-col items-center gap-2 p-12 text-center">
              <FileText className="h-8 w-8 text-muted-foreground" />
              <p className="text-sm font-medium">No documents yet</p>
              <p className="text-xs text-muted-foreground">
                Upload your first document to enable AI investigations.
              </p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-card-elevated/50 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">Filename</th>
                  <th className="px-4 py-3 text-left font-medium">Status</th>
                  <th className="px-4 py-3 text-left font-medium">Chunks</th>
                  <th className="px-4 py-3 text-left font-medium">Size</th>
                  <th className="px-4 py-3 text-left font-medium">Uploaded</th>
                  <th className="px-4 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.map((d) => (
                  <tr key={d.id} className="hover:bg-card-elevated/40">
                    <td className="px-4 py-3 font-medium">
                      <div className="flex items-center gap-2">
                        <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                        <span className="truncate max-w-xs">
                          {d.original_filename}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <IndexStatusBadge status={d.index_status ?? "pending"} />
                    </td>
                    <td className="px-4 py-3">
                      {d.chunk_count != null ? (
                        <span className="tabular-nums text-xs font-medium">
                          {d.chunk_count}
                          {d.chunks_total != null &&
                            d.chunks_total !== d.chunk_count && (
                              <span className="text-muted-foreground">
                                {" "}
                                / {d.chunks_total}
                              </span>
                            )}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatBytes(d.file_size)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatRelative(d.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => reindex.mutate(d.id)}
                          disabled={reindex.isPending}
                          title="Re-index document"
                        >
                          <RefreshCw
                            className={cn(
                              "h-3.5 w-3.5",
                              reindex.isPending && "animate-spin",
                            )}
                          />
                          Re-index
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground hover:text-danger"
                          onClick={() => setToDelete(d)}
                          title="Delete document"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Delete confirmation */}
      <AlertDialog
        open={!!toDelete}
        onOpenChange={(o) => !o && setToDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete document?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove "{toDelete?.original_filename}" and
              all its embeddings from the knowledge base.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-danger text-white hover:bg-danger/90"
              onClick={() => {
                if (toDelete) del.mutate(toDelete.id);
                setToDelete(null);
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  );
}
