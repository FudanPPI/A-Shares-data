# 股票数据采集与分析系统

基于 akshare + DuckDB 的股票数据采集、存储和分析系统。

## 数据配置
本项目只采集了部分股票相关数据，可以根据需要配置不同股票列表获取数据，配置方式在 `src/config.py` 中的 `STOCK_CODES` 列表。

## 功能特点

### 数据采集
- **日线行情**：开盘价、收盘价、最高价、最低价、成交量、成交额、复权因子
- **财务报表**：利润表、资产负债表、现金流量表（含扣非归母净利润、利息支出等详细指标）
- **公告数据**：历史公告列表
- **分红数据**：分红记录
- **股本数据**：总股本、流通股本等
- **北向资金**：北向资金流入流出
- **融资融券**：融资融券余额
- **龙虎榜**：龙虎榜上榜记录及详细交易数据

### 指标计算
- **盈利能力**：ROE（净资产收益率）、ROA（总资产收益率）、毛利率、净利率（归母/扣非）
- **成长能力**：营收/净利润同比增速、3年复合增长率
- **杜邦分析**：三层分解（净利率 × 总资产周转率 × 权益乘数）
- **营运能力**：存货/应收/应付周转率、周转天数、现金周期
- **现金流质量**：盈利现金保障倍数、自由现金流（FCF）、FCF利润覆盖率、现金利息保障倍数
- **技术指标**：MA、MACD、RSI、KDJ、BOLL、布林带等

### 口径支持
- 年度口径（年报）
- TTM 口径（滚动12个月）

## 项目结构

```
Stockdata/
├── src/                    # 核心代码
│   ├── config.py           # 配置文件
│   ├── main.py             # 采集主入口
│   ├── scheduler.py        # 流程调度
│   ├── collector/          # 数据采集模块
│   ├── database/           # 数据库操作
│   └── indicators/         # 指标计算
├── api/                    # REST API 服务
│   └── main.py             # FastAPI 应用
├── data/                   # 数据存储
│   ├── stock_data.duckdb       # DuckDB数据库
│   ├── parquet/               # Parquet持久化
│   ├── samples/               # 数据采样
│   └── backups/               # 数据库备份
├── logs/                   # 日志
│   └── stock_collector.log      # 运行日志
├── scripts/                # 脚本
└── tests/                  # 测试
```

## 快速开始

### 环境准备
```bash
pip install -r requirements.txt
# 或单独安装
pip install akshare duckdb pandas fastapi uvicorn
```

### 配置股票列表
编辑 `src/config.py`：
```python
STOCK_CODES = [
    "sh600519",  # 贵州茅台
    "sh513700",  # ETF（支持）
    # 添加更多代码
]
START_DATE = "20160510"
```

### 运行数据采集
```bash
cd Stockdata
python -m src.main
```

### 启动 REST API 服务
```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```
访问 http://localhost:8000/docs 查看 Swagger 文档。

---

## REST API 接口说明

### 服务启动
```bash
# 启动API服务
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# 访问文档
http://localhost:8000/docs  # Swagger UI
http://localhost:8000/redoc # Redoc
```

### 公共接口
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 服务健康检查 |
| `/api/stocks` | GET | 获取所有股票列表 |
| `/api/latest` | GET | 获取最新数据日期（支持 `stock_code` 参数） |

### 行情与基本面接口
| 接口 | 方法 | 说明 | 支持参数 |
|------|------|------|----------|
| `/api/daily/{stock_code}` | GET | 日线行情 | `start_date`, `end_date`, `limit` |
| `/api/financial/{stock_code}` | GET | 财务报表 | `start_date`, `end_date`, `report_type` |
| `/api/indicators/technical/{stock_code}` | GET | 技术指标 | `start_date`, `end_date`, `limit` |
| `/api/indicators/financial/{stock_code}` | GET | 财务指标 | `start_date`, `end_date` |
| `/api/indicators/valuation/{stock_code}` | GET | 估值指标 | `start_date`, `end_date`, `limit` |

### 资金与交易接口
| 接口 | 方法 | 说明 | 支持参数 |
|------|------|------|----------|
| `/api/northbound/{stock_code}` | GET | 北向资金 | `start_date`, `end_date`, `limit` |
| `/api/margin/{stock_code}` | GET | 融资融券数据 | `start_date`, `end_date`, `limit` |
| `/api/dragon/{stock_code}` | GET | 龙虎榜数据 | `start_date`, `end_date`, `limit` |

