import React from "react";
import { Sidebar } from "@/components/Sidebar";
import { DashboardOverview } from "@/components/DashboardOverview";
import { EngineVisibilityChart } from "@/components/EngineVisibilityChart";

/**
 * Centropic Enterprise GEO Dashboard — root composition.
 * Layout: fixed Sidebar + scrollable main (GEO Overview + Engine Visibility).
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
        <DashboardOverview embedded />
        <div className="px-8 pb-10 -mt-2">
          <EngineVisibilityChart />
        </div>
      </div>
    </div>
  );
}
