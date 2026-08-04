import React from "react";
import {
  TrendingUp,
  CheckCircle2,
  AlertCircle,
  ArrowUpRight,
  RefreshCw,
} from "lucide-react";
import {
  ShareOfModelChart,
  type SomSeriesPoint,
} from "./ShareOfModelChart";

export type OverviewEngineRow = {
  id: string;
  label: string;
  share: number | null;
  status: "dominant" | "optimal" | "needs_action" | "unknown";
  topDomain?: string;
  tone?: "emerald" | "cyan" | "violet" | "amber";
};

export type OverviewInsight = {
  severity: "high" | "gap" | "info";
  title: string;
  detail: string;
};

export type DashboardOverviewProps = {
  rangeLabel?: string;
  onRunAudit?: () => void;
  auditHref?: string;
  reportHref?: string;
  somPercent?: number | null;
  somDelta?: number | null;
  enginesTracked?: number;
  recRank?: string | null;
  recRankDelta?: number | null;
  citations?: number | null;
  citationsDeltaPct?: number | null;
  sentiment?: number | null;
  sentimentLabel?: string;
  engines?: OverviewEngineRow[];
  insights?: OverviewInsight[];
  evidenceLabel?: string;
  somSeries?: SomSeriesPoint[];
  /** When true, omit the fixed sidebar offset (embed inside an existing shell). */
  embedded?: boolean;
};

const DEFAULT_ENGINES: OverviewEngineRow[] = [
  {
    id: "chatgpt",
    label: "ChatGPT (GPT-4o)",
    share: 48.2,
    status: "dominant",
    topDomain: "centropic.ai/blog",
    tone: "emerald",
  },
  {
    id: "perplexity",
    label: "Perplexity Pro",
    share: 39.5,
    status: "optimal",
    topDomain: "centropic.ai/docs",
    tone: "cyan",
  },
  {
    id: "claude",
    label: "Claude 3.5 Sonnet",
    share: 41.0,
    status: "optimal",
    topDomain: "centropic.ai/case-studies",
    tone: "violet",
  },
  {
    id: "searchgpt",
    label: "SearchGPT",
    share: 28.4,
    status: "needs_action",
    topDomain: "centropic.ai",
    tone: "amber",
  },
];

const DEFAULT_INSIGHTS: OverviewInsight[] = [
  {
    severity: "high",
    title: "Add JSON-LD Schema to Pricing Page",
    detail: "Will increase Perplexity citation likelihood by ~24%.",
  },
  {
    severity: "gap",
    title: "Competitor Mention in SearchGPT",
    detail: "Competitor X is currently top-ranked for key prompt query.",
  },
];

const statusClass: Record<OverviewEngineRow["status"], string> = {
  dominant: "text-emerald-400",
  optimal: "text-brand-cyan",
  needs_action: "text-amber-400",
  unknown: "text-brand-muted",
};

const statusText: Record<OverviewEngineRow["status"], string> = {
  dominant: "Dominant",
  optimal: "Optimal",
  needs_action: "Needs Action",
  unknown: "—",
};

const toneDot: Record<NonNullable<OverviewEngineRow["tone"]>, string> = {
  emerald: "bg-emerald-400",
  cyan: "bg-brand-cyan",
  violet: "bg-brand-violet",
  amber: "bg-amber-400",
};

