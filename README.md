# Aben Financial Data Cache

面向内在价值计算器的轻量股票数据缓存。前端只读取标准化 JSON，正向 DCF 与
Reverse DCF 均在本地计算，不把用户的增长率、折现率等判断上传到数据层。

## 当前股票池

- S&P 500：503 个证券，包含 SEC CIK。
- Invesco QQQ / Nasdaq-100：101 个证券代码。
- SSE 50 / 上证50：50 个证券，来自中证指数官方成份股文件。
- CSI 300 / 沪深300：300 个证券，来自中证指数官方成份股文件。
- CSI 500 / 中证500：500 个证券，来自中证指数官方成份股文件。
- CSI 800 / 中证800：800 个证券，来自中证指数官方成份股文件。
- CSI 1000 / 中证1000：1000 个证券，来自中证指数官方成份股文件。
- SSE STAR 50 / 科创50：50 个证券，来自中证指数官方成份股文件。
- SSE STAR 100 / 科创100：100 个证券，来自中证指数官方成份股文件。
- ChiNext Index / 创业板指：100 个证券，来自国证指数当前样本快照。
- Hang Seng TECH：30 个证券，当前为可审计快照。
- 上述指数包含大量重叠成份股；各指数重叠证券按代码去重，唯一证券数量以
  `universe/stocks.json` 为准。

运行以下命令可重新同步名单：

```bash
python -m scripts.sync_universe
```

标准化代码采用 yfinance 格式，例如 `AAPL`、`600519.SS`、`0700.HK`。

## 数据来源

优先级设计：

1. SEC EDGAR：美国公司年度财报主来源。
2. yfinance：当前价格、季度 TTM、非美国公司财报及 SEC 失败时的备用来源。
3. Stooq：规划中的价格备用源；由于当前下载接口存在浏览器验证，尚未启用自动回退。

SEC 请求必须设置可识别的 User-Agent：

```bash
cp .env.example .env
# then edit .env:
# SEC_USER_AGENT="Your Name your-email@example.com"
```

GitHub Actions 中应创建同名仓库 Secret：`SEC_USER_AGENT`。未配置时系统会明确标记
警告，并只使用 yfinance；不会假装已经使用 SEC 数据。

## JSON 数据

每只股票保存为：

```text
cache/dcf/<SYMBOL>.json
```

内容包括：

- 当前价格、股本、市值、现金、债务和企业价值。
- TTM Revenue、Net Income、Diluted EPS、Operating Cash Flow、CapEx 和 FCF。
- SEC/yfinance 可取得的年度财务数据，以及已入库的更早年度。
- Revenue/share、FCF/share、净利率和现金转换率。
- 1/3/5/10 年 Revenue、Earnings、FCF CAGR。
- 1/3/5/10 年平均净利率、现金转换率、P/E 和 P/FCF。
- 三种正向估值模型及 Reverse DCF 的字段合同。
- `historical_metrics.available_growth_windows` 告诉前端哪些历史周期真实可用。

仓库不保存日线 OHLC。脚本只在更新时临时读取历史价格，并缓存各财年末价格，用于计算
历史 P/E 与 P/FCF。

长期历史会追加保存为：

```text
cache/history/dcf/<SYMBOL>/<TIMESTAMP>.json
cache/history/prices/<YYYY-MM-DD>.json
```

- `cache/dcf/<SYMBOL>.json` 永远是前端读取的最新快照。
- 每次财报快照被覆盖前，旧 JSON 会归档到 `cache/history/dcf/`。
- 每日行情任务会写入轻量价格历史文件，长期形成自己的价格时间序列。
- 年度财务数据按年份合并，新数据优先，但不会因为某次免费源少返回几年就删除旧年份。

## 股本与每股指标口径

- 当前 TTM 每股收入、每股 FCF：最近四个季度总额 ÷ 最新可取得股本。
- 当前股本优先来自 yfinance 资产负债表里的普通股数/发行股数，缺失时回退到最近季度的
  稀释或基本加权股数。
