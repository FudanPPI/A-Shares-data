# 股票数据 API 接口文档

> **Base URL**: `http://localhost:8001`
> **Swagger 文档**: `http://localhost:8001/docs`
> **数据格式**: JSON
> **日期格式**: `YYYY-MM-DD`（ISO 8601）

---

## 一、接口清单

| # | 接口 | 方法 | 说明 |
|---|------|------|------|
| 1 | `/api/health` | GET | 健康检查 |
| 2 | `/api/stocks` | GET | 股票列表 |
| 3 | `/api/latest` | GET | 各股票最新数据日期 |
| 4 | `/api/daily/{stock_code}` | GET | 日线行情 |
| 5 | `/api/indicators/technical/{stock_code}` | GET | 技术指标 |
| 6 | `/api/indicators/valuation/{stock_code}` | GET | 估值指标 |
| 7 | `/api/indicators/financial/{stock_code}` | GET | 财务指标 |
| 8 | `/api/financial/{stock_code}` | GET | 财务原始报表 |
| 9 | `/api/northbound/{stock_code}` | GET | 北向资金 |
| 10 | `/api/margin/{stock_code}` | GET | 融资融券 |
| 11 | `/api/capital/{stock_code}` | GET | 股本数据 |
| 12 | `/api/dividends/{stock_code}` | GET | 分红数据 |
| 13 | `/api/announcements/{stock_code}` | GET | 公告数据 |
| 14 | `/api/dragon/{stock_code}` | GET | 龙虎榜 |
| 15 | `/api/industry/{stock_code}` | GET | 个股行业信息 |
| 16 | `/api/industry/list` | GET | 行业列表 |
| 17 | `/api/industry/{industry_name}/stocks` | GET | 行业内股票 |
| 18 | `/api/master` | GET | 股票主数据 |
| 19 | `/api/master/{stock_code}` | GET | 单只股票主数据 |
| 20 | `/api/metadata/tables` | GET | 元数据-所有表定义 |
| 21 | `/api/metadata/tables/{table_name}` | GET | 元数据-单表定义 |
| 22 | `/api/metadata/search?q=` | GET | 元数据搜索 |
| 23 | `/api/quality` | GET | 质量检查 |
| 24 | `/api/quality/history` | GET | 质量检查历史 |

---

## 二、统一响应格式

### 列表接口
```json
{
  "stock_code": "sz002272",
  "count": 100,
  "data": [ { ... }, { ... } ]
}
```

### 单条/聚合接口
直接返回对象，如：
```json
{
  "status": "ok",
  "db_path": "..."
}
```

---

## 三、股票代码格式

**重要**：股票代码必须带交易所前缀，**小写**：

| 交易所 | 前缀 | 示例 |
|--------|------|------|
| 上海主板 | `sh` | `sh600519`（贵州茅台） |
| 深圳主板/中小板 | `sz` | `sz002272`（川润股份） |
| 创业板 | `sz` | `sz300750` |
| 科创板 | `sh` | `sh688981` |

**错误示例**：`600519`、`SH600519`、`002272`

---

## 四、各接口字段详解

### 1. `/api/daily/{stock_code}` 日线行情

**参数**：
- `start_date` (可选): 开始日期 YYYY-MM-DD
- `end_date` (可选): 结束日期 YYYY-MM-DD
- `limit` (可选): 最大返回条数，默认 10000，最大 100000

**返回字段**：

| 字段 | 类型 | 说明 | 状态 |
|------|------|------|------|
| stock_code | string | 股票代码 | ✓ |
| trade_date | string | 交易日期 | ✓ |
| open | float | 开盘价 | ✓ |
| high | float | 最高价 | ✓ |
| low | float | 最低价 | ✓ |
| close | float | 收盘价 | ✓ |
| volume | int | 成交量（股） | ✓ |
| amount | float | 成交额（元） | ✓ |
| adjust_factor | float | 复权因子 | 可能为 null |
| prev_close | float | 前收盘价 | ✓ |
| change_pct | float | 涨跌幅（%） | ✓ |
| amplitude | float | 振幅（%） | ✓ |
| body_size | float | 实体大小 | ✓ |
| upper_shadow | float | 上影线 | ✓ |
| lower_shadow | float | 下影线 | ✓ |
| high_20 | float | 20日最高 | ✓ |
| low_20 | float | 20日最低 | ✓ |
| high_60 | float | 60日最高 | ✓ |
| low_60 | float | 60日最低 | ✓ |
| **turnover** | float | 换手率（%） | ⚠️ **当前恒为 null** |
| **outstanding_share** | int | 流通股本 | ⚠️ **当前恒为 null** |

