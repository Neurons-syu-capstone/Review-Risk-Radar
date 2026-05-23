# 감지된 이벤트를 위험도(위험/경고/양호)로 분류해 최종 경보(RiskAlert)로 변환한다.
from typing import List
from ..events.event_types import KeywordSpikeEvent, RatingDropEvent, RiskAlert
from ..detectors.keyword_detector import DANGER_THRESHOLD, WARNING_THRESHOLD
from ..detectors.rating_detector import DANGER_DROP, WARNING_DROP


def _keyword_level(delta_pct: float) -> str:
    """키워드 증가율로 위험도 레벨을 결정한다."""
    if delta_pct >= DANGER_THRESHOLD:
        return "위험"
    if delta_pct >= WARNING_THRESHOLD:
        return "경고"
    return "양호"


def _rating_level(delta: float) -> str:
    """평점 하락폭으로 위험도 레벨을 결정한다."""
    if delta >= DANGER_DROP:
        return "위험"
    if delta >= WARNING_DROP:
        return "경고"
    return "양호"


class AlertGenerator:
    def from_keyword_events(self, events: List[KeywordSpikeEvent]) -> List[RiskAlert]:
        """KeywordSpikeEvent 목록을 RiskAlert 목록으로 변환한다."""
        alerts = []
        for e in events:
            level = _keyword_level(e.delta_pct)
            alerts.append(
                RiskAlert(
                    brand=e.brand,
                    attribute=e.attribute,
                    level=level,
                    trigger="keyword_spike",
                    delta_pct=round(e.delta_pct * 100, 1),
                    description=(
                        f"'{e.top_keyword}' 관련 부정 언급 "
                        f"+{e.delta_pct * 100:.0f}% 증가 ({e.window})"
                    ),
                    evidence=e.evidence,
                    window=e.window,
                )
            )
        return alerts

    def from_rating_events(self, events: List[RatingDropEvent]) -> List[RiskAlert]:
        """RatingDropEvent 목록을 RiskAlert 목록으로 변환한다."""
        alerts = []
        for e in events:
            level = _rating_level(e.delta)
            alerts.append(
                RiskAlert(
                    brand=e.brand,
                    attribute="전체 평점",
                    level=level,
                    trigger="rating_drop",
                    # 평점 하락폭을 5점 만점 기준 비율로 환산해 delta_pct에 통일
                    delta_pct=round((e.delta / 5.0) * 100, 1),
                    description=(
                        f"평점 {e.previous_rating:.2f} → {e.current_rating:.2f} "
                        f"(▼{e.delta:.2f}점, {e.window})"
                    ),
                    evidence=[],
                    window=e.window,
                )
            )
        return alerts
