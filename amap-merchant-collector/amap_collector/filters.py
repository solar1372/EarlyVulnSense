"""商户过滤：排除品牌、只保留座机号。"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# 中国大陆手机号
_MOBILE_RE = re.compile(r"(?:\+?86[-\s]?)?1[3-9]\d{9}")

# 带分隔符的座机：区号与本地号分开写
_LANDLINE_SPLIT_RE = re.compile(
    r"(?:\+?86[-\s]?)?"
    r"\(?(0\d{2,3})\)?[-\s]+"
    r"(\d{7,8})"
)

# 连续数字中的候选座机
_DIGITS_RE = re.compile(r"0\d{9,11}")

# 400/800 等企业热线，不算传统座机
_HOTLINE_RE = re.compile(r"(?:400|800)[-\s]?\d{3}[-\s]?\d{4}")

DEFAULT_EXCLUDE_NAME_KEYWORDS: Tuple[str, ...] = ("立邦",)


def _area_code_len(digits: str) -> int:
    """
    推断区号长度（含开头 0）。
    - 010 / 02x：3 位区号
    - 其余：4 位区号（如 0871 昆明、0851 贵阳）
    """
    if digits.startswith("010") or digits.startswith("02"):
        return 3
    return 4


def _from_digits_block(digits: str) -> Optional[str]:
    if not digits.startswith("0"):
        return None
    # 排除误把手机号前补 0 的情况
    if len(digits) == 12 and digits.startswith("01") and digits[1] == "1":
        return None
    area_len = _area_code_len(digits)
    area = digits[:area_len]
    local = digits[area_len:]
    if len(local) not in (7, 8):
        return None
    if len(digits) < 10 or len(digits) > 12:
        return None
    return f"{area}-{local}"


def extract_landlines(raw: str) -> List[str]:
    """从 tel 字段抽出座机号，去掉手机号与 400/800。"""
    if not raw:
        return []
    text = _HOTLINE_RE.sub(" ", str(raw))
    # 先去掉明确手机号，降低干扰
    text = _MOBILE_RE.sub(" ", text)

    found: List[str] = []
    seen = set()

    def _add(candidate: Optional[str]) -> None:
        if not candidate or candidate in seen:
            return
        digits = candidate.replace("-", "")
        if not digits.startswith("0"):
            return
        if len(digits) < 10 or len(digits) > 12:
            return
        seen.add(candidate)
        found.append(candidate)

    for m in _LANDLINE_SPLIT_RE.finditer(text):
        area, local = m.group(1), m.group(2)
        # 校正：02x/010 若区号被写成 4 位则再切
        block = area + local
        _add(_from_digits_block(block) or f"{area}-{local}")

    for m in _DIGITS_RE.finditer(re.sub(r"\D", " ", text)):
        _add(_from_digits_block(m.group(0)))

    # 再扫一遍去掉非数字分隔后的整段
    compact = re.sub(r"[^\d]", "", text)
    for m in _DIGITS_RE.finditer(compact):
        _add(_from_digits_block(m.group(0)))

    return found


def has_landline(raw: str) -> bool:
    return bool(extract_landlines(raw))


def name_excluded(name: str, keywords: Sequence[str] = DEFAULT_EXCLUDE_NAME_KEYWORDS) -> bool:
    text = name or ""
    return any(k and k in text for k in keywords)


def filter_record(
    record: Dict[str, str],
    *,
    landline_only: bool = True,
    exclude_name_keywords: Sequence[str] = DEFAULT_EXCLUDE_NAME_KEYWORDS,
) -> Optional[Dict[str, str]]:
    """
    过滤单条记录。
    - 名称含排除词（默认立邦）-> 丢弃
    - landline_only：无座机 -> 丢弃；有座机则 tel 只保留座机
    """
    if name_excluded(record.get("name", ""), exclude_name_keywords):
        return None

    raw_tel = record.get("tel", "") or ""
    landlines = extract_landlines(raw_tel)

    if landline_only:
        if not landlines:
            return None
        out = dict(record)
        out["tel"] = ";".join(landlines)
        out["tel_raw"] = raw_tel
        return out

    return dict(record)


def filter_records(
    records: Iterable[Dict[str, str]],
    *,
    landline_only: bool = True,
    exclude_name_keywords: Sequence[str] = DEFAULT_EXCLUDE_NAME_KEYWORDS,
) -> List[Dict[str, str]]:
    kept: List[Dict[str, str]] = []
    for rec in records:
        filtered = filter_record(
            rec,
            landline_only=landline_only,
            exclude_name_keywords=exclude_name_keywords,
        )
        if filtered:
            kept.append(filtered)
    return kept
