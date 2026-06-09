"use client";

import { FormEvent, useState } from "react";
import toast from "react-hot-toast";
import { CheckCircle2, Clock3, Database, Download, Lightbulb, Send, Sparkles } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ErrorState } from "@/components/ui/ErrorState";
import { MotionPanel } from "@/components/ui/PageTransition";
import { apiPost } from "@/lib/api";
import { formatINR, formatNumber } from "@/lib/formatters";
import { useApiData } from "@/lib/useApiData";

type AssistantColumn = {
  key: string;
  label: string;
};

type AssistantTable = {
  title: string;
  columns: AssistantColumn[];
  rows: Record<string, string | number | null | undefined>[];
};

type AssistantChart = {
  title: string;
  type: "line";
  xKey: string;
  yKeys: { key: string; label: string; color?: string }[];
  data: Record<string, string | number | null | undefined>[];
};

type AssistantCsvFile = {
  filename: string;
  content: string;
};

type AssistantSummaryCard = {
  label: string;
  value: string | number;
  detail?: string;
  tone?: "green" | "orange" | "red" | "neutral" | string;
};

type AssistantRecommendation = {
  priority?: string;
  title: string;
  action: string;
  reason?: string;
  evidence: string;
  impact?: string;
  next_step?: string;
  styles?: string[];
  channels?: string[];
};

type MessageBlock =
  | { type: "paragraph"; text: string }
  | { type: "markdown-table"; table: AssistantTable };

type Message = {
  role: "user" | "assistant";
  content: string;
  intent?: string;
  summaryCards?: AssistantSummaryCard[];
  recommendations?: AssistantRecommendation[];
  evidence?: Record<string, string | number | null | undefined>[];
  tables?: AssistantTable[];
  charts?: AssistantChart[];
  csvFiles?: AssistantCsvFile[];
  usedSources?: string[];
  createdAt?: string;
};

type DailyBrief = {
  urgent_count: number;
  top_channel: string;
  fast_movers?: { style_color?: string; priority?: string; inventory_status?: string }[];
};

type AssistantResponse = {
  answer: string;
  intent?: string;
  summary_cards?: AssistantSummaryCard[];
  recommendations?: AssistantRecommendation[];
  evidence?: Record<string, string | number | null | undefined>[];
  tables?: AssistantTable[];
  charts?: AssistantChart[];
  csv_files?: AssistantCsvFile[];
  used_sources?: string[];
};

const QUICK_PROMPTS = [
  "How can I improve sales this month?",
  "Which styles are causing high returns?",
  "What needs urgent replenishment?",
  "Give me today's business summary",
];

function cleanText(value: string) {
  return value.replace(/\*\*/g, "").trim();
}

function splitMarkdownCells(line: string) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cleanText(cell));
}

function isMarkdownSeparator(line: string) {
  return /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line.trim());
}

function parseMessageBlocks(content: string): MessageBlock[] {
  const lines = cleanText(content).split(/\r?\n/);
  const blocks: MessageBlock[] = [];
  const paragraphLines: string[] = [];

  const flushParagraph = () => {
    const text = paragraphLines.join(" ").trim();
    if (text) blocks.push({ type: "paragraph", text });
    paragraphLines.length = 0;
  };

  let index = 0;
  while (index < lines.length) {
    const line = lines[index].trim();
    const nextLine = lines[index + 1]?.trim() ?? "";
    const isTableStart = line.includes("|") && isMarkdownSeparator(nextLine);

    if (isTableStart) {
      flushParagraph();
      const headers = splitMarkdownCells(line);
      const columns = headers.map((label, columnIndex) => ({
        key: `col_${columnIndex}`,
        label: label || `Column ${columnIndex + 1}`,
      }));
      const rows: AssistantTable["rows"] = [];
      index += 2;

      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        const cells = splitMarkdownCells(lines[index]);
        rows.push(
          Object.fromEntries(
            columns.map((column, columnIndex) => [column.key, cells[columnIndex] ?? ""])
          )
        );
        index += 1;
      }

      blocks.push({ type: "markdown-table", table: { title: "Details", columns, rows } });
      continue;
    }

    if (line) paragraphLines.push(line);
    index += 1;
  }

  flushParagraph();
  return blocks.length ? blocks : [{ type: "paragraph", text: cleanText(content) }];
}

