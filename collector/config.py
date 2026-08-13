# -*- coding: utf-8 -*-
"""全局配置：市场、种子词、路径。"""
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
