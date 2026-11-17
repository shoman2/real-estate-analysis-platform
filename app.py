"""서울시 집값 지도 — Streamlit 앱.

실행:  streamlit run app.py
"""
import copy
import json
import os
import sqlite3
from pathlib import Path

import branca.colormap as cm
import folium
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from streamlit_folium import st_folium

import db

load_dotenv(override=True)  # 앱 실행 중 .env를 고쳐도 새로고침하면 반영
VWORLD_KEY = os.getenv("VWORLD_API_KEY", "").strip()
GEOJSON_PATH = Path(__file__).parent / "geo" / "seoul_gu.geojson"
PYEONG = 3.3058  # 1평 = 3.3058㎡

st.set_page_config(page_title="서울 집값 지도", page_icon="🏙️", layout="wide")


# ───────────────────────── 데이터 ─────────────────────────
@st.cache_data
def load_trades(_mtime: float) -> pd.DataFrame:
    """취소되지 않은 전체 거래를 읽는다. (_mtime: DB가 바뀌면 캐시 갱신용)"""
    with sqlite3.connect(db.DB_PATH) as conn:
        df = pd.read_sql_query(
            """SELECT gu_name, dong_name, bldg_name, bldg_type, contract_date,
                      price_manwon, area_m2, floor, build_year, deal_type
               FROM trades WHERE cancel_date = ''""",
            conn,
        )
    df["month"] = df["contract_date"].str[:7]
    df["pyeong_price"] = df["price_manwon"] * PYEONG / df["area_m2"]  # 평당가(만원)
    return df


@st.cache_data
def load_geojson() -> dict:
    return json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))


def fmt_money(manwon: float) -> str:
    """만원 단위 숫자를 '12억 3,000만' 형식으로."""
    if pd.isna(manwon):
        return "-"
    manwon = int(round(manwon))
    eok, man = divmod(manwon, 10000)
    if eok and man:
        return f"{eok}억 {man:,}만"
    return f"{eok}억" if eok else f"{man:,}만"


def centroid(geometry: dict) -> tuple[float, float]:
    """폴리곤 외곽선 좌표의 평균 (구 이름 라벨 위치용)."""
    rings = geometry["coordinates"]
    if geometry["type"] == "MultiPolygon":
        rings = max(rings, key=lambda p: len(p[0]))
    pts = rings[0]
    return sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)


# ───────────────────────── 시작 체크 ─────────────────────────
if not db.DB_PATH.exists():
    st.title("🏙️ 서울 집값 지도")
    st.warning("아직 데이터가 없습니다. 터미널에서 먼저 `python collect.py` 를 실행해 주세요.")
    st.stop()

df_all = load_trades(db.DB_PATH.stat().st_mtime)
if df_all.empty:
    st.warning("DB에 거래 데이터가 없습니다. `python collect.py` 를 실행해 주세요.")
    st.stop()


# ───────────────────────── 사이드바 필터 ─────────────────────────
st.sidebar.header("🔎 필터")

types = sorted(df_all["bldg_type"].dropna().unique())
bldg_type = st.sidebar.selectbox(
    "건물 용도", types, index=types.index("아파트") if "아파트" in types else 0
)

area_options = {
    "전체": (0, 10_000),
    "소형 (60㎡ 이하)": (0, 60),
    "중형 (60~85㎡)": (60, 85),
    "대형 (85㎡ 초과)": (85, 10_000),
}
area_label = st.sidebar.selectbox("면적", list(area_options))

months = sorted(df_all["month"].unique())
default_start = months[max(0, len(months) - 12)]
month_from, month_to = st.sidebar.select_slider(
    "계약 기간", options=months, value=(default_start, months[-1])
)

metric_options = {
    "평균 평당가": ("pyeong_price", "mean"),
    "중앙값 평당가": ("pyeong_price", "median"),
    "평균 거래금액": ("price_manwon", "mean"),
    "거래건수": ("price_manwon", "count"),
}
metric = st.sidebar.selectbox("지도 색칠 기준", list(metric_options))

