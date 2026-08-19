import React from "react";
import {
  TrendingUp,
  AlertCircle,
  ArrowUpRight,
  RefreshCw,
} from "lucide-react";
import {
  ShareOfModelChart,
  type SomSeriesPoint,
} from "./ShareOfModelChart";
import { SomTrendChart, type SomPoint } from "./SomTrendChart";

export type OverviewEngineRow = {
  id: string;
  label: string;
  share: number | null;
  status: "dominant" | "optimal" | "needs_action" | "unknown";
  topDomain?: string;
  tone?: "emerald" | "cyan" | "steel" | "amber";
};

export type OverviewInsight = {
  severity: "critical" | "warn" | "info";
  /** Server-translated severity chip (Critico / Attenzione / Info). */
  severityLabel?: string;
  title: string;
  detail: string;
};

export type OverviewUiChrome = {
  insightsTitle?: string;
  insightsEmpty?: string;
  pagesScored?: string;
  findingsInLastAudit?: string;
  chartsTitle?: string;
  overviewTitle?: string;
  emptyBody?: string;
  runAudit?: string;
  liveSubtitle?: string;
  rangeLast30?: string;
  rangeLast7?: string;
  rangeQuarter?: string;
  rangeComingSoon?: string;
  somLabel?: string;
  acrossEngines?: string;
  recRankLabel?: string;
  recRankHint?: string;
  issuePressureTitle?: string;
  issuePressureHint?: string;
  somTrendTitle?: string;
  breakdownTitle?: string;
  viewReport?: string;
  enginesEmpty?: string;
  colEngine?: string;
  colShare?: string;
  colTopDomain?: string;
  colStatus?: string;
  statusDominant?: string;
  statusOptimal?: string;
  statusNeedsAction?: string;
  statusUnknown?: string;
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
  citationsLabel?: string;
  citationsHint?: string;
  /** Open critical+warn count — not model sentiment. */
  issuePressure?: number | null;
  issuePressureLabel?: string;
  engines?: OverviewEngineRow[];
  insights?: OverviewInsight[];
  /** Server-translated chrome for Charts (locale from Flask). */
  ui?: OverviewUiChrome;
  evidenceLabel?: string;
  somSeries?: SomSeriesPoint[];
  /** Live brand SoM history from Flask (preferred over demo multi-brand series). */
  somTrend?: SomPoint[];
  /** When true, omit the fixed sidebar offset (embed inside an existing shell). */
  embedded?: boolean;
  /** Suppress demo defaults — show empty/live values only. */
  live?: boolean;
  /** No analysis yet. */
  empty?: boolean;
  domain?: string;
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
    tone: "steel",
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
    severity: "critical",
    title: "Add JSON-LD Schema to Pricing Page",
    detail: "Missing Organization schema on a money page.",
  },
  {
    severity: "warn",
    title: "Competitor Mention in SearchGPT",
    detail: "Competitor X appears for a tracked prompt — verify your signals.",
  },
];

const statusClass: Record<OverviewEngineRow["status"], string> = {
  dominant: "text-emerald-400",
  optimal: "text-brand-cyan",
  needs_action: "text-amber-400",
  unknown: "text-brand-muted",
};

const toneDot: Record<NonNullable<OverviewEngineRow["tone"]>, string> = {
  emerald: "bg-emerald-400",
  cyan: "bg-brand-cyan",
  steel: "bg-brand-blue",
  amber: "bg-amber-400",
};

function fillN(template: string, n: string | number): string {
  return template.replace("%(n)s", String(n));
}