- 每日价格刷新会尽量同步 yfinance fast_info 里的最新股本，并用它重算市值和企业价值。
- 年度历史 Revenue/share、FCF/share：当年年度总额 ÷ 当年财报里的 diluted_shares。
- EPS 优先使用财报披露的 diluted EPS；缺失时才用净利润 ÷ 股数估算。

因此：当前估值基准反映“最新股本下的 TTM 经营能力”，历史增长率反映“各年度真实稀释后每股
变化”。这能更好处理回购、增发、拆股和股权激励摊薄。

## 正向估值

核心公式位于 `core/dcf.py`：

```text
未来每股指标 = 当前每股指标 × (1 + 增长率)^预测年数
未来价格 = 未来每股指标 × 利润率 × 终值倍数
内在价值 = 未来价格 ÷ (1 + 折现率)^预测年数
```

支持：

- Revenue Growth：Revenue/share × 净利率 × 终值 P/E。
- Earnings Growth：EPS × 终值 P/E。
- FCF Growth：FCF/share × 终值 P/FCF。

Reverse DCF 使用同一公式反解市场价格隐含的复合增长率，因此正向和反向计算能够通过
单元测试验证互逆。

## 本地运行

需要 Python 3.9 或更高版本：

```bash
python -m pip install -r requirements.txt
python -m scripts.update_cache --symbols AAPL 600519.SS 0700.HK
python -m scripts.rebuild_manifest
python -m scripts.validate_cache --symbols AAPL 600519.SS 0700.HK
```

也可以按指数或分片更新：

```bash
python -m scripts.update_cache --index sp500
python -m scripts.update_cache --shard-index 0 --shard-count 24
```

## 自动更新

- `update-financial-cache.yml`：每周同步指数名单，24 个分片刷新财报并统一发布。
- `update-prices.yml`：交易日每日批量刷新已有缓存的当前价格。

财报任务允许个别免费源失败，但发布前要求至少 80% 股票池覆盖率。旧的成功缓存不会因
单次抓取失败被覆盖，已入库的历史年份和历史快照会继续保留。

财报刷新支持三种模式，避免每次都全量重跑：

- `stale`：默认模式，只刷新超过指定天数的缓存，当前默认 7 天。
- `missing`：只补缺失 JSON，适合新增指数成份股后快速补洞。
- `force`：强制全量刷新，适合重大逻辑升级或数据源修复后手动运行。

本地可用：

```bash
python -m scripts.update_cache --stale-days 7
python -m scripts.update_cache --missing-only
python -m scripts.update_cache --force
```

关于 5/10 年数据来源、Power BI 页面和各市场补全策略，见
`docs/data-source-strategy.md`。

## 数据 API

```text
https://raw.githubusercontent.com/310606239-debug/aben-financial-data-cache/main/cache/manifest.json
https://raw.githubusercontent.com/310606239-debug/aben-financial-data-cache/main/cache/dcf/AAPL.json
```

GitHub Raw 适合调试，不建议让小程序长期直连。推荐使用 `worker/` 里的
Cloudflare Worker 作为稳定数据网关：

```text
GET /health
GET /manifest
GET /dcf/AAPL
```

这样小程序只绑定你自己的域名，Worker 负责 CDN 缓存、CORS 和后续 R2/KV 备份切换；
DCF 计算仍在小程序或浏览器本地完成。部署取舍见 `docs/deployment-strategy.md`。

## Web 原型

`web/` 包含零依赖的响应式估值工作台，支持：

- Revenue、Earnings、FCF 三种正向估值。
- Reverse DCF 隐含增长率。
- 5 年/10 年、增长率、利润率、终值倍数和折现率调整。
- 美元、人民币和港币股票切换。
- 历史 CAGR、估值倍数和缺失周期提示。

本地预览：

```bash
python -m http.server 4173
```

然后打开 `http://localhost:4173/web/`。

> 免费数据可能延迟、缺失或受再分发条款限制。本缓存适合研究工具，重要决策应回到公司
> 披露、SEC 文件或持牌数据源复核。
