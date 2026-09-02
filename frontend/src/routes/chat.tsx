import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { BookOpen, FileText, Plus, Send, X } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/app-shell";
import { Protected } from "@/components/protected";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/markdown";
import { PDFViewer } from "@/components/pdf-viewer";
import { api, type ConversationSummary, type ConversationDetail, type ChatMessage } from "@/lib/api";
import type { DocumentResponse } from "@/routes/documents";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/chat")({
  ssr: false,
  component: () => (
    <Protected>
      <ChatPage />
    </Protected>
  ),
});

function ChatPage() {
  const qc = useQueryClient();
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [showDocSelector, setShowDocSelector] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const convos = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.get<ConversationSummary[]>("/api/v1/chat/conversations"),
  });

  const docsQuery = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.get<DocumentResponse[]>("/api/v1/documents"),
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function loadConversation(id: number) {
    setConversationId(id);
    try {
      // Backend returns ConversationDetail { id, title, created_at, messages: [...] }
      const detail = await api.get<ConversationDetail>(`/api/v1/chat/conversations/${id}`);
      setMessages(detail.messages ?? []);
    } catch {
      setMessages([]);
    }
  }

  function newChat() {
    setConversationId(null);
    setMessages([]);
  }

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    const next: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setSending(true);
    try {
      const res = await api.post<{ answer: string; conversation_id: number }>("/api/v1/chat", {
        question: text,
        conversation_id: conversationId,
      });
      setConversationId(res.conversation_id);
      setMessages([...next, { role: "assistant", content: res.answer }]);
      qc.invalidateQueries({ queryKey: ["conversations"] });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
      setMessages(messages); // revert optimistic update
    } finally {
      setSending(false);
    }
  }

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  return (
    <AppShell title="Chat">
      <div className="mx-auto flex h-[calc(100vh-8rem)] max-w-7xl overflow-hidden rounded-lg border border-border bg-card">
        {/* Sidebar — conversation list */}
        <aside className="flex w-60 shrink-0 flex-col border-r border-border">
          <div className="p-3">
            <Button className="w-full" size="sm" onClick={newChat}>
              <Plus className="h-3.5 w-3.5" />New Chat
            </Button>
          </div>
          <div className="flex-1 overflow-auto px-2 pb-2">
            {convos.data?.map((c) => (
              <button
                key={c.id}
                onClick={() => loadConversation(c.id)}
                className={cn(
                  "w-full rounded-md px-2.5 py-2 text-left text-xs transition",
                  conversationId === c.id
                    ? "bg-card-elevated text-foreground"
                    : "text-muted-foreground hover:bg-card-elevated/60 hover:text-foreground",
                )}
              >
                <div className="truncate font-medium">{c.title || "Untitled"}</div>
                <div className="text-[10px] text-muted-foreground">
                  {formatRelative(c.created_at)}
                </div>
              </button>
            ))}
          </div>
        </aside>

        {/* Main chat area */}
        <section className="flex flex-1 overflow-hidden">
          {/* PDF Previewer Pane */}
          {selectedDocumentId && (
            <div className="flex w-1/2 flex-col border-r border-border bg-card relative">
              <Button 
                variant="outline" 
                size="icon" 
                className="absolute right-4 top-4 z-10 h-8 w-8 rounded-full bg-background/80 backdrop-blur"
                onClick={() => setSelectedDocumentId(null)}
              >
                <X className="h-4 w-4" />
              </Button>
              <PDFViewer url={`${api.baseUrl}/api/v1/documents/${selectedDocumentId}/download`} />
            </div>
          )}

          {/* Chat Pane */}
          <div className="flex flex-1 flex-col overflow-hidden relative">
            {/* Top Bar for Document Selection */}
            <div className="flex items-center justify-between border-b border-border bg-card/50 px-4 py-2">
              <div className="text-sm font-medium">Chat</div>
              <div className="relative">
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-8 gap-2"
                  onClick={() => setShowDocSelector(!showDocSelector)}
                >
                  <BookOpen className="h-3.5 w-3.5" />
                  {selectedDocumentId ? "Change Preview" : "Preview Document"}
                </Button>
                {showDocSelector && (
                  <div className="absolute right-0 top-10 z-20 w-64 rounded-md border border-border bg-card shadow-lg p-1">
                    <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground border-b border-border mb-1">
                      Select Document to Preview
                    </div>
                    <div className="max-h-60 overflow-y-auto">
                      {docsQuery.data?.map(doc => (
                        <button
                          key={doc.id}
                          className={cn(
                            "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs text-left hover:bg-accent hover:text-accent-foreground",
                            selectedDocumentId === doc.id && "bg-primary/10 text-primary"
                          )}
                          onClick={() => {
                            setSelectedDocumentId(doc.id);
                            setShowDocSelector(false);
                          }}
                        >
                          <FileText className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate">{doc.original_filename}</span>
                        </button>
                      ))}
                      {(!docsQuery.data || docsQuery.data.length === 0) && (
                        <div className="p-2 text-center text-xs text-muted-foreground">No documents uploaded</div>
                      )}
                    </div>
                  </div>
                )}
                {/* Click outside overlay */}
                {showDocSelector && (
                  <div className="fixed inset-0 z-10" onClick={() => setShowDocSelector(false)} />
                )}
              </div>
            </div>

            <div className="flex-1 overflow-auto p-4 md:p-6">
              {messages.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center text-center text-muted-foreground">
                  <div className="text-sm font-medium text-foreground">
                    Ask anything about your documentation
                  </div>
                  <p className="mt-1 text-xs">Chat is grounded on documents you've uploaded.</p>
                </div>
              ) : (
                <div className="mx-auto max-w-3xl space-y-4">
                  {messages.map((m, i) => (
                    <div
                      key={i}
                      className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}
                    >
                      <div
                        className={cn(
                          "max-w-[85%] rounded-lg px-4 py-3 text-sm shadow-sm",
                          m.role === "user"
                            ? "bg-primary text-primary-foreground"
                            : "border border-border bg-card-elevated text-foreground",
                        )}
                      >
                        {m.role === "assistant" ? (
                          <Markdown content={m.content} />
                        ) : (
                          m.content
                        )}
                      </div>
                    </div>
                  ))}
                  {sending && (
                    <div className="flex justify-start">
                      <div className="flex gap-1 rounded-lg border border-border bg-card-elevated px-4 py-3 shadow-sm">
                        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:0ms]" />
                        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:150ms]" />
                        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:300ms]" />
                      </div>
                    </div>
                  )}
                  <div ref={bottomRef} />
                </div>
              )}
            </div>

            {/* Input */}
            <div className="border-t border-border p-4 bg-card">
              <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-lg border border-border bg-background p-2 focus-within:ring-1 focus-within:ring-primary shadow-sm">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onKey}
                  rows={1}
                  placeholder="Message OpsLens…"
                  className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground"
                  style={{ minHeight: "2rem" }}
                />
                <Button
                  size="icon"
                  onClick={send}
                  disabled={sending || !input.trim()}
                  className="shrink-0"
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
