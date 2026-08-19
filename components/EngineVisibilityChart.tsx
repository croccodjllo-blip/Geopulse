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
  tone?: "emerald" | "cyan" | "steel" | "amber";
};

const TONE: Record<NonNullable<EngineBarPoint["tone"]>, string> = {
  emerald: "#10A37F",
  cyan: "#3FA8B5",
  steel: "#8BA3BD",
  amber: "#D4A574",
};

const DEFAULT: EngineBarPoint[] = [
  { id: "chatgpt", label: "ChatGPT", share: 48.2, tone: "emerald" },
  { id: "claude", label: "Claude", share: 41.0, tone: "steel" },
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
  const rows = [...data].sort((a, b) => b.share - a.share);

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
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            layout="vertical"
            data={rows}
            margin={{ top: 4, right: 16, left: 8, bottom: 0 }}
          >
            <CartesianGrid
              stroke="#1F2937"
              strokeDasharray="3 3"
              horizontal={false}
            />
            <XAxis
              type="number"
              domain={[0, 100]}
              axisLine={false}
              tickLine={false}
              fontSize={11}
              stroke="#94A3B8"
              unit="%"
            />
            <YAxis
              type="category"
              dataKey="label"
              axisLine={false}
              tickLine={false}
              fontSize={11}
              stroke="#94A3B8"
              width={88}
            />
            <Tooltip
              cursor={{ fill: "rgba(201,211,221,0.06)" }}
              contentStyle={{
                background: "#111827",
                border: "1px solid #1F2937",
                borderRadius: 8,
                fontSize: 12,
                color: "#F8FAFC",
              }}
              formatter={(value) => [`${value}%`, "SoV"]}
            />
            <Bar dataKey="share" radius={[0, 6, 6, 0]} barSize={18}>
              {rows.map((entry) => (
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
