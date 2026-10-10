"""导出 CSV / JSON。"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

from .normalize import FIELD_ORDER, records_to_rows


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def export_csv(records: List[Dict[str, str]], path: Path) -> Path:
    ensure_dir(path.parent)
    rows = records_to_rows(records)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELD_ORDER, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def export_json(records: List[Dict[str, str]], path: Path) -> Path:
    ensure_dir(path.parent)
    rows = records_to_rows(records)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
    return path
