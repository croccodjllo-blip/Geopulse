"use client";

import React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

export type SomSeriesPoint = {
  date: string;
  centropic: number;
  competitorA: number;
  competitorB: number;
};

const DEFAULT_DATA: SomSeriesPoint[] = [
  { date: "01 Aug", centropic: 32, competitorA: 24, competitorB: 18 },
  { date: "05 Aug", centropic: 35, competitorA: 23, competitorB: 17 },
  { date: "10 Aug", centropic: 38, competitorA: 22, competitorB: 16 },
  { date: "15 Aug", centropic: 36, competitorA: 25, competitorB: 15 },
  { date: "20 Aug", centropic: 40, competitorA: 21, competitorB: 14 },
  { date: "25 Aug", centropic: 41, competitorA: 20, competitorB: 13 },
  { date: "30 Aug", centropic: 42.8, competitorA: 19.5, competitorB: 12.2 },
];

type TooltipPayloadItem = { value?: number | string };

function CustomTooltip({
  active,
  payload,
  label,
  brandLabel = "Centropic.ai",
  competitorALabel = "Competitor A",
  competitorBLabel = "Competitor B",
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
  brandLabel?: string;
  competitorALabel?: string;
  competitorBLabel?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="bg-brand-card border border-brand-border p-3 rounded-lg shadow-xl text-xs space-y-1.5">
      <p className="font-semibold text-white border-b border-brand-border/60 pb-1">
        {label}
      </p>
      <p className="text-brand-cyan flex justify-between gap-4">
        <span>{brandLabel}:</span>
        <span className="font-bold">{payload[0]?.value}%</span>
      </p>
      <p className="text-brand-violet flex justify-between gap-4">
        <span>{competitorALabel}:</span>
        <span className="font-bold">{payload[1]?.value}%</span>
      </p>
      <p className="text-brand-muted flex justify-between gap-4">
        <span>{competitorBLabel}:</span>
        <span className="font-bold">{payload[2]?.value}%</span>
      </p>
    </div>
  );
}

export type ShareOfModelChartProps = {
  data?: SomSeriesPoint[];
  brandLabel?: string;
  competitorALabel?: string;
  competitorBLabel?: string;
  className?: string;
};

export function ShareOfModelChart({
  data = DEFAULT_DATA,
  brandLabel = "Centropic.ai",
  competitorALabel = "Competitor A",
  competitorBLabel = "Competitor B",
  className,
}: ShareOfModelChartProps) {
  return (
    <div
      className={
        className ||
        "p-6 rounded-xl bg-brand-card border border-brand-border space-y-4"
      }
    >
      <div className="flex flex-col gap-3 md:flex-row md:justify-between md:items-center">
        <div>
          <h3 className="text-lg font-bold text-white">
            Share of Model (SoM) Trend
          </h3>
          <p className="text-xs text-brand-muted">
            Historical visibility comparison across generative engines
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-brand-cyan" />
            <span className="text-white font-medium">{brandLabel}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-brand-violet" />
            <span className="text-brand-muted">{competitorALabel}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-brand-border" />
            <span className="text-brand-muted">{competitorBLabel}</span>
          </div>
        </div>
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
          >
            <defs>
              <linearGradient id="colorCentropic" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6EC6C0" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#6EC6C0" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="colorCompA" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#4A7C8C" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#4A7C8C" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              stroke="#1F2937"
              strokeDasharray="3 3"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              axisLine={false}
              tickLine={false}
              fontSize={11}
              stroke="#94A3B8"
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              fontSize={11}
              stroke="#94A3B8"
              unit="%"
            />
            <Tooltip
              content={
                <CustomTooltip
                  brandLabel={brandLabel}
                  competitorALabel={competitorALabel}
                  competitorBLabel={competitorBLabel}
                />
              }
            />
            <Area
              type="monotone"
              dataKey="centropic"
              stroke="#6EC6C0"
              strokeWidth={2}
              fill="url(#colorCentropic)"
              fillOpacity={1}
            />
            <Area
              type="monotone"
              dataKey="competitorA"
              stroke="#4A7C8C"
              strokeWidth={1.5}
              fill="url(#colorCompA)"
              fillOpacity={1}
            />
            <Area
              type="monotone"
              dataKey="competitorB"
              stroke="#475569"
              strokeWidth={1}
              strokeDasharray="4 4"
              fill="transparent"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default ShareOfModelChart;