basemaps = {"브이월드 회색": "white", "브이월드 기본": "Base",
            "브이월드 야간": "midnight", "브이월드 위성": "Satellite"}
if VWORLD_KEY:
    basemap = st.sidebar.selectbox("배경지도", list(basemaps))
else:
    basemap = None
    st.sidebar.caption("ℹ️ .env에 VWORLD_API_KEY를 넣으면 브이월드 배경지도를 쓸 수 있습니다.")

last_date = df_all["contract_date"].max()
st.sidebar.divider()
st.sidebar.caption(f"DB 거래 {len(df_all):,}건 · 최근 계약일 {last_date}")
st.sidebar.caption("데이터: 서울 열린데이터광장 · 배경지도: 브이월드")

# 필터 적용
lo, hi = area_options[area_label]
df = df_all[
    (df_all["bldg_type"] == bldg_type)
    & (df_all["month"].between(month_from, month_to))
    & (df_all["area_m2"] > lo) & (df_all["area_m2"] <= hi)
]

# 자치구별 집계
col, how = metric_options[metric]
by_gu = df.groupby("gu_name").agg(
    value=(col, how),
    avg_pyeong=("pyeong_price", "mean"),
    median_price=("price_manwon", "median"),
    count=("price_manwon", "count"),
)


def fmt_metric(v: float) -> str:
    return f"{int(v):,}건" if metric == "거래건수" else fmt_money(v)


# ───────────────────────── 지도 ─────────────────────────
st.title("🏙️ 서울 집값 지도")
st.caption(f"{bldg_type} · {area_label} · {month_from} ~ {month_to} · 거래 {len(df):,}건")

geo = copy.deepcopy(load_geojson())
if by_gu.empty:
    colormap = None
else:
    vmin, vmax = float(by_gu["value"].min()), float(by_gu["value"].max())
    if vmin == vmax:
        vmax = vmin + 1
    colormap = cm.LinearColormap(
        cm.linear.YlOrRd_09.colors, vmin=vmin, vmax=vmax,
        tick_labels=[round(vmin), round((vmin + vmax) / 2), round(vmax)],
    )
    colormap.caption = f"{metric} ({'건' if metric == '거래건수' else '만원'})"

for f in geo["features"]:
    name = f["properties"]["name"]
    row = by_gu.loc[name] if name in by_gu.index else None
    f["properties"]["value"] = None if row is None else float(row["value"])
    f["properties"]["v_label"] = "-" if row is None else fmt_metric(row["value"])
    f["properties"]["c_label"] = "0건" if row is None else f"{int(row['count']):,}건"

m = folium.Map(
    location=[37.5665, 126.978], zoom_start=11, min_zoom=10, max_zoom=18,
    tiles=None, max_bounds=True,
    min_lat=37.35, max_lat=37.75, min_lon=126.70, max_lon=127.25,
)
if basemap:
    layer = basemaps[basemap]
    ext = "jpeg" if layer == "Satellite" else "png"
    folium.TileLayer(
        tiles=f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/{layer}/{{z}}/{{y}}/{{x}}.{ext}",
        attr="© VWorld (국토교통부)", name=basemap,
    ).add_to(m)
else:
    folium.TileLayer("OpenStreetMap").add_to(m)

folium.GeoJson(
    geo,
    style_function=lambda f: {
        "fillColor": colormap(f["properties"]["value"])
        if colormap and f["properties"]["value"] is not None else "#cccccc",
        "color": "#555555", "weight": 1, "fillOpacity": 0.65,
    },
    highlight_function=lambda f: {"weight": 3, "color": "#000000", "fillOpacity": 0.8},
    tooltip=folium.GeoJsonTooltip(
        fields=["name", "v_label", "c_label"], aliases=["자치구", metric, "거래건수"]
    ),
).add_to(m)

