"""命令行入口。"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import click
import yaml
from dotenv import load_dotenv

from .client import AmapAPIError, AmapClient
from .collector import MerchantCollector
from .export import export_csv, export_json
from .filters import DEFAULT_EXCLUDE_NAME_KEYWORDS, filter_records
from .presets import CATEGORY_KEYWORDS, EXCLUDE_BRANDS, SOUTHWEST_CITIES, iter_jobs


def _load_config(config_path: Optional[Path]) -> Dict[str, Any]:
    defaults = {
        "request_interval": 0.25,
        "page_size": 25,
        "max_pages": 100,
        "output_dir": "./output",
        "fetch_detail": False,
    }
    if not config_path:
        return defaults
    if not config_path.exists():
        raise click.ClickException(f"配置文件不存在: {config_path}")
    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    defaults.update({k: v for k, v in data.items() if v is not None})
    return defaults


def _resolve_key(cli_key: Optional[str]) -> str:
    load_dotenv()
    key = cli_key or os.getenv("AMAP_API_KEY", "").strip()
    if not key:
        raise click.ClickException(
            "未找到 API Key。请设置环境变量 AMAP_API_KEY，或使用 --key。"
            "申请地址：https://console.amap.com/dev/key/app"
        )
    return key


def _stamp_name(prefix: str, city: str, keywords: str, types: str) -> str:
    parts = [prefix]
    if city:
        parts.append(city)
    label = keywords or types or "all"
    # 文件名友好
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:40]
    parts.append(safe)
    parts.append(datetime.now().strftime("%Y%m%d_%H%M%S"))
    return "_".join(parts)


@click.group()
@click.version_option(version="1.0.0", prog_name="amap-collector")
def main() -> None:
    """高德地图商户数据采集（官方 Place Web 服务 API）。

    仅通过高德开放平台正式接口拉取 POI/商户信息，需自备 Web 服务 Key。
    """


@main.command("search")
@click.option("--keywords", "-k", default="", help="关键字，如：火锅 / 理发店")
@click.option("--types", "-t", default="", help="POI 分类编码，多个用 | 分隔")
@click.option("--city", "-c", required=True, help="城市名或 citycode，如：北京 / 110000")
@click.option("--citylimit/--no-citylimit", default=True, help="是否限制在城市内")
@click.option("--key", "api_key", default=None, help="高德 Web 服务 Key（优先于环境变量）")
@click.option("--config", "config_path", type=click.Path(path_type=Path), default=None)
@click.option("--output-dir", type=click.Path(path_type=Path), default=None)
@click.option("--format", "fmt", type=click.Choice(["csv", "json", "both"]), default="both")
@click.option("--max-pages", type=int, default=None, help="最多翻页数")
@click.option("--interval", type=float, default=None, help="请求间隔秒")
@click.option("--detail/--no-detail", default=None, help="是否再调详情接口补全")
def search_cmd(
    keywords: str,
    types: str,
    city: str,
    citylimit: bool,
    api_key: Optional[str],
    config_path: Optional[Path],
    output_dir: Optional[Path],
    fmt: str,
    max_pages: Optional[int],
    interval: Optional[float],
    detail: Optional[bool],
) -> None:
    """按城市 + 关键字/分类采集商户。"""
    if not keywords and not types:
        raise click.ClickException("请至少提供 --keywords 或 --types 之一")

    cfg = _load_config(config_path)
    key = _resolve_key(api_key)
    client = AmapClient(
        api_key=key,
        request_interval=interval if interval is not None else float(cfg["request_interval"]),
    )
    collector = MerchantCollector(
        client=client,
        page_size=int(cfg["page_size"]),
        max_pages=max_pages if max_pages is not None else int(cfg["max_pages"]),
        fetch_detail=detail if detail is not None else bool(cfg["fetch_detail"]),
    )

    click.echo(f"开始采集：city={city} keywords={keywords!r} types={types!r}")
    try:
        collector.collect_by_keyword(
            keywords=keywords,
            city=city,
            types=types,
            citylimit=citylimit,
            on_progress=lambda msg: click.echo(msg),
        )
        if collector.fetch_detail:
            collector.enrich_details(on_progress=lambda msg: click.echo(msg))
    except AmapAPIError as exc:
        raise click.ClickException(str(exc)) from exc

    _write_outputs(collector, cfg, output_dir, fmt, "search", city, keywords, types)


@main.command("around")
@click.option("--location", "-l", default=None, help="中心点 经度,纬度")
@click.option("--address", "-a", default=None, help="中心地址（自动地理编码）")
@click.option("--city", "-c", default="", help="地理编码时的城市限定")
@click.option("--keywords", "-k", default="", help="关键字")
@click.option("--types", "-t", default="", help="POI 分类编码")
@click.option("--radius", type=int, default=3000, help="半径（米），最大约 50000")
@click.option("--key", "api_key", default=None)
@click.option("--config", "config_path", type=click.Path(path_type=Path), default=None)
@click.option("--output-dir", type=click.Path(path_type=Path), default=None)
@click.option("--format", "fmt", type=click.Choice(["csv", "json", "both"]), default="both")
@click.option("--max-pages", type=int, default=None)
@click.option("--interval", type=float, default=None)
@click.option("--detail/--no-detail", default=None)
@click.option("--grid", type=int, default=1, help="网格边长，1=单点，3=3x3")
@click.option("--grid-km", type=float, default=2.0, help="网格间距（公里）")
def around_cmd(
    location: Optional[str],
    address: Optional[str],
    city: str,
    keywords: str,
    types: str,
    radius: int,
    api_key: Optional[str],
    config_path: Optional[Path],
    output_dir: Optional[Path],
    fmt: str,
    max_pages: Optional[int],
    interval: Optional[float],
    detail: Optional[bool],
    grid: int,
    grid_km: float,
) -> None:
    """按中心点周边采集；可用 --grid 做简易网格扩大覆盖。"""
    if not location and not address:
        raise click.ClickException("请提供 --location 或 --address")
    if not keywords and not types:
        raise click.ClickException("请至少提供 --keywords 或 --types 之一")

    cfg = _load_config(config_path)
    key = _resolve_key(api_key)
    client = AmapClient(
        api_key=key,
        request_interval=interval if interval is not None else float(cfg["request_interval"]),
    )

    if not location:
        geos = client.geocode(address=address or "", city=city)
        if not geos:
            raise click.ClickException(f"地理编码失败，未找到地址：{address}")
        location = str(geos[0].get("location", ""))
        click.echo(f"地址解析：{address} -> {location} ({geos[0].get('formatted_address', '')})")

    collector = MerchantCollector(
        client=client,
        page_size=int(cfg["page_size"]),
        max_pages=max_pages if max_pages is not None else int(cfg["max_pages"]),
        fetch_detail=detail if detail is not None else bool(cfg["fetch_detail"]),
    )

    try:
        if grid <= 1:
            collector.collect_around(
                location=location,
                keywords=keywords,
                types=types,
                radius=radius,
                on_progress=lambda msg: click.echo(msg),
            )
        else:
            collector.collect_grid(
                center=location,
                keywords=keywords,
                types=types,
                radius=radius,
                grid_km=grid_km,
                grid_size=grid,
                on_progress=lambda msg: click.echo(msg),
            )
        if collector.fetch_detail:
            collector.enrich_details(on_progress=lambda msg: click.echo(msg))
    except AmapAPIError as exc:
        raise click.ClickException(str(exc)) from exc

    _write_outputs(
        collector, cfg, output_dir, fmt, "around", city or "loc", keywords, types
    )


@main.command("types")
def types_cmd() -> None:
    """打印常用商户分类编码提示。"""
    samples = [
        ("050000", "餐饮服务"),
        ("050100", "中餐厅"),
        ("050500", "快餐厅"),
        ("060000", "购物服务"),
        ("060100", "商场"),
        ("070000", "生活服务"),
        ("071100", "美容美发店"),
        ("080000", "体育休闲服务"),
        ("100000", "住宿服务"),
        ("140000", "科教文化服务"),
        ("170000", "公司企业"),
        ("190000", "地名地址信息"),
    ]
    click.echo("常用 POI typecode（完整表见高德开放平台）：")
    for code, name in samples:
        click.echo(f"  {code}  {name}")
    click.echo("文档：https://lbs.amap.com/api/webservice/download")


@main.command("southwest")
@click.option("--key", "api_key", default=None, help="高德 Web 服务 Key")
@click.option("--config", "config_path", type=click.Path(path_type=Path), default=None)
@click.option("--output-dir", type=click.Path(path_type=Path), default=None)
@click.option("--format", "fmt", type=click.Choice(["csv", "json", "both"]), default="both")
@click.option("--max-pages", type=int, default=None, help="每个关键字最多翻页数")
@click.option("--interval", type=float, default=None, help="请求间隔秒")
@click.option(
    "--city",
    "cities",
    multiple=True,
    help="覆盖默认西南四城，可重复传入，如 --city 成都 --city 重庆",
)
@click.option(
    "--landline-only/--keep-all-phones",
    default=True,
    help="默认只保留含座机号的商户，tel 字段仅输出座机",
)
@click.option(
    "--exclude-brand",
    multiple=True,
    default=EXCLUDE_BRANDS,
    show_default=True,
    help="商户名包含即排除，可重复",
)
def southwest_cmd(
    api_key: Optional[str],
    config_path: Optional[Path],
    output_dir: Optional[Path],
    fmt: str,
    max_pages: Optional[int],
    interval: Optional[float],
    cities: tuple,
    landline_only: bool,
    exclude_brand: tuple,
) -> None:
    """西南四城：五金店 / 家装 / 家居 / 涂料；排除立邦；默认只留座机号。"""
    cfg = _load_config(config_path)
    key = _resolve_key(api_key)
    city_list = cities or SOUTHWEST_CITIES
    jobs = iter_jobs(cities=tuple(city_list))

    client = AmapClient(
        api_key=key,
        request_interval=interval if interval is not None else float(cfg["request_interval"]),
    )
    collector = MerchantCollector(
        client=client,
        page_size=int(cfg["page_size"]),
        max_pages=max_pages if max_pages is not None else int(cfg["max_pages"]),
        fetch_detail=False,
    )

    click.echo(
        f"任务数 {len(jobs)} | 城市={','.join(city_list)} | "
        f"品类={','.join(CATEGORY_KEYWORDS.keys())} | "
        f"排除品牌={','.join(exclude_brand) or '无'} | "
        f"座机过滤={'开' if landline_only else '关'}"
    )

    try:
        for i, job in enumerate(jobs, start=1):
            click.echo(
                f"[{i}/{len(jobs)}] {job['city']} / {job['category']} / {job['keyword']}"
            )
            before = {r["id"] for r in collector.records}
            collector.collect_by_keyword(
                keywords=job["keyword"],
                city=job["city"],
                citylimit=True,
                on_progress=lambda msg: click.echo(f"  {msg}"),
            )
            # 给本轮新入库记录打上 keyword / category 标记
            for rec in collector.records:
                if rec["id"] not in before:
                    rec["keyword"] = job["keyword"]
                    rec["category"] = job["category"]
                elif not rec.get("keyword"):
                    rec["keyword"] = job["keyword"]
                    rec["category"] = job["category"]
    except AmapAPIError as exc:
        raise click.ClickException(str(exc)) from exc

    raw_count = len(collector.records)
    brands = exclude_brand or DEFAULT_EXCLUDE_NAME_KEYWORDS
    filtered = filter_records(
        collector.records,
        landline_only=landline_only,
        exclude_name_keywords=brands,
    )
    click.echo(f"原始唯一商户 {raw_count} -> 过滤后 {len(filtered)}")

    out_dir = Path(output_dir or cfg["output_dir"])
    stem = _stamp_name("southwest", "西南4城", "五金家装家居涂料", "landline")
    _dump_records(filtered, out_dir, stem, fmt, empty_hint="过滤后无数据（无座机或均被品牌排除）")


@main.command("filter-landline")
@click.argument("input_path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None)
@click.option(
    "--exclude-brand",
    multiple=True,
    default=EXCLUDE_BRANDS,
    show_default=True,
)
def filter_landline_cmd(
    input_path: Path,
    output: Optional[Path],
    exclude_brand: tuple,
) -> None:
    """对已有 CSV/JSON 只保留座机号，并排除指定品牌名。"""
    import csv
    import json

    if input_path.suffix.lower() == ".json":
        records = json.loads(input_path.read_text(encoding="utf-8"))
    else:
        with input_path.open("r", encoding="utf-8-sig", newline="") as fh:
            records = list(csv.DictReader(fh))

    filtered = filter_records(
        records,
        landline_only=True,
        exclude_name_keywords=exclude_brand or DEFAULT_EXCLUDE_NAME_KEYWORDS,
    )
    out = output or input_path.with_name(input_path.stem + "_landline" + input_path.suffix)
    if out.suffix.lower() == ".json":
        export_json(filtered, out)
    else:
        export_csv(filtered, out)
    click.echo(f"{len(records)} -> {len(filtered)} 条，已写入 {out}")


def _write_outputs(
    collector: MerchantCollector,
    cfg: Dict[str, Any],
    output_dir: Optional[Path],
    fmt: str,
    prefix: str,
    city: str,
    keywords: str,
    types: str,
    *,
    landline_only: bool = True,
    exclude_brands: tuple = EXCLUDE_BRANDS,
) -> None:
    records = collector.records
    if landline_only or exclude_brands:
        before = len(records)
        records = filter_records(
            records,
            landline_only=landline_only,
            exclude_name_keywords=exclude_brands,
        )
        click.echo(f"过滤座机/品牌：{before} -> {len(records)}")

    out_dir = Path(output_dir or cfg["output_dir"])
    stem = _stamp_name(prefix, city, keywords, types)
    _dump_records(records, out_dir, stem, fmt)


def _dump_records(
    records: list,
    out_dir: Path,
    stem: str,
    fmt: str,
    empty_hint: str = "未采集到商户数据。请检查关键字/城市/Key 权限与配额。",
) -> None:
    if not records:
        click.echo(empty_hint)
        sys.exit(2)

    written = []
    if fmt in ("csv", "both"):
        written.append(export_csv(records, out_dir / f"{stem}.csv"))
    if fmt in ("json", "both"):
        written.append(export_json(records, out_dir / f"{stem}.json"))

    click.echo(f"完成：唯一商户 {len(records)} 条")
    for path in written:
        click.echo(f"  -> {path}")


if __name__ == "__main__":
    main()
