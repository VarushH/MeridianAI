import React, { useState } from "react";
import { Search, Send, Sparkles, MessageSquare, Clock, Trash2 } from "lucide-react";
import { askQuestion } from "@/lib/api";

const EXAMPLE_QUERIES = [
  "What is the Revenue in FY2022?",
  "What countries does Acme Manufacturing operate in?",
  "What percentage of the workforce will retire in 5 years?",
  "What is the COGS in FY2024?",
];

interface HistoryEntry {
  query: string;
  answer: string | null;
  error: string | null;
  ts: number;
}

export default function RagQATab() {
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);

  const handleAsk = async (q?: string) => {
    const text = (q || query).trim();
    if (!text || loading) return;
    setQuery("");
    setLoading(true);
    const entry: HistoryEntry = { query: text, answer: null, error: null, ts: Date.now() };
    setHistory((prev) => [entry, ...prev]);

    try {
      const res = await askQuestion(text);
      setHistory((prev) => prev.map((h) => (h.ts === entry.ts ? { ...h, answer: res.answer } : h)));
    } catch (err: any) {
      setHistory((prev) => prev.map((h) => (h.ts === entry.ts ? { ...h, error: err.message } : h)));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 animate-fade-in">
      {/* Left: Query Input - 2 cols */}
      <div className="lg:col-span-2 space-y-5">
        <div className="rounded-lg border border-border bg-card p-6">
          <div className="flex items-center gap-2.5 mb-1">
            <Search className="w-[18px] h-[18px] text-primary" />
            <h2 className="text-base font-semibold font-heading text-card-foreground">Knowledge Query</h2>
          </div>
          <p className="text-sm text-muted-foreground mb-5">
            Ask questions against your ingested documents. The RAG pipeline retrieves relevant chunks and generates an answer.
          </p>

          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Your Question</label>
          <textarea
            className="w-full mt-2 p-3 rounded-md border border-border bg-background text-card-foreground text-sm font-body resize-vertical focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary transition-colors min-h-[110px] placeholder:text-muted-foreground"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleAsk(); } }}
            placeholder="e.g. What was the total revenue in FY2022?"
          />
          <div className="flex items-center justify-between mt-3">
            <span className="text-xs text-muted-foreground">Enter to send · Shift+Enter for newline</span>
            <button
              className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold transition-colors hover:bg-primary/90 disabled:opacity-50"
              disabled={!query.trim() || loading}
              onClick={() => handleAsk()}
            >
              {loading ? (
                <><span className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" /> Thinking…</>
              ) : (
                <><Send className="w-4 h-4" /> Ask</>
              )}
            </button>
          </div>
        </div>

        {/* Example queries */}
        <div className="rounded-lg border border-border bg-card p-6">
          <div className="flex items-center gap-2.5 mb-4">
            <Sparkles className="w-[18px] h-[18px] text-accent" />
            <h2 className="text-base font-semibold font-heading text-card-foreground">Example Queries</h2>
          </div>
          <div className="space-y-2">
            {EXAMPLE_QUERIES.map((eq) => (
              <button
                key={eq}
                className="w-full flex items-center gap-2 text-left p-3 rounded-md border border-border text-sm text-muted-foreground hover:bg-muted hover:text-card-foreground transition-colors"
                onClick={() => { setQuery(eq); handleAsk(eq); }}
              >
                <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-50" />
                {eq}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right: Answer History - 3 cols */}
      <div className="lg:col-span-3">
        <div className="rounded-lg border border-border bg-card p-6 flex flex-col" style={{ minHeight: 400 }}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2.5">
              <Clock className="w-[18px] h-[18px] text-muted-foreground" />
              <h2 className="text-base font-semibold font-heading text-card-foreground">Answers</h2>
              <span className="text-xs text-muted-foreground">{history.length} queries</span>
            </div>
            {history.length > 0 && (
              <button
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-card-foreground transition-colors"
                onClick={() => setHistory([])}
              >
                <Trash2 className="w-3.5 h-3.5" /> Clear
              </button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto max-h-[calc(100vh-300px)]">
            {history.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full py-16 text-muted-foreground">
                <Search className="w-10 h-10 mb-3 opacity-30" />
                <p className="text-sm">No queries yet. Ask a question or pick an example.</p>
              </div>
            ) : (
              <div className="space-y-5">
                {history.map((h) => (
                  <div key={h.ts} className="animate-fade-in">
                    <div className="flex items-start gap-2.5 mb-2.5">
                      <div className="w-7 h-7 rounded-md bg-accent/10 text-accent flex items-center justify-center shrink-0 mt-0.5">
                        <MessageSquare className="w-3.5 h-3.5" />
                      </div>
                      <p className="text-sm font-medium text-card-foreground leading-relaxed">{h.query}</p>
                    </div>
                    {h.answer ? (
                      <div className="ml-9 p-3.5 rounded-md bg-muted/50 border border-border">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-primary mb-2">Answer</p>
                        <p className="text-sm text-card-foreground leading-relaxed whitespace-pre-wrap">{h.answer}</p>
                      </div>
                    ) : h.error ? (
                      <div className="ml-9 p-3.5 rounded-md bg-danger/5 border border-danger/20">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-danger mb-2">Error</p>
                        <p className="text-sm text-danger">{h.error}</p>
                      </div>
                    ) : (
                      <div className="ml-9 flex items-center gap-2 text-sm text-muted-foreground">
                        <span className="w-4 h-4 border-2 border-muted-foreground/30 border-t-muted-foreground rounded-full animate-spin" />
                        Retrieving context & generating answer…
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
