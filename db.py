"""SQLite 데이터베이스 관련 함수 모음."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "realestate.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    rcpt_year     INTEGER,  -- 접수연도
    gu_code       TEXT,     -- 자치구 코드
    gu_name       TEXT,     -- 자치구 이름
    dong_name     TEXT,     -- 법정동
    lot_main      TEXT,     -- 본번
    lot_sub       TEXT,     -- 부번
    bldg_name     TEXT,     -- 건물명
    bldg_type     TEXT,     -- 아파트 / 연립다세대 / 오피스텔 / 단독다가구
    contract_date TEXT,     -- 계약일 YYYY-MM-DD
    price_manwon  INTEGER,  -- 거래금액 (만원)
    area_m2       REAL,     -- 건물면적 (㎡)
    floor         INTEGER,  -- 층
    build_year    INTEGER,  -- 건축연도
    deal_type     TEXT,     -- 중개거래 / 직거래
    cancel_date   TEXT,     -- 계약 해제일 (값이 있으면 취소된 거래)
    UNIQUE (gu_code, dong_name, lot_main, lot_sub, bldg_name,
            contract_date, price_manwon, area_m2, floor)
);
CREATE INDEX IF NOT EXISTS idx_trades_filter ON trades (bldg_type, contract_date);
CREATE INDEX IF NOT EXISTS idx_trades_gu ON trades (gu_name);
"""

COLUMNS = [
    "rcpt_year", "gu_code", "gu_name", "dong_name", "lot_main", "lot_sub",
    "bldg_name", "bldg_type", "contract_date", "price_manwon", "area_m2",
    "floor", "build_year", "deal_type", "cancel_date",
]


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def save_trades(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """거래 목록을 저장한다. 이미 있는 거래는 최신 값(해제 여부 등)으로 덮어쓴다."""
    if not rows:
        return 0
    placeholders = ", ".join("?" for _ in COLUMNS)
    sql = f"INSERT OR REPLACE INTO trades ({', '.join(COLUMNS)}) VALUES ({placeholders})"
    conn.executemany(sql, [tuple(r[c] for c in COLUMNS) for r in rows])
    conn.commit()
    return len(rows)
