# -*- coding: utf-8 -*-
"""Shopee 公开接口封装（全免费，仅用公开类目树与搜索联想接口）。"""
import json
import random
import ssl
import time
import urllib.parse
import urllib.request

from config import HINT_LIMIT, REQUEST_DELAY, USER_AGENT


class ShopeeAPI:
    def __init__(self, market: str, domain: str):
        self.market = market
        self.domain = domain
        self.base = f"https://{domain}"
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def _headers(self, referer: str) -> dict:
        return {
            "User-Agent": USER_AGENT,
            "Referer": referer,
            "x-api-source": "pc",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
        }

    def _get(self, url: str, retries: int = 3) -> dict | list | None:
        last_err = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=self._headers(self.base + "/"))
                with urllib.request.urlopen(req, timeout=15, context=self.ctx) as resp:
                    raw = resp.read()
                    data = json.loads(raw.decode("utf-8", "ignore"))
                    return data
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"{self.market} GET failed: {url} -> {last_err}")

    def category_tree(self) -> dict | None:
        url = f"{self.base}/api/v4/pages/get_category_tree"
        return self._get(url)

    def search_hint(self, keyword: str) -> dict | None:
        q = urllib.parse.quote(keyword)
        url = f"{self.base}/api/v4/search/search_hint?keyword={q}"
        return self._get(url)

    def polite_sleep(self):
        time.sleep(random.uniform(*REQUEST_DELAY))


def parse_tree(tree: dict, market: str) -> list[dict]:
    """把类目树接口结果递归展开成列表，并计算层级与路径。"""
    raw = (tree or {}).get("data", {}).get("category_list", [])
    cats = []

    def walk(node, parent_catid, level, path_names):
        c = {
            "catid": node["catid"],
            "parent_catid": node.get("parent_catid") or parent_catid,
            "name": node.get("name") or "",
            "display_name": node.get("display_name") or node.get("name") or "",
            "level": level,
            "path": "/".join(path_names + [node.get("display_name") or node.get("name") or ""]),
        }
        cats.append(c)
        for ch in node.get("children") or []:
            walk(ch, node["catid"], level + 1, path_names + [c["display_name"]])

    for node in raw:
        walk(node, node.get("parent_catid") or 0, node.get("level") or 1, [])
    return cats


def fetch_hints_for_seed(api: ShopeeAPI, seed: str) -> list[dict]:
    """抓取某个种子词的所有联想词。"""
    data = api.search_hint(seed)
    keywords = []
    for k in (data or {}).get("keywords", []):
        keywords.append({"keyword": k.get("keyword", ""), "position": k.get("position", 99)})
    return keywords