for f in geo["features"]:  # 구 이름 라벨
    lat, lon = centroid(f["geometry"])
    folium.Marker(
        [lat, lon], interactive=False,  # 라벨이 클릭을 가로채지 않도록
        icon=folium.DivIcon(html=f'<div style="pointer-events:none;font-size:11px;font-weight:700;color:#222;'
                                 f'white-space:nowrap;transform:translate(-50%,-50%);'
                                 f'text-shadow:0 0 3px #fff,0 0 3px #fff">{f["properties"]["name"]}</div>'),
    ).add_to(m)

if colormap:
    colormap.add_to(m)

map_col, rank_col = st.columns([3, 1.3])
with map_col:
    out = st_folium(m, height=600, use_container_width=True,
                    returned_objects=["last_active_drawing"], key="map")

with rank_col:
    st.subheader("자치구 순위")
    rank = by_gu.sort_values("value", ascending=False).reset_index()
    rank.index = rank.index + 1
    st.dataframe(
        pd.DataFrame({
            "자치구": rank["gu_name"],
            metric: rank["value"].map(fmt_metric),
            "거래": rank["count"].map(lambda c: f"{int(c):,}"),
        }, index=rank.index),
        height=560, use_container_width=True,
    )

# ───────────────────────── 선택한 구 상세 ─────────────────────────
gu_list = sorted(f["properties"]["name"] for f in geo["features"])
clicked = ((out or {}).get("last_active_drawing") or {}).get("properties", {}).get("name")
if clicked and clicked != st.session_state.get("last_clicked"):
    st.session_state["last_clicked"] = clicked
    st.session_state["gu"] = clicked
if "gu" not in st.session_state:
    st.session_state["gu"] = rank["gu_name"].iloc[0] if not rank.empty else "강남구"

st.divider()
gu = st.selectbox("📍 자치구 선택 (지도에서 클릭해도 바뀝니다)", gu_list, key="gu")
gu_df = df[df["gu_name"] == gu]

st.subheader(f"{gu} 상세")
if gu_df.empty:
    st.info("선택한 조건에 해당하는 거래가 없습니다.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("거래건수", f"{len(gu_df):,}건")
c2.metric("평균 평당가", fmt_money(gu_df["pyeong_price"].mean()))
c3.metric("거래금액 중앙값", fmt_money(gu_df["price_manwon"].median()))
seoul_avg = df["pyeong_price"].mean()
c4.metric("서울 평균 대비", f"{gu_df['pyeong_price'].mean() / seoul_avg * 100:.0f}%")

trend_col, dong_col = st.columns([2, 1])
with trend_col:
    st.markdown("**월별 평균 평당가 (만원)**")
    trend = pd.DataFrame({
        gu: gu_df.groupby("month")["pyeong_price"].mean(),
        "서울 전체": df.groupby("month")["pyeong_price"].mean(),
    }).round(0)
    st.line_chart(trend, height=300)
with dong_col:
    st.markdown("**동별 평균 평당가**")
    dong = (gu_df.groupby("dong_name")
            .agg(평당가=("pyeong_price", "mean"), 거래=("price_manwon", "count"))
            .sort_values("평당가", ascending=False))
    dong["평당가"] = dong["평당가"].map(fmt_money)
    st.dataframe(dong, height=300, use_container_width=True)

st.markdown("**거래 목록** (최신순)")
table = gu_df.sort_values("contract_date", ascending=False).head(500)
st.dataframe(
    pd.DataFrame({
        "계약일": table["contract_date"],
        "동": table["dong_name"],
        "건물명": table["bldg_name"],
        "거래금액": table["price_manwon"].map(fmt_money),
        "면적(㎡)": table["area_m2"].round(1),
        "평당가": table["pyeong_price"].map(fmt_money),
        "층": table["floor"],
        "건축연도": table["build_year"],
        "거래유형": table["deal_type"],
    }),
    hide_index=True, use_container_width=True,
)
