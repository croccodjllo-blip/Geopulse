"use client";

import React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Cell,
} from "recharts";

export type EngineBarPoint = {
  id: string;
  label: string;
  share: number;
  tone?: "emerald" | "cyan" | "violet" | "amber";
};

const TONE: Record<NonNullable<EngineBarPoint["tone"]>, string> = {
  emerald: "#34d399",
  cyan: "#6EC6C0",
  violet: "#4A7C8C",
  amber: "#fbbf24",
};

const DEFAULT: EngineBarPoint[] = [
  { id: "chatgpt", label: "ChatGPT", share: 48.2, tone: "emerald" },
  { id: "claude", label: "Claude", share: 41.0, tone: "violet" },
  { id: "perplexity", label: "Perplexity", share: 39.5, tone: "cyan" },
  { id: "searchgpt", label: "SearchGPT", share: 28.4, tone: "amber" },
];

export type EngineVisibilityChartProps = {
  data?: EngineBarPoint[];
  className?: string;
};

export function EngineVisibilityChart({
  data = DEFAULT,
  className,
}: EngineVisibilityChartProps) {
  return (
    <div
      className={
        className ||
        "p-6 rounded-xl bg-brand-card border border-brand-border space-y-4"
      }
    >
      <div>
        <h3 className="text-lg font-bold text-white">Engine Share Snapshot</h3>
        <p className="text-xs text-brand-muted">
          Relative Share of Voice by generative engine
        </p>
      </div>
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 8, right: 8, left: -12, bottom: 0 }}
          >
            <CartesianGrid
              stroke="#1F2937"
              strokeDasharray="3 3"
              vertical={false}
            />
            <XAxis
              dataKey="label"
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
              domain={[0, 100]}
            />
            <Tooltip
              cursor={{ fill: "rgba(110,198,192,0.06)" }}
              contentStyle={{
                background: "#111827",
                border: "1px solid #1F2937",
                borderRadius: 8,
                fontSize: 12,
                color: "#F8FAFC",
              }}
              formatter={(value) => [`${value}%`, "SoV"]}
            />
            <Bar dataKey="share" radius={[6, 6, 0, 0]}>
              {data.map((entry) => (
                <Cell
                  key={entry.id}
                  fill={TONE[entry.tone || "cyan"]}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default EngineVisibilityChart;
