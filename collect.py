"""서울 열린데이터광장 '서울시 부동산 실거래가 정보' API에서 데이터를 받아 SQLite에 저장한다.

사용법:
    python collect.py                 # 최근 3년 (올해 포함)
    python collect.py 2025 2026       # 원하는 접수연도만
"""
import os
import sys
import time
from datetime import date

import requests
from dotenv import load_dotenv

import db

load_dotenv()

BASE_URL = "http://openapi.seoul.go.kr:8088/{key}/json/tbLnOpendataRtmsV/{start}/{end}/{year}/{gu}"
PAGE_SIZE = 1000  # API 1회 최대 건수

GU_CODES = {
    "11110": "종로구", "11140": "중구", "11170": "용산구", "11200": "성동구",
    "11215": "광진구", "11230": "동대문구", "11260": "중랑구", "11290": "성북구",
    "11305": "강북구", "11320": "도봉구", "11350": "노원구", "11380": "은평구",
    "11410": "서대문구", "11440": "마포구", "11470": "양천구", "11500": "강서구",
    "11530": "구로구", "11545": "금천구", "11560": "영등포구", "11590": "동작구",
    "11620": "관악구", "11650": "서초구", "11680": "강남구", "11710": "송파구",
    "11740": "강동구",
}


def to_int(value, default=None):
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return default


def clean(row: dict) -> dict | None:
    """API 한 건을 DB 저장용으로 변환. 쓸 수 없는 데이터면 None."""
    price = to_int(row.get("THING_AMT"))
    area = float(row.get("ARCH_AREA") or 0)
    day = str(row.get("CTRT_DAY") or "")
    if not price or area <= 0 or len(day) != 8:
        return None
    build_year = to_int(row.get("ARCH_YR"))
    return {
        "rcpt_year": to_int(row.get("RCPT_YR")),
        "gu_code": row.get("CGG_CD", ""),
        "gu_name": row.get("CGG_NM", ""),
        "dong_name": row.get("STDG_NM", ""),
        "lot_main": row.get("MNO", ""),
        "lot_sub": row.get("SNO", ""),
        "bldg_name": (row.get("BLDG_NM") or "").strip(),
        "bldg_type": row.get("BLDG_USG", ""),
        "contract_date": f"{day[:4]}-{day[4:6]}-{day[6:]}",
        "price_manwon": price,
        "area_m2": area,
        "floor": to_int(row.get("FLR")),
        "build_year": build_year if build_year else None,  # 0 = 정보 없음
        "deal_type": row.get("DCLR_SE", ""),
        "cancel_date": (row.get("RTRCN_DAY") or "").strip(),
    }


def fetch_page(key: str, year: int, gu: str, start: int, end: int) -> tuple[int, list[dict]]:
    """한 페이지 요청. (전체건수, 행 목록) 반환."""
    url = BASE_URL.format(key=key, start=start, end=end, year=year, gu=gu)
    for attempt in range(3):
        try:
            res = requests.get(url, timeout=30)
            res.raise_for_status()
            data = res.json()
            break
        except (requests.RequestException, ValueError) as e:
            if attempt == 2:
                raise
            print(f"    재시도 ({e})")
            time.sleep(2)

    body = data.get("tbLnOpendataRtmsV")
    if body is None:  # 오류 응답은 최상위에 RESULT만 온다
        result = data.get("RESULT", {})
        if result.get("CODE") == "INFO-200":  # 해당 데이터 없음
            return 0, []
        raise RuntimeError(f"API 오류: {result.get('CODE')} {result.get('MESSAGE')}")
    return body.get("list_total_count", 0), body.get("row", [])


def collect(key: str, years: list[int]) -> None:
    conn = db.connect()
    page_size = 5 if key == "sample" else PAGE_SIZE  # 'sample' 키는 5건까지만 허용
    grand_total = 0

    for year in years:
        print(f"\n=== {year}년 접수분 ===")
        for gu_code, gu_name in GU_CODES.items():
            start, saved, total = 1, 0, None
            while True:
                end = start + page_size - 1
                total, rows = fetch_page(key, year, gu_code, start, end)
                cleaned = [c for c in (clean(r) for r in rows) if c]
                saved += db.save_trades(conn, cleaned)
                if key == "sample" or end >= total or not rows:
                    break
                start = end + 1
                time.sleep(0.1)  # 서버 부담 줄이기
            grand_total += saved
            print(f"  {gu_name:<5} 전체 {total:>6,}건 → 저장 {saved:>6,}건")

    count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    conn.close()
    print(f"\n완료! 이번에 {grand_total:,}건 처리, DB 총 {count:,}건 ({db.DB_PATH})")


if __name__ == "__main__":
    api_key = os.getenv("SEOUL_API_KEY", "").strip()
    if not api_key:
        sys.exit("❌ .env 파일에 SEOUL_API_KEY를 넣어주세요. (테스트만 하려면 SEOUL_API_KEY=sample)")

    this_year = date.today().year
    target_years = [int(y) for y in sys.argv[1:]] or [this_year - 2, this_year - 1, this_year]
    collect(api_key, target_years)
