# Review Risk Radar

> **부정 리스크 감지 및 조기 경보** 모듈  
> 리뷰 기반 상품 분석 인사이트 대시보드의 4개 핵심 기능 중 하나

---

## 한 줄 요약

기준 날짜를 기준으로 **최근 N일 vs 이전 N일**을 비교해, 부정 키워드가 급증하거나 평점이 하락한 **상품(parent_asin)/속성**을 자동으로 감지하고 **위험 / 경고 / 양호** 세 단계로 경보를 출력한다.

---

## 왜 이벤트 기반 아키텍처인가

리뷰 데이터는 2018~2023 정적 데이터지만, 구조는 실제 서비스와 동일하게 설계했다.


| 실제 서비스          | 이 프로젝트            |
| --------------- | ----------------- |
| 새 리뷰가 실시간으로 들어옴 | 기준 날짜를 바꿔가며 시뮬레이션 |
| 파이프라인이 자동 실행    | API 요청 시 파이프라인 실행 |
| 경보 즉시 알림        | API 응답으로 경보 반환    |


즉, **알고리즘 자체는 동일**하고 데이터 입력 방식만 다르다.  
기준 날짜를 2021년 초로 설정하면 "그 시점에 모니터링했다면 언제 경보가 울렸을지" 재현할 수 있다.

---

## 데이터 플로우

```
[Amazon Reviews DataFrame]
          │
          ▼
  ReviewProcessor        ← 전체 DataFrame에서 필요한 조각을 잘라줌
          │
          ├──────────────────────────┐
          ▼                          ▼
KeywordSpikeDetector        RatingTrendDetector
 속성별 부정 키워드 빈도 비교    기간별 평균 평점 비교
          │                          │
          └──────────┬───────────────┘
                     ▼
             AlertGenerator      ← 변화량이 임계값 초과 시 위험도 분류
                     │
                     ▼
              RiskAlert[]        ← {level, attribute, delta_pct, description, evidence}
                     │
                     ▼
           FastAPI 엔드포인트     ← React 프론트엔드에 JSON 응답
```

---

## 디렉토리 구조

```
Review-Risk-Radar/
│
├── backend/
│   ├── main.py                         # FastAPI 앱 진입점
│   ├── requirements.txt
│   ├── data/                           # 데이터 파일 (git 제외, 별도 공유)
│   │   └── shoes_sample.json
│   └── src/
│       ├── events/
│       │   └── event_types.py          # 데이터 모델 (dataclass)
│       ├── detectors/
│       │   ├── keyword_detector.py     # 부정 키워드 급증 감지
│       │   └── rating_detector.py      # 평점 하락 감지
│       ├── processors/
│       │   └── review_processor.py     # 슬라이딩 윈도우, 시계열 집계
│       ├── alert/
│       │   └── alert_generator.py      # 이벤트 → 위험도 분류
│       └── risk_radar.py               # 파이프라인 오케스트레이터
│
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── package.json
    └── src/
        ├── App.jsx
        ├── index.css
        ├── api/
        │   └── riskApi.js              # API 호출 함수 모음
        ├── components/
        │   ├── AlertCard.jsx           # 경보 카드 (위험도 색상 + 증거 리뷰 토글)
        │   └── TrendChart.jsx          # 평점 / 키워드 시계열 차트 (Recharts)
        └── pages/
            └── RiskRadarPage.jsx       # 메인 페이지 (상품 선택, 날짜 선택, 경보 목록)
```

---

## 각 파일 역할

### `src/events/event_types.py`

파이프라인에서 주고받는 데이터 구조를 정의한다.


| 타입                  | 설명                                |
| ------------------- | --------------------------------- |
| `KeywordSpikeEvent` | 특정 속성의 부정 키워드 비율이 이전 기간 대비 급증한 사건 |
| `RatingDropEvent`   | 평균 평점이 이전 기간 대비 하락한 사건            |
| `RiskAlert`         | 최종 출력. 위험도 레벨 + 설명 + 증거 리뷰 포함     |


---

### `src/processors/review_processor.py`

DataFrame을 받아 **상품(parent_asin) 단위** 슬라이딩 윈도우를 제공한다.

**필수 컬럼**


| 컬럼            | 타입    | 설명                                      |
| ------------- | ----- | --------------------------------------- |
| `rating`      | float | 별점 (1.0 ~ 5.0)                          |
| `text`        | str   | 리뷰 본문                                   |
| `timestamp`   | int   | Unix 시각 (초 단위)                          |
| `parent_asin` | str   | 상품 ID ← 컬럼명이 다르면 `product_col` 파라미터로 지정 |


**선택 컬럼**


| 컬럼      | 타입  | 설명                                    |
| ------- | --- | ------------------------------------- |
| `title` | str | 상품명 (없으면 `parent_asin` 값을 그대로 UI에 표시) |


---

### `src/detectors/keyword_detector.py`

리뷰 본문(`text`)에서 직접 부정 키워드를 찾아 **속성별 언급 비율**을 계산하고, 이전 윈도우 대비 급증 여부를 감지한다.

딥러닝 모델 없이 **규칙 기반(Rule-based) 문자열 매칭**으로 동작한다. `str.contains(pattern)`으로 키워드가 리뷰 텍스트에 포함되어 있는지 확인하고, 해당 월 전체 리뷰 중 언급 비율을 계산한다. "coming apart"처럼 두 단어로 된 키워드도 연속된 문자열로 정확히 매칭한다.

