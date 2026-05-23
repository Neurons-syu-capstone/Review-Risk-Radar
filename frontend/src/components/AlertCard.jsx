import React, { useState } from "react";

const LEVEL_META = {
  위험: { badge: "badge-danger",  icon: "🔴", label: "위험" },
  경고: { badge: "badge-warning", icon: "🟡", label: "경고" },
  양호: { badge: "badge-safe",    icon: "🟢", label: "양호" },
};

export default function AlertCard({ alert }) {
  const [open, setOpen] = useState(false);
  const meta = LEVEL_META[alert.level] ?? LEVEL_META["양호"];

  return (
    <div className="card" style={{ borderLeft: `4px solid ${borderColor(alert.level)}` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <span style={{ fontSize: 14, fontWeight: 700 }}>{alert.attribute}</span>
          <span className={`badge ${meta.badge}`} style={{ marginLeft: 8 }}>
            {meta.icon} {meta.label}
          </span>
        </div>
        <span style={{ fontSize: 22, fontWeight: 800, color: borderColor(alert.level) }}>
          {alert.delta_pct > 0 ? "+" : ""}{alert.delta_pct}%
        </span>
      </div>

      <p style={{ marginTop: 8, fontSize: 13, color: "#555" }}>{alert.description}</p>

      {alert.evidence?.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <button
            onClick={() => setOpen((v) => !v)}
            style={{ fontSize: 12, color: "#6366f1", background: "none", border: "none", cursor: "pointer" }}
          >
            {open ? "▲ 증거 리뷰 숨기기" : `▼ 증거 리뷰 ${alert.evidence.length}건 보기`}
          </button>
          {open && (
            <ul style={{ marginTop: 6, paddingLeft: 16 }}>
              {alert.evidence.map((ev, i) => (
                <li key={i} style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>
                  "{ev.slice(0, 120)}{ev.length > 120 ? "…" : ""}"
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function borderColor(level) {
  if (level === "위험") return "#d32f2f";
  if (level === "경고") return "#e65100";
  return "#2e7d32";
}
