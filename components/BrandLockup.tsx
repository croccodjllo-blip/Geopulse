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
  sm: { emblem: 36, text: "text-base tracking-[-0.02em]" },
  md: { emblem: 48, text: "text-xl tracking-[-0.02em]" },
  lg: { emblem: 72, text: "text-3xl tracking-[-0.03em]" },
  hero: { emblem: 96, text: "text-5xl md:text-6xl tracking-[-0.03em]" },
} as const;

/**
 * centropic.ai wordmark — Formal Futurist (Space Grotesk + Instrument Teal).
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
          className={`m-0 font-bold lowercase text-[#F5F7FA] ${s.text}`}
          style={{ fontFamily: '"Inter", system-ui, sans-serif' }}
        >
          centropic
          <span className="font-semibold text-[#C9D3DD]">.ai</span>
        </p>
        {showTagline ? (
          <span className="text-[0.65rem] md:text-xs uppercase tracking-[0.18em] text-[#8B97A8]">
            {tagline}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export default BrandLockup;