**속성별 키워드 매핑**

```
사이즈   → narrow, tight, too small, size issue, run small ...
내구성   → broke, fell apart, sole, glue, worn out ...
착용감   → uncomfortable, painful, blister, rub ...
디자인   → ugly, cheap, faded, flimsy ...
반품     → return, refund, exchange ...
```

**위험도 기준 (delta_pct = 이전 대비 증가율)**


| 레벨    | 기준          |
| ----- | ----------- |
| 위험 🔴 | +30% 이상     |
| 경고 🟡 | +15% ~ +30% |
| 양호 🟢 | +15% 미만     |


---

### `src/detectors/rating_detector.py`

이전 윈도우 평균 평점과 현재 윈도우 평균 평점을 비교한다.


| 레벨    | 기준            |
| ----- | ------------- |
| 위험 🔴 | 0.5점 이상 하락    |
| 경고 🟡 | 0.2 ~ 0.5점 하락 |
| 양호 🟢 | 0.2점 미만 하락    |


---

### `src/risk_radar.py`

모든 컴포넌트를 연결하는 오케스트레이터. 외부에서는 이것만 사용하면 된다.

```python
from src.risk_radar import RiskRadar

radar = RiskRadar(df)  # product_col 기본값: "parent_asin"

# 상품 목록 조회 (product_id, title, review_count)
products = radar.processor.get_products()

# 기준 날짜 기준 경보 조회
alerts = radar.scan("B001NIK001", reference_date="2021-06-01", window_days=90)

# 월별 평점 시계열
trend = radar.rating_trend("B001NIK001")

# 월별 속성별 부정 키워드 비율
kw_trend = radar.keyword_trend("B001NIK001", "사이즈")
```

---

## API 엔드포인트


| 메서드 | 경로                                            | 설명                                                  |
| --- | --------------------------------------------- | --------------------------------------------------- |
| GET | `/api/meta`                                   | 상품 목록 (product_id·title·review_count), 날짜 범위, 속성 목록 |
| GET | `/api/alerts/{product_id}`                    | 경보 조회. `reference_date`, `window_days` 쿼리 파라미터      |
| GET | `/api/trend/rating/{product_id}`              | 월별 평균 평점 시계열                                        |
| GET | `/api/trend/keyword/{product_id}/{attribute}` | 월별 속성별 부정 키워드 비율 시계열                                |


---

## 실행 방법

### 백엔드

```bash
# 프로젝트 루트에서
source .venv/bin/activate
pip install -r backend/requirements.txt

cd backend
uvicorn main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### 프론트엔드

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

> 백엔드를 먼저 실행해야 프론트엔드가 데이터를 받아올 수 있다.

---

## 데이터 연동 방법

데이터 파일은 용량 문제로 git에 포함되지 않는다. 팀 공유 채널을 통해 전달받은 후 `backend/data/`에 위치시킨다.

```
backend/data/shoes_sample.json   ← 여기에 배치
```

`main.py`는 로딩 시 아래 컬럼명을 자동으로 변환한다.

| 원본 컬럼        | 변환 후       | 처리                          |
| ------------ | ---------- | --------------------------- |
| `review_date` | `timestamp` | datetime 문자열 → Unix 초 (int) |
| `product_title` | `title`   | 리뷰 제목(`title`) 컬럼 대체        |

**필수 컬럼**: `rating`, `text`, `review_date`, `parent_asin`  
**선택 컬럼**: `product_title` (없으면 `parent_asin` 값이 UI에 표시됨)

다른 경로를 사용하려면 환경변수로 지정한다.

```bash
DATA_PATH=../shared/shoes_reviews.json uvicorn main:app --reload
```

파일이 없으면 목업 데이터(10개 상품, 약 1만 건)로 자동 대체된다.

---

## 기술 스택


| 구분    | 기술                                  |
| ----- | ----------------------------------- |
| 백엔드   | Python 3.9+, FastAPI, Pandas, NumPy |
| 프론트엔드 | React 18, Vite, Recharts            |
| 데이터   | Amazon Reviews (Shoes, 2018-2023)   |


---

## 개발 현황

### ✅ 완료

- 이벤트 기반 파이프라인 전체 구조 (Processor → Detector → AlertGenerator → RiskAlert)
- 부정 키워드 급증 감지 (`KeywordSpikeDetector`)
- 평점 하락 감지 (`RatingTrendDetector`)
- 위험 / 경고 / 양호 분류 (`AlertGenerator`)
- FastAPI 엔드포인트 4개
- React 프론트엔드 (상품 선택, 기준 날짜 선택, 경보 카드, 시계열 차트)
- 실데이터 연동 (`shoes_sample.json`, 약 28,000건)
- 실데이터 기준 프론트 ↔ 백엔드 통합 테스트 완료

---

### 🔲 남은 작업


| 항목             | 설명                                              | 우선순위 |
| -------------- | ----------------------------------------------- | ---- |
| 속성 이름 통일       | 한국어(사이즈/내구성 등) → 팀 스코어보드 영어(size/durability 등)와 맞추기 | 높음   |
| 키워드 튜닝         | 실데이터 기반으로 `ATTRIBUTE_KEYWORDS` 보완                | 중간   |
| 위험도 임계값 조정     | 실데이터 분포 확인 후 30% / 15% 기준 재검토                  | 중간   |
| 전체 대시보드 통합     | 다른 기능(스코어보드, AI처방전 등)과 탭으로 묶기                  | 팀 협의 |