export function DashboardOverview({
  onRunAudit,
  auditHref = "/dashboard#analyze",
  reportHref = "/dashboard",
  somPercent,
  somDelta,
  enginesTracked,
  recRank,
  recRankDelta,
  citations,
  citationsDeltaPct,
  citationsLabel = "Total AI Citations",
  citationsHint = "Verified source links",
  issuePressure,
  issuePressureLabel = "Clear",
  engines,
  insights,
  ui,
  evidenceLabel,
  somSeries,
  somTrend,
  embedded = false,
  live = false,
  empty = false,
  domain,
}: DashboardOverviewProps) {
  const useDemo = !live;
  const resolvedEngines = engines ?? (useDemo ? DEFAULT_ENGINES : []);
  const resolvedInsights = insights ?? (useDemo ? DEFAULT_INSIGHTS : []);
  const insightsTitle = ui?.insightsTitle || "Actionable GEO Insights";
  const insightsEmpty =
    ui?.insightsEmpty ||
    "Nessun finding critico/warn nell'ultimo audit.";
  const chartsTitle = ui?.chartsTitle || "GEO Charts";
  const overviewTitle = ui?.overviewTitle || "GEO Overview";
  const emptyBody =
    ui?.emptyBody ||
    "Nessuna analisi ancora. Esegui un audit per vedere Share of Model, engine breakdown e insight dal tuo sito — niente dati demo.";
  const runAudit = ui?.runAudit || "Run Instant GEO Audit";
  const liveSubtitle =
    ui?.liveSubtitle ||
    "Live Share of Model & AI Visibility from your latest audit.";
  const somLabel = ui?.somLabel || "Share of Model";
  const recRankLabel = ui?.recRankLabel || "AI Rec. Rank";
  const recRankHint =
    ui?.recRankHint ||
    (live ? "Composite grade from AIO/GEO" : "Average position in answers");
  const issuePressureTitle = ui?.issuePressureTitle || "Issue pressure";
  const issuePressureHint =
    ui?.issuePressureHint || "Critical + warn open (not model sentiment)";
  const somTrendTitle = ui?.somTrendTitle || "Share of Model trend";
  const breakdownTitle = ui?.breakdownTitle || "LLM Visibility Breakdown";
  const viewReport = ui?.viewReport || "View Detailed Report";
  const enginesEmpty =
    ui?.enginesEmpty ||
    "Nessun engine breakdown ancora — riesegui l'audit.";
  const statusLabels: Record<OverviewEngineRow["status"], string> = {
    dominant: ui?.statusDominant || "Dominant",
    optimal: ui?.statusOptimal || "Optimal",
    needs_action: ui?.statusNeedsAction || "Needs Action",
    unknown: ui?.statusUnknown || "—",
  };

  const resolvedSom = somPercent ?? (useDemo ? 42.8 : null);
  const resolvedDelta = somDelta ?? (useDemo ? 5.4 : null);
  const resolvedTracked = enginesTracked ?? (useDemo ? 5 : resolvedEngines.length);
  const resolvedRank = recRank ?? (useDemo ? "#1.4" : null);
  const resolvedRankDelta = recRankDelta ?? (useDemo ? 0.8 : null);
  const resolvedCitations = citations ?? (useDemo ? 12840 : null);
  const resolvedCitationsDelta = citationsDeltaPct ?? (useDemo ? 12 : null);
  const resolvedPressure = issuePressure ?? (useDemo ? 2 : null);
  const resolvedPressureLabel =
    issuePressureLabel ||
    (resolvedPressure == null
      ? "—"
      : resolvedPressure <= 0
        ? "Clear"
        : resolvedPressure <= 2
          ? "Watch"
          : resolvedPressure <= 5
            ? "Elevated"
            : "High");
  const pressureTone =
    resolvedPressure == null
      ? "text-brand-muted"
      : resolvedPressure <= 0
        ? "text-emerald-400"
        : resolvedPressure <= 2
          ? "text-brand-cyan"
          : resolvedPressure <= 5
            ? "text-amber-400"
            : "text-rose-400";
  const acrossEngines = fillN(
    ui?.acrossEngines || "Across %(n)s tracked LLM platforms",
    resolvedTracked || "—",
  );

  if (empty) {
    return (
      <main
        className={`${
          embedded ? "" : "ml-64"
        } p-8 bg-brand-bg min-h-[50vh] text-white`}
      >
        <div className="max-w-xl rounded-xl border border-brand-border bg-brand-card p-8 space-y-4">
          <h2 className="text-2xl font-bold tracking-tight">{chartsTitle}</h2>
          <p className="text-sm text-brand-muted">{emptyBody}</p>
          <a
            href={auditHref}
            className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-brand-cyan to-brand-cyan/80 text-black font-semibold rounded-lg shadow-glow hover:opacity-90 transition-opacity"
          >
            <RefreshCw className="w-4 h-4" aria-hidden /> {runAudit}
          </a>
        </div>
      </main>
    );
  }

  return (
    <main
      className={`${
        embedded ? "" : "ml-64"
      } p-8 bg-brand-bg min-h-screen text-white space-y-8`}
    >
      <div className="flex flex-col gap-4 md:flex-row md:justify-between md:items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">{overviewTitle}</h2>
          <p className="text-sm text-brand-muted">
            {live
              ? liveSubtitle
              : "Real-time Share of Model & AI Visibility metrics."}
            {domain ? (
              <span className="ml-2 text-white/80">{domain}</span>
            ) : null}
            {evidenceLabel ? (
              <span className="ml-2 text-brand-cyan">· {evidenceLabel}</span>
            ) : null}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <select
            className="bg-brand-card border border-brand-border px-3 py-2 rounded-lg text-sm text-white focus:outline-none focus:border-brand-cyan"
            disabled={live}
            title={live ? ui?.rangeComingSoon || "Range storico: in arrivo" : undefined}
          >
            <option>{ui?.rangeLast30 || "Last 30 Days"}</option>
            <option>{ui?.rangeLast7 || "Last 7 Days"}</option>
            <option>{ui?.rangeQuarter || "Quarter to Date"}</option>
          </select>
          {onRunAudit ? (
            <button
              type="button"
              onClick={onRunAudit}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-brand-cyan to-brand-cyan/80 text-black font-semibold rounded-lg shadow-glow hover:opacity-90 transition-opacity"
            >
              <RefreshCw className="w-4 h-4" aria-hidden /> {runAudit}
            </button>
          ) : (
            <a
              href={auditHref}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-brand-cyan to-brand-cyan/80 text-black font-semibold rounded-lg shadow-glow hover:opacity-90 transition-opacity"
            >
              <RefreshCw className="w-4 h-4" aria-hidden /> {runAudit}
            </a>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-brand-card border border-brand-border space-y-2">
          <p className="text-xs text-brand-muted uppercase font-medium">
            {somLabel}
          </p>
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold text-white">
              {resolvedSom != null ? `${resolvedSom}%` : "—"}
            </h3>
            {resolvedDelta != null ? (
              <span className="flex items-center text-xs font-semibold text-emerald-400">
                <ArrowUpRight className="w-3 h-3" aria-hidden /> +{resolvedDelta}%
              </span>
            ) : null}
          </div>
          <p className="text-xs text-brand-muted">{acrossEngines}</p>
        </div>

        <div className="p-5 rounded-xl bg-brand-card border border-brand-border space-y-2">
          <p className="text-xs text-brand-muted uppercase font-medium">
            {recRankLabel}
          </p>
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold text-white">
              {resolvedRank ?? "—"}
            </h3>
            {resolvedRankDelta != null ? (
              <span className="flex items-center text-xs font-semibold text-emerald-400">
                <ArrowUpRight className="w-3 h-3" aria-hidden /> +
                {resolvedRankDelta}
              </span>
            ) : null}
          </div>
          <p className="text-xs text-brand-muted">{recRankHint}</p>
        </div>

        <div className="p-5 rounded-xl bg-brand-card border border-brand-border space-y-2">
          <p className="text-xs text-brand-muted uppercase font-medium">
            {citationsLabel}
          </p>
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold text-white">
              {resolvedCitations != null
                ? resolvedCitations.toLocaleString()
                : "—"}
            </h3>
            {resolvedCitationsDelta != null ? (
              <span className="flex items-center text-xs font-semibold text-emerald-400">
                <ArrowUpRight className="w-3 h-3" aria-hidden /> +
                {resolvedCitationsDelta}%
              </span>
            ) : null}
          </div>
          <p className="text-xs text-brand-muted">{citationsHint}</p>
        </div>

        <div className="p-5 rounded-xl bg-brand-card border border-brand-border space-y-2">
          <p className="text-xs text-brand-muted uppercase font-medium">
            {issuePressureTitle}
          </p>
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold text-white">
              {resolvedPressure != null ? resolvedPressure : "—"}
            </h3>
            <span className={`text-xs font-semibold ${pressureTone}`}>
              {resolvedPressureLabel}
            </span>
          </div>
          <p className="text-xs text-brand-muted">{issuePressureHint}</p>
        </div>
      </div>

      {live || (somTrend && somTrend.length > 0) ? (
        <div className="space-y-2">
          <h3 className="text-lg font-bold">{somTrendTitle}</h3>
          <SomTrendChart data={somTrend || []} />
        </div>
      ) : (
        <ShareOfModelChart data={somSeries} />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 p-6 rounded-xl bg-brand-card border border-brand-border space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-bold">{breakdownTitle}</h3>
            <a
              href={reportHref}
              className="text-xs text-brand-cyan hover:underline cursor-pointer"
            >
              {viewReport}
            </a>
          </div>
          {resolvedEngines.length === 0 ? (
            <p className="text-sm text-brand-muted py-6">{enginesEmpty}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs text-brand-muted uppercase border-b border-brand-border">
                  <tr>
                    <th className="py-3 px-2">{ui?.colEngine || "Engine"}</th>
                    <th className="py-3 px-2">{ui?.colShare || "Share of Voice"}</th>
                    <th className="py-3 px-2">
                      {ui?.colTopDomain || "Top Cited Domain"}
                    </th>
                    <th className="py-3 px-2">{ui?.colStatus || "Status"}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-brand-border/50">
                  {resolvedEngines.map((e) => (
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
                        {statusLabels[e.status]}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="p-6 rounded-xl bg-brand-card border border-brand-border space-y-4">
          <div className="flex items-center gap-2 text-brand-cyan">
            <TrendingUp className="w-5 h-5" aria-hidden />
            <h3 className="text-lg font-bold text-white">{insightsTitle}</h3>
          </div>
          <div className="space-y-3">
            {resolvedInsights.length === 0 ? (
              <p className="text-sm text-brand-muted">{insightsEmpty}</p>
            ) : (
              resolvedInsights.map((ins, i) => (
                <div
                  key={`${ins.title}-${i}`}
                  className="p-3 rounded-lg bg-brand-bg border border-brand-border/80 space-y-1"
                >
                  <div
                    className={`flex items-center gap-2 text-xs font-medium ${
                      ins.severity === "critical"
                        ? "text-rose-400"
                        : ins.severity === "warn"
                          ? "text-amber-400"
                          : "text-brand-cyan"
                    }`}
                  >
                    <AlertCircle className="w-3.5 h-3.5" aria-hidden />
                    {ins.severityLabel ||
                      (ins.severity === "critical"
                        ? "Critical"
                        : ins.severity === "warn"
                          ? "Warn"
                          : "Info")}
                  </div>
                  <p className="text-xs font-semibold text-white">{ins.title}</p>
                  <p className="text-xs text-brand-muted">{ins.detail}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

export default DashboardOverview;
