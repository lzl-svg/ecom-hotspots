# -*- coding: utf-8 -*-
"""Collect free, public full-market category signals from Ozon and Wildberries.

This module deliberately does not use Seller APIs or private shop data.  The
result is a relative category activity signal built from public popular-list
positions, feedback counts, ratings and the reported catalogue size.  It is
not sales volume, GMV or search volume.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "web" / "data"
WATCHLIST_FILE = BASE_DIR / "collector" / "watchlist.json"
CST = timezone(timedelta(hours=8))
TODAY = datetime.now(CST).strftime("%Y-%m-%d")
NOW = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
HISTORY_DAYS = 30
ROTATION_DAYS = 7
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def stable_id(platform: str, key: str) -> int:
    return zlib.crc32(f"{platform}:{key}".encode("utf-8")) & 0x7FFFFFFF


def node(platform: str, name: str, cn: str, url: str, source_id: str = "", **extra: Any) -> dict:
    value = {
        "catid": stable_id(platform, url or source_id or name),
        "source_id": str(source_id),
        "name": name,
        "cn": cn,
        "source_url": url,
        "subs": [],
    }
    value.update(extra)
    return value


OZON_ROOTS = [
    (39803, "Автомобили", "汽车", "avtomobili"),
    (13500, "Хобби и творчество", "爱好与创作", "hobbi-i-tvorchestvo"),
    (7697, "Аксессуары", "配饰", "aksessuary"),
    (33332, "Туризм, рыбалка, охота", "旅行、钓鱼与狩猎", "turizm-rybalka-ohota"),
    (11000, "Спорт и отдых", "运动与休闲", "sport-i-otdyh"),
    (8500, "Автотовары", "汽车用品", "avtotovary"),
    (17777, "Обувь", "鞋靴", "obuv"),
    (12300, "Товары для животных", "宠物用品", "tovary-dlya-zhivotnyh"),
    (18000, "Канцелярские товары", "文具", "kantselyarskie-tovary"),
    (14500, "Дом и сад", "家居与园艺", "dom-i-sad"),
    (13300, "Игры и консоли", "游戏与主机", "igry-i-konsoli"),
    (15000, "Мебель", "家具", "mebel"),
    (32056, "Цифровые товары", "数字商品", "tsifrovye-tovary"),
    (9000, "Товары для взрослых", "成人用品", "tovary-dlya-vzroslyh"),
    (7000, "Детские товары", "母婴与儿童", "detskie-tovary"),
    (15500, "Электроника", "电子产品", "elektronika"),
    (13100, "Музыка и видео", "音乐与视频", "muzyka-i-video"),
    (9700, "Строительство и ремонт", "建材与装修", "stroitelstvo-i-remont"),
    (50001, "Ювелирные украшения", "珠宝首饰", "yuvelirnye-ukrasheniya"),
    (7500, "Одежда", "服装", "odezhda"),
    (8000, "Антиквариат и коллекционирование", "古董与收藏", "antikvariat-i-kollektsionirovanie"),
    (6500, "Красота и здоровье", "美妆与健康", "krasota-i-zdorove"),
    (10500, "Бытовая техника", "家用电器", "bytovaya-tehnika"),
    (9200, "Продукты питания", "食品", "produkty-pitaniya"),
    (16500, "Книги", "图书", "knigi"),
    (14572, "Бытовая химия и гигиена", "清洁与个人卫生", "bytovaya-himiya-i-gigiena"),
    (6000, "Аптека", "药房", "apteka"),
]

WB_ROOTS = [
    ("Женщинам", "女装", "zhenshchinam"), ("Мужчинам", "男装", "muzhchinam"),
    ("Детям", "母婴与儿童", "detyam"), ("Обувь", "鞋靴", "obuv"),
    ("Красота", "美妆", "krasota"), ("Дом", "家居", "dom"),
    ("Электроника", "电子产品", "elektronika"), ("Бытовая техника", "家用电器", "bytovaya-tehnika"),
    ("Спорт", "运动", "sport"), ("Товары для животных", "宠物用品", "tovary-dlya-zhivotnyh"),
    ("Автотовары", "汽车用品", "avtotovary"), ("Книги", "图书", "knigi"),
    ("Ювелирные украшения", "珠宝首饰", "yuvelirnye-ukrasheniya"),
    ("Продукты", "食品", "produkty"), ("Аптека", "药房", "apteka"),
]

SEED_SUBS = {
    "Электроника": [("Смартфоны", "智能手机"), ("Ноутбуки", "笔记本电脑"), ("Наушники", "耳机")],
    "Одежда": [("Женская одежда", "女装"), ("Мужская одежда", "男装"), ("Детская одежда", "童装")],
    "Красота и здоровье": [("Уход за лицом", "面部护理"), ("Макияж", "彩妆"), ("Уход за волосами", "头发护理")],
    "Красота": [("Уход за лицом", "面部护理"), ("Макияж", "彩妆"), ("Уход за волосами", "头发护理")],
    "Дом и сад": [("Товары для кухни", "厨房用品"), ("Текстиль", "家纺"), ("Сад", "园艺")],
    "Дом": [("Товары для кухни", "厨房用品"), ("Текстиль", "家纺"), ("Хранение", "收纳")],
    "Товары для животных": [("Для кошек", "猫用品"), ("Для собак", "狗用品"), ("Корма", "宠物食品")],
    "Продукты питания": [("Напитки", "饮料"), ("Сладости", "糖果零食"), ("Бакалея", "粮油干货")],
    "Продукты": [("Напитки", "饮料"), ("Сладости", "糖果零食"), ("Бакалея", "粮油干货")],
    "Бытовая техника": [("Техника для кухни", "厨房电器"), ("Уборка", "清洁电器"), ("Климатическая техника", "环境电器")],
    "Детские товары": [("Игрушки", "玩具"), ("Товары для малышей", "婴儿用品"), ("Детская одежда", "童装")],
    "Детям": [("Игрушки", "玩具"), ("Товары для малышей", "婴儿用品"), ("Детская одежда", "童装")],
    "Женщинам": [("Женская одежда", "女装"), ("Сумки", "女包"), ("Аксессуары", "女式配饰")],
    "Мужчинам": [("Мужская одежда", "男装"), ("Сумки", "男包"), ("Аксессуары", "男式配饰")],
    "Спорт": [("Фитнес", "健身"), ("Туризм", "户外旅行"), ("Командные виды спорта", "球类运动")],
    "Спорт и отдых": [("Фитнес", "健身"), ("Туризм", "户外旅行"), ("Командные виды спорта", "球类运动")],
}


def attach_seed_subs(platform: str, root: dict) -> dict:
    base = str(root.get("source_url") or "/").rstrip("/")
    root["subs"] = [
        node(platform, name, cn, f"{base}/{urllib.parse.quote(name.lower().replace(' ', '-'))}/seed")
        for name, cn in SEED_SUBS.get(root["name"], [])
    ]
    return root


def seed_ozon() -> list[dict]:
    return [
        attach_seed_subs("ozon", node("ozon", name, cn, f"/category/{slug}-{source_id}/", source_id))
        for source_id, name, cn, slug in OZON_ROOTS
    ]


def seed_wb() -> list[dict]:
    return [attach_seed_subs("wb", node("wb", name, cn, f"/catalog/{slug}")) for name, cn, slug in WB_ROOTS]


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def request_json(url: str, referer: str, timeout: float = 18.0) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
            "Referer": referer,
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        body = response.read(12_000_000)
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("返回内容不是 JSON，可能触发了验证页") from exc


def walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)
    elif isinstance(value, str) and value[:1] in "[{" and len(value) < 4_000_000:
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return
        yield from walk(decoded)


def numeric(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(" ", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def nested_number(record: dict, keys: tuple[str, ...]) -> float:
    for key in keys:
        if key in record:
            value = record[key]
            if isinstance(value, dict):
                for nested in ("value", "count", "amount"):
                    if nested in value:
                        return numeric(value[nested])
            return numeric(value)
    return 0.0


def product_signal(products: list[dict], total: float = 0.0) -> dict:
    feedback_sum = 0.0
    ratings = []
    rank_signal = 0.0
    names = []
    for rank, product in enumerate(products[:60], start=1):
        feedbacks = nested_number(product, ("feedbacks", "reviewCount", "reviewsCount", "commentsAmount", "comments"))
        rating = nested_number(product, ("rating", "reviewRating", "score"))
        name = str(product.get("name") or product.get("title") or product.get("productName") or "").strip()
        brand = str(product.get("brand") or product.get("brandName") or "").strip()
        feedback_sum += max(feedbacks, 0)
        if rating > 0:
            ratings.append(rating)
        rank_signal += (math.log1p(max(feedbacks, 0)) + min(max(rating, 0), 5) * 0.18 + 0.3) / (rank + 4)
        if name:
            names.append({"keyword": (brand + " · " if brand and brand.lower() not in name.lower() else "") + name, "heat": round(1 / rank, 3)})
    assortment = max(total, len(products))
    heat = rank_signal + math.log1p(assortment) * 0.22
    return {
        "heat": round(heat, 3),
        "hot_keywords": names[:12],
        "metrics": {
            "assortment": int(assortment),
            "sampled_products": len(products),
            "feedback_sum": int(feedback_sum),
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
        },
    }


def wb_menu() -> list[dict]:
    payload = request_json(
        "https://static-basket-01.wbbasket.ru/vol0/data/main-menu-ru-ru-v3.json",
        "https://www.wildberries.ru/",
    )
    if not isinstance(payload, list):
        raise RuntimeError("WB 类目菜单结构发生变化")

    def convert(raw: dict) -> dict:
        url = str(raw.get("url") or "")
        result = node(
            "wb", str(raw.get("name") or "未命名类目"), "", url,
            str(raw.get("id") or ""), shard=str(raw.get("shard") or ""), query=str(raw.get("query") or "")
        )
        result["subs"] = [convert(child) for child in (raw.get("childs") or []) if isinstance(child, dict)][:120]
        return result

    roots = [convert(item) for item in payload if isinstance(item, dict)]
    return [item for item in roots if item.get("source_url")][:80]


def queryable_wb(item: dict) -> dict | None:
    if item.get("shard") and item.get("query"):
        return item
    for child in item.get("subs") or []:
        found = queryable_wb(child)
        if found:
            return found
    return None


def wb_sample(item: dict) -> dict:
    source = queryable_wb(item)
    if not source:
        raise RuntimeError("该类目暂未提供公开查询参数")
    suffix = str(source["query"]).lstrip("?&")
    endpoints = ["v4/catalog", "v2/catalog", "catalog"]
    last_error: Exception | None = None
    for endpoint in endpoints:
        url = (
            f"https://catalog.wb.ru/catalog/{source['shard']}/{endpoint}"
            f"?appType=1&curr=rub&dest=-1257786&lang=ru&page=1&sort=popular&spp=30&{suffix}"
        )
        try:
            payload = request_json(url, "https://www.wildberries.ru" + str(item.get("source_url") or "/"))
            data = payload.get("data") if isinstance(payload, dict) else None
            products = data.get("products") if isinstance(data, dict) else None
            if not isinstance(products, list):
                raise RuntimeError("WB 商品列表结构发生变化")
            total = numeric(data.get("total") or data.get("totalCount") or len(products))
            return product_signal([p for p in products if isinstance(p, dict)], total)
        except Exception as exc:  # each endpoint is an intentional compatibility fallback
            last_error = exc
    raise RuntimeError(str(last_error or "WB 公开商品页不可用"))


def ozon_children(root: dict) -> list[dict]:
    source_id = root.get("source_id")
    url = (
        "https://www.ozon.ru/api/composer-api.bx/_action/v2/categoryChildV3?"
        + urllib.parse.urlencode({"menuId": "185", "categoryId": source_id})
    )
    payload = request_json(url, "https://www.ozon.ru" + str(root.get("source_url") or "/"))
    candidates = []
    for value in walk(payload):
        if not isinstance(value, dict):
            continue
        category_id = value.get("categoryId") or value.get("category_id")
        name = value.get("title") or value.get("name")
        path = value.get("url") or value.get("link") or value.get("href")
        if category_id and name and str(category_id) != str(source_id):
            if not path:
                path = f"/category/{category_id}/"
            candidates.append(node("ozon", str(name), "", str(path), str(category_id)))
    unique = {}
    for item in candidates:
        unique[item["catid"]] = item
    return list(unique.values())[:120]


def ozon_products(payload: Any) -> tuple[list[dict], float]:
    products = []
    seen = set()
    total = 0.0
    for value in walk(payload):
        if not isinstance(value, dict):
            continue
        total = max(total, nested_number(value, ("total", "totalCount", "itemsCount")))
        title = value.get("title") or value.get("name") or value.get("productName")
        product_id = value.get("sku") or value.get("productId") or value.get("id")
        productish = any(key in value for key in ("price", "priceV2", "rating", "reviewCount", "reviewsCount"))
        if product_id and title and productish and str(product_id) not in seen:
            seen.add(str(product_id))
            products.append(value)
    return products[:60], total


def ozon_sample(item: dict) -> dict:
    path = str(item.get("source_url") or "")
    if not path:
        raise RuntimeError("该类目缺少公开地址")
    path = path if path.startswith("/") else "/" + path
    encoded = urllib.parse.quote(path + ("&" if "?" in path else "?") + "sorting=rating", safe="/?=&-")
    endpoints = [
        "https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url=" + encoded,
        "https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=" + encoded,
        "https://api.ozon.ru/composer-api.bx/page/json/v2?url=" + encoded,
    ]
    last_error: Exception | None = None
    for url in endpoints:
        try:
            payload = request_json(url, "https://www.ozon.ru" + path)
            products, total = ozon_products(payload)
            if not products:
                raise RuntimeError("未找到商品卡片，可能触发了 Ozon 验证")
            return product_signal(products, total)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(str(last_error or "Ozon 公开商品页不可用"))


def load_watchlist(platform: str) -> set[int]:
    saved = read_json(WATCHLIST_FILE, {})
    try:
        return {int(value) for value in saved.get(platform, [])}
    except (TypeError, ValueError):
        return set()


def old_index(old: dict) -> tuple[dict[int, dict], dict[int, dict]]:
    roots, subs = {}, {}
    for root in old.get("categories") or []:
        roots[int(root.get("catid") or 0)] = root
        for sub in root.get("subs") or []:
            subs[int(sub.get("catid") or 0)] = sub
    return roots, subs


def merge_taxonomy(seeds: list[dict], old: dict, fresh: list[dict] | None) -> list[dict]:
    old_roots, old_subs = old_index(old)
    merged = fresh or seeds
    result = []
    for root in merged:
        previous = old_roots.get(int(root["catid"]))
        if previous:
            root["cn"] = root.get("cn") or previous.get("cn", "")
            if not root.get("subs"):
                root["subs"] = previous.get("subs") or []
        children = []
        for sub in root.get("subs") or []:
            prior = old_subs.get(int(sub["catid"]))
            if prior:
                sub["cn"] = sub.get("cn") or prior.get("cn", "")
            children.append(sub)
        root["subs"] = children
        result.append(root)
    return result


def should_sample_sub(catid: int, fixed: set[int]) -> bool:
    if catid in fixed:
        return True
    day_number = datetime.now(CST).date().toordinal()
    return (catid + day_number) % ROTATION_DAYS == 0


def merge_history(current: dict, previous: dict | None, sample: dict | None) -> dict:
    history = {}
    if previous:
        for date, value in zip(previous.get("dates") or [], previous.get("series") or []):
            if value is not None:
                history[str(date)] = float(value)
    if sample is not None:
        history[TODAY] = float(sample["heat"])
    dates = sorted(history)[-HISTORY_DAYS:]
    observed_desc = list(reversed(dates))
    latest = observed_desc[0] if observed_desc else ""
    prior_date = observed_desc[1] if len(observed_desc) > 1 else ""
    comparable = latest == TODAY and bool(prior_date)
    current.update({
        "heat": round(history[latest], 3) if latest else 0,
        "delta": round(history[latest] - history[prior_date], 3) if comparable else 0,
        "dates": dates,
        "series": [round(history[d], 3) for d in dates],
        "sample_count": len(dates),
        "last_tracked_date": latest,
        "previous_tracked_date": prior_date,
        "comparison_days": ((datetime.fromisoformat(latest) - datetime.fromisoformat(prior_date)).days if comparable else 0),
        "comparable": comparable,
        "tracking_status": "tracked" if comparable else ("warming_up" if latest == TODAY else ("not_today" if latest else "never")),
        "hot_keywords": sample.get("hot_keywords", []) if sample else (previous or {}).get("hot_keywords", []),
        "metrics": sample.get("metrics", {}) if sample else (previous or {}).get("metrics", {}),
    })
    return current


def collect_platform(platform: str, seed_only: bool = False) -> dict:
    path = DATA_DIR / f"{platform}.json"
    old = read_json(path, {})
    seeds = seed_ozon() if platform == "ozon" else seed_wb()
    fresh_taxonomy = None
    errors = []
    samples = 0

    if not seed_only and platform == "wb":
        try:
            fresh_taxonomy = wb_menu()
        except Exception as exc:
            errors.append(f"类目菜单：{exc}")

    roots = merge_taxonomy(seeds, old, fresh_taxonomy)
    old_roots, old_subs = old_index(old)
    fixed = load_watchlist(platform)
    output_roots = []
    ozon_failures = 0

    for root_position, root in enumerate(roots):
        if not seed_only and platform == "ozon":
            try:
                fresh_children = ozon_children(root)
                if fresh_children:
                    root["subs"] = fresh_children
            except Exception as exc:
                errors.append(f"{root['name']}类目树：{exc}")

        root_sample = None
        if not seed_only:
            try:
                root_sample = ozon_sample(root) if platform == "ozon" else wb_sample(root)
                samples += 1
                ozon_failures = 0
            except Exception as exc:
                errors.append(f"{root['name']}：{exc}")
                if platform == "ozon":
                    ozon_failures += 1

        old_root = old_roots.get(int(root["catid"]))
        children = []
        for sub in root.get("subs") or []:
            sub_sample = None
            if not seed_only and should_sample_sub(int(sub["catid"]), fixed) and not (platform == "ozon" and ozon_failures >= 2):
                try:
                    sub_sample = ozon_sample(sub) if platform == "ozon" else wb_sample(sub)
                    samples += 1
                except Exception as exc:
                    errors.append(f"{sub['name']}：{exc}")
                time.sleep(random.uniform(0.18, 0.42))
            children.append(merge_history(sub, old_subs.get(int(sub["catid"])), sub_sample))
        root["subs"] = children
        output_roots.append(merge_history(root, old_root, root_sample))

        if platform == "ozon" and ozon_failures >= 2 and samples == 0:
            errors.append("连续两次触发限制，已停止本次 Ozon 请求并保留旧数据")
            for remaining in roots[root_position + 1:]:
                previous = old_roots.get(int(remaining["catid"]))
                remaining["subs"] = [
                    merge_history(sub, old_subs.get(int(sub["catid"])), None)
                    for sub in (remaining.get("subs") or (previous or {}).get("subs") or [])
                ]
                output_roots.append(merge_history(remaining, previous, None))
            break
        if not seed_only:
            time.sleep(random.uniform(0.22, 0.55))

    all_dates = sorted({date for root in output_roots for date in root.get("dates", [])}, reverse=True)[:HISTORY_DAYS]
    status = "warming" if seed_only and not old.get("dates") else ("healthy" if not errors else ("partial" if samples else "degraded"))
    if seed_only:
        note = "已接入免费公开市场采集器，等待首次联网采集；当前只展示类目结构，不生成模拟行情。"
    elif status == "healthy":
        note = "公开市场信号采集正常。"
    elif status == "partial":
        note = f"部分公开页面不可用，本次保留旧数据；成功采集 {samples} 个类目。"
    else:
        note = "公开页面触发访问限制或结构变化，已保留上一份有效数据；未使用模拟值。"

    output_roots.sort(key=lambda item: float(item.get("heat") or 0), reverse=True)
    latest_effective = old.get("updated_at") if status == "degraded" and old.get("updated_at") else NOW
    return {
        "market": platform,
        "platform": "Ozon" if platform == "ozon" else "Wildberries",
        "updated_at": latest_effective,
        "attempted_at": NOW,
        "dates": all_dates,
        "categories": output_roots,
        "keywords": [],
        "source_status": status,
        "source_note": note,
        "source_errors": errors[:12],
        "signal_definition": (
            "活跃度由公开热门商品排序位置、反馈量、评分和类目规模信号合成，只用于同一平台内相对比较；"
            "不使用卖家后台数据，也不代表真实销量、GMV或搜索量。"
        ),
    }


def patch_meta(results: list[dict]) -> None:
    path = DATA_DIR / "meta.json"
    meta = read_json(path, {"site": "电商热点台", "markets": []})
    public_codes = {result["market"] for result in results}
    markets = [item for item in meta.get("markets", []) if item.get("code") not in public_codes]
    labels = {"ozon": ("俄罗斯", "Ozon", "RUB"), "wb": ("俄罗斯", "Wildberries", "RUB")}
    for result in results:
        name, label, currency = labels[result["market"]]
        markets.append({
            "code": result["market"], "name": name, "label": label, "currency": currency,
            "updated_at": result["updated_at"], "n_categories": len(result["categories"]),
            "n_keywords": 0, "history_days": len(result["dates"]),
            "source_status": result["source_status"],
        })
    meta["markets"] = markets
    meta["updated_at"] = NOW
    path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-only", action="store_true", help="create taxonomy-only preview without network requests")
    args = parser.parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for platform in ("ozon", "wb"):
        result = collect_platform(platform, seed_only=args.seed_only)
        (DATA_DIR / f"{platform}.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        results.append(result)
        print(f"[{platform}] roots={len(result['categories'])} status={result['source_status']}")
    patch_meta(results)


if __name__ == "__main__":
    main()