> **已知问题**：`turnover`（换手率）和 `outstanding_share`（流通股本）字段存在但未填充数据。如需换手率，可调用 `/api/capital/{stock_code}` 获取总股本后自行计算：`换手率 = volume / total_shares × 100`。

---

### 2. `/api/indicators/technical/{stock_code}` 技术指标

**参数**：同日线接口

**返回字段**（共 35 个技术指标）：

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string | 股票代码 |
| trade_date | string | 交易日期 |
| ma5 / ma10 / ma20 / ma60 | float | 5/10/20/60日均线 |
| ema12 / ema26 | float | 12/26日指数均线 |
| boll_mid / boll_upper / boll_lower | float | 布林带中轨/上轨/下轨 |
| macd_dif / macd_dea / macd_hist | float | MACD 三线 |
| bias5 / bias10 / bias20 / bias60 | float | 乖离率 |
| rsi6 / rsi12 / rsi24 | float | RSI 指标 |
| kdj_k / kdj_d / kdj_j | float | KDJ 三线 |
| cci20 | float | CCI 指标 |
| wr14 | float | WR 指标 |
| atr14 | float | ATR 指标 |
| std20 | float | 20日标准差 |
| vol_ma5 / vol_ma10 | int | 成交量均线 |
| obv | int | OBV 指标 |
| mfi14 | float | MFI 指标 |
| vr | float | VR 指标 |
| dmi_pdi / dmi_mdi / dmi_adx / dmi_adxr | float | DMI 四线 |
| sar | float | SAR 抛物线 |
| wvad | float | WVAD 指标 |

> **说明**：技术指标数据完整，无缺失问题。用户报告中"MA5/MA20 缺失"应为调用方解析错误。

---

### 3. `/api/indicators/valuation/{stock_code}` 估值指标

**参数**：同日线接口

**返回字段**：

| 字段 | 类型 | 说明 | 备注 |
|------|------|------|------|
| stock_code | string | 股票代码 | |
| trade_date | string | 交易日期 | |
| pe_ttm | float | 市盈率TTM | 亏损时为负值 |
| pb | float | 市净率 | |
| ps_ttm | float | 市销率TTM | |
| dividend_yield | float | 股息率（%） | 可能为 null |
| roe | float | 净资产收益率 | 亏损时为负值 |
| pe_annual | float | 年度市盈率 | |
| ps_annual | float | 年度市销率 | |
| roe_ttm | float | ROE TTM | |
| roe_annual | float | 年度ROE | 可能为 null |
| used_report_date | string | 使用的财报日期 | |
| used_announcement_date | string | 使用的公告日期 | |

> **重要说明**：
> - **PE_TTM 为负值是正常现象**，表示公司亏损（如 sz002272 2026Q1 亏损，PE_TTM = -381）。调用方应判断 `pe_ttm < 0` 时标注"公司亏损，PE 不适用"，而非报错。
> - **没有 `pe` 字段**，只有 `pe_ttm` 和 `pe_annual`，请勿调用 `pe`。

---

### 4. `/api/indicators/financial/{stock_code}` 财务指标

**参数**：
- `start_date` / `end_date`：按 `report_date` 过滤

**返回字段**（共 88 个字段，关键字段如下）：

| 字段 | 类型 | 说明 | 状态 |
|------|------|------|------|
| stock_code | string | 股票代码 | ✓ |
| report_date | string | 报告期 | ✓ |
| report_type | string | 报告类型（合并期末） | ✓ |
| eps | float | 每股收益 | ✓ |
| bvps | float | 每股净资产 | ✓ |
| net_profit | float | 净利润 | ✓ |
| total_revenue | float | 营业总收入 | ✓ |
| operating_cost | float | 营业成本 | ✓ |
| gross_margin_annual | float | 毛利率（年度） | ✓ |
| gross_margin_ttm | float | 毛利率（TTM） | ✓ |
| net_margin_parent_annual | float | 净利率（年度） | ✓ |
| roe_annual / roe_ttm | float | ROE | ✓ |
| roa_annual / roa_ttm | float | ROA | ✓ |
| revenue_yoy_annual | float | 营收同比 | ✓ |
| net_profit_yoy_annual | float | 净利润同比 | ✓ |
| inventory_turnover_annual | float | 存货周转率 | ✓ |
| accounts_receivable_turnover_annual | float | 应收账款周转率 | ✓ |
| fcf_ttm | float | 自由现金流TTM | ✓ |
| **current_ratio** | - | 流动比率 | ❌ **不存在** |
| **quick_ratio** | - | 速动比率 | ❌ **不存在** |
| **gross_margin** | - | 毛利率（无后缀） | ❌ **不存在，请用 gross_margin_ttm** |

