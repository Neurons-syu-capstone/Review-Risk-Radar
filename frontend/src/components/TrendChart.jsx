import React from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

export function RatingTrendChart({ data }) {
  if (!data?.length) return <Empty />;

  // x축 레이블: 6개월 간격으로만 표시
  const ticks = data
    .map((d) => d.date)
    .filter((_, i) => i % 6 === 0);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis dataKey="date" ticks={ticks} tick={{ fontSize: 11 }} />
        <YAxis domain={[1, 5]} tickCount={5} tick={{ fontSize: 11 }} />
        <Tooltip
          formatter={(v) => [v.toFixed(2), "평균 평점"]}
          labelStyle={{ fontSize: 12 }}
        />
        <ReferenceLine y={3} stroke="#e65100" strokeDasharray="4 2" label={{ value: "기준 3.0", fontSize: 10, fill: "#e65100" }} />
        <Line
          type="monotone"
          dataKey="avg_rating"
          stroke="#6366f1"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function KeywordTrendChart({ data, attribute }) {
  if (!data?.length) return <Empty />;

  const ticks = data
    .map((d) => d.date)
    .filter((_, i) => i % 6 === 0);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis dataKey="date" ticks={ticks} tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={(v) => `${(v * 100).toFixed(1)}%`} tick={{ fontSize: 11 }} />
        <Tooltip
          formatter={(v) => [`${(v * 100).toFixed(2)}%`, `${attribute} 부정 언급 비율`]}
          labelStyle={{ fontSize: 12 }}
        />
        <Line
          type="monotone"
          dataKey="neg_ratio"
          stroke="#d32f2f"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function Empty() {
  return (
    <div style={{ height: 220, display: "flex", alignItems: "center", justifyContent: "center", color: "#aaa", fontSize: 13 }}>
      데이터 없음
    </div>
  );
}
