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

# 取热度前 N 个一级类目做下钻
TOP_LEVEL2 = 5

# 每个一级类目最多取多少个二级类目做种子
SUBS_PER_CAT = 10

# 每个种子取多少个联想词
HINT_LIMIT = 40

# 请求间隔（秒），放慢节奏避免触发反爬
REQUEST_DELAY = (0.7, 1.5)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
