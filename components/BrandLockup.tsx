"use client";

import React from "react";
import { HoloEmblem } from "./HoloEmblem";

export type BrandLockupProps = {
  size?: "sm" | "md" | "lg" | "hero";
  showTagline?: boolean;
  tagline?: string;
  className?: string;
  emblem?: boolean;
  particles?: boolean;
};

const SIZE = {
  sm: { emblem: 36, text: "text-base tracking-[0.14em]" },
  md: { emblem: 48, text: "text-xl tracking-[0.16em]" },
  lg: { emblem: 72, text: "text-3xl tracking-[0.18em]" },
  hero: { emblem: 96, text: "text-5xl md:text-6xl tracking-[0.14em]" },
} as const;

/**
 * centropic.ai wordmark — geometric Sora-style weight with iridescent gradient
 * and soft holographic glow (glassmorphism-ready).
 */
export function BrandLockup({
  size = "md",
  showTagline = false,
  tagline = "GEO Intelligence",
  className,
  emblem = true,
  particles = false,
}: BrandLockupProps) {
  const s = SIZE[size];
  return (
    <div
      className={
        className ||
        "inline-flex items-center gap-3 md:gap-4"
      }
    >
      {emblem ? (
        <HoloEmblem size={s.emblem} particles={particles} />
      ) : null}
      <div className="flex flex-col gap-1 min-w-0">
        <p
          className={`m-0 font-bold uppercase text-transparent bg-clip-text bg-gradient-to-r from-[#0066FF] via-[#00F0FF] to-[#8A2BE2] drop-shadow-[0_0_18px_rgba(0,240,255,0.35)] ${s.text}`}
          style={{ fontFamily: '"Sora", "Plus Jakarta Sans", system-ui, sans-serif' }}
        >
          centropic
          <span className="font-medium normal-case tracking-normal">.ai</span>
        </p>
        {showTagline ? (
          <span className="text-[0.65rem] md:text-xs uppercase tracking-[0.22em] text-[#94A3B8]">
            {tagline}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export default BrandLockup;
