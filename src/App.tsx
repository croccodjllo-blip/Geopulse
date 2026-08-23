import React from "react";
import { Sidebar } from "@/components/Sidebar";
import {
  DashboardOverview,
  type DashboardOverviewProps,
  type OverviewEngineRow,
  type OverviewInsight,
} from "@/components/DashboardOverview";
import {
  EngineVisibilityChart,
  type EngineBarPoint,
} from "@/components/EngineVisibilityChart";
import { SomTrendChart, type SomPoint } from "@/components/SomTrendChart";

type GeoUiChrome = {
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

type GeoUiData = {
  ready: boolean;
  domain?: string | null;
  somPercent?: number | null;
  somDelta?: number | null;
  enginesTracked?: number;
  recRank?: string | null;
  aioScore?: number | null;
  geoScore?: number | null;
  pagesAnalyzed?: number | null;
  findingsCount?: number;
  issuePressure?: number | null;
  issuePressureLabel?: string | null;
  evidenceLabel?: string | null;
  engines?: OverviewEngineRow[];
  engineBars?: EngineBarPoint[];
  insights?: OverviewInsight[];
  somTrend?: SomPoint[];
  auditHref?: string;
  reportHref?: string;
  ui?: GeoUiChrome;
};

function isEmbedMode(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as Window & { __CENTROPIC_GEO_EMBED__?: boolean };
  if (w.__CENTROPIC_GEO_EMBED__) return true;
  const q = new URLSearchParams(window.location.search);
  return q.get("embed") === "1";
}

function isCompactMode(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as Window & { __CENTROPIC_GEO_COMPACT__?: boolean };
  return Boolean(w.__CENTROPIC_GEO_COMPACT__);
}

function readLiveData(): GeoUiData | null {
  if (typeof window === "undefined") return null;
  const w = window as Window & { __CENTROPIC_GEO_DATA__?: GeoUiData };
  return w.__CENTROPIC_GEO_DATA__ ?? null;
}

/**
 * Centropic Enterprise GEO Dashboard.
 * Embed mode (Flask GEO Charts): no React sidebar — Flask owns navigation.
 * Live data comes from window.__CENTROPIC_GEO_DATA__ (no demo KPIs in embed).
 */
export default function App() {
  const embed = isEmbedMode();
  const live = readLiveData();

  // Embed must never fall open to demo KPIs if Flask payload is missing.
  const overviewProps: DashboardOverviewProps = live
    ? {
        embedded: true,
        live: true,
        evidenceLabel: live.evidenceLabel || undefined,
        somPercent: live.somPercent ?? null,
        somDelta: live.somDelta ?? null,
        enginesTracked: live.enginesTracked ?? 0,
        recRank: live.recRank ?? null,
        citations: live.pagesAnalyzed ?? null,
        citationsLabel: live.ui?.pagesScored || "Pages scored",
        citationsHint: `${live.findingsCount ?? 0} ${
          live.ui?.findingsInLastAudit || "findings in last audit"
        }`,
        citationsDeltaPct: null,
        issuePressure: live.issuePressure ?? null,
        issuePressureLabel: live.issuePressureLabel || undefined,
        engines: live.engines || [],
        insights: live.insights || [],
        ui: live.ui,
        somTrend: live.somTrend || [],
        auditHref: live.auditHref || "/dashboard#analyze",
        reportHref: live.reportHref || "/dashboard",
        empty: !live.ready,
        domain: live.domain || undefined,
      }
    : embed
      ? {
          embedded: true,
          live: true,
          empty: true,
          auditHref: "/dashboard#analyze",
          reportHref: "/dashboard",
        }
      : { embedded: false };

  const bars = live?.engineBars || [];
  const compact = embed && isCompactMode();

  if (compact) {
    const trend = live?.somTrend || [];
    const hasTrend = trend.some((p) => p && p.rate != null);
    if (!live?.ready || (!hasTrend && bars.length === 0)) {
      return <div className="geo-compact" hidden />;
    }
    return (
      <div className="geo-compact grid grid-cols-1 gap-3 xl:grid-cols-2">
        {hasTrend ? (
          <section className="min-w-0">
            <p className="mb-1.5 text-[0.66rem] font-semibold uppercase tracking-[0.14em] text-brand-cyan">
              {live?.ui?.somTrendTitle || "Share of Model"}
            </p>
            <SomTrendChart
              data={trend}
              height={168}
              className="h-[168px] rounded-xl border border-brand-border bg-brand-card p-3"
            />
          </section>
        ) : null}
        {bars.length > 0 ? (
          <EngineVisibilityChart data={bars} compact />
        ) : null}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-brand-bg text-white antialiased">
      {embed ? null : (
        <Sidebar
          active="dashboard"
          planLabel="Pro"
          creditsUsed={4200}
          creditsCap={10000}
        />
      )}
      <div className={embed ? "min-h-screen" : "ml-64 min-h-screen"}>
        {/* Charts embed: no brand panel — Flask shell owns chrome; content starts at top. */}
        <DashboardOverview {...overviewProps} />
        {live?.ready && bars.length > 0 ? (
          <div className="px-6 md:px-8 pb-10">
            <EngineVisibilityChart data={bars} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