export function DashboardOverview({
  onRunAudit,
  auditHref = "#",
  reportHref = "#",
  somPercent = 42.8,
  somDelta = 5.4,
  enginesTracked = 5,
  recRank = "#1.4",
  recRankDelta = 0.8,
  citations = 12840,
  citationsDeltaPct = 12,
  sentiment = 88,
  sentimentLabel = "Positive",
  engines = DEFAULT_ENGINES,
  insights = DEFAULT_INSIGHTS,
  evidenceLabel,
  somSeries,
  embedded = false,
}: DashboardOverviewProps) {
  const sent = Math.max(0, Math.min(100, Number(sentiment ?? 0)));
  const pos = sent;
  const mid = Math.max(0, Math.min(100 - pos, Math.round((100 - pos) * 0.66)));
  const neg = Math.max(0, 100 - pos - mid);

  return (
    <main
      className={`${
        embedded ? "" : "ml-64"
      } p-8 bg-brand-bg min-h-screen text-white space-y-8`}
    >
      {/* Header Bar */}
      <div className="flex flex-col gap-4 md:flex-row md:justify-between md:items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">GEO Overview</h2>
          <p className="text-sm text-brand-muted">
            Real-time Share of Model &amp; AI Visibility metrics.
            {evidenceLabel ? (
              <span className="ml-2 text-brand-cyan">· {evidenceLabel}</span>
            ) : null}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <select className="bg-brand-card border border-brand-border px-3 py-2 rounded-lg text-sm text-white focus:outline-none focus:border-brand-cyan">
            <option>Last 30 Days</option>
            <option>Last 7 Days</option>
            <option>Quarter to Date</option>
          </select>
          {onRunAudit ? (
            <button
              type="button"
              onClick={onRunAudit}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-brand-cyan to-brand-cyan/80 text-black font-semibold rounded-lg shadow-glow hover:opacity-90 transition-opacity"
            >
              <RefreshCw className="w-4 h-4" aria-hidden /> Run Instant GEO Audit
            </button>
          ) : (
            <a
              href={auditHref}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-brand-cyan to-brand-cyan/80 text-black font-semibold rounded-lg shadow-glow hover:opacity-90 transition-opacity"
            >
              <RefreshCw className="w-4 h-4" aria-hidden /> Run Instant GEO Audit
            </a>
          )}
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-brand-card border border-brand-border space-y-2">
          <p className="text-xs text-brand-muted uppercase font-medium">
            Share of Model (SoM)
          </p>
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold text-white">
              {somPercent != null ? `${somPercent}%` : "—"}
            </h3>
            {somDelta != null ? (
              <span className="flex items-center text-xs font-semibold text-emerald-400">
                <ArrowUpRight className="w-3 h-3" aria-hidden /> +{somDelta}%
              </span>
            ) : null}
          </div>
          <p className="text-xs text-brand-muted">
            Across {enginesTracked} tracked LLM platforms
          </p>
        </div>

        <div className="p-5 rounded-xl bg-brand-card border border-brand-border space-y-2">
          <p className="text-xs text-brand-muted uppercase font-medium">
            AI Rec. Rank
          </p>
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold text-white">{recRank ?? "—"}</h3>
            {recRankDelta != null ? (
              <span className="flex items-center text-xs font-semibold text-emerald-400">
                <ArrowUpRight className="w-3 h-3" aria-hidden /> +{recRankDelta}
              </span>
            ) : null}
          </div>
          <p className="text-xs text-brand-muted">Average position in answers</p>
        </div>

        <div className="p-5 rounded-xl bg-brand-card border border-brand-border space-y-2">
          <p className="text-xs text-brand-muted uppercase font-medium">
            Total AI Citations
          </p>
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold text-white">
              {citations != null ? citations.toLocaleString() : "—"}
            </h3>
            {citationsDeltaPct != null ? (
              <span className="flex items-center text-xs font-semibold text-emerald-400">
                <ArrowUpRight className="w-3 h-3" aria-hidden /> +
                {citationsDeltaPct}%
              </span>
            ) : null}
          </div>
          <p className="text-xs text-brand-muted">Verified source links</p>
        </div>

        <div className="p-5 rounded-xl bg-brand-card border border-brand-border space-y-2">
          <p className="text-xs text-brand-muted uppercase font-medium">
            AI Sentiment Index
          </p>
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold text-white">
              {sentiment != null ? `${sentiment}/100` : "—"}
            </h3>
            <span className="text-xs font-semibold text-brand-cyan">
              {sentimentLabel}
            </span>
          </div>
          <div className="w-full bg-brand-border h-1.5 rounded-full overflow-hidden flex">
            <div className="bg-emerald-400 h-full" style={{ width: `${pos}%` }} />
            <div className="bg-amber-400 h-full" style={{ width: `${mid}%` }} />
            <div className="bg-rose-400 h-full" style={{ width: `${neg}%` }} />
          </div>
        </div>
      </div>

      {/* Interactive Recharts Dynamic Graph */}
      <ShareOfModelChart data={somSeries} />

      {/* Grid: Multi-LLM Performance & Actionable Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 p-6 rounded-xl bg-brand-card border border-brand-border space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-bold">LLM Visibility Breakdown</h3>
            <a
              href={reportHref}
              className="text-xs text-brand-cyan hover:underline cursor-pointer"
            >
              View Detailed Report
            </a>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-brand-muted uppercase border-b border-brand-border">
                <tr>
                  <th className="py-3 px-2">Engine</th>
                  <th className="py-3 px-2">Share of Voice</th>
                  <th className="py-3 px-2">Top Cited Domain</th>
                  <th className="py-3 px-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-border/50">
                {engines.map((e) => (
                  <tr key={e.id}>
                    <td className="py-3 px-2 font-medium">
                      <span className="inline-flex items-center gap-2">
                        <span
                          className={`w-2 h-2 rounded-full ${
                            toneDot[e.tone || "cyan"]
                          }`}
                        />
                        {e.label}
                      </span>
                    </td>
                    <td className="py-3 px-2">
                      {e.share != null ? `${e.share}%` : "—"}
                    </td>
                    <td className="py-3 px-2 text-brand-muted">
                      {e.topDomain || "—"}
                    </td>
                    <td
                      className={`py-3 px-2 font-medium text-xs ${
                        statusClass[e.status]
                      }`}
                    >
                      {statusText[e.status]}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="p-6 rounded-xl bg-brand-card border border-brand-border space-y-4">
          <div className="flex items-center gap-2 text-brand-violet">
            <TrendingUp className="w-5 h-5" aria-hidden />
            <h3 className="text-lg font-bold text-white">
              Actionable GEO Insights
            </h3>
          </div>
          <div className="space-y-3">
            {insights.map((ins, i) => (
              <div
                key={`${ins.title}-${i}`}
                className="p-3 rounded-lg bg-brand-bg border border-brand-border/80 space-y-1"
              >
                <div
                  className={`flex items-center gap-2 text-xs font-medium ${
                    ins.severity === "high"
                      ? "text-emerald-400"
                      : ins.severity === "gap"
                        ? "text-amber-400"
                        : "text-brand-cyan"
                  }`}
                >
                  {ins.severity === "high" ? (
                    <CheckCircle2 className="w-3.5 h-3.5" aria-hidden />
                  ) : (
                    <AlertCircle className="w-3.5 h-3.5" aria-hidden />
                  )}
                  {ins.severity === "high"
                    ? "High Impact"
                    : ins.severity === "gap"
                      ? "Gap Detected"
                      : "Insight"}
                </div>
                <p className="text-xs font-semibold text-white">{ins.title}</p>
                <p className="text-xs text-brand-muted">{ins.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}

export default DashboardOverview;
