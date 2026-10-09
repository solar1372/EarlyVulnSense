"""把高德 POI 原始字段整理成统一商户记录。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        # 高德偶发返回 [] 表示空
        if not value:
            return ""
        return ";".join(_as_str(v) for v in value if v not in (None, "", []))
    if isinstance(value, dict):
        return str(value)
    return str(value).strip()


def _split_location(location: str) -> tuple[str, str]:
    if not location or "," not in location:
        return "", ""
    lng, lat = location.split(",", 1)
    return lng.strip(), lat.strip()


def normalize_poi(poi: Dict[str, Any], source: str = "") -> Dict[str, str]:
    """标准化单条 POI。"""
    location = _as_str(poi.get("location"))
    lng, lat = _split_location(location)
    biz_ext = poi.get("biz_ext") if isinstance(poi.get("biz_ext"), dict) else {}
    indoor = poi.get("indoor_data") if isinstance(poi.get("indoor_data"), dict) else {}

    return {
        "id": _as_str(poi.get("id")),
        "name": _as_str(poi.get("name")),
        "type": _as_str(poi.get("type")),
        "typecode": _as_str(poi.get("typecode")),
        "address": _as_str(poi.get("address")),
        "pname": _as_str(poi.get("pname")),
        "cityname": _as_str(poi.get("cityname")),
        "adname": _as_str(poi.get("adname")),
        "pcode": _as_str(poi.get("pcode")),
        "citycode": _as_str(poi.get("citycode")),
        "adcode": _as_str(poi.get("adcode")),
        "location": location,
        "lng": lng,
        "lat": lat,
        "tel": _as_str(poi.get("tel")),
        "website": _as_str(poi.get("website")),
        "email": _as_str(poi.get("email")),
        "postcode": _as_str(poi.get("postcode")),
        "business_area": _as_str(poi.get("business_area")),
        "alias": _as_str(poi.get("alias")),
        "tag": _as_str(poi.get("tag")),
        "rating": _as_str(biz_ext.get("rating")),
        "cost": _as_str(biz_ext.get("cost")),
        "meal_ordering": _as_str(biz_ext.get("meal_ordering")),
        "opentime_week": _as_str(
            poi.get("opentime_week")
            or poi.get("open_time")
            or biz_ext.get("open_time")
        ),
        "parking_type": _as_str(poi.get("parking_type")),
        "indoor_map": _as_str(indoor.get("indoor_map")),
        "cpid": _as_str(indoor.get("cpid")),
        "floor": _as_str(indoor.get("floor")),
        "truefloor": _as_str(indoor.get("truefloor")),
        "photos": _join_photos(poi.get("photos")),
        "source": source,
    }


def _join_photos(photos: Any) -> str:
    if not isinstance(photos, list):
        return ""
    urls: List[str] = []
    for item in photos:
        if isinstance(item, dict) and item.get("url"):
            urls.append(str(item["url"]))
        elif isinstance(item, str) and item:
            urls.append(item)
    return ";".join(urls)


def merge_records(existing: Dict[str, str], incoming: Dict[str, str]) -> Dict[str, str]:
    """按字段非空合并，保留更完整的一条。"""
    merged = dict(existing)
    for key, value in incoming.items():
        if value and not merged.get(key):
            merged[key] = value
        elif value and key == "source" and existing.get("source"):
            sources = {s for s in existing["source"].split("|") if s}
            sources.add(value)
            merged["source"] = "|".join(sorted(sources))
    return merged


FIELD_ORDER: List[str] = [
    "id",
    "name",
    "type",
    "typecode",
    "tel",
    "tel_raw",
    "address",
    "pname",
    "cityname",
    "adname",
    "lng",
    "lat",
    "location",
    "business_area",
    "rating",
    "cost",
    "tag",
    "alias",
    "website",
    "email",
    "opentime_week",
    "photos",
    "adcode",
    "citycode",
    "pcode",
    "category",
    "keyword",
    "source",
]


def records_to_rows(records: List[Dict[str, str]]) -> List[Dict[str, str]]:
    rows = []
    for rec in records:
        rows.append({k: rec.get(k, "") for k in FIELD_ORDER})
    return rows
