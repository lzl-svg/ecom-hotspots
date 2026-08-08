# -*- coding: utf-8 -*-
"""每日采集主流程：类目树 + 搜索联想词 -> 热度 -> 入库。"""
from datetime import datetime, timedelta, timezone

from config import FIXED_SEEDS, MARKETS, SUBS_PER_CAT, TOP_LEVEL2
from db import (
    categories_of_market,
    connect,
    init_db,
    save_category_rows,
    save_keyword_rows,
    upsert_categories,
    upsert_markets,
)
from shopee_api import ShopeeAPI, fetch_hints_for_seed, parse_tree

CST = timezone(timedelta(hours=8))


def contribution(position: int) -> float:
    return 1.0 / (position + 5)


def run_market(conn, market: str, date: str, domain: str):
    api = ShopeeAPI(market, domain)

    # 1) 类目树
    tree = api.category_tree()
    cats = parse_tree(tree, market)
    upsert_categories(conn, market, cats)
    print(f"[{market}] 类目数: {len(cats)}")
    api.polite_sleep()

    level1 = [c for c in cats if c["parent_catid"] in (0, None)]
    level2_by_parent = {}
    for c in cats:
        if c["level"] == 2:
            level2_by_parent.setdefault(c["parent_catid"], []).append(c)

    # 2) 一级类目种子
    seeds = [(c["catid"], c["display_name"]) for c in level1]
    seed_rows = []  # (seed, keyword, position)
    cat_heat = {}  # catid -> heat

    def collect(seed_list):
        for catid, seed in seed_list:
            hints = fetch_hints_for_seed(api, seed)
            for h in hints:
                seed_rows.append((seed, h["keyword"], h["position"]))
                if catid is not None:
                    cat_heat[catid] = cat_heat.get(catid, 0.0) + contribution(h["position"])
            api.polite_sleep()

    collect(seeds)

    # 3) 热度前 N 个一级类目，下钻二级类目种子
    ranked = sorted(cat_heat.items(), key=lambda x: x[1], reverse=True)
    top_catids = [cid for cid, _ in ranked[:TOP_LEVEL2]]
    level2_seeds = []
    for cid in top_catids:
        for c in level2_by_parent.get(cid, [])[:SUBS_PER_CAT]:
            level2_seeds.append((c["catid"], c["display_name"]))
    if level2_seeds:
        collect(level2_seeds)

    # 4) 固定热门种子词（不计入类目热度，只贡献关键词榜）
    fixed_rows = []
    for seed in FIXED_SEEDS.get(market, []):
        hints = fetch_hints_for_seed(api, seed)
        for h in hints:
            fixed_rows.append((seed, h["keyword"], h["position"]))
        api.polite_sleep()

    save_keyword_rows(conn, market, date, seed_rows + fixed_rows)

    # 5) 类目热度排名入库
    ranked = sorted(cat_heat.items(), key=lambda x: x[1], reverse=True)
    cat_rows = []
    for idx, (catid, heat) in enumerate(ranked, start=1):
        cat_name = next((c["display_name"] for c in cats if c["catid"] == catid), "")
        n_kw = sum(1 for seed, _, _ in seed_rows if seed == cat_name)
        cat_rows.append((catid, round(heat, 3), idx, n_kw))
    save_category_rows(conn, market, date, cat_rows)
    print(f"[{market}] 类目热度已入库: {len(cat_rows)} 个，排名前 3: "
          f"{[(next((c['display_name'] for c in cats if c['catid'] == cid), cid), round(h,2)) for cid,h in ranked[:3]]}")


def main():
    conn = connect()
    init_db(conn)
    upsert_markets(conn, MARKETS)
    today = datetime.now(CST).strftime("%Y-%m-%d")
    print(f"采集日期: {today}")
    for code, m in MARKETS.items():
        try:
            run_market(conn, code, today, m["domain"])
        except Exception as exc:  # noqa: BLE001
            print(f"[{code}] 采集失败: {exc}")
    conn.close()
    print("完成。")


if __name__ == "__main__":
    main()
