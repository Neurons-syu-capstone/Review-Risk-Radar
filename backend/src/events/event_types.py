# 파이프라인 내부에서 주고받는 이벤트 및 최종 경보 데이터 구조를 정의한다.
from dataclasses import dataclass, field
from typing import List


@dataclass
class KeywordSpikeEvent:
    """부정 키워드 비율이 이전 기간 대비 급증했을 때 생성되는 이벤트."""
    brand: str
    attribute: str       # 감지된 속성 (사이즈, 내구성 등)
    top_keyword: str     # 해당 속성에서 가장 많이 언급된 부정 키워드
    current_freq: float  # 현재 윈도우 부정 키워드 언급 비율 (0.0 ~ 1.0)
    previous_freq: float # 이전 윈도우 부정 키워드 언급 비율
    delta_pct: float     # (current - previous) / previous — 증가율
    window: str          # 윈도우 레이블 (예: "최근 90일")
    evidence: List[str] = field(default_factory=list)  # 실제 리뷰 원문 (최대 3건)


@dataclass
class RatingDropEvent:
    """평균 평점이 이전 기간 대비 하락했을 때 생성되는 이벤트."""
    brand: str
    current_rating: float
    previous_rating: float
    delta: float  # previous - current (양수 = 하락, 음수 = 상승)
    window: str


@dataclass
class RiskAlert:
    """최종 출력 단위. AlertGenerator가 이벤트를 변환해 생성한다."""
    brand: str
    attribute: str   # 이상이 감지된 속성 또는 "전체 평점"
    level: str       # "위험" | "경고" | "양호"
    trigger: str     # "keyword_spike" | "rating_drop"
    delta_pct: float # 변화율 % (프론트 표시용)
    description: str # 한 줄 요약 메시지
    evidence: List[str]  # 근거 리뷰 원문 (keyword_spike만 제공)
    window: str