### 基础信息接口
| 接口 | 方法 | 说明 | 支持参数 |
|------|------|------|----------|
| `/api/dividends/{stock_code}` | GET | 分红数据 | — |
| `/api/announcements/{stock_code}` | GET | 公告数据 | `limit` |
| `/api/capital/{stock_code}` | GET | 股本数据 | — |
| `/api/industry/{stock_code}` | GET | 股票所属行业 | — |
| `/api/industry/list` | GET | 获取所有行业列表 | — |
| `/api/industry/{industry_name}/stocks` | GET | 获取某行业下的所有股票 | — |

### 参数说明
- `start_date` / `end_date`: 日期格式 `YYYY-MM-DD`
- `limit`: 返回条数，默认 10000，最大 100000
- `report_type`: 财务报表类型，可选 `all`/`income`/`balance`/`cashflow`

### 返回格式
```json
{
  "stock_code": "sh600519",
  "count": 100,
  "data": [
    { "trade_date": "2026-05-12", "close": 1361.33, ... },
    ...
  ]
}
```

---

## 接口详细说明与示例

### 1. 公共接口

#### 健康检查
```bash
# 请求
GET /api/health

# 返回
{
  "status": "ok",
  "db_path": "E:\\AI\\data\\Stockdata\\data\\stock_data.duckdb"
}
```

#### 获取股票列表
```bash
# 请求
GET /api/stocks

# 返回
{
  "stocks": ["sh513700", "sh600089", "sh600276", ...],
  "count": 12
}
```

#### 获取最新数据日期
```bash
# 请求 - 所有股票
GET /api/latest

# 请求 - 单只股票
GET /api/latest?stock_code=sh600089

# 返回
{
  "latest": [
    {"stock_code": "sh600089", "latest_date": "2026-05-13"},
    ...
  ]
}
```

### 2. 融资融券接口（新增）

#### 获取融资融券数据
```bash
# 请求
GET /api/margin/{stock_code}
GET /api/margin/sh600089?start_date=2026-04-01&end_date=2026-05-13&limit=50

# 返回
{
  "stock_code": "sh600089",
  "count": 50,
  "data": [
    {
      "stock_code": "sh600089",
      "trade_date": "2026-05-13",
      "rz_balance": 123456789.0,
      "rz_change": 1234567.0,
      "rz_change_pct": 1.01,
      "rq_balance": null,
      "rq_change": null,
      "rq_change_pct": null,
      "total_balance": 123456789.0,
      "total_change": 1234567.0,
      "total_change_pct": 1.01
    },
    ...
  ]
}
```

**字段说明：**
- `rz_balance`: 融资余额
- `rz_change`: 融资余额变化
- `rz_change_pct`: 融资余额变化率
- `rq_balance`: 融券余额
- `total_balance`: 融资融券总余额

### 3. 龙虎榜接口（新增）

#### 获取龙虎榜数据
```bash
# 请求
GET /api/dragon/{stock_code}
GET /api/dragon/sh600089?start_date=2026-01-01&end_date=2026-05-13

# 返回
{
  "stock_code": "sh600089",
  "count": 0,
  "data": []
}
```

**字段说明：**
- `trade_date`: 上榜日期
- `list_type`: 上榜类型
- `reason`: 上榜原因
- `buy_amount`: 龙虎榜买入额
- `sell_amount`: 龙虎榜卖出额
- `net_amount`: 龙虎榜净买额

### 4. 行业信息接口（新增）

#### 获取单只股票行业
```bash
# 请求
GET /api/industry/{stock_code}
GET /api/industry/sh600887

# 返回
{
  "stock_code": "sh600887",
  "count": 1,
  "data": [
    {
      "stock_code": "sh600887",
      "industry_name": "饮料乳品",
      "industry_level": "东财行业",
      "source": "Eastmoney",
      "update_date": "2026-05-14"
    }
  ]
}
```

#### 获取行业列表
```bash
# 请求
GET /api/industry/list

# 返回
{
  "count": 2,
  "data": [
    {
      "industry_name": "通用设备",
      "stock_count": 1,
      "latest_update": "2026-05-14"
    },
    {
      "industry_name": "饮料乳品",
      "stock_count": 1,
      "latest_update": "2026-05-14"
    }
  ]
}
```

#### 获取行业下的股票
```bash
# 请求
GET /api/industry/{industry_name}/stocks
GET /api/industry/饮料乳品/stocks

# 返回
{
  "industry_name": "饮料乳品",
  "count": 1,
  "data": [
    {
      "stock_code": "sh600887",
      "industry_name": "饮料乳品",
      "source": "Eastmoney",
      "update_date": "2026-05-14"
    }
  ]
}
```