> **已知问题**：
> 1. **没有 `current_ratio`（流动比率）和 `quick_ratio`（速动比率）字段**。当前财务中间表未采集流动资产/流动负债数据，无法计算。调用方应将这两个指标标注为"数据源未提供"。
> 2. **毛利率字段名带后缀**：`gross_margin_annual`（年度毛利率）、`gross_margin_ttm`（TTM毛利率），**没有不带后缀的 `gross_margin` 字段**。

---

### 5. `/api/northbound/{stock_code}` 北向资金

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string | 股票代码 |
| trade_date | string | 交易日期 |
| net_inflow | float | 当日净流入（元） |
| holding_shares | int | 持股数量（股） |
| holding_value | float | 持股市值（元） |
| holding_ratio | float | 持股占比（%） |
| inflow_5d | float | 5日累计净流入 |
| inflow_10d | float | 10日累计净流入 |
| inflow_30d | float | 30日累计净流入 |

> ⚠️ **数据源已失效**：AKShare 北向资金接口已不可用，当前所有股票的北向资金数据可能为空（`count: 0`）。调用方应处理空数据情况，标注"北向资金数据暂不可用"。

---

### 6. `/api/margin/{stock_code}` 融资融券

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string | 股票代码 |
| trade_date | string | 交易日期 |
| rz_balance | float | 融资余额（元） |
| rz_change | float | 融资余额变动 |
| rz_change_pct | float | 融资余额变动百分比 |
| rq_balance | float | 融券余额（元） |
| rq_change | float | 融券余额变动 |
| rq_change_pct | float | 融券余额变动百分比 |
| total_balance | float | 融资融券余额合计 |
| total_change | float | 余额合计变动 |
| total_change_pct | float | 余额合计变动百分比 |

---

### 7. `/api/capital/{stock_code}` 股本数据

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string | 股票代码 |
| record_date | string | 记录日期 |
| total_shares | int | 总股本（股） |

> **注意**：日期字段是 `record_date`（不是 `trade_date`）。此表仅存总股本，**没有流通股本字段**。

---

### 8. `/api/dividends/{stock_code}` 分红数据

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string | 股票代码 |
| dividend_date | string | 除权除息日 |
| cash_per_share | float | 每股派息（元） |
| announcement_date | string | 公告日期 |

---

### 9. `/api/industry/{stock_code}` 行业信息

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string | 股票代码 |
| industry_name | string | 行业名称（如"C34通用设备制造业"） |
| industry_level | string | 分类级别（"证监会行业分类"） |
| source | string | 数据来源（"BaoStock"） |
| update_date | string | 更新日期 |

---

### 10. `/api/dragon/{stock_code}` 龙虎榜

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 记录ID |
| stock_code | string | 股票代码 |
| trade_date | string | 交易日期 |
| list_type | string | 上榜类型 |
| reason | string | 上榜原因 |
| buy_amount | float | 买入金额 |
| sell_amount | float | 卖出金额 |
| net_amount | float | 净额 |
| institution_buy_ratio | float | 机构买入占比 |
| institution_sell_ratio | float | 机构卖出占比 |
| institution_net_ratio | float | 机构净额占比 |

---

## 五、调用方常见问题与修复建议

### 问题 1：股价 = 0.0

**根因**：调用方取错字段或未正确解析嵌套结构。

**修复**：
```python
# 正确取法
resp = requests.get(f"{BASE_URL}/api/daily/{code}?limit=1").json()
if resp["count"] > 0:
    close = resp["data"][0]["close"]  # 取 data 数组的第一条的 close 字段
else:
    close = None  # 无数据
```

**验证**：`sz002272` 最新收盘价（2026-06-08）= **18.32**，非 0。

---

### 问题 2：MA5/MA20 缺失

**根因**：调用方可能调用了错误接口，或字段名拼写错误。

**修复**：
```python
# 技术指标在 /api/indicators/technical/ 接口，不在 /api/daily/
resp = requests.get(f"{BASE_URL}/api/indicators/technical/{code}?limit=1").json()
if resp["count"] > 0:
    ma5 = resp["data"][0]["ma5"]   # 小写 ma5
    ma20 = resp["data"][0]["ma20"] # 小写 ma20
```

