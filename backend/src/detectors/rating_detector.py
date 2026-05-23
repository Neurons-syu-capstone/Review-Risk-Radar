# 현재 기간과 이전 기간의 평균 평점을 비교해 하락 이벤트를 감지한다.
import pandas as pd
from typing import List
from ..events.event_types import RatingDropEvent

# 68.6% 긍정 편향 데이터 특성상 소폭 하락도 유의미한 이상 신호로 해석
DANGER_DROP = 0.5   # 0.5점 이상 하락 → 위험
WARNING_DROP = 0.2  # 0.2점 이상 하락 → 경고


class RatingTrendDetector:
    def detect(
        self,
        current: pd.DataFrame,
        previous: pd.DataFrame,
        brand: str,
        window: str,
    ) -> List[RatingDropEvent]:
        """이전 윈도우 대비 평균 평점 하락 이벤트를 반환한다."""
        # 어느 한쪽 기간에 리뷰가 없으면 비교 불가
        if len(current) == 0 or len(previous) == 0:
            return []

        curr_avg = current["rating"].mean()
        prev_avg = previous["rating"].mean()
        delta = prev_avg - curr_avg  # 양수 = 하락, 음수 = 상승

        if delta < WARNING_DROP:
            return []

        return [
            RatingDropEvent(
                brand=brand,
                current_rating=round(curr_avg, 3),
                previous_rating=round(prev_avg, 3),
                delta=round(delta, 3),
                window=window,
            )
        ]
