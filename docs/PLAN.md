# 서울시 집값 지도 플랫폼 — 기획서 (MVP)

> 작성일: 2026-11-17 · 대상: 개인 사용 (로컬 PC에서 실행) · 최종 목표: GitHub 공개 저장소에 코드 공유

---

## 1. 한 줄 요약

**서울시 공공 실거래가 데이터를 받아와 SQLite에 저장하고, 서울 지도 위에 자치구별 평균 집값을 색깔로 보여주는 로컬 웹앱.**
Python 하나로 전부 만든다. 실행은 `streamlit run app.py` 한 줄.

## 2. 목표와 범위

| 구분 | 포함 (MVP) | 제외 (나중에) |
|---|---|---|
| 지역 | 서울시 25개 자치구 | 경기도, 전국 |
| 데이터 | 매매 실거래가 (아파트·연립다세대·오피스텔·단독다가구) | 전월세, 공시지가, 가격지수 |
| 지도 | 자치구 단위 색칠 지도 (Choropleth) | 단지별 핀, 법정동 단위 |
| 기능 | 기간/건물용도 필터, 구 클릭 시 상세 통계·거래목록·월별 추이 | 로그인, 알림, 예측 모델 |
| 사용자 | 나 혼자, 내 컴퓨터 (localhost) | 외부 배포, 다중 사용자 |

## 3. 무료 공공 데이터 소스

### ⭐ 추천: 서울 열린데이터광장 — 서울시 부동산 실거래가 정보 (MVP에서 이것만 사용)

