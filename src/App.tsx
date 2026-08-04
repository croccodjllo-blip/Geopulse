import React from "react";
import { Sidebar } from "@/components/Sidebar";
import { BrandModule } from "@/components/BrandModule";
import { DashboardOverview } from "@/components/DashboardOverview";
import { EngineVisibilityChart } from "@/components/EngineVisibilityChart";

/**
 * Centropic Enterprise GEO Dashboard — holographic brand + analytics shell.
 */
export default function App() {
  return (
    <div className="min-h-screen bg-brand-bg text-white antialiased">
      <Sidebar
        active="dashboard"
        planLabel="Pro"
        creditsUsed={4200}
        creditsCap={10000}
      />
      <div className="ml-64 min-h-screen">
        <div className="p-8 pb-0">
          <BrandModule variant="panel" ctaHref="/register" />
        </div>
        <DashboardOverview embedded />
        <div className="px-8 pb-10">
          <EngineVisibilityChart />
        </div>
      </div>
    </div>
  );
}
