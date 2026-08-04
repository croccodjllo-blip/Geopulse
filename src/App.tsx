import React from "react";
import { Sidebar } from "@/components/Sidebar";
import { BrandModule } from "@/components/BrandModule";
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
import type { SomPoint } from "@/components/SomTrendChart";

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
};

function isEmbedMode(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as Window & { __CENTROPIC_GEO_EMBED__?: boolean };
  if (w.__CENTROPIC_GEO_EMBED__) return true;
  const q = new URLSearchParams(window.location.search);
  return q.get("embed") === "1";
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
        citationsLabel: "Pages scored",
        citationsHint: `${live.findingsCount ?? 0} findings in last audit`,
        citationsDeltaPct: null,
        issuePressure: live.issuePressure ?? null,
        issuePressureLabel: live.issuePressureLabel || undefined,
        engines: live.engines || [],
        insights: live.insights || [],
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
        <div className="p-6 md:p-8 pb-0">
          <BrandModule variant="panel" ctaHref="/dashboard" />
        </div>
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
