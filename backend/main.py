# FastAPI 앱 진입점. 데이터 로딩, 컬럼 정규화, API 엔드포인트 4개를 정의한다.
import os
from contextlib import asynccontextmanager
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.risk_radar import RiskRadar
from src.detectors.keyword_detector import ATTRIBUTE_KEYWORDS

# 환경변수 DATA_PATH로 데이터 파일 경로를 외부 주입 가능
# 예: DATA_PATH=../shared/shoes_reviews.json uvicorn main:app --reload
DATA_PATH = os.getenv("DATA_PATH", "data/shoes_sample.json")

radar: Optional[RiskRadar] = None


def _load_data() -> pd.DataFrame:
    """parquet / CSV / JSON 자동 감지 로딩. 파일이 없으면 목업 데이터로 대체."""
    if os.path.exists(DATA_PATH):
        if DATA_PATH.endswith(".parquet"):
            df = pd.read_parquet(DATA_PATH)
        elif DATA_PATH.endswith(".json"):
            # convert_dates=False: pandas가 review_date를 자동으로 datetime 변환하면
            # 이후 _normalize_columns에서 to_numeric이 실패하므로 수동 변환
            df = pd.read_json(DATA_PATH, convert_dates=False)
        else:
            df = pd.read_csv(DATA_PATH)
        return _normalize_columns(df)

    print("⚠️  실제 데이터 없음 → 목업 데이터로 실행합니다.")
    return _mock_data()


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """실제 데이터의 컬럼명을 파이프라인 표준 컬럼명으로 변환한다."""
    # review_date (datetime 문자열) → timestamp (Unix 초 정수)
    # datetime 문자열 파싱을 먼저 시도하고, 실패 시 밀리초 정수로 재시도
    if "review_date" in df.columns and "timestamp" not in df.columns:
        df = df.rename(columns={"review_date": "timestamp"})
        parsed = pd.to_datetime(df["timestamp"], errors="coerce")
        if parsed.notna().any():
            df["timestamp"] = parsed
        else:
            df["timestamp"] = pd.to_datetime(
                pd.to_numeric(df["timestamp"], errors="coerce"), unit="ms", errors="coerce"
            )
        df = df.dropna(subset=["timestamp"])
        df["timestamp"] = df["timestamp"].astype("int64") // 10 ** 9

    # product_title → title
    # 데이터에 review title과 product_title이 공존하므로 review title은 제거
    if "product_title" in df.columns:
        df = df.drop(columns=["title"], errors="ignore")
        df = df.rename(columns={"product_title": "title"})

    return df


def _mock_data() -> pd.DataFrame:
    """실제 데이터 없을 때 사용하는 개발용 목업 데이터.
    2021년 이후 부정 키워드와 평점 하락을 의도적으로 삽입해 경보 동작을 검증한다."""
    import numpy as np

    rng = np.random.default_rng(42)

    products = [
        ("B001NIK001", "Nike Air Max 270"),
        ("B001NIK002", "Nike Revolution 6"),
        ("B001ADI001", "Adidas Ultraboost 22"),
        ("B001ADI002", "Adidas Grand Court"),
        ("B001NB001",  "New Balance 574"),
        ("B001NB002",  "New Balance Fresh Foam 1080"),
        ("B001CRO001", "Crocs Classic Clog"),
        ("B001CRO002", "Crocs LiteRide"),
        ("B001SKE001", "Skechers Go Walk 6"),
        ("B001SKE002", "Skechers Max Cushioning"),
    ]

    rows = []
    neg_keywords = ["too narrow", "size issue", "fell apart", "broke",
                    "uncomfortable", "returned", "tight", "blister"]

    for parent_asin, title in products:
        n = rng.integers(800, 1200)
        timestamps = pd.date_range("2018-01-01", "2023-12-31", periods=n)
        is_post_2021 = timestamps >= pd.Timestamp("2021-01-01")

        ratings = rng.choice([1, 2, 3, 4, 5], size=n,
                              p=[0.08, 0.07, 0.10, 0.25, 0.50])
        # 2021년 이후 평점을 의도적으로 낮춰 경보 시나리오 재현
        ratings = np.where(
            is_post_2021,
            np.clip(ratings - rng.integers(0, 2, n), 1, 5),
            ratings
        )

        def make_text(i):
            # 2021년 이후 리뷰의 20%에 부정 키워드 삽입
            if is_post_2021[i] and rng.random() < 0.20:
                kw = rng.choice(neg_keywords)
                return f"Really disappointed. The shoe is {kw}. Would not buy again."
            if ratings[i] >= 4:
                return "Great shoes, very comfortable and good support."
            return "Decent shoes but not perfect."

        rows.extend(
            {
                "parent_asin": parent_asin,
                "title": title,
                "rating": float(ratings[i]),
                "text": make_text(i),
                "timestamp": int(timestamps[i].timestamp()),
            }
            for i in range(n)
        )

    return pd.DataFrame(rows)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 데이터 로딩과 RiskRadar 초기화를 수행한다."""
    global radar
    df = _load_data()
    radar = RiskRadar(df)
    products = radar.processor.get_products()
    print(f"✅ RiskRadar 초기화 완료 | 상품 수: {len(products)}")
    yield


app = FastAPI(title="Review Risk Radar API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/meta")
def get_meta():
    """상품 목록, 데이터 날짜 범위, 감지 속성 목록을 반환한다."""
    min_d, max_d = radar.processor.get_date_range()
    return {
        "products": radar.processor.get_products(),
        "date_range": {"min": min_d, "max": max_d},
        "attributes": list(ATTRIBUTE_KEYWORDS.keys()),
    }


@app.get("/api/alerts/{product_id}")
def get_alerts(
    product_id: str,
    reference_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    window_days: int = Query(90, ge=30, le=365),
):
    """기준 날짜 기준으로 부정 리스크 경보를 반환한다.
    reference_date 미지정 시 데이터 최신 시점을 기준으로 사용한다."""
    alerts = radar.scan(product_id, reference_date=reference_date, window_days=window_days)
    return {
        "product_id": product_id,
        "reference_date": reference_date,
        "window_days": window_days,
        "alerts": [vars(a) for a in alerts],
    }


@app.get("/api/trend/rating/{product_id}")
def get_rating_trend(product_id: str):
    """월별 평균 평점 시계열을 반환한다."""
    return {"product_id": product_id, "trend": radar.rating_trend(product_id)}


@app.get("/api/trend/keyword/{product_id}/{attribute}")
def get_keyword_trend(product_id: str, attribute: str):
    """월별 속성별 부정 키워드 언급 비율 시계열을 반환한다."""
    if attribute not in ATTRIBUTE_KEYWORDS:
        raise HTTPException(status_code=404, detail=f"Unknown attribute: {attribute}")
    return {
        "product_id": product_id,
        "attribute": attribute,
        "trend": radar.keyword_trend(product_id, attribute),
    }
