import React from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type SomPoint = {
  /** ISO date or short label */
  t: string;
  /** Brand share of model % */
  rate: number | null;
};

export type SomTrendChartProps = {
  data: SomPoint[];
  height?: number;
  className?: string;
};

const CYAN = "#00F0FF";
const VIOLET = "#7000FF";
const MUTED = "#94A3B8";
const BORDER = "#1F2937";

function formatTick(value: string) {
  if (!value) return "";
  // Prefer YYYY-MM-DD → DD/MM
  const m = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[3]}/${m[2]}`;
  return value.slice(0, 10);
}

export function SomTrendChart({
  data,
  height = 220,
  className,
}: SomTrendChartProps) {
  const series = (data || [])
    .filter((d) => d && d.rate != null && !Number.isNaN(Number(d.rate)))
    .map((d) => ({ t: d.t, rate: Number(d.rate) }));

  if (series.length === 0) {
    return (
      <div
        className={
          className ||
          "flex h-[220px] items-center justify-center rounded-xl border border-brand-border bg-brand-card text-sm text-brand-muted"
        }
      >
        No SoM series yet — run a measured audit.
      </div>
    );
  }

  return (
    <div
      className={
        className ||
        "rounded-xl border border-brand-border bg-brand-card p-4 shadow-glow"
      }
      style={{ height }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="somFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CYAN} stopOpacity={0.35} />
              <stop offset="55%" stopColor={VIOLET} stopOpacity={0.12} />
              <stop offset="100%" stopColor={VIOLET} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="somStroke" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={CYAN} />
              <stop offset="100%" stopColor={VIOLET} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={BORDER} strokeDasharray="3 6" vertical={false} />
          <XAxis
            dataKey="t"
            tickFormatter={formatTick}
            tick={{ fill: MUTED, fontSize: 11 }}
            axisLine={{ stroke: BORDER }}
            tickLine={false}
            minTickGap={28}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: MUTED, fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={36}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            contentStyle={{
              background: "#111827",
              border: `1px solid ${BORDER}`,
              borderRadius: 8,
              color: "#F8FAFC",
              fontSize: 12,
            }}
            labelFormatter={(l) => String(l)}
            formatter={(value) => [`${value}%`, "SoM"]}
          />
          <Area
            type="monotone"
            dataKey="rate"
            stroke="url(#somStroke)"
            strokeWidth={2.5}
            fill="url(#somFill)"
            dot={{ r: 3, fill: CYAN, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: CYAN, stroke: "#0B0F19", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default SomTrendChart;
