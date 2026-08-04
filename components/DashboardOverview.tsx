import React from "react";
import {
  TrendingUp,
  CheckCircle2,
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
} from "lucide-react";

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
};

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

function Delta({ value, suffix = "%" }: { value: number | null | undefined; suffix?: string }) {
  if (value == null || Number.isNaN(value)) return null;
  const up = value >= 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span
      className={`flex items-center text-xs font-semibold ${
        up ? "text-emerald-400" : "text-rose-400"
      }`}
    >
      <Icon className="w-3 h-3" aria-hidden />
      {up ? "+" : ""}
      {value}
      {suffix}
    </span>
  );
}

export function DashboardOverview({
  rangeLabel = "Last 30 Days",
  onRunAudit,
  auditHref = "#",
  reportHref = "#",
  somPercent = null,
  somDelta = null,
  enginesTracked = 0,
  recRank = null,
  recRankDelta = null,
  citations = null,
  citationsDeltaPct = null,
  sentiment = null,
  sentimentLabel = "—",
  engines = [],
  insights = [],
  evidenceLabel,
}: DashboardOverviewProps) {
  const sent = Math.max(0, Math.min(100, Number(sentiment ?? 0)));
  const pos = sent;
  const mid = Math.max(0, Math.min(100 - pos, Math.round((100 - pos) * 0.66)));
  const neg = Math.max(0, 100 - pos - mid);

  return (
    <section className="space-y-8 text-white" aria-labelledby="geo-overview-title">
      <div className="flex flex-col gap-4 md:flex-row md:justify-between md:items-center">
        <div>
          <h2 id="geo-overview-title" className="text-2xl font-bold tracking-tight">
            GEO Overview
          </h2>
          <p className="text-sm text-brand-muted">
            Real-time Share of Model &amp; AI Visibility metrics.
            {evidenceLabel ? (
              <span className="ml-2 text-brand-cyan">· {evidenceLabel}</span>
            ) : null}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <select
            className="bg-brand-card border border-brand-border px-3 py-2 rounded-lg text-sm text-white focus:outline-none focus:border-brand-cyan"
            defaultValue={rangeLabel}
            aria-label="Date range"
          >
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

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-brand-card border border-brand-border space-y-2">
          <p className="text-xs text-brand-muted uppercase font-medium">
            Share of Model (SoM)
          </p>
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold text-white">
              {somPercent != null ? `${somPercent}%` : "—"}
            </h3>
            <Delta value={somDelta} />
          </div>
          <p className="text-xs text-brand-muted">
            Across {enginesTracked || engines.length || "—"} tracked LLM platforms
          </p>
        </div>

        <div className="p-5 rounded-xl bg-brand-card border border-brand-border space-y-2">
          <p className="text-xs text-brand-muted uppercase font-medium">AI Rec. Rank</p>
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold text-white">{recRank ?? "—"}</h3>
            <Delta value={recRankDelta} suffix="" />
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
            <Delta value={citationsDeltaPct} />
          </div>
          <p className="text-xs text-brand-muted">Verified source links / pages scored</p>
        </div>

        <div className="p-5 rounded-xl bg-brand-card border border-brand-border space-y-2">
          <p className="text-xs text-brand-muted uppercase font-medium">
            AI Sentiment Index
          </p>
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold text-white">
              {sentiment != null ? `${sentiment}/100` : "—"}
            </h3>
            <span className="text-xs font-semibold text-brand-cyan">{sentimentLabel}</span>
          </div>
          <div className="w-full bg-brand-border h-1.5 rounded-full overflow-hidden flex">
            <div className="bg-emerald-400 h-full" style={{ width: `${pos}%` }} />
            <div className="bg-amber-400 h-full" style={{ width: `${mid}%` }} />
            <div className="bg-rose-400 h-full" style={{ width: `${neg}%` }} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 p-6 rounded-xl bg-brand-card border border-brand-border space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-bold">LLM Visibility Breakdown</h3>
            <a href={reportHref} className="text-xs text-brand-cyan hover:underline">
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
                {engines.length === 0 ? (
                  <tr>
                    <td className="py-3 px-2 text-brand-muted" colSpan={4}>
                      No engine breakdown yet — run an audit.
                    </td>
                  </tr>
                ) : (
                  engines.map((e) => (
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
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="p-6 rounded-xl bg-brand-card border border-brand-border space-y-4">
          <div className="flex items-center gap-2 text-brand-violet">
            <TrendingUp className="w-5 h-5" aria-hidden />
            <h3 className="text-lg font-bold text-white">Actionable GEO Insights</h3>
          </div>
          <div className="space-y-3">
            {insights.length === 0 ? (
              <p className="text-xs text-brand-muted">No critical insights on this run.</p>
            ) : (
              insights.map((ins, i) => (
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
              ))
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export default DashboardOverview;
