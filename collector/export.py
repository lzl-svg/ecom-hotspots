# -*- coding: utf-8 -*-
"""把数据库数据和 Git 中保留的历史快照导出成前端使用的 JSON。"""
import json
import subprocess
from datetime import datetime, timedelta, timezone

from config import EXPORT_DIR, MARKETS
from db import (
    categories_of_market,
    category_series,
    connect,
    daily_dates,
    keyword_seed_rows,
    keyword_heat_by_date,
    seed_keywords,
)
from translations import CAT_CN, KW_CN

CST = timezone(timedelta(hours=8))
HISTORY_DAYS = 30


def export_market(conn, market: str, dates: list[str]) -> dict:
    cats = categories_of_market(conn, market)
    level1 = [c for c in cats if c["parent_catid"] in (0, None)]
    by_parent = {}
    for c in cats:
        by_parent.setdefault(c["parent_catid"], []).append(c)

    today = dates[0] if dates else ""
    prev = dates[1] if len(dates) > 1 else ""
    asc = list(reversed(dates))

    # 种子词 -> 所属一级类目（用于热搜词按类目筛选）
    cats_by_id = {c["catid"]: c for c in cats}
    seed_roots = {}
    for c in cats:
        node = c
        seen = set()
        while node and node["parent_catid"] not in (0, None) and node["catid"] not in seen:
            seen.add(node["catid"])
            node = cats_by_id.get(node["parent_catid"])
        root = node["display_name"] if node else None
        if root:
            seed_roots.setdefault(c["display_name"], set()).add(root)

    kw_seeds = {}
    if today:
        for kw, seed in keyword_seed_rows(conn, market, today):
            kw_seeds.setdefault(kw, set()).add(seed)

    kw_prev = {
        k["keyword"]: k["heat"] for k in keyword_heat_by_date(conn, market, prev)
    } if prev else {}

    roots = []
    for c in sorted(level1, key=lambda x: x["catid"]):
        series_desc = category_series(conn, market, c["catid"], dates)
        subs = []
        for s in sorted(by_parent.get(c["catid"], []), key=lambda x: x["catid"]):
            s_series_desc = category_series(conn, market, s["catid"], dates)
            subs.append({
                "catid": s["catid"],
                "name": s["display_name"],
                "cn": CAT_CN.get(market, {}).get(s["display_name"], ""),
                "heat": round(s_series_desc[0], 3) if s_series_desc else 0,
                "delta": round(s_series_desc[0] - s_series_desc[1], 3) if len(s_series_desc) > 1 else 0,
                "dates": asc,
                "series": [round(v, 3) for v in reversed(s_series_desc)],
                "hot_keywords": seed_keywords(conn, market, today, s["display_name"]) if today else [],
            })
        roots.append({
            "catid": c["catid"],
            "name": c["display_name"],
            "cn": CAT_CN.get(market, {}).get(c["display_name"], ""),
            "heat": round(series_desc[0], 3) if series_desc else 0,
            "delta": round(series_desc[0] - series_desc[1], 3) if len(series_desc) > 1 else 0,
            "dates": asc,
            "series": [round(v, 3) for v in reversed(series_desc)],
            "hot_keywords": seed_keywords(conn, market, today, c["display_name"]) if today else [],
            "subs": subs,
        })
    roots.sort(key=lambda x: x["heat"], reverse=True)

    keywords = []
    for k in keyword_heat_by_date(conn, market, today, limit=100) if today else []:
        prev_h = kw_prev.get(k["keyword"], 0)
        cat_set = set()
        for s in kw_seeds.get(k["keyword"], set()):
            cat_set |= seed_roots.get(s, set())
        keywords.append({
            "keyword": k["keyword"],
            "cn": KW_CN.get(market, {}).get(k["keyword"], ""),
            "heat": k["heat"],
            "delta": round(k["heat"] - prev_h, 3),
            "cats": sorted(cat_set),
        })

    return {
        "market": market,
        "updated_at": datetime.now(CST).strftime("%Y-%m-%d %H:%M"),
        "dates": dates,
        "categories": roots,
        "keywords": keywords,
    }


