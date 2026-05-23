const BASE = "/api";

export async function fetchMeta() {
  const res = await fetch(`${BASE}/meta`);
  if (!res.ok) throw new Error("meta fetch failed");
  return res.json();
}

export async function fetchAlerts(productId, referenceDate, windowDays = 90) {
  const params = new URLSearchParams({ window_days: windowDays });
  if (referenceDate) params.set("reference_date", referenceDate);
  const res = await fetch(`${BASE}/alerts/${encodeURIComponent(productId)}?${params}`);
  if (!res.ok) throw new Error("alerts fetch failed");
  return res.json();
}

export async function fetchRatingTrend(productId) {
  const res = await fetch(`${BASE}/trend/rating/${encodeURIComponent(productId)}`);
  if (!res.ok) throw new Error("rating trend fetch failed");
  return res.json();
}

export async function fetchKeywordTrend(productId, attribute) {
  const res = await fetch(
    `${BASE}/trend/keyword/${encodeURIComponent(productId)}/${encodeURIComponent(attribute)}`
  );
  if (!res.ok) throw new Error("keyword trend fetch failed");
  return res.json();
}
