"""业务预设：西南四城 + 品类关键字。"""

from __future__ import annotations

from typing import Dict, List, Tuple

# 西南四城：成都、重庆、昆明、贵阳
SOUTHWEST_CITIES: Tuple[str, ...] = ("成都", "重庆", "昆明", "贵阳")

# 五金 / 家装 / 家居 / 涂料（非立邦用名称排除，不用关键字搜立邦）
CATEGORY_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "五金店": ("五金店", "五金建材", "五金机电"),
    "家装": ("家装", "装修公司", "装饰公司", "家装设计"),
    "家居": ("家居", "家具店", "家居建材", "全屋定制"),
    "涂料": ("涂料店", "油漆涂料", "墙漆", "乳胶漆"),
}

# 默认排除品牌名（出现在商户名中即丢弃）
EXCLUDE_BRANDS: Tuple[str, ...] = ("立邦",)


def iter_jobs(
    cities: Tuple[str, ...] = SOUTHWEST_CITIES,
    categories: Dict[str, Tuple[str, ...]] | None = None,
) -> List[Dict[str, str]]:
    """展开为 (city, category, keyword) 任务列表。"""
    cats = categories or CATEGORY_KEYWORDS
    jobs: List[Dict[str, str]] = []
    for city in cities:
        for category, keywords in cats.items():
            for kw in keywords:
                jobs.append({"city": city, "category": category, "keyword": kw})
    return jobs
