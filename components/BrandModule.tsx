"use client";

import React from "react";
import { BrandLockup } from "./BrandLockup";
import { HoloEmblem } from "./HoloEmblem";

export type BrandModuleProps = {
  /** Compact strip vs full hero composition */
  variant?: "hero" | "panel" | "inline";
  className?: string;
  ctaHref?: string;
  ctaLabel?: string;
};

/**
 * Centropic branding module — Formal Futurist layout.
 * Void Graphite field, Instrument Teal accent, quiet orbital emblem.
 */
export function BrandModule({
  variant = "hero",
  className,
  ctaHref = "#",
  ctaLabel = "Enter the signal field",
}: BrandModuleProps) {
  if (variant === "inline") {
    return (
      <BrandLockup
        size="sm"
        emblem
        particles={false}
        className={className}
      />
    );
  }

  if (variant === "panel") {
    return (
      <div
        className={
          className ||
          "relative overflow-hidden rounded-xl border border-[#1A222D] bg-[#0A0E14] p-6"
        }
      >
        <div
          className="pointer-events-none absolute inset-0 opacity-70"
          style={{
            background:
              "radial-gradient(ellipse 60% 50% at 20% 20%, rgba(110,198,192,0.08), transparent 55%), radial-gradient(ellipse 50% 40% at 80% 80%, rgba(74,124,140,0.08), transparent 50%)",
          }}
          aria-hidden
        />
        <div className="relative flex items-center gap-5">
          <HoloEmblem size={88} particles={false} />
          <div>
            <BrandLockup size="md" emblem={false} showTagline />
            <p className="mt-2 max-w-sm text-sm text-[#8B97A8]">
              Signal intelligence for AIO and GEO — measure where engines cite you.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <section
      className={
        className ||
        "relative isolate min-h-[70vh] overflow-hidden border border-[#1A222D] bg-[#04060A]"
      }
      aria-label="Centropic brand"
    >
      <div
        className="absolute inset-0 -z-10"
        style={{
          background: `
            radial-gradient(ellipse 70% 55% at 70% 40%, rgba(110,198,192,0.10), transparent 58%),
            radial-gradient(ellipse 55% 45% at 20% 70%, rgba(74,124,140,0.08), transparent 55%),
            linear-gradient(165deg, #04060A 0%, #070A10 45%, #0A0E14 100%)
          `,
        }}
        aria-hidden
      />

      <div className="relative z-10 flex flex-col items-center justify-center gap-8 px-6 py-16 text-center md:py-24">
        <HoloEmblem size={180} particles={false} />
        <BrandLockup size="hero" emblem={false} showTagline tagline="Signal Intelligence · AIO / GEO" />
        <p className="max-w-xl text-base text-[#8B97A8] md:text-lg">
          Measure where ChatGPT, Claude and Perplexity cite your brand — and what to fix.
        </p>
        <a
          href={ctaHref}
          className="inline-flex items-center justify-center rounded-md bg-[#6EC6C0] px-6 py-3 text-sm font-semibold text-[#04060A] transition hover:brightness-110"
        >
          {ctaLabel}
        </a>
      </div>
    </section>
  );
}

export default BrandModule;
