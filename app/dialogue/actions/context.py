"""产品咨询的上下文解析工具。

从用户自然语言中解析目的地城市、星级、类型、车次 / 航班号等筛选条件，
再交给对应的 Action 查询数据库。地区名通过 areas 表动态加载并缓存。
"""

from __future__ import annotations

import re
import threading
from typing import Any

from ...database import fetch_all

_areas: list[dict[str, Any]] | None = None
_areas_lock = threading.Lock()

# 行政区划名称常见后缀，用于生成可匹配的简称
_SUFFIXES = ("特别行政区", "自治区", "自治州", "自治县", "地区", "市", "省", "县", "区", "盟")

# 车次号：G/D/C/K/T/Z/L/Y 开头
VEHICLE_NO_RE = re.compile(r"\b[GDCKTZLY]\d{1,4}\b")

STAR_MAP = {"五星": "5", "5星": "5", "四星": "4", "4星": "4", "三星": "3", "3星": "3"}
HOTEL_TYPE_MAP = {
    "度假": "resort",
    "商务": "business",
    "豪华": "luxury",
    "精品": "boutique",
}
SCENIC_RATING_MAP = {"5A": "5A", "5a": "5A", "4A": "4A", "4a": "4A", "3A": "3A", "3a": "3A"}
SCENIC_TYPE_MAP = {
    "主题公园": "theme_park", "博物馆": "museum", "山地": "mountain", "文化遗产": "heritage",
    "湿地": "wetland", "海滨": "beach", "冰雪": "snow", "森林": "forest", "瀑布": "waterfall",
    "古镇": "ancient_town", "宗教": "religious", "水上乐园": "theme_water", "动物园": "zoo",
    "植物园": "botanical_garden", "红色": "red_tourism", "生态": "ecological",
}
SERVICE_TYPE_MAP = {
    "接机": "airport_pickup", "送机": "airport_dropoff", "包车": "charter_daily",
    "车站接送": "station_transfer", "接送": "station_transfer",
}


def _load_areas() -> list[dict[str, Any]]:
    global _areas
    if _areas is not None:
        return _areas
    with _areas_lock:
        if _areas is None:
            _areas = fetch_all(
                """
                SELECT id, area_name, area_full_name, parent_id, `level`
                FROM areas
                WHERE status_code = 'active'
                """
            )
    return _areas


def _short_names(name: str) -> list[str]:
    names = [name]
    for suffix in _SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix):
            names.append(name[: -len(suffix)])
    return names


def find_area_mentions(text: str) -> list[dict[str, Any]]:
    """返回文本中命中的地区（按名称长度降序，优先更具体的地名）。"""
    hits: list[dict[str, Any]] = []
    for area in _load_areas():
        for name in _short_names(area["area_name"]):
            if name and len(name) >= 2 and name in text:
                hits.append({**area, "matched_name": name})
                break
    hits.sort(key=lambda a: len(a["matched_name"]), reverse=True)
    # 去重（同一地区可能以全称、简称分别命中）
    seen: set[int] = set()
    result: list[dict[str, Any]] = []
    for h in hits:
        if h["id"] not in seen:
            seen.add(h["id"])
            result.append(h)
    return result


def expand_area_ids(area_id: int) -> list[int]:
    """返回该地区自身及其所有后代地区 ID（用于按城市模糊检索产品）。"""
    areas = _load_areas()
    result = [area_id]
    # 自底向上扩展后代
    changed = True
    frontier = {area_id}
    while changed:
        changed = False
        for a in areas:
            if a["parent_id"] in frontier and a["id"] not in result:
                result.append(a["id"])
                frontier.add(a["id"])
                changed = True
    return result


def extract_star_rating(text: str) -> str | None:
    for word, code in STAR_MAP.items():
        if word in text:
            return code
    return None


def extract_hotel_type(text: str) -> str | None:
    for word, code in HOTEL_TYPE_MAP.items():
        if word in text:
            return code
    return None


def extract_scenic_rating(text: str) -> str | None:
    for word, code in SCENIC_RATING_MAP.items():
        if word in text:
            return code
    return None


def extract_scenic_type(text: str) -> str | None:
    for word, code in SCENIC_TYPE_MAP.items():
        if word in text:
            return code
    return None


def extract_service_type(text: str) -> str | None:
    for word, code in SERVICE_TYPE_MAP.items():
        if word in text:
            return code
    return None


def extract_vehicle_no(text: str) -> str | None:
    m = VEHICLE_NO_RE.search(text)
    return m.group(0).upper() if m else None
