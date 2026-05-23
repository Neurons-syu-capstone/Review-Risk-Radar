# 파이프라인 전체를 조율하는 오케스트레이터. 외부에서는 이 클래스만 사용한다.
import pandas as pd
from typing import List, Optional
from .processors.review_processor import ReviewProcessor
from .detectors.keyword_detector import KeywordSpikeDetector
from .detectors.rating_detector import RatingTrendDetector
from .alert.alert_generator import AlertGenerator
from .events.event_types import RiskAlert

# 경보 정렬 순서: 위험이 가장 위, 양호가 가장 아래
_LEVEL_ORDER = {"위험": 0, "경고": 1, "양호": 2}


class RiskRadar:
    """
    이벤트 기반 부정 리스크 감지 파이프라인.

    흐름:
        ReviewProcessor (슬라이딩 윈도우)
            → KeywordSpikeDetector  → KeywordSpikeEvent
            → RatingTrendDetector   → RatingDropEvent
            → AlertGenerator        → RiskAlert (위험/경고/양호)
    """

    def __init__(self, df: pd.DataFrame, product_col: str = "parent_asin"):
        self.processor = ReviewProcessor(df, product_col=product_col)
        self._keyword_detector = KeywordSpikeDetector()
        self._rating_detector = RatingTrendDetector()
        self._alert_gen = AlertGenerator()

    # ── 핵심: 기준 날짜 기준 스캔 ─────────────────────────────

    def scan(
        self,
        product_id: str,
        reference_date: Optional[str] = None,
        window_days: int = 90,
    ) -> List[RiskAlert]:
        """
        reference_date 시점 기준으로 최근 window_days 와 이전 window_days 를 비교해
        부정 리스크 경보를 반환한다.

        reference_date=None 이면 데이터 최신 시점을 사용한다.
        """
        ref = (
            pd.Timestamp(reference_date)
            if reference_date
            else self.processor.df["_date"].max()
        )

        # current:  [ref - N일, ref)
        # previous: [ref - 2N일, ref - N일)
        current = self.processor.get_window(product_id, ref, window_days)
        previous_end = ref - pd.Timedelta(days=window_days)
        previous = self.processor.get_window(product_id, previous_end, window_days)

        window_label = f"최근 {window_days}일"

        keyword_events = self._keyword_detector.detect(
            current, previous, product_id, window_label
        )
        rating_events = self._rating_detector.detect(
            current, previous, product_id, window_label
        )

        alerts = (
            self._alert_gen.from_keyword_events(keyword_events)
            + self._alert_gen.from_rating_events(rating_events)
        )

        alerts.sort(key=lambda a: _LEVEL_ORDER.get(a.level, 3))
        return alerts

    # ── 시계열 조회 (차트용) ──────────────────────────────────

    def rating_trend(self, product_id: str) -> List[dict]:
        """월별 평균 평점 시계열 (프론트 차트용)."""
        return self.processor.get_rating_timeseries(product_id)

    def keyword_trend(self, product_id: str, attribute: str) -> List[dict]:
        """월별 속성별 부정 키워드 언급 비율 시계열 (프론트 차트용)."""
        from .detectors.keyword_detector import ATTRIBUTE_KEYWORDS
        keywords = ATTRIBUTE_KEYWORDS.get(attribute, [])
        return self.processor.get_keyword_timeseries(product_id, attribute, keywords)
