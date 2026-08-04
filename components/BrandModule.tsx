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
 * Centropic branding module — hyper-futuristic holographic layout.
 * Liquid-chrome field, neon emissions, iridescent wordmark, ascending emblem.
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
          "relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-[#080B10] via-[#0C1220] to-[#121824] p-6 shadow-[0_0_40px_rgba(0,240,255,0.08)]"
        }
      >
        <div
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(ellipse 60% 50% at 20% 20%, rgba(0,240,255,0.14), transparent 55%), radial-gradient(ellipse 50% 40% at 80% 80%, rgba(138,43,226,0.16), transparent 50%)",
          }}
          aria-hidden
        />
        <div className="relative flex items-center gap-5">
          <HoloEmblem size={88} particles />
          <div>
            <BrandLockup size="md" emblem={false} showTagline />
            <p className="mt-2 max-w-sm text-sm text-slate-400">
              Ascending signal intelligence — order from quantum noise.
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
        "relative isolate min-h-[70vh] overflow-hidden rounded-3xl border border-white/10 bg-[#080B10]"
      }
      aria-label="Centropic brand"
    >
      {/* Liquid chrome / metallic carbon field */}
      <div
        className="absolute inset-0 -z-10"
        style={{
          background: `
            radial-gradient(ellipse 70% 55% at 70% 40%, rgba(0,240,255,0.16), transparent 58%),
            radial-gradient(ellipse 55% 45% at 20% 70%, rgba(138,43,226,0.18), transparent 55%),
            radial-gradient(ellipse 40% 30% at 50% 0%, rgba(0,102,255,0.12), transparent 50%),
            linear-gradient(165deg, #080B10 0%, #0C1220 45%, #121824 100%)
          `,
        }}
        aria-hidden
      />
      {/* Wave-like liquid distortion (CSS only) */}
      <div
        className="pointer-events-none absolute inset-0 -z-10 opacity-[0.35] mix-blend-screen"
        style={{
          backgroundImage:
            "repeating-linear-gradient(115deg, transparent 0 14px, rgba(0,240,255,0.03) 14px 15px), repeating-linear-gradient(0deg, transparent 0 22px, rgba(138,43,226,0.025) 22px 23px)",
          animation: "holo-wave 12s ease-in-out infinite alternate",
        }}
        aria-hidden
      />

      <div className="relative z-10 flex flex-col items-center justify-center gap-8 px-6 py-16 text-center md:py-24">
        <HoloEmblem size={220} particles className="rounded-full" />
        <BrandLockup size="hero" emblem={false} showTagline tagline="Signal Intelligence · AIO / GEO" />
        <p className="max-w-xl text-base text-slate-300/90 md:text-lg">
          A glowing ascent from the quantum vortex — machine-readable order for
          generative visibility.
        </p>
        <a
          href={ctaHref}
          className="inline-flex items-center justify-center rounded-lg bg-gradient-to-r from-[#0066FF] via-[#00F0FF] to-[#8A2BE2] px-6 py-3 text-sm font-semibold text-[#080B10] shadow-[0_0_28px_rgba(0,240,255,0.35)] transition hover:brightness-110"
        >
          {ctaLabel}
        </a>
      </div>

      <style>{`
        @keyframes holo-wave {
          from { transform: translate3d(0,0,0) skewX(0deg); }
          to { transform: translate3d(-1.5%, 1%, 0) skewX(-0.6deg); }
        }
      `}</style>
    </section>
  );
}

export default BrandModule;
