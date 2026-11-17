# 🏙️ 서울 집값 지도

서울시 공공 실거래가 데이터를 받아 SQLite에 저장하고, 서울 지도 위에 **자치구별 집값을 색으로** 보여주는 개인용 로컬 웹앱입니다.

- 건물 용도(아파트·연립다세대·오피스텔·단독다가구), 면적, 계약 기간으로 필터
- 평균/중앙값 평당가, 평균 거래금액, 거래건수 기준으로 지도 색칠
- 지도에서 구를 클릭하면 월별 추이, 동별 평당가, 거래 목록 표시
- 배경지도: 브이월드(국토교통부) — 키가 없으면 OpenStreetMap

## 기술 스택
Python · SQLite · pandas · Streamlit · Folium(Leaflet)

## 실행 방법

### 1. 준비물
- Python 3.11 이상
- [서울 열린데이터광장](https://data.seoul.go.kr) 인증키 (무료)
- (선택) [브이월드](https://www.vworld.kr) 인증키 (무료, 배경지도용)

### 2. 설치
```bash
git clone <이 저장소 주소>
cd real-estate-analysis-platform
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. API 키 넣기
```bash
cp .env.example .env
```
`.env` 파일을 열어 `=` 뒤에 키를 붙여넣습니다.
```
SEOUL_API_KEY=발급받은_서울_키
VWORLD_API_KEY=발급받은_브이월드_키
```
> `.env`는 `.gitignore`에 등록돼 있어 깃허브에 올라가지 않습니다.

### 4. 데이터 수집
```bash
python collect.py              # 최근 3년 (몇 분 소요)
python collect.py 2026         # 특정 연도만 (최신 데이터 갱신할 때)
```
`data/realestate.db` 파일이 생성됩니다. 여러 번 실행해도 중복 저장되지 않습니다.

### 5. 앱 실행
```bash
streamlit run app.py
```
브라우저에서 http://localhost:8501 이 열립니다.

## 폴더 구조
```
collect.py     데이터 수집 → SQLite 저장
db.py          DB 테이블 정의·저장 함수
app.py         지도 화면 (Streamlit)
geo/           서울 자치구 경계 GeoJSON
data/          SQLite DB (자동 생성, 깃허브 제외)
docs/PLAN.md   기획서
```

## 데이터 출처
- 실거래가: [서울 열린데이터광장 — 서울시 부동산 실거래가 정보 (OA-21275)](https://data.seoul.go.kr/dataList/OA-21275/S/1/datasetView.do)
- 배경지도: [브이월드](https://www.vworld.kr) (국토교통부)
- 자치구 경계: [southkorea/seoul-maps](https://github.com/southkorea/seoul-maps) (통계청 2013 경계)

> 평당가 = 거래금액 ÷ 건물면적(㎡) × 3.3058. 계약 해제된 거래는 제외합니다.