**验证**：`sz002272` 的 ma5=19.38, ma20=20.97，数据完整。

---

### 问题 3：流动比率/速动比率 = 0

**根因**：API **不提供**这两个字段。

**修复**：调用方应移除对 `current_ratio`、`quick_ratio` 的依赖，或标注为"数据源未提供"。后续版本会补充。

---

### 问题 4：毛利率缺失

**根因**：字段名带后缀，调用方用了不带后缀的 `gross_margin`。

**修复**：
```python
# 错误
gross_margin = data["gross_margin"]  # KeyError

# 正确（推荐用 TTM 口径）
gross_margin = data.get("gross_margin_ttm")  # TTM 毛利率
# 或
gross_margin = data.get("gross_margin_annual")  # 年度毛利率
```

---

### 问题 5：PE_TTM 为负值

**根因**：公司亏损时 PE 为负是正常现象。

**修复**：
```python
pe_ttm = data["pe_ttm"]
if pe_ttm is None:
    pe_status = "无数据"
elif pe_ttm < 0:
    pe_status = "公司亏损，PE不适用"
else:
    pe_status = f"PE={pe_ttm:.2f}"
```

---

### 问题 6：北向资金缺失

**根因**：数据源（AKShare）接口已失效。

**修复**：
```python
resp = requests.get(f"{BASE_URL}/api/northbound/{code}").json()
if resp["count"] == 0:
    northbound_status = "北向资金数据暂不可用（数据源失效）"
else:
    northbound_data = resp["data"]
```

---

### 问题 7：换手率缺失

**根因**：`turnover` 字段当前恒为 null。

**临时修复**（调用方自行计算）：
```python
# 1. 获取总股本
capital_resp = requests.get(f"{BASE_URL}/api/capital/{code}").json()
total_shares = capital_resp["data"][0]["total_shares"] if capital_resp["count"] > 0 else None

# 2. 获取日线数据
daily_resp = requests.get(f"{BASE_URL}/api/daily/{code}?limit=1").json()
daily = daily_resp["data"][0]

# 3. 计算换手率
if total_shares and total_shares > 0:
    turnover = daily["volume"] / total_shares * 100  # 单位：%
else:
    turnover = None
```

---

## 六、字段命名约定

1. **全部小写 + 下划线**：如 `pe_ttm`、`gross_margin_annual`（非驼峰命名）
2. **日期字段**：`trade_date`（交易日期）、`report_date`（报告期）、`record_date`（记录日期）、`announcement_date`（公告日期）、`dividend_date`（除权日）
3. **后缀约定**：
   - `_ttm`：滚动十二个月（Trailing Twelve Months）
   - `_annual`：年度口径
   - `_q`：单季度
   - `_yoy`：同比
   - `_qoq`：环比
   - `_cagr_3y`：三年复合增长率

---

## 七、元数据查询接口

如需查询任意表的完整字段定义，调用：

```
GET /api/metadata/tables/{table_name}
```

示例：
```
GET /api/metadata/tables/financial_intermediate
```

返回该表所有字段的：字段名、显示名、描述、数据类型、是否可空、数据来源、计算公式、单位、示例值。

**搜索字段**：
```
GET /api/metadata/search?q=毛利率
```

---

## 八、快速验证脚本

```python
import requests

BASE = "http://localhost:8001"
code = "sz002272"

# 1. 日线（股价）
r = requests.get(f"{BASE}/api/daily/{code}?limit=1").json()
print(f"收盘价: {r['data'][0]['close']}")  # 18.32

# 2. 技术指标（MA5/MA20）
r = requests.get(f"{BASE}/api/indicators/technical/{code}?limit=1").json()
print(f"MA5: {r['data'][0]['ma5']}, MA20: {r['data'][0]['ma20']}")  # 19.38, 20.97

# 3. 估值（PE_TTM）
r = requests.get(f"{BASE}/api/indicators/valuation/{code}?limit=1").json()
print(f"PE_TTM: {r['data'][0]['pe_ttm']}")  # -381.00（亏损，正常）

# 4. 财务（毛利率）
r = requests.get(f"{BASE}/api/indicators/financial/{code}?limit=1").json()
print(f"毛利率TTM: {r['data'][0]['gross_margin_ttm']}")  # 有值
print(f"流动比率: {r['data'][0].get('current_ratio', '字段不存在')}")  # 字段不存在

# 5. 北向资金
r = requests.get(f"{BASE}/api/northbound/{code}").json()
print(f"北向资金条数: {r['count']}")  # 0（数据源失效）
```
