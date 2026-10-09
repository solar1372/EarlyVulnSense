# 高德地图商户数据采集

基于[高德开放平台 Place Web 服务 API](https://lbs.amap.com/api/webservice/guide/api/search) 的商户 / POI 采集工具。只走官方接口，需要你自己申请 Web 服务 Key。

## 功能

- **城市关键字搜索**：按城市 + 关键词 / 分类翻页采集
- **周边搜索**：按坐标或地址半径采集
- **西南四城预设**：成都 / 重庆 / 昆明 / 贵阳 × 五金店、家装、家居、涂料
- **座机过滤**：只保留含座机号的商户，`tel` 仅输出座机（手机号剔除）
- **品牌排除**：默认排除商户名含「立邦」
- **去重合并**：按 POI `id` 去重
- **导出**：CSV（Excel 可直接打开）与 JSON

## 准备 Key

1. 打开 [高德开放平台控制台](https://console.amap.com/dev/key/app)
2. 创建应用，添加 **Web 服务** Key
3. 复制 Key：

```bash
cp .env.example .env
# 编辑 .env，填入 AMAP_API_KEY=...
```

请遵守高德服务条款与配额限制；本工具默认请求间隔 0.25s，可用 `--interval` 调整。

## 安装

```bash
cd amap-merchant-collector
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 用法

```bash
# 西南四城：五金/家装/家居/涂料，排除立邦，只要座机号
export AMAP_API_KEY=你的Web服务Key
python -m amap_collector southwest

# 只跑部分城市
python -m amap_collector southwest --city 成都 --city 重庆

# 对已有结果再过滤座机
python -m amap_collector filter-landline ./output/xxx.csv

# 城市内关键字采集（默认也会座机过滤）
python -m amap_collector search -c 成都 -k 五金店

# 查看常用分类编码
python -m amap_collector types
```

### 座机判定规则

- 保留：`0` 开头区号 + 7~8 位号码，如 `028-85551234`、`02386661234`
- 剔除：手机号 `1[3-9]xxxxxxxxx`、以及 `400`/`800` 热线
- 若 `tel` 同时含手机与座机，只输出座机，原值写入 `tel_raw`

常用参数：

| 参数 | 说明 |
|------|------|
| `--key` | 临时指定 Key（否则读 `AMAP_API_KEY`） |
| `--max-pages` | 最大翻页数 |
| `--interval` | 请求间隔（秒） |
| `--format` | `csv` / `json` / `both` |
| `--output-dir` | 输出目录，默认 `./output` |
| `--detail` | 额外调用详情接口补全字段 |

## 输出字段

`id, name, type, typecode, tel, address, pname, cityname, adname, lng, lat, rating, cost, tag, website, photos, ...`

## 说明

- 单次关键字搜索受高德分页上限约束，大数据量请拆分关键词 / 行政区，或使用 `around --grid`。
- 不提供、也不包含任何非官方抓取、逆向或绕过访问控制的实现。
- 采集到的公开商户信息请合法合规使用，勿用于骚扰或违法用途。
