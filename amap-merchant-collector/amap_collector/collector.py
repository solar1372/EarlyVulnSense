"""商户采集编排：翻页、去重、可选详情补全。"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Iterable, List, Optional, Set

from .client import AmapAPIError, AmapClient
from .normalize import merge_records, normalize_poi

logger = logging.getLogger(__name__)

ProgressCb = Callable[[str], None]


class MerchantCollector:
    def __init__(
        self,
        client: AmapClient,
        page_size: int = 25,
        max_pages: int = 100,
        fetch_detail: bool = False,
    ):
        self.client = client
        self.page_size = min(25, max(1, page_size))
        self.max_pages = max(1, max_pages)
        self.fetch_detail = fetch_detail
        self._by_id: Dict[str, Dict[str, str]] = {}

    @property
    def records(self) -> List[Dict[str, str]]:
        return list(self._by_id.values())

    def clear(self) -> None:
        self._by_id.clear()

    def _ingest(self, pois: Iterable[dict], source: str) -> int:
        added = 0
        for poi in pois:
            rec = normalize_poi(poi, source=source)
            poi_id = rec.get("id") or ""
            if not poi_id:
                # 极端情况下无 id，用 name+location 兜底
                poi_id = f"{rec.get('name')}|{rec.get('location')}"
                rec["id"] = poi_id
            if poi_id in self._by_id:
                self._by_id[poi_id] = merge_records(self._by_id[poi_id], rec)
            else:
                self._by_id[poi_id] = rec
                added += 1
        return added

    def _paginate(
        self,
        fetch_page,
        source: str,
        on_progress: Optional[ProgressCb] = None,
    ) -> int:
        total_added = 0
        seen_page_ids: Set[str] = set()

        for page in range(1, self.max_pages + 1):
            try:
                data = fetch_page(page)
            except AmapAPIError as exc:
                # 部分情况末页会返回无效页，直接结束
                if exc.infocode in {"20800", "20801", "20802", "20803"}:
                    if on_progress:
                        on_progress(f"{source}: 到达结果边界，停止翻页")
                    break
                raise

            pois = data.get("pois") or []
            if not isinstance(pois, list) or not pois:
                if on_progress:
                    on_progress(f"{source}: 第 {page} 页无数据，结束")
                break

            page_ids = {str(p.get("id", "")) for p in pois if isinstance(p, dict)}
            already_seen_page = bool(page_ids) and page_ids <= seen_page_ids

            added = self._ingest(pois, source=source)
            total_added += added
            seen_page_ids |= page_ids
            count_hint = data.get("count", "?")
            if on_progress:
                on_progress(
                    f"{source}: 第 {page} 页 +{added} 条 "
                    f"（本批 {len(pois)}，累计唯一 {len(self._by_id)}，接口 count={count_hint}）"
                )

            if already_seen_page:
                if on_progress:
                    on_progress(f"{source}: 检测到重复页，结束")
                break

            if len(pois) < self.page_size:
                break

        return total_added

    def collect_by_keyword(
        self,
        keywords: str,
        city: str,
        types: str = "",
        citylimit: bool = True,
        on_progress: Optional[ProgressCb] = None,
    ) -> int:
        source = f"text:{city}:{keywords or types}"

        def fetch_page(page: int):
            return self.client.place_text(
                keywords=keywords,
                types=types,
                city=city,
                citylimit=citylimit,
                page=page,
                offset=self.page_size,
                extensions="all",
            )

        return self._paginate(fetch_page, source=source, on_progress=on_progress)

    def collect_around(
        self,
        location: str,
        keywords: str = "",
        types: str = "",
        radius: int = 3000,
        on_progress: Optional[ProgressCb] = None,
    ) -> int:
        source = f"around:{location}:{keywords or types}"

        def fetch_page(page: int):
            return self.client.place_around(
                location=location,
                keywords=keywords,
                types=types,
                radius=radius,
                page=page,
                offset=self.page_size,
                extensions="all",
            )

        return self._paginate(fetch_page, source=source, on_progress=on_progress)

    def collect_grid(
        self,
        center: str,
        keywords: str = "",
        types: str = "",
        radius: int = 2000,
        grid_km: float = 2.0,
        grid_size: int = 3,
        on_progress: Optional[ProgressCb] = None,
    ) -> int:
        """
        以中心点做简易网格周边扫描，扩大覆盖面。
        grid_size=3 表示 3x3；grid_km 为相邻网格点间距（公里）。
        """
        try:
            lng_s, lat_s = center.split(",", 1)
            lng0, lat0 = float(lng_s), float(lat_s)
        except Exception as exc:
            raise ValueError("center 需为 '经度,纬度'") from exc

        # 粗略：1°纬度≈111km；经度随纬度变化
        import math

        lat_deg = grid_km / 111.0
        lng_deg = grid_km / (111.0 * max(0.2, math.cos(math.radians(lat0))))
        half = grid_size // 2
        total = 0

        for iy in range(-half, half + 1):
            for ix in range(-half, half + 1):
                lng = lng0 + ix * lng_deg
                lat = lat0 + iy * lat_deg
                loc = f"{lng:.6f},{lat:.6f}"
                if on_progress:
                    on_progress(f"网格点 ({ix},{iy}) -> {loc}")
                total += self.collect_around(
                    location=loc,
                    keywords=keywords,
                    types=types,
                    radius=radius,
                    on_progress=on_progress,
                )
        return total

    def enrich_details(self, on_progress: Optional[ProgressCb] = None) -> int:
        if not self.fetch_detail:
            return 0
        updated = 0
        ids = list(self._by_id.keys())
        for idx, poi_id in enumerate(ids, start=1):
            if "|" in poi_id and len(poi_id) > 20 and not poi_id.isalnum():
                # 兜底 id，跳过详情
                continue
            try:
                data = self.client.place_detail(poi_id)
            except AmapAPIError as exc:
                logger.warning("详情失败 %s: %s", poi_id, exc)
                continue
            pois = data.get("pois") or []
            if not pois:
                continue
            rec = normalize_poi(pois[0], source="detail")
            self._by_id[poi_id] = merge_records(self._by_id[poi_id], rec)
            updated += 1
            if on_progress and idx % 20 == 0:
                on_progress(f"详情补全进度 {idx}/{len(ids)}")
        return updated