function renderValue(value: string | number | null | undefined, key: string, row?: Record<string, string | number | null | undefined>) {
  if (typeof value === "number") {
    const metric = String(row?.metric ?? row?.Metric ?? "").toLowerCase();
    if (key === "value" && metric) {
      if (metric.includes("%") || metric.includes("rate") || metric.includes("growth")) return `${value.toFixed(2)}%`;
      if (
        (metric.includes("sales") ||
          metric.includes("revenue") ||
          metric.includes("return value") ||
          metric.includes("net sales") ||
          metric.includes("asp") ||
          metric.includes("spend") ||
          metric.includes("forecast")) &&
        !metric.includes("qty") &&
        !metric.includes("unit") &&
        !metric.includes("inventory")
      ) {
        return formatINR(value);
      }
      return formatNumber(value);
    }
    if (key.includes("value") || key.includes("sales") || key.includes("revenue")) return formatINR(value);
    if (key.includes("pct")) return `${value.toFixed(2)}%`;
    return formatNumber(value);
  }
  return value ?? "NA";
}

function downloadCsv(file: AssistantCsvFile) {
  const blob = new Blob([file.content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = file.filename;
  link.click();
  URL.revokeObjectURL(url);
}

function analysisTimestamp() {
  return new Date().toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function priorityClasses(priority?: string) {
  const value = (priority || "").toUpperCase();
  if (value.startsWith("P0")) return "border-red-200 bg-red-50 text-red-700";
  if (value.startsWith("P1")) return "border-orange-200 bg-orange-50 text-orange-700";
  if (value.startsWith("P2")) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function cardToneClasses(tone?: string) {
  if (tone === "red") return "border-red-200 bg-red-50 text-red-700";
  if (tone === "orange") return "border-orange-200 bg-orange-50 text-orange-700";
  if (tone === "green") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  return "border-line bg-white text-ink";
}

function analystLead(content: string) {
  return cleanText(content).split(/\r?\n/).find(Boolean) || cleanText(content);
}

function SummaryCards({ cards }: { cards: AssistantSummaryCard[] }) {
  if (!cards.length) return null;
  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
      {cards.map((card) => (
        <div className={`rounded-lg border px-3 py-2 ${cardToneClasses(card.tone)}`} key={`${card.label}-${card.value}`}>
          <div className="text-[11px] font-semibold uppercase text-muted">{card.label}</div>
          <div className="mt-1 text-base font-semibold text-ink">{card.value}</div>
          {card.detail ? <div className="mt-1 text-xs text-muted">{card.detail}</div> : null}
        </div>
      ))}
    </div>
  );
}

function RecommendationCards({ recommendations }: { recommendations: AssistantRecommendation[] }) {
  if (!recommendations.length) return null;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-muted">
        <Lightbulb className="h-4 w-4" />
        Recommended Actions
      </div>
      {recommendations.map((item, index) => (
        <div className="rounded-lg border border-line bg-white p-3" key={`${item.title}-${index}`}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="text-sm font-semibold text-ink">{item.title}</div>
              <div className="mt-1 text-sm leading-5 text-ink">{item.action}</div>
            </div>
            {item.priority ? <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold ${priorityClasses(item.priority)}`}>{item.priority}</span> : null}
          </div>
          <div className="mt-3 grid gap-2 text-xs md:grid-cols-3">
            <div className="rounded border border-line bg-slate-50 px-2 py-2">
              <div className="font-semibold text-muted">Evidence</div>
              <div className="mt-1 text-ink">{item.evidence}</div>
            </div>
            <div className="rounded border border-line bg-slate-50 px-2 py-2">
              <div className="font-semibold text-muted">Impact</div>
              <div className="mt-1 text-ink">{item.impact || item.reason || "Data-backed operating improvement."}</div>
            </div>
            <div className="rounded border border-line bg-slate-50 px-2 py-2">
              <div className="font-semibold text-muted">Next Step</div>
              <div className="mt-1 text-ink">{item.next_step || "Review the evidence table and assign an owner."}</div>
            </div>
          </div>
          {item.styles?.length || item.channels?.length ? (
            <div className="mt-2 flex flex-wrap gap-1">
              {[...(item.styles || []), ...(item.channels || [])].map((token) => (
                <span className="rounded-full border border-line bg-slate-50 px-2 py-1 text-[11px] text-muted" key={token}>
                  {token}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function SourceStrip({ message }: { message: Message }) {
  if (!message.createdAt && !message.usedSources?.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
      {message.createdAt ? (
        <span className="inline-flex items-center gap-1 rounded-full border border-line bg-slate-50 px-2 py-1">
          <Clock3 className="h-3 w-3" />
          Analysis based on latest synced data: {message.createdAt}
        </span>
      ) : null}
      {message.usedSources?.length ? (
        <span className="inline-flex flex-wrap items-center gap-1">
          <span className="inline-flex items-center gap-1 rounded-full border border-line bg-slate-50 px-2 py-1">
            <Database className="h-3 w-3" />
            Sources
          </span>
          {message.usedSources.map((source) => (
            <span className="rounded-full border border-line bg-slate-50 px-2 py-1" key={source}>
              {source}
            </span>
          ))}
        </span>
      ) : null}
      {message.intent ? (
        <span className="inline-flex items-center gap-1 rounded-full border border-line bg-slate-50 px-2 py-1">
          <CheckCircle2 className="h-3 w-3" />
          {message.intent.replace(/_/g, " ")}
        </span>
      ) : null}
    </div>
  );
}

function AssistantTableView({ table, showTitle = true }: { table: AssistantTable; showTitle?: boolean }) {
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-white">
      {showTitle ? <div className="border-b border-line bg-slate-50 px-3 py-2 text-xs font-semibold uppercase text-muted">{table.title}</div> : null}
      <div className="max-h-80 overflow-auto">
        <table className="min-w-full text-xs">
          <thead className="sticky top-0 bg-slate-50 text-left text-muted">
            <tr>
              {table.columns.map((column) => (
                <th className="px-3 py-2 font-semibold" key={column.key}>
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, rowIndex) => (
              <tr className="border-t border-line odd:bg-white even:bg-slate-50/40" key={rowIndex}>
                {table.columns.map((column) => (
                  <td className="whitespace-nowrap px-3 py-2 text-ink" key={column.key}>
                    {renderValue(row[column.key], column.key, row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AssistantMessageView({ message }: { message: Message }) {
  const blocks = parseMessageBlocks(message.content);
  const hasAnalystBlocks = Boolean(message.summaryCards?.length || message.recommendations?.length);

  return (
    <div className="space-y-3">
      <SourceStrip message={message} />

      {hasAnalystBlocks ? (
        <p className="leading-6">{analystLead(message.content)}</p>
      ) : (
        blocks.map((block, index) =>
          block.type === "paragraph" ? (
            <p className="leading-6" key={`paragraph-${index}`}>
              {block.text}
            </p>
          ) : (
            <AssistantTableView key={`markdown-table-${index}`} showTitle={false} table={block.table} />
          )
        )
      )}

      <SummaryCards cards={message.summaryCards ?? []} />
      <RecommendationCards recommendations={message.recommendations ?? []} />

      {message.tables?.map((table) => (
        <AssistantTableView key={table.title} table={table} />
      ))}

      {message.charts?.map((chart) => (
        <div className="h-72 rounded-lg border border-line bg-white p-3" key={chart.title}>
          <div className="mb-2 text-xs font-semibold uppercase text-muted">{chart.title}</div>
          <ResponsiveContainer width="100%" height="85%">
            <LineChart data={chart.data}>
              <CartesianGrid stroke="#dbe3ee" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey={chart.xKey} stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip />
              {chart.yKeys.map((key) => (
                <Line key={key.key} type="monotone" dataKey={key.key} name={key.label} stroke={key.color || "#0f9488"} strokeWidth={2} dot={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ))}

      {message.csvFiles?.length ? (
        <div className="flex flex-wrap gap-2">
          {message.csvFiles.map((file) => (
            <button
              className="inline-flex items-center gap-2 rounded border border-line bg-slate-50 px-3 py-2 text-xs font-medium text-ink transition duration-200 ease-in-out hover:scale-[1.02]"
              key={file.filename}
              onClick={() => downloadCsv(file)}
              type="button"
            >
              <Download className="h-3.5 w-3.5" />
              {file.filename}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function AssistantPage() {
  const brief = useApiData<DailyBrief>("/notifications/daily_brief", { urgent_count: 0, top_channel: "Unknown", fast_movers: [] });
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const sendMessage = async (rawMessage: string) => {
    const message = rawMessage.trim();
    if (!message || sending) return;
    const nextMessages: Message[] = [...messages, { role: "user", content: message }];
    setMessages(nextMessages);
    setInput("");
    setSending(true);
    try {
      const response = await apiPost<AssistantResponse>("/assistant/chat", {
        message,
        conversation_history: nextMessages,
      });
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.answer,
          intent: response.intent,
          summaryCards: response.summary_cards ?? [],
          recommendations: response.recommendations ?? [],
          evidence: response.evidence ?? [],
          tables: response.tables ?? [],
          charts: response.charts ?? [],
          csvFiles: response.csv_files ?? [],
          usedSources: response.used_sources ?? [],
          createdAt: analysisTimestamp(),
        },
      ]);
    } catch (err) {
      const text = err instanceof Error ? err.message : "Assistant request failed";
      toast.error(text);
      setMessages((current) => [...current, { role: "assistant", content: text }]);
    } finally {
      setSending(false);
    }
  };

  const send = async (event: FormEvent) => {
    event.preventDefault();
    await sendMessage(input);
  };

  if (brief.error) return <ErrorState message={brief.error} onRetry={brief.retry} />;

  return (
    <div className="w-full space-y-6">
      <MotionPanel className="rounded-lg border border-line bg-white p-4 shadow-soft">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-ink">AI Assistant</div>
            <div className="mt-1 text-sm text-muted">Ask about sales, inventory, returns, ads performance, replenishment, or anomalies.</div>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Urgent alerts <b className="text-ink">{brief.data.urgent_count}</b></span>
            <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Top channel <b className="text-ink">{brief.data.top_channel}</b></span>
          </div>
        </div>

        <div className="min-h-[420px] rounded-lg border border-line bg-slate-50/40 p-4">
          {messages.length ? (
            <div className="space-y-3">
              {messages.map((message, index) => (
                <div className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`} key={`${message.role}-${index}`}>
                  <div className={`${message.role === "user" ? "max-w-3xl bg-ink text-white" : "max-w-5xl border border-line bg-white text-ink"} rounded-lg px-4 py-3 text-sm shadow-sm`}>
                    {message.role === "assistant" ? <AssistantMessageView message={message} /> : message.content}
                  </div>
                </div>
              ))}
              {sending ? <div className="text-sm text-muted">Assistant is analyzing current BI context...</div> : null}
            </div>
          ) : (
            <div className="flex min-h-[360px] flex-col items-center justify-center gap-4 text-center">
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-full border border-line bg-white text-ink shadow-sm">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <div className="text-sm font-semibold text-ink">Ask for analyst-grade business answers</div>
                <div className="mt-1 max-w-xl text-sm text-muted">Use live sales, returns, inventory, replenishment, forecast, ads, and anomaly data to get ranked actions with evidence.</div>
              </div>
              <div className="flex max-w-3xl flex-wrap justify-center gap-2">
                {QUICK_PROMPTS.map((prompt) => (
                  <button
                    className="rounded-full border border-line bg-white px-3 py-2 text-xs font-medium text-ink shadow-sm transition duration-200 ease-in-out hover:scale-[1.02] hover:border-teal-300 disabled:opacity-50"
                    disabled={sending}
                    key={prompt}
                    onClick={() => sendMessage(prompt)}
                    type="button"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <form className="mt-4 flex gap-3" onSubmit={send}>
          <input
            className="w-full rounded border border-line px-3 py-2 text-sm"
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask E-Commerce BI..."
            value={input}
          />
          <button className="inline-flex items-center gap-2 rounded bg-ink px-4 py-2 text-sm font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02] disabled:opacity-50" disabled={sending} type="submit">
            <Send className="h-4 w-4" />
            Send
          </button>
        </form>
      </MotionPanel>
    </div>
  );
}