def _read_json(text: str):
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def git_snapshots(market: str, limit: int = 80) -> list[dict]:
    """读取 Git 历史中的网页快照；失败时安全退化为仅使用当前数据。"""
    rel_path = f"web/data/{market}.json"
    try:
        log = subprocess.run(
            ["git", "log", f"--max-count={limit}", "--format=%H", "--", rel_path],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return []

    snapshots = []
    seen_dates = set()
    for sha in log.stdout.splitlines():
        try:
            shown = subprocess.run(
                ["git", "show", f"{sha}:{rel_path}"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except (OSError, subprocess.CalledProcessError):
            continue
        snapshot = _read_json(shown.stdout)
        if not snapshot or snapshot.get("market") != market:
            continue
        snapshot_dates = snapshot.get("dates") or []
        # 新提交优先；同一天多次采集只保留最新一份。
        fresh_dates = [d for d in snapshot_dates if d not in seen_dates]
        if fresh_dates:
            snapshots.append(snapshot)
            seen_dates.update(fresh_dates)
        if len(seen_dates) >= HISTORY_DAYS:
            break
    return snapshots


def _store_category(history: dict, category: dict):
    key = str(category.get("catid"))
    dates = category.get("dates") or []
    series = category.get("series") or []
    values = history.setdefault(key, {})
    for date, heat in zip(dates, series):
        values.setdefault(date, float(heat or 0))


def merge_git_history(current: dict, snapshots: list[dict]) -> dict:
    """把当前采集与旧 JSON 合并，并重新计算类目和关键词变化。"""
    all_snapshots = [current, *snapshots]
    all_dates = set()
    root_history = {}
    sub_history = {}
    keyword_history = {}

    for snapshot in all_snapshots:
        dates = snapshot.get("dates") or []
        all_dates.update(dates)
        latest_date = dates[0] if dates else ""
        for root in snapshot.get("categories") or []:
            _store_category(root_history, root)
            for sub in root.get("subs") or []:
                _store_category(sub_history, sub)
        if latest_date:
            for keyword in snapshot.get("keywords") or []:
                keyword_history.setdefault(keyword.get("keyword", ""), {}).setdefault(
                    latest_date, float(keyword.get("heat") or 0)
                )

    dates_desc = sorted(all_dates, reverse=True)[:HISTORY_DAYS]
    dates_asc = list(reversed(dates_desc))
    today = dates_desc[0] if dates_desc else ""
    previous = dates_desc[1] if len(dates_desc) > 1 else ""
    current["dates"] = dates_desc

    def apply(category: dict, history: dict):
        values = history.get(str(category.get("catid")), {})
        current_heat = float(values.get(today, category.get("heat") or 0))
        previous_heat = values.get(previous) if previous else None
        category["heat"] = round(current_heat, 3)
        category["delta"] = round(current_heat - previous_heat, 3) if previous_heat is not None else 0
        category["dates"] = dates_asc
        category["series"] = [round(float(values.get(d, 0)), 3) for d in dates_asc]

    for root in current.get("categories") or []:
        apply(root, root_history)
        for sub in root.get("subs") or []:
            apply(sub, sub_history)
    current["categories"].sort(key=lambda x: x["heat"], reverse=True)

    for keyword in current.get("keywords") or []:
        old_heat = keyword_history.get(keyword.get("keyword", ""), {}).get(previous, 0)
        keyword["delta"] = round(float(keyword.get("heat") or 0) - old_heat, 3)
    return current


def main():
    conn = connect()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    meta_markets = []
    for code, market_config in MARKETS.items():
        db_dates = daily_dates(conn, code, days=HISTORY_DAYS)
        data = export_market(conn, code, db_dates)
        data = merge_git_history(data, git_snapshots(code))
        path = EXPORT_DIR / f"{code}.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        meta_markets.append({
            "code": code,
            "name": market_config["name"],
            "label": market_config["label"],
            "currency": market_config["currency"],
            "updated_at": data["updated_at"],
            "n_categories": len(data["categories"]),
            "n_keywords": len(data["keywords"]),
            "history_days": len(data["dates"]),
        })
        print(
            f"[{code}] 导出 {path.name}: 类目 {len(data['categories'])} / "
            f"关键词 {len(data['keywords'])} / 历史 {len(data['dates'])} 天"
        )

    meta = {
        "site": "电商热点台",
        "updated_at": datetime.now(CST).strftime("%Y-%m-%d %H:%M"),
        "markets": meta_markets,
    }
    (EXPORT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    conn.close()
    print("导出完成。")


if __name__ == "__main__":
    main()
