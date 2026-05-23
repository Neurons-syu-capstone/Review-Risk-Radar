import React, { useEffect, useState, useCallback } from "react";
import AlertCard from "../components/AlertCard";
import { RatingTrendChart, KeywordTrendChart } from "../components/TrendChart";
import { fetchMeta, fetchAlerts, fetchRatingTrend, fetchKeywordTrend } from "../api/riskApi";

export default function RiskRadarPage() {
  const [meta, setMeta] = useState(null);
  const [productId, setProductId] = useState("");
  const [referenceDate, setReferenceDate] = useState("");
  const [windowDays, setWindowDays] = useState(90);
  const [selectedAttr, setSelectedAttr] = useState("");

  const [alerts, setAlerts] = useState([]);
  const [ratingTrend, setRatingTrend] = useState([]);
  const [keywordTrend, setKeywordTrend] = useState([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 초기 메타 로드
  useEffect(() => {
    fetchMeta()
      .then((data) => {
        setMeta(data);
        setProductId(data.products[0]?.product_id ?? "");
        setReferenceDate(data.date_range.max);
        setSelectedAttr(data.attributes[0] ?? "");
      })
      .catch(() => setError("API 서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요."));
  }, []);

  // 상품/날짜/윈도우 변경 시 경보 재조회
  const loadAlerts = useCallback(async () => {
    if (!productId) return;
    setLoading(true);
    setError("");
    try {
      const [alertData, trendData] = await Promise.all([
        fetchAlerts(productId, referenceDate, windowDays),
        fetchRatingTrend(productId),
      ]);
      setAlerts(alertData.alerts);
      setRatingTrend(trendData.trend);
    } catch (e) {
      setError("데이터 로드 실패: " + e.message);
    } finally {
      setLoading(false);
    }
  }, [productId, referenceDate, windowDays]);

  useEffect(() => { loadAlerts(); }, [loadAlerts]);

  // 속성 키워드 트렌드
  useEffect(() => {
    if (!productId || !selectedAttr) return;
    fetchKeywordTrend(productId, selectedAttr)
      .then((data) => setKeywordTrend(data.trend))
      .catch(() => {});
  }, [productId, selectedAttr]);

  const levelCount = (level) => alerts.filter((a) => a.level === level).length;

  const currentProduct = meta?.products.find((p) => p.product_id === productId);

  if (!meta) return <div className="page" style={{ color: "#999" }}>{error || "로딩 중…"}</div>;

  return (
    <div className="page">
      {/* 헤더 */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800 }}>🔔 부정 리스크 감지 및 조기 경보</h1>
        <p style={{ color: "#666", marginTop: 4, fontSize: 14 }}>
          기준 날짜 기준 부정 키워드 급증 · 평점 하락 이상 패턴을 자동 감지합니다
        </p>
      </div>

      {/* 컨트롤 패널 */}
      <div className="card" style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 24, alignItems: "flex-end" }}>
        <div style={{ flex: "1 1 220px" }}>
          <label htmlFor="product-select" style={labelStyle}>상품 선택</label>
          <select id="product-select" value={productId} onChange={(e) => setProductId(e.target.value)} style={{ ...selectStyle, width: "100%" }}>
            {meta.products.map((p) => (
              <option key={p.product_id} value={p.product_id}>
                {p.title} ({p.review_count.toLocaleString()}개)
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="reference-date" style={labelStyle}>기준 날짜</label>
          <input
            id="reference-date"
            type="date"
            value={referenceDate}
            min={meta.date_range.min}
            max={meta.date_range.max}
            onChange={(e) => setReferenceDate(e.target.value)}
            style={selectStyle}
          />
        </div>
        <div>
          <label htmlFor="window-select" style={labelStyle}>비교 윈도우</label>
          <select id="window-select" value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value))} style={selectStyle}>
            <option value={30}>최근 30일</option>
            <option value={60}>최근 60일</option>
            <option value={90}>최근 90일</option>
            <option value={180}>최근 180일</option>
          </select>
        </div>
        <div style={{ fontSize: 12, color: "#888", lineHeight: 1.6 }}>
          데이터 범위<br />
          <strong>{meta.date_range.min} ~ {meta.date_range.max}</strong>
        </div>
      </div>

      {error && <div style={{ color: "#d32f2f", marginBottom: 16, fontSize: 14 }}>⚠️ {error}</div>}

      {/* 요약 뱃지 */}
      <div className="grid-3" style={{ marginBottom: 24 }}>
        {[
          { level: "위험", color: "#d32f2f", bg: "#ffe5e5" },
          { level: "경고", color: "#e65100", bg: "#fff3e0" },
          { level: "양호", color: "#2e7d32", bg: "#e8f5e9" },
        ].map(({ level, color, bg }) => (
          <div key={level} className="card" style={{ background: bg, textAlign: "center" }}>
            <div style={{ fontSize: 28, fontWeight: 800, color }}>{levelCount(level)}</div>
            <div style={{ fontSize: 13, color, fontWeight: 600 }}>{level}</div>
          </div>
        ))}
      </div>

      {/* 경보 카드 목록 */}
      <div style={{ marginBottom: 32 }}>
        <div className="section-title">
          경보 목록
          {currentProduct && (
            <span style={{ fontSize: 13, fontWeight: 400, color: "#888", marginLeft: 8 }}>
              — {currentProduct.title}
            </span>
          )}
        </div>
        {loading ? (
          <div style={{ color: "#999", fontSize: 14 }}>분석 중…</div>
        ) : alerts.length === 0 ? (
          <div className="card" style={{ color: "#888", fontSize: 14 }}>이상 패턴이 감지되지 않았습니다.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {alerts.map((a, i) => <AlertCard key={i} alert={a} />)}
          </div>
        )}
      </div>

      {/* 시계열 차트 */}
      <div className="grid-2">
        <div className="card">
          <div className="section-title">📈 월별 평균 평점 추이</div>
          <RatingTrendChart data={ratingTrend} />
        </div>
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <span className="section-title" style={{ margin: 0 }}>📉 속성별 부정 키워드 비율</span>
            <select id="attr-select" value={selectedAttr} onChange={(e) => setSelectedAttr(e.target.value)} style={{ ...selectStyle, width: "auto" }}>
              {meta.attributes.map((a) => <option key={a}>{a}</option>)}
            </select>
          </div>
          <KeywordTrendChart data={keywordTrend} attribute={selectedAttr} />
        </div>
      </div>
    </div>
  );
}

const labelStyle = { display: "block", fontSize: 12, color: "#666", marginBottom: 4, fontWeight: 600 };
const selectStyle = {
  padding: "7px 12px", borderRadius: 8, border: "1px solid #ddd",
  fontSize: 14, outline: "none", background: "#fff", cursor: "pointer",
};
