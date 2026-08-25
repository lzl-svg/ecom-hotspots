# -*- coding: utf-8 -*-
"""全局配置：市场、种子词、路径。"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "ecommerce.db"
EXPORT_DIR = BASE_DIR / "web" / "data"

# 市场配置（P0 三个市场）
MARKETS = {
    "id": {"name": "印尼", "label": "印尼站", "domain": "shopee.co.id", "currency": "IDR"},
    "my": {"name": "马来", "label": "马来站", "domain": "shopee.com.my", "currency": "MYR"},
    "vn": {"name": "越南", "label": "越南站", "domain": "shopee.vn", "currency": "VND"},
}

# 固定监控的小类目默认值。网页选择器保存后，会优先读取 watchlist.json。
DEFAULT_CORE_SUBCATEGORY_IDS = {
    "id": {11044245, 11043573, 11043032, 11043959, 11042643, 11042901},
    "my": {11000691, 11133423, 11001537, 11000989, 11000746, 11000711},
    "vn": {11036102, 11036280, 11036479, 11035742, 11036526, 11035899},
    "ozon": set(),
    "wb": set(),
}

WATCHLIST_MARKETS = ("id", "my", "vn", "ozon", "wb")


def load_core_subcategory_ids():
    """读取网页保存的固定采集清单，失败时使用演示默认值。"""
    path = BASE_DIR / "collector" / "watchlist.json"
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        return {
            market: {int(catid) for catid in saved.get(market, [])}
            for market in WATCHLIST_MARKETS
        }
    except (OSError, ValueError, TypeError):
        return {market: set(catids) for market, catids in DEFAULT_CORE_SUBCATEGORY_IDS.items()}


CORE_SUBCATEGORY_IDS = load_core_subcategory_ids()

# 每个市场固定的热门种子词（类目名之外补充，覆盖真实搜索习惯）
FIXED_SEEDS = {
    "id": ["gamis", "casing hp", "sepatu", "skincare", "tas wanita"],
    "my": ["baju kurung", "tudung", "casing telefon", "skincare", "jam tangan"],
    "vn": ["ốp lưng điện thoại", "áo khoác", "giày thể thao", "túi xách nữ", "mỹ phẩm"],
}

# 热度最高的 N 个一级类目：其全部二级类目每天采集
DAILY_LEVEL1_COUNT = 8

# 其余一级类目下的二级类目分组轮换，保证每个子类目至少每 7 天采集一次
SUBCATEGORY_ROTATION_DAYS = 7

# 轮换类目近期单次涨幅达到该值时，临时升级为每日采集
PROMOTION_MIN_GROWTH = 0.10
PROMOTION_LOOKBACK_DAYS = 14
PROMOTION_LIMIT = 30

# 每个种子取多少个联想词
HINT_LIMIT = 40

# 请求间隔（秒）。扩展子类目覆盖后仍保留抖动，并控制每日任务耗时。
REQUEST_DELAY = (0.45, 0.9)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
