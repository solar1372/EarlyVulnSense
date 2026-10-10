"""高德开放平台 Place API 客户端。"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests


class AmapAPIError(RuntimeError):
    """高德 API 返回业务错误。"""

    def __init__(self, info: str, infocode: str = "", raw: Optional[dict] = None):
        super().__init__(f"Amap API error: {info} (infocode={infocode})")
        self.info = info
        self.infocode = infocode
        self.raw = raw or {}


class AmapClient:
    """封装关键字搜索、周边搜索、详情查询。"""

    BASE = "https://restapi.amap.com"

    def __init__(
        self,
        api_key: str,
        request_interval: float = 0.25,
        timeout: float = 20.0,
        session: Optional[requests.Session] = None,
    ):
        if not api_key or api_key.startswith("your_"):
            raise ValueError(
                "请设置有效的高德 Web 服务 Key（环境变量 AMAP_API_KEY 或 --key）"
            )
        self.api_key = api_key
        self.request_interval = max(0.0, float(request_interval))
        self.timeout = timeout
        self.session = session or requests.Session()
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self._throttle()
        query = {k: v for k, v in params.items() if v is not None and v != ""}
        query["key"] = self.api_key
        url = f"{self.BASE}{path}"
        resp = self.session.get(url, params=query, timeout=self.timeout)
        self._last_request_at = time.monotonic()
        resp.raise_for_status()
        data = resp.json()
        status = str(data.get("status", ""))
        if status != "1":
            raise AmapAPIError(
                info=str(data.get("info", "UNKNOWN")),
                infocode=str(data.get("infocode", "")),
                raw=data,
            )
        return data

    def place_text(
        self,
        keywords: str = "",
        types: str = "",
        city: str = "",
        citylimit: bool = True,
        page: int = 1,
        offset: int = 25,
        extensions: str = "all",
    ) -> Dict[str, Any]:
        """关键字搜索：https://lbs.amap.com/api/webservice/guide/api/search"""
        return self._get(
            "/v3/place/text",
            {
                "keywords": keywords,
                "types": types,
                "city": city,
                "citylimit": "true" if citylimit else "false",
                "page": page,
                "offset": min(25, max(1, offset)),
                "extensions": extensions,
            },
        )

    def place_around(
        self,
        location: str,
        keywords: str = "",
        types: str = "",
        radius: int = 3000,
        page: int = 1,
        offset: int = 25,
        extensions: str = "all",
        sortrule: str = "distance",
    ) -> Dict[str, Any]:
        """周边搜索。location 格式：经度,纬度"""
        return self._get(
            "/v3/place/around",
            {
                "location": location,
                "keywords": keywords,
                "types": types,
                "radius": radius,
                "page": page,
                "offset": min(25, max(1, offset)),
                "extensions": extensions,
                "sortrule": sortrule,
            },
        )

    def place_detail(self, poi_id: str) -> Dict[str, Any]:
        """ID 查询详情。"""
        return self._get("/v3/place/detail", {"id": poi_id})

    def geocode(self, address: str, city: str = "") -> List[Dict[str, Any]]:
        """地理编码，便于把地址转成中心点做周边搜索。"""
        data = self._get("/v3/geocode/geo", {"address": address, "city": city})
        return data.get("geocodes") or []
