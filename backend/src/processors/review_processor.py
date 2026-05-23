# 리뷰 DataFrame을 상품 단위 슬라이딩 윈도우로 잘라주는 전처리 모듈.
import pandas as pd
from typing import List, Tuple


class ReviewProcessor:
    """
    Amazon 리뷰 DataFrame을 받아 슬라이딩 윈도우로 분석 단위를 제공한다.

    필수 컬럼:
        - rating      (float) : 1.0 ~ 5.0
        - text        (str)   : 리뷰 본문
        - timestamp   (int)   : Unix 시각 (초)
        - parent_asin (str)   : 상품 ID  ← 컬럼명이 다르면 product_col 파라미터로 지정
    선택 컬럼:
        - title       (str)   : 상품명 (없으면 parent_asin 그대로 표시)
    """

    def __init__(self, df: pd.DataFrame, product_col: str = "parent_asin"):
        self.df = df.copy()
        self.product_col = product_col
        self._prepare()

    def _prepare(self):
        # timestamp(Unix 초) → datetime으로 변환해 내부 컬럼 _date에 보관
        self.df["_date"] = pd.to_datetime(self.df["timestamp"], unit="s")
        # 원본 product_col 이름에 상관없이 내부에서 _product로 통일
        self.df["_product"] = self.df[self.product_col]

    # ── 기본 조회 ──────────────────────────────────────────────

    def get_products(self) -> List[dict]:
        """상품 목록 반환. title 컬럼이 있으면 이름도 포함."""
        products = (
            self.df.groupby("_product")
            .agg(review_count=("rating", "count"))
            .reset_index()
            .rename(columns={"_product": "product_id"})
        )
        if "title" in self.df.columns:
            titles = self.df.drop_duplicates("_product")[["_product", "title"]]
            titles = titles.rename(columns={"_product": "product_id"})
            products = products.merge(titles, on="product_id", how="left")
        else:
            products["title"] = products["product_id"]

        return (
            products.sort_values("review_count", ascending=False)
            [["product_id", "title", "review_count"]]
            .to_dict("records")
        )

    def get_date_range(self) -> Tuple[str, str]:
        """전체 데이터의 최소·최대 날짜를 YYYY-MM-DD 문자열로 반환한다."""
        min_d = self.df["_date"].min().strftime("%Y-%m-%d")
        max_d = self.df["_date"].max().strftime("%Y-%m-%d")
        return min_d, max_d

    # ── 슬라이딩 윈도우 ────────────────────────────────────────

    def get_window(
        self, product_id: str, end_date: pd.Timestamp, window_days: int
    ) -> pd.DataFrame:
        """
        [end_date - window_days, end_date) 구간의 해당 상품 리뷰를 반환한다.

        RiskRadar.scan()에서 이 메서드를 두 번 호출해 current/previous 윈도우를 만든다:
            current  = get_window(id, reference_date, N)
            previous = get_window(id, reference_date - N일, N)
        """
        start = end_date - pd.Timedelta(days=window_days)
        mask = (
            (self.df["_product"] == product_id)
            & (self.df["_date"] >= start)
            & (self.df["_date"] < end_date)
        )
        return self.df[mask]

    # ── 시계열 집계 ────────────────────────────────────────────

    def get_rating_timeseries(self, product_id: str, freq: str = "ME") -> List[dict]:
        """월별 평균 평점 + 리뷰 수를 반환한다. 리뷰 없는 달은 제외한다."""
        df = self.df[self.df["_product"] == product_id].copy()
        ts = (
            df.set_index("_date")["rating"]
            .resample(freq)  # ME: Month End 기준 리샘플링
            .agg(avg_rating="mean", review_count="count")
            .reset_index()
        )
        # review_count=0인 달은 avg_rating이 NaN → JSON 직렬화 오류 방지를 위해 제거
        ts = ts[ts["review_count"] > 0]
        ts["date"] = ts["_date"].dt.strftime("%Y-%m")
        ts["avg_rating"] = ts["avg_rating"].round(3)
        return ts[["date", "avg_rating", "review_count"]].to_dict("records")

    def get_keyword_timeseries(
        self, product_id: str, attribute: str, keywords: List[str], freq: str = "ME"
    ) -> List[dict]:
        """월별 특정 속성 부정 키워드 언급 비율을 반환한다. 리뷰 없는 달은 제외한다."""
        df = self.df[self.df["_product"] == product_id].copy()
        pattern = "|".join(keywords)
        df["_match"] = df["text"].str.lower().fillna("").str.contains(pattern, regex=True)
        ts = (
            df.set_index("_date")["_match"]
            .resample(freq)
            .mean()  # True/False 평균 = 해당 월 리뷰 중 키워드 언급 비율
            .reset_index()
        )
        # 리뷰 없는 달은 mean()이 NaN → JSON 직렬화 오류 방지를 위해 제거
        ts = ts[ts["_match"].notna()]
        ts["date"] = ts["_date"].dt.strftime("%Y-%m")
        ts["neg_ratio"] = ts["_match"].round(4)
        return ts[["date", "neg_ratio"]].to_dict("records")
