import React from "react";
import {
  Line,
  LineChart,
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

const CHROME = "#E8A04A";
const CHROME_DEEP = "#8BA3BD";
const MUTED = "#94A3B8";
const BORDER = "#1F2937";

function formatTick(value: string) {
  if (!value) return "";
  const m = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[3]}/${m[2]}`;
  return value.slice(0, 10);
}

export function SomTrendChart({
  data,
  height: _height = 220,
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
        "h-[220px] rounded-xl border border-brand-border bg-brand-card p-4 shadow-glow"
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
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
          <Line
            type="monotone"
            dataKey="rate"
            stroke={CHROME}
            strokeWidth={2.5}
            dot={{ r: 3.5, fill: CHROME_DEEP, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: CHROME, stroke: "#0B0F19", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default SomTrendChart;