| 항목 | 내용 |
|---|---|
| 데이터셋 | [OA-21275 서울시 부동산 실거래가 정보](https://data.seoul.go.kr/dataList/OA-21275/S/1/datasetView.do) |
| 제공 | 서울특별시 도시공간본부 토지관리과 |
| 갱신 | **매일** |
| 비용/키 | 무료. data.seoul.go.kr 회원가입 → 마이페이지 → 인증키 신청 (즉시 발급) |
| 형식 | JSON (키 하나로 서울 전체 조회, 1회 최대 1,000건) |
| 서비스명 | `tbLnOpendataRtmsV` |

**호출 예시** (실제 호출로 확인 완료)
```
http://openapi.seoul.go.kr:8088/{인증키}/json/tbLnOpendataRtmsV/{시작}/{끝}/{접수연도}/{자치구코드}
예) .../json/tbLnOpendataRtmsV/1/1000/2025/11680   → 2025년 강남구 거래 1~1000번째
```
- 테스트는 인증키 대신 `sample`을 넣으면 됨 (최대 5건만 반환)

**주요 필드**
| 필드 | 의미 | 예시 |
|---|---|---|
| `RCPT_YR` | 접수연도 | 2026 |
| `CGG_CD` / `CGG_NM` | 자치구 코드 / 이름 | 11440 / 마포구 |
| `STDG_NM` | 법정동 | 노고산동 |
| `BLDG_NM` | 건물명 | 빌리브디에이블 |
| `CTRT_DAY` | 계약일 | 20261113 |
| `THING_AMT` | 거래금액 (**만원**) | 90000 (= 9억) |
| `ARCH_AREA` | 건물면적 (㎡) | 44.36 |
| `FLR` | 층 | 21 |
| `ARCH_YR` | 건축연도 | 2020 |
| `BLDG_USG` | 건물용도 | 아파트 / 연립다세대 / 오피스텔 / 단독다가구 |
| `RTRCN_DAY` | 계약 해제일 (값이 있으면 **취소된 거래 → 제외**) | |

**왜 이걸 추천하나**: 국토부 API는 구별·월별로 수백 번 나눠 호출해야 하고 응답이 XML인데, 이 API는 서울 전체를 JSON으로 한 번에 페이지만 넘기며 받을 수 있어서 가장 쉽다.

### 그 외 참고 소스 (확장 시)

| 소스 | 내용 | 비고 |
|---|---|---|
| [공공데이터포털 — 국토교통부 아파트 매매 실거래가](https://www.data.go.kr) | 전국 실거래가 API | 무료 키 필요, XML, 구×월 단위로 호출. 전국 확장 시 사용 |
| [국토부 실거래가 공개시스템](https://rt.molit.go.kr) | CSV 직접 다운로드 | 키 불필요. 수동 다운로드용 |
| [한국부동산원 R-ONE](https://www.reb.or.kr/r-one) | 주간/월간 매매가격지수 | 무료 키. "추이" 지표 보강용 |
| 서울 열린데이터광장 — 전월세가 정보 | 서울 전월세 실거래 | 같은 키로 사용 가능. 2단계에서 추가 |
| 카카오 로컬 API / VWorld | 주소 → 좌표 변환 | 단지별 핀 찍을 때 필요 (3단계) |

### 지도 경계 데이터 (자치구 모양)

- [southkorea/seoul-maps](https://github.com/southkorea/seoul-maps) — `kostat/2013/json/seoul_municipalities_geo_simple.json` (25개 구, 약 57KB, 무료)
- ⚠️ 이 파일의 구 코드(예: 강남구 `11230`)는 실거래가 API 코드(`11680`)와 **다르다** → **구 이름(`name` ↔ `CGG_NM`)으로 연결**한다.

## 4. 기술 스택 — "Python 하나로 끝내기"

| 역할 | 도구 | 선택 이유 |
|---|---|---|
| 언어 | Python 3.11+ | 데이터 수집·저장·화면을 한 언어로 |
| 데이터 수집 | `requests` | API 호출 몇 줄이면 끝 |
| DB | **SQLite** (Python 내장 `sqlite3`) | 설치 불필요, 파일 하나(`data/realestate.db`), 수십만 건도 빠름 |
| 데이터 가공 | `pandas` | SQL 결과를 표로 바로 다룸 |
| 웹 화면 | **Streamlit** | HTML/JS 몰라도 파이썬만으로 웹 화면. 필터·표·차트 기본 제공 |
| 지도 | **Folium** + `streamlit-folium` | Leaflet(오픈소스 지도) 기반, 색칠 지도 한 함수로 가능, 지도 API 키 불필요 |
| 차트 | Streamlit 내장 `st.line_chart` | 월별 추이 |

> 프론트엔드(React 등)·별도 백엔드 서버(FastAPI 등)는 **만들지 않는다.** Streamlit이 둘 다 대신한다.

## 5. 전체 구조

```
[서울 열린데이터광장 API]
          │  ① collect.py  (수동 실행: python collect.py)
          ▼
   [SQLite: data/realestate.db]   ← 거래 원본 저장, 중복 제거
          │  ② app.py가 SQL로 집계 (구별 평균 ㎡당 가격 등)
          ▼
 [Streamlit 화면 + Folium 지도]  → 브라우저 http://localhost:8501
```

### 폴더 구조
```
real-estate-analysis-platform/
├── README.md              # 설치·실행 방법
├── requirements.txt       # 필요한 패키지 목록
├── .env.example           # SEOUL_API_KEY=여기에_키 (예시 파일, 깃허브에 올림)
├── .env                   # 실제 키 (깃허브에 올리지 않음!)
├── .gitignore             # .env, data/*.db, __pycache__ 제외
├── collect.py             # 데이터 수집 → SQLite 저장
├── db.py                  # 테이블 생성·조회 함수
├── app.py                 # Streamlit 지도 앱
├── geo/
│   └── seoul_gu.geojson   # 자치구 경계
├── data/
│   └── realestate.db      # 수집 후 자동 생성
└── docs/
    └── PLAN.md            # 이 문서
```

## 6. DB 설계 (SQLite)

테이블 하나로 시작한다.

```sql
CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    gu_code     TEXT,     -- CGG_CD
    gu_name     TEXT,     -- CGG_NM
    dong_name   TEXT,     -- STDG_NM
    bldg_name   TEXT,     -- BLDG_NM
    bldg_type   TEXT,     -- BLDG_USG (아파트/연립다세대/오피스텔/단독다가구)
    contract_date TEXT,   -- CTRT_DAY → 'YYYY-MM-DD'
    price_manwon  INTEGER,-- THING_AMT (만원)
    area_m2     REAL,     -- ARCH_AREA
    floor       INTEGER,  -- FLR
    build_year  INTEGER,  -- ARCH_YR
    -- 같은 거래가 다시 수집돼도 중복 저장되지 않도록
    UNIQUE (gu_code, dong_name, bldg_name, contract_date, price_manwon, area_m2, floor)
);
CREATE INDEX IF NOT EXISTS idx_trades_gu_date ON trades (gu_name, contract_date);
```

- 저장 시 `INSERT OR IGNORE` → 여러 번 돌려도 안전
- 해제된 거래(`RTRCN_DAY` 값 있음), 면적 0인 거래는 저장 단계에서 제외

## 7. 핵심 로직

### ① 수집 (`collect.py`)
1. `.env`에서 인증키 읽기
2. 연도(예: 2024, 2025, 2026) × 25개 구 반복
3. 각 조합마다 1~1000, 1001~2000 … 페이지를 넘기며 `list_total_count`까지 받기
4. 정제 후 SQLite에 `INSERT OR IGNORE`
5. 진행 상황 출력 ("강남구 2025: 6,282건 저장")

> 예상 규모: 서울 1년 약 10만~15만 건 → 최근 3년 수집에 수 분 내외.

### ② 집계 (화면에서 쓰는 SQL)
```sql
-- 자치구별 지표 (선택한 기간·용도 기준)
SELECT gu_name,
       COUNT(*)                                  AS 거래건수,
       ROUND(AVG(price_manwon * 1.0 / area_m2))  AS 평균_㎡당_만원,
       ROUND(AVG(price_manwon * 3.3058 / area_m2)) AS 평균_평당_만원
FROM trades
WHERE bldg_type = ? AND contract_date BETWEEN ? AND ?
GROUP BY gu_name;
```
- 집값 비교 기준은 **평당가(만원/3.3㎡)** — 면적이 달라도 공정하게 비교 가능

### ③ 화면 (`app.py`)
```
┌──────────────┬──────────────────────────────────────────┐
│ [사이드바]    │  서울 지도 (자치구 색칠: 진할수록 비쌈)       │
│ 건물용도 ▼    │                                          │
│ 기간 슬라이더  │   마우스 올리면: 구 이름 / 평당가 / 거래건수  │
│ 지표 선택 ▼   │                                          │
│ (평당가/건수)  ├──────────────────────────────────────────┤
│              │ 선택한 구 상세: 요약 숫자 3개                │
│ [데이터 기준일]│  · 월별 평당가 추이 (꺾은선)                 │
│              │  · 최근 거래 목록 (표, 정렬 가능)             │
└──────────────┴──────────────────────────────────────────┘
```
- 지도 클릭 → `streamlit-folium`이 클릭한 구 이름을 돌려줌 → 아래 상세 영역 갱신

## 8. 개발 일정 (Claude와 함께 진행 기준)

| 단계 | 작업 | 결과물 | 예상 |
|---|---|---|---|
| 0 | 사전 준비: Python 설치 확인, 서울 열린데이터광장 키 발급, GitHub 계정 | 키 1개 | 30분 |
| 1 | 프로젝트 뼈대: 폴더, `requirements.txt`, `.gitignore`, `.env`, `git init` | 빈 저장소 | 15분 |
| 2 | `db.py` + `collect.py` → 데이터 수집 | `realestate.db` | 1시간 |
| 3 | `app.py` 지도 + 필터 | 색칠된 서울 지도 | 1~2시간 |
| 4 | 구 클릭 상세(추이 차트·거래표) | 완성된 MVP | 1시간 |
| 5 | `README.md` 작성 → GitHub 업로드 | 공개 저장소 URL | 30분 |

**MVP 완료 기준**
- [ ] `python collect.py` 실행 시 최근 3년 서울 거래가 DB에 저장된다
- [ ] `streamlit run app.py` 실행 시 브라우저에 서울 지도가 뜬다
- [ ] 용도·기간을 바꾸면 지도 색이 바뀐다
- [ ] 구를 클릭하면 추이 차트와 거래 목록이 나온다
- [ ] GitHub에 코드가 올라가 있고, README대로 따라 하면 남도 실행할 수 있다

## 9. GitHub 업로드 시 주의사항

- **API 키는 절대 올리지 않는다.** 키는 `.env`에만 두고 `.gitignore`에 `.env` 등록. 대신 `.env.example`을 올려 "여기에 본인 키를 넣으세요" 안내
- **DB 파일(`data/*.db`)도 올리지 않는다.** 용량이 크고, 받는 사람이 `collect.py`로 직접 만들면 됨
- 경계 GeoJSON(57KB)은 저장소에 포함 (출처 표기)
- README에 데이터 출처 명시: "서울 열린데이터광장 (공공누리)"

## 10. 확장 아이디어 (MVP 이후)

1. **법정동 단위 지도** — 구보다 촘촘하게 (동 경계 GeoJSON 추가)
2. **단지별 핀** — 카카오 로컬 API로 주소→좌표 변환, 아파트 단지를 점으로 표시
3. **전월세 데이터 추가** — 전세가율(전세가/매매가) 지도
4. **가격지수(R-ONE)** 연동 — 상승/하락률 지도
5. **자동 업데이트** — 매일 아침 `collect.py` 자동 실행 (macOS `launchd`/cron)

## 11. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| API 일일 호출 제한 / 일시 오류 | 호출 사이 짧은 대기, 실패 시 재시도, 중복 저장 방지로 재실행 안전 |
| 구 코드 불일치 (경계파일 ↔ API) | 구 이름으로 연결 |
| 소형 오피스텔 등으로 평균 왜곡 | 용도 필터 기본값 "아파트", 중앙값 옵션 제공 |
| 해제(취소) 거래 포함 | `RTRCN_DAY` 있는 행 제외 |
| 개발 지식 부족 | 단계별로 Claude가 코드 작성·실행·검증, 사용자는 결과 화면 확인 |
