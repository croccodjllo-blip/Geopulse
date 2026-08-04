import React from "react";
import { Sidebar } from "@/components/Sidebar";
import { BrandModule } from "@/components/BrandModule";
import { DashboardOverview } from "@/components/DashboardOverview";
import { EngineVisibilityChart } from "@/components/EngineVisibilityChart";

function isEmbedMode(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as Window & { __CENTROPIC_GEO_EMBED__?: boolean };
  if (w.__CENTROPIC_GEO_EMBED__) return true;
  const q = new URLSearchParams(window.location.search);
  return q.get("embed") === "1";
}

/**
 * Centropic Enterprise GEO Dashboard.
 * Embed mode (Flask Live Charts): no React sidebar — Flask owns navigation.
 */
export default function App() {
  const embed = isEmbedMode();

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
        <DashboardOverview embedded />
        <div className="px-6 md:px-8 pb-10">
          <EngineVisibilityChart />
        </div>
      </div>
    </div>
  );
}