### 5. 股本接口（新增）

#### 获取股本数据
```bash
# 请求
GET /api/capital/{stock_code}

# 返回
{
  "stock_code": "sh600089",
  "count": 0,
  "data": []
}
```

---

## Python 调用示例

### 完整示例代码
```python
import requests
import json

base_url = "http://127.0.0.1:8000"

# 1. 获取股票列表
print("=== 股票列表 ===")
stocks_resp = requests.get(f"{base_url}/api/stocks").json()
print(f"共 {stocks_resp['count']} 只股票: {stocks_resp['stocks']}")

# 2. 获取融资融券数据
stock_code = "sh600089"
print(f"\n=== {stock_code} 融资融券数据 ===")
margin_resp = requests.get(
    f"{base_url}/api/margin/{stock_code}",
    params={"limit": 5}
).json()
print(f"共 {margin_resp['count']} 条数据")
for item in margin_resp['data']:
    print(f"{item['trade_date']}: 融资余额 {item['rz_balance']:,.0f}")

# 3. 获取行业信息
print(f"\n=== {stock_code} 行业信息 ===")
industry_resp = requests.get(f"{base_url}/api/industry/{stock_code}").json()
if industry_resp['count'] > 0:
    print(f"所属行业: {industry_resp['data'][0]['industry_name']}")
else:
    print("暂无行业信息")

# 4. 获取行业列表
print("\n=== 行业列表 ===")
industry_list = requests.get(f"{base_url}/api/industry/list").json()
for industry in industry_list['data']:
    print(f"- {industry['industry_name']}: {industry['stock_count']} 只股票")

# 5. 获取日线行情
print(f"\n=== {stock_code} 最近3天行情 ===")
daily_resp = requests.get(
    f"{base_url}/api/daily/{stock_code}",
    params={"limit": 3}
).json()
for item in daily_resp['data']:
    print(f"{item['trade_date']}: 开盘 {item['open']}, 收盘 {item['close']}, 涨跌 {item['pct_chg']}%")
```

### 其他接口调用示例

#### 获取财务指标
```python
resp = requests.get(
    f"{base_url}/api/indicators/financial/sh600519",
    params={"start_date": "2025-01-01"}
).json()
print(f"财务指标数: {resp['count']}")
```

#### 获取北向资金
```python
resp = requests.get(
    f"{base_url}/api/northbound/sh600089",
    params={"limit": 10}
).json()
```

#### 获取技术指标
```python
resp = requests.get(
    f"{base_url}/api/indicators/technical/sh600089",
    params={"start_date": "2026-05-01"}
).json()
```

## 数据库表结构

| 表名 | 说明 |
|------|------|
| stock_daily | 股票日线行情数据 |
| financial_statements | 财务报表原始数据 |
| financial_intermediate | 财务指标计算结果 |
| technical_indicators | 技术指标 |
| valuation_indicators | 估值指标 |
| announcements | 公告数据 |
| dividends | 分红数据 |
| stock_capital | 股本数据 |
| northbound_flow | 北向资金 |
| margin_trading | 融资融券 |
| dragon_tiger | 龙虎榜 |
| dragon_tiger_detail | 龙虎榜详细 |
| stock_industry | 股票行业信息 |
| column_metadata | 元数据 |
| update_log | 更新记录 |

## 使用示例

### 查询财务数据
```python
import duckdb
conn = duckdb.connect('data/stock_data.duckdb')

# 查询贵州茅台的财务指标
df = conn.execute("""
    SELECT report_date, roe_annual, roa_annual, revenue_yoy_annual
    FROM financial_intermediate
    WHERE stock_code = 'sh600519' AND roe_annual IS NOT NULL
    ORDER BY report_date DESC
""").fetchdf()
print(df)
```

### 查询技术指标
```python
# 查询贵州茅台的日线和MA5
df = conn.execute("""
    SELECT trade_date, close, ma5, ma10, ma20, macd
    FROM stock_daily d LEFT JOIN technical_indicators t
    ON d.stock_code = t.stock_code AND d.trade_date = t.trade_date
    WHERE d.stock_code = 'sh600519'
    ORDER BY trade_date DESC LIMIT 100
""").fetchdf()
```

## 依赖
- akshare：金融数据采集
- duckdb：列式数据库
- pandas：数据处理
- fastapi：REST API 框架
- uvicorn：ASGI 服务器
- logging：日志

## 许可证
本项目仅供学习研究使用。
