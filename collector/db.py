# -*- coding: utf-8 -*-
"""SQLite 存储层。"""
import sqlite3
from pathlib import Path

from config import DB_PATH


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS markets(
            code TEXT PRIMARY KEY,
            name TEXT,
            domain TEXT,
            currency TEXT
        );
        CREATE TABLE IF NOT EXISTS categories(
            market TEXT NOT NULL,
            catid INTEGER NOT NULL,
            parent_catid INTEGER,
            name TEXT,
            display_name TEXT,
            level INTEGER,
            path TEXT,
            PRIMARY KEY(market, catid)
        );
        CREATE TABLE IF NOT EXISTS keyword_daily(
            market TEXT NOT NULL,
            date TEXT NOT NULL,
            seed TEXT NOT NULL,
            keyword TEXT NOT NULL,
            position INTEGER,
            PRIMARY KEY(market, date, seed, keyword)
        );
        CREATE INDEX IF NOT EXISTS idx_kwd ON keyword_daily(market, date, keyword);
        CREATE TABLE IF NOT EXISTS category_daily(
            market TEXT NOT NULL,
            date TEXT NOT NULL,
            catid INTEGER NOT NULL,
            heat REAL,
            rank INTEGER,
            n_keywords INTEGER,
            PRIMARY KEY(market, date, catid)
        );
        CREATE INDEX IF NOT EXISTS idx_catd ON category_daily(market, catid, date);
        """
    )
    conn.commit()


def upsert_markets(conn: sqlite3.Connection, markets: dict):
    for code, m in markets.items():
        conn.execute(
            "INSERT OR REPLACE INTO markets(code, name, domain, currency) VALUES(?,?,?,?)",
            (code, m["name"], m["domain"], m["currency"]),
        )
    conn.commit()


def upsert_categories(conn: sqlite3.Connection, market: str, cats: list[dict]):
    conn.executemany(
        """INSERT OR REPLACE INTO categories(market, catid, parent_catid, name, display_name, level, path)
           VALUES(?,?,?,?,?,?,?)""",
        [
            (market, c["catid"], c["parent_catid"], c["name"], c["display_name"], c["level"], c["path"])
            for c in cats
        ],
    )
    conn.commit()


def save_keyword_rows(conn: sqlite3.Connection, market: str, date: str, rows: list[tuple]):
    conn.executemany(
        """INSERT OR REPLACE INTO keyword_daily(market, date, seed, keyword, position)
           VALUES(?,?,?,?,?)""",
        [(market, date, seed, keyword, pos) for seed, keyword, pos in rows],
    )
    conn.commit()


def save_category_rows(conn: sqlite3.Connection, market: str, date: str, rows: list[tuple]):
    conn.executemany(
        """INSERT OR REPLACE INTO category_daily(market, date, catid, heat, rank, n_keywords)
           VALUES(?,?,?,?,?,?)""",
        [(market, date, catid, heat, rank, n_kw) for catid, heat, rank, n_kw in rows],
    )
    conn.commit()


def categories_of_market(conn: sqlite3.Connection, market: str) -> list[dict]:
    cur = conn.execute(
        "SELECT catid, parent_catid, name, display_name, level, path FROM categories WHERE market=?",
        (market,),
    )
    return [
        {"catid": r[0], "parent_catid": r[1], "name": r[2], "display_name": r[3], "level": r[4], "path": r[5]}
        for r in cur.fetchall()
    ]


def daily_dates(conn: sqlite3.Connection, market: str, days: int = 30) -> list[str]:
    cur = conn.execute(
        """SELECT DISTINCT date FROM category_daily WHERE market=?
           ORDER BY date DESC LIMIT ?""",
        (market, days),
    )
    return [r[0] for r in cur.fetchall()]


def category_series(conn: sqlite3.Connection, market: str, catid: int, dates: list[str]) -> list[float]:
    if not dates:
        return []
    q = ",".join("?" * len(dates))
    cur = conn.execute(
        f"SELECT date, heat FROM category_daily WHERE market=? AND catid=? AND date IN ({q})",
        (market, catid, *dates),
    )
    m = dict(cur.fetchall())
    return [m.get(d) or 0.0 for d in dates]


def keyword_heat_by_date(conn: sqlite3.Connection, market: str, date: str, limit: int = 120) -> list[dict]:
    """某天全部关键词热度（按 1/(position+5) 求和）。"""
    cur = conn.execute(
        "SELECT keyword, SUM(1.0/(position+5)) AS heat FROM keyword_daily WHERE market=? AND date=? "
        "GROUP BY keyword ORDER BY heat DESC LIMIT ?",
        (market, date, limit),
    )
    return [{"keyword": r[0], "heat": round(r[1], 3)} for r in cur.fetchall()]


def seed_keywords(conn: sqlite3.Connection, market: str, date: str, seed: str, limit: int = 8) -> list[dict]:
    cur = conn.execute(
        "SELECT keyword, SUM(1.0/(position+5)) AS heat FROM keyword_daily WHERE market=? AND date=? AND seed=? "
        "GROUP BY keyword ORDER BY heat DESC LIMIT ?",
        (market, date, seed, limit),
    )
    return [{"keyword": r[0], "heat": round(r[1], 3)} for r in cur.fetchall()]
