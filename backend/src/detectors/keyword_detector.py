import pandas as pd
from typing import Dict, List
from ..events.event_types import KeywordSpikeEvent

# 리뷰 텍스트에서 속성별 부정 키워드 언급 비율을 계산하고 이전 기간 대비 급증을 감지한다.

# 신발 카테고리 속성별 부정 키워드 매핑 (휴리스틱 기반 — 도메인 상식으로 직접 작성)
ATTRIBUTE_KEYWORDS: Dict[str, List[str]] = {
    "사이즈": ["narrow", "tight", "too small", "too big", "sizing", "size issue",
               "run small", "run big", "wide", "length", "half size"],
    "내구성": ["broke", "broken", "fell apart", "falling apart", "sole", "glue",
               "worn out", "separated", "coming apart", "peeling", "durability"],
    "착용감": ["uncomfortable", "painful", "pain", "blister", "blisters",
               "rub", "rubbing", "hurt", "sore", "no support", "no cushion"],
    "디자인": ["ugly", "cheap", "faded", "color", "looks cheap", "cheap looking",
               "flimsy", "poor quality"],
    "반품":   ["return", "returned", "refund", "exchange", "sent back", "returning"],
}

# 위험도 분류 임계값 (delta_pct 기준)
# 68.6% 긍정 편향 데이터 특성과 파일럿 실험을 통해 도출한 값
DANGER_THRESHOLD = 0.30   # 이전 대비 30% 이상 증가 → 위험
WARNING_THRESHOLD = 0.15  # 이전 대비 15% 이상 증가 → 경고


class KeywordSpikeDetector:
    def __init__(self, attribute_keywords: Dict[str, List[str]] = None):
        # 외부에서 커스텀 키워드 맵을 주입할 수 있도록 설계
        self.attribute_keywords = attribute_keywords or ATTRIBUTE_KEYWORDS

    def _keyword_freq(self, reviews: pd.DataFrame) -> Dict[str, float]:
        """리뷰 텍스트에서 속성별 부정 키워드 언급 비율(0.0~1.0)을 계산한다."""
        if len(reviews) == 0:
            return {attr: 0.0 for attr in self.attribute_keywords}

        text = reviews["text"].str.lower().fillna("")
        result = {}
        for attr, keywords in self.attribute_keywords.items():
            pattern = "|".join(keywords)
            result[attr] = text.str.contains(pattern, regex=True).mean()
        return result

    def detect(
        self,
        current: pd.DataFrame,
        previous: pd.DataFrame,
        brand: str,
        window: str,
    ) -> List[KeywordSpikeEvent]:
        """현재 윈도우와 이전 윈도우를 비교해 급증한 속성의 이벤트를 반환한다."""
        curr_freq = self._keyword_freq(current)
        prev_freq = self._keyword_freq(previous)

        events = []
        for attr in self.attribute_keywords:
            prev = prev_freq[attr]
            curr = curr_freq[attr]

            if prev == 0:
                # 이전 기간 언급이 없을 때 비율 계산이 불가능하므로 별도 처리:
                # 현재 비율이 3% 미만이면 노이즈로 간주해 무시
                if curr < 0.03:
                    continue
                delta_pct = 1.0  # 100% 증가로 처리
            else:
                delta_pct = (curr - prev) / prev

            if delta_pct < WARNING_THRESHOLD:
                continue

            # 경보 근거로 사용할 실제 리뷰 원문 최대 3건 추출
            text_lower = current["text"].str.lower().fillna("")
            pattern = "|".join(self.attribute_keywords[attr])
            matched = current[text_lower.str.contains(pattern, regex=True)]
            evidence = matched["text"].head(3).tolist()

            # 해당 속성에서 가장 많이 언급된 단일 키워드
            kw_counts = {
                kw: text_lower.str.contains(kw).sum()
                for kw in self.attribute_keywords[attr]
            }
            top_keyword = max(kw_counts, key=kw_counts.get)

            events.append(
                KeywordSpikeEvent(
                    brand=brand,
                    attribute=attr,
                    top_keyword=top_keyword,
                    current_freq=curr,
                    previous_freq=prev,
                    delta_pct=delta_pct,
                    window=window,
                    evidence=evidence,
                )
            )

        return events
