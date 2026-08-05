import React from "react";
import {
  LayoutDashboard,
  Bot,
  Sparkles,
  Settings,
  CreditCard,
  History,
} from "lucide-react";

export type SidebarNavId =
  | "dashboard"
  | "tracker"
  | "geo"
  | "integrations"
  | "history"
  | "settings"
  | "billing";

export type SidebarProps = {
  active?: SidebarNavId;
  planLabel?: string;
  /** Displayed credits used (e.g. analyses or prepaid units). */
  creditsUsed?: number;
  /** Soft cap for the progress bar (0 hides the ratio). */
  creditsCap?: number;
  creditsLabel?: string;
  billingHref?: string;
  dashboardHref?: string;
  trackerHref?: string;
  geoHref?: string;
  integrationsHref?: string;
  historyHref?: string;
  settingsHref?: string;
  logoSrc?: string;
};

const navItemClass = (active: boolean) =>
  active
    ? "flex items-center gap-3 px-3 py-2.5 rounded-lg bg-gradient-to-r from-brand-cyan/10 to-transparent border-l-2 border-brand-cyan text-white text-sm font-medium"
    : "flex items-center gap-3 px-3 py-2.5 rounded-lg text-brand-muted hover:text-white hover:bg-brand-border/40 text-sm font-medium transition-colors";

function LogoMark({ src }: { src?: string }) {
  if (src) {
    return (
      <img
        src={src}
        alt=""
        width={28}
        height={28}
        className="w-7 h-7"
        decoding="async"
      />
    );
  }
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 64 64"
      fill="none"
      aria-hidden
      className="w-7 h-7"
    >
      <defs>
        <linearGradient id="sidebarLogoGrad" x1="10" y1="54" x2="54" y2="10">
          <stop stopColor="#5B6B7A" />
          <stop offset="0.5" stopColor="#C9D3DD" />
          <stop offset="1" stopColor="#8B97A8" />
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="26" stroke="url(#sidebarLogoGrad)" strokeOpacity="0.35" strokeWidth="1" />
      <path
        d="M32 46c9-1 14-7 13-14s-8-11-14-10c-5 1-8 6-7 11"
        stroke="url(#sidebarLogoGrad)"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path d="M32 48V18" stroke="url(#sidebarLogoGrad)" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M32 12 L40 24 L32 21 L24 24 Z" fill="url(#sidebarLogoGrad)" />
    </svg>
  );
}

export function Sidebar({
  active = "dashboard",
  planLabel = "Enterprise",
  creditsUsed = 0,
  creditsCap = 10000,
  creditsLabel = "GEO Credits",
  billingHref = "/prezzi",
  dashboardHref = "/dashboard",
  trackerHref = "/dashboard#panel-sov",
  geoHref = "/dashboard#edge-signals",
  integrationsHref = "/dashboard#edge-signals",
  historyHref = "/dashboard/storico",
  settingsHref = "/dashboard/impostazioni",
  logoSrc = "/static/img/logo.svg",
}: SidebarProps) {
  const pct =
    creditsCap > 0
      ? Math.max(0, Math.min(100, (creditsUsed / creditsCap) * 100))
      : 0;

  return (
    <aside className="w-64 max-w-[16rem] bg-brand-card border-r border-brand-border h-screen flex flex-col justify-between p-4 fixed left-0 top-0 z-40 overflow-hidden">
      <div className="min-h-0 flex flex-col flex-1 overflow-hidden">
        <a
          href={dashboardHref}
          className="flex items-center gap-3 px-2 py-4 border-b border-brand-border/60 mb-4 min-w-0"
        >
          <div className="p-1.5 rounded-lg bg-gradient-to-br from-brand-cyan/20 to-brand-violet/20 border border-brand-cyan/40 shadow-glow shrink-0">
            <LogoMark src={logoSrc} />
          </div>
          <div className="min-w-0">
            <h1 className="text-base font-bold tracking-wide text-white truncate">
              centropic
              <span className="text-brand-cyan font-medium">.ai</span>
            </h1>
            <p className="text-xs text-brand-muted truncate">GEO Intelligence</p>
          </div>
        </a>

        <nav className="space-y-1 overflow-y-auto min-h-0 pr-1" aria-label="Primary">
          <a href={dashboardHref} className={navItemClass(active === "dashboard")}>
            <LayoutDashboard
              className={`w-4 h-4 shrink-0 ${active === "dashboard" ? "text-brand-cyan" : ""}`}
              aria-hidden
            />
            <span className="truncate">Dashboard</span>
          </a>
          <a href={trackerHref} className={navItemClass(active === "tracker")}>
            <Bot className="w-4 h-4 shrink-0" aria-hidden />
            <span className="truncate">Share of Voice</span>
          </a>
          <a href={geoHref} className={navItemClass(active === "geo")}>
            <Sparkles className="w-4 h-4 shrink-0" aria-hidden />
            <span className="truncate">Edge Signals</span>
          </a>
          <a href={historyHref} className={navItemClass(active === "history")}>
            <History className="w-4 h-4 shrink-0" aria-hidden />
            <span className="truncate">History</span>
          </a>
          <a href={settingsHref} className={navItemClass(active === "settings")}>
            <Settings className="w-4 h-4 shrink-0" aria-hidden />
            <span className="truncate">Settings</span>
          </a>
          <a href={billingHref} className={navItemClass(active === "billing")}>
            <CreditCard className="w-4 h-4 shrink-0" aria-hidden />
            <span className="truncate">Billing</span>
          </a>
        </nav>
      </div>

      <div className="p-4 rounded-xl bg-brand-bg border border-brand-border space-y-3 shrink-0 mt-4">
        <div className="flex justify-between items-center text-xs gap-2">
          <span className="text-brand-muted truncate">{creditsLabel}</span>
          <span className="text-brand-cyan font-semibold whitespace-nowrap">
            {creditsCap > 0
              ? `${creditsUsed.toLocaleString()} / ${creditsCap.toLocaleString()}`
              : creditsUsed.toLocaleString()}
          </span>
        </div>
        {creditsCap > 0 ? (
          <div className="w-full bg-brand-border h-2 rounded-full overflow-hidden">
            <div
              className="bg-gradient-to-r from-brand-cyan to-brand-violet h-full transition-[width] duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        ) : null}
        <div className="flex items-center justify-between pt-2 border-t border-brand-border/40 text-xs gap-2">
          <span className="px-2 py-0.5 rounded bg-brand-violet/20 text-brand-violet border border-brand-violet/30 font-medium">
            {planLabel}
          </span>
          <a
            href={billingHref}
            className="text-brand-muted hover:text-white flex items-center gap-1 transition-colors"
          >
            <CreditCard className="w-3 h-3" aria-hidden /> Plus
          </a>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
