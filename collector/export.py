# -*- coding: utf-8 -*-
"""把数据库历史导出成前端使用的 JSON。"""
import json
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

    kw_today = {k["keyword"]: k["heat"] for k in keyword_heat_by_date(conn, market, today)} if today else {}
    kw_prev = {k["keyword"]: k["heat"] for k in keyword_heat_by_date(conn, market, prev)} if prev else {}

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


def main():
    conn = connect()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    meta_markets = []
    for code, m in MARKETS.items():
        dates = daily_dates(conn, code, days=30)
        data = export_market(conn, code, dates)
        path = EXPORT_DIR / f"{code}.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        meta_markets.append({
            "code": code,
            "name": m["name"],
            "label": m["label"],
            "currency": m["currency"],
            "updated_at": data["updated_at"],
            "n_categories": len(data["categories"]),
            "n_keywords": len(data["keywords"]),
            "history_days": len(data["dates"]),
        })
        print(f"[{code}] 导出 {path.name}: 类目 {len(data['categories'])} / 关键词 {len(data['keywords'])} / 历史 {len(dates)} 天")

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
