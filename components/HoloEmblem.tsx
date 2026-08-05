"use client";

import React, { useEffect, useId, useRef } from "react";

export type HoloEmblemProps = {
  size?: number;
  className?: string;
  /** Enable orbital particle canvas overlay */
  particles?: boolean;
  title?: string;
};

type Particle = {
  a: number;
  r: number;
  s: number;
  size: number;
  hue: "cyan" | "violet" | "blue";
};

/**
 * Holographic Centropic emblem — ascending vector from a quantum vortex,
 * with optional orbital particle trails (canvas, no Three.js dependency).
 */
export function HoloEmblem({
  size = 160,
  className,
  particles = true,
  title = "Centropic",
}: HoloEmblemProps) {
  const uid = useId().replace(/:/g, "");
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!particles) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const resize = () => {
      canvas.width = size * dpr;
      canvas.height = size * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();

    const parts: Particle[] = Array.from({ length: 36 }, (_, i) => ({
      a: (i / 36) * Math.PI * 2,
      r: 28 + (i % 5) * 7,
      s: 0.004 + (i % 7) * 0.0012,
      size: 0.8 + (i % 3) * 0.45,
      hue: i % 3 === 0 ? "violet" : i % 3 === 1 ? "blue" : "cyan",
    }));

    let raf = 0;
    let t = 0;
    const color = (h: Particle["hue"]) =>
      h === "violet" ? "rgba(139,151,168,0.85)" : h === "blue" ? "rgba(91,107,122,0.8)" : "rgba(201,211,221,0.9)";

    const tick = () => {
      t += 1;
      ctx.clearRect(0, 0, size, size);
      const cx = size / 2;
      const cy = size / 2;
      for (const p of parts) {
        p.a += p.s;
        const wobble = Math.sin(t * 0.02 + p.r) * 2.2;
        const x = cx + Math.cos(p.a) * (p.r + wobble);
        const y = cy + Math.sin(p.a * 0.92 + 0.4) * (p.r * 0.42 + wobble * 0.4);
        ctx.beginPath();
        ctx.fillStyle = color(p.hue);
        ctx.shadowColor = color(p.hue);
        ctx.shadowBlur = 8;
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    const onVis = () => {
      if (document.hidden) cancelAnimationFrame(raf);
      else raf = requestAnimationFrame(tick);
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [particles, size]);

  return (
    <div
      className={
        className ||
        "relative inline-grid place-items-center rounded-full bg-[#04060A] shadow-[0_0_40px_rgba(201,211,221,0.22),0_0_80px_rgba(139,151,168,0.12)]"
      }
      style={{ width: size, height: size }}
      role="img"
      aria-label={title}
    >
      <svg
        viewBox="0 0 128 128"
        width={size}
        height={size}
        className="relative z-[1]"
        aria-hidden
      >
        <defs>
          <linearGradient id={`${uid}-holo`} x1="20" y1="110" x2="108" y2="18" gradientUnits="userSpaceOnUse">
            <stop stopColor="#5B6B7A" />
            <stop offset="0.45" stopColor="#C9D3DD" />
            <stop offset="1" stopColor="#8B97A8" />
          </linearGradient>
          <linearGradient id={`${uid}-metal`} x1="32" y1="96" x2="96" y2="28" gradientUnits="userSpaceOnUse">
            <stop stopColor="#D7DEE5" stopOpacity="0.15" />
            <stop offset="0.5" stopColor="#C9D3DD" stopOpacity="0.55" />
            <stop offset="1" stopColor="#8B97A8" stopOpacity="0.35" />
          </linearGradient>
          <radialGradient id={`${uid}-core`} cx="50%" cy="58%" r="42%">
            <stop stopColor="#C9D3DD" stopOpacity="0.95" />
            <stop offset="0.45" stopColor="#5B6B7A" stopOpacity="0.55" />
            <stop offset="1" stopColor="#8B97A8" stopOpacity="0" />
          </radialGradient>
          <filter id={`${uid}-glow`} x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="2.2" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <circle cx="64" cy="64" r="58" fill="#04060A" stroke={`url(#${uid}-metal)`} strokeWidth="1.2" />
        <g className="origin-center animate-[spin_28s_linear_infinite]" style={{ transformOrigin: "64px 64px" }}>
          <ellipse cx="64" cy="64" rx="40" ry="16" stroke="#C9D3DD" strokeOpacity="0.28" strokeWidth="0.9" transform="rotate(-28 64 64)" fill="none" />
          <ellipse cx="64" cy="64" rx="36" ry="14" stroke="#8B97A8" strokeOpacity="0.22" strokeWidth="0.8" transform="rotate(38 64 64)" fill="none" />
        </g>

        <g filter={`url(#${uid}-glow)`} className="origin-center animate-[spin_18s_linear_infinite_reverse]" style={{ transformOrigin: "64px 72px" }}>
          <path d="M64 92c18-2 28-14 26-28s-16-22-28-20c-10 2-16 12-14 22" stroke={`url(#${uid}-holo)`} strokeWidth="1.6" strokeLinecap="round" fill="none" />
          <path d="M64 86c14-1 22-11 20-22s-12-17-22-15c-8 1.5-12.5 9.5-11 17" stroke="#5B6B7A" strokeWidth="1.2" strokeLinecap="round" fill="none" opacity="0.85" />
          <path d="M64 80c10 0 16-8 14.5-15.5S70 54 64 55.5s-8.5 6.5-7.5 12" stroke="#8B97A8" strokeWidth="1.1" strokeLinecap="round" fill="none" opacity="0.9" />
        </g>

        <g stroke="#C9D3DD" strokeOpacity="0.35" strokeWidth="0.7" fill="none">
          <path d="M22 48h10v6h6" />
          <path d="M106 74h-9v-5h-5" />
          <path d="M28 86h8m0 0v5m0-5h4" />
          <path d="M96 40h-7m0 0v-4m0 4h-4" />
        </g>

        <g fill="#C9D3DD" fillOpacity="0.28" fontFamily="ui-monospace, monospace" fontSize="5.2">
          <text x="18" y="34">01</text>
          <text x="102" y="30">10</text>
          <text x="16" y="102">11</text>
          <text x="100" y="104">01</text>
        </g>

        <circle cx="64" cy="72" r="18" fill={`url(#${uid}-core)`} opacity="0.75" />

        <g filter={`url(#${uid}-glow)`}>
          <path d="M64 96V34" stroke={`url(#${uid}-holo)`} strokeWidth="3.2" strokeLinecap="round" />
          <path d="M64 22 L78 42 L64 36 L50 42 Z" fill={`url(#${uid}-holo)`} />
          <path d="M64 28 L72 40 L64 37 L56 40 Z" fill="#FFFFFF" fillOpacity="0.35" />
        </g>
        <path d="M40 38c8-10 24-14 38-8" stroke="#FFFFFF" strokeOpacity="0.22" strokeWidth="1.4" strokeLinecap="round" fill="none" />
      </svg>

      {particles ? (
        <canvas
          ref={canvasRef}
          className="pointer-events-none absolute inset-0 z-[2]"
          style={{ width: size, height: size }}
          aria-hidden
        />
      ) : null}

      <div
        className="pointer-events-none absolute inset-[8%] z-0 rounded-full bg-[radial-gradient(circle_at_50%_40%,rgba(201,211,221,0.18),transparent_55%),radial-gradient(circle_at_60%_70%,rgba(139,151,168,0.16),transparent_50%)] animate-pulse"
        aria-hidden
      />
    </div>
  );
}

export default HoloEmblem;
