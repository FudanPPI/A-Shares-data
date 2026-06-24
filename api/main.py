import duckdb
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.metadata.data_dictionary import ALL_TABLES

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "stock_data.duckdb"

app = FastAPI(title="Stock Data API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def _get_conn(read_only: bool = True):
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def _rows_to_dicts(rows, columns):
    result = []
    for row in rows:
        d = {}
        for i, col in enumerate(columns):
            val = row[i]
            if isinstance(val, Decimal):
                val = float(val)
            elif isinstance(val, (date, datetime)):
                val = val.isoformat()
            d[col] = val
        result.append(d)
    return result


@app.get("/api/stocks")
def get_stocks():
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT DISTINCT stock_code FROM stock_daily ORDER BY stock_code"
        ).fetchall()
        return {"stocks": [r[0] for r in rows], "count": len(rows)}
    finally:
        conn.close()


@app.get("/api/latest")
def get_latest(stock_code: Optional[str] = Query(None)):
    conn = _get_conn()
    try:
        if stock_code:
            rows = conn.execute(
                "SELECT stock_code, MAX(trade_date) FROM stock_daily WHERE stock_code = ? GROUP BY stock_code",
                (stock_code,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT stock_code, MAX(trade_date) FROM stock_daily GROUP BY stock_code ORDER BY stock_code"
            ).fetchall()
        return {"latest": [{"stock_code": r[0], "latest_date": r[1].isoformat() if r[1] else None} for r in rows]}
    finally:
        conn.close()


@app.get("/api/daily/{stock_code}")
def get_daily(
    stock_code: str,
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(10000, ge=1, le=100000, description="最大返回条数"),
):
    conn = _get_conn()
    try:
        conditions = ["stock_code = ?"]
        params = [stock_code]

        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date)

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM stock_daily WHERE {where} ORDER BY trade_date DESC LIMIT ?"
        params.append(limit)

        result = conn.execute(sql, params)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        return {"stock_code": stock_code, "count": len(rows), "data": _rows_to_dicts(rows, columns)}
    finally:
        conn.close()


@app.get("/api/financial/{stock_code}")
def get_financial(
    stock_code: str,
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    report_type: Optional[str] = Query(None, description="报告类型: 年报/中报/季报"),
):
    conn = _get_conn()
    try:
        conditions = ["stock_code = ?"]
        params = [stock_code]

        if start_date:
            conditions.append("report_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("report_date <= ?")
            params.append(end_date)
        if report_type:
            conditions.append("report_type = ?")
            params.append(report_type)

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM financial_statements WHERE {where} ORDER BY report_date DESC"

        result = conn.execute(sql, params)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        return {"stock_code": stock_code, "count": len(rows), "data": _rows_to_dicts(rows, columns)}
    finally:
        conn.close()


@app.get("/api/indicators/technical/{stock_code}")
def get_technical_indicators(
    stock_code: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(10000, ge=1, le=100000),
):
    conn = _get_conn()
    try:
        conditions = ["stock_code = ?"]
        params = [stock_code]

        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date)

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM technical_indicators WHERE {where} ORDER BY trade_date DESC LIMIT ?"
        params.append(limit)

        result = conn.execute(sql, params)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        return {"stock_code": stock_code, "count": len(rows), "data": _rows_to_dicts(rows, columns)}
    finally:
        conn.close()


@app.get("/api/indicators/valuation/{stock_code}")
def get_valuation_indicators(
    stock_code: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(10000, ge=1, le=100000),
):
    conn = _get_conn()
    try:
        conditions = ["stock_code = ?"]
        params = [stock_code]

        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date)

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM valuation_indicators WHERE {where} ORDER BY trade_date DESC LIMIT ?"
        params.append(limit)

        result = conn.execute(sql, params)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        return {"stock_code": stock_code, "count": len(rows), "data": _rows_to_dicts(rows, columns)}
    finally:
        conn.close()


@app.get("/api/indicators/financial/{stock_code}")
def get_financial_indicators(
    stock_code: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    conn = _get_conn()
    try:
        conditions = ["stock_code = ?"]
        params = [stock_code]

        if start_date:
            conditions.append("report_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("report_date <= ?")
            params.append(end_date)

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM financial_intermediate WHERE {where} ORDER BY report_date DESC"

        result = conn.execute(sql, params)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        return {"stock_code": stock_code, "count": len(rows), "data": _rows_to_dicts(rows, columns)}
    finally:
        conn.close()


@app.get("/api/northbound/{stock_code}")
def get_northbound(
    stock_code: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(10000, ge=1, le=100000),
):
    conn = _get_conn()
    try:
        conditions = ["stock_code = ?"]
        params = [stock_code]

        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date)

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM northbound_flow WHERE {where} ORDER BY trade_date DESC LIMIT ?"
        params.append(limit)

        result = conn.execute(sql, params)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        resp = {"stock_code": stock_code, "count": len(rows), "data": _rows_to_dicts(rows, columns)}
        if len(rows) == 0:
            resp["note"] = "该股票可能非沪深港通标的,无北向资金数据"
        return resp
    finally:
        conn.close()


@app.get("/api/dividends/{stock_code}")
def get_dividends(stock_code: str):
    conn = _get_conn()
    try:
        result = conn.execute(
            "SELECT * FROM dividends WHERE stock_code = ? ORDER BY dividend_date DESC",
            (stock_code,),
        )
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        return {"stock_code": stock_code, "count": len(rows), "data": _rows_to_dicts(rows, columns)}
    finally:
        conn.close()


@app.get("/api/announcements/{stock_code}")
def get_announcements(
    stock_code: str,
    limit: int = Query(100, ge=1, le=1000),
):
    conn = _get_conn()
    try:
        result = conn.execute(
            "SELECT * FROM announcements WHERE stock_code = ? ORDER BY announcement_date DESC LIMIT ?",
            (stock_code, limit),
        )
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        return {"stock_code": stock_code, "count": len(rows), "data": _rows_to_dicts(rows, columns)}
    finally:
        conn.close()


@app.get("/api/margin/{stock_code}")
def get_margin_trading(
    stock_code: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(10000, ge=1, le=100000),
):
    conn = _get_conn()
    try:
        conditions = ["stock_code = ?"]
        params = [stock_code]

        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date)

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM margin_trading WHERE {where} ORDER BY trade_date DESC LIMIT ?"
        params.append(limit)

        result = conn.execute(sql, params)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        return {"stock_code": stock_code, "count": len(rows), "data": _rows_to_dicts(rows, columns)}
    finally:
        conn.close()


@app.get("/api/dragon/{stock_code}")
def get_dragon_tiger(
    stock_code: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    conn = _get_conn()
    try:
        conditions = ["stock_code = ?"]
        params = [stock_code]

        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date)

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM dragon_tiger WHERE {where} ORDER BY trade_date DESC LIMIT ?"
        params.append(limit)

        result = conn.execute(sql, params)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        return {"stock_code": stock_code, "count": len(rows), "data": _rows_to_dicts(rows, columns)}
    finally:
        conn.close()


@app.get("/api/capital/{stock_code}")
def get_capital(stock_code: str):
    conn = _get_conn()
    try:
        result = conn.execute(
            "SELECT * FROM stock_capital WHERE stock_code = ? ORDER BY record_date DESC",
            (stock_code,),
        )
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        return {"stock_code": stock_code, "count": len(rows), "data": _rows_to_dicts(rows, columns)}
    finally:
        conn.close()


@app.get("/api/industry/list")
def list_industries():
    conn = _get_conn()
    try:
        result = conn.execute("""
        SELECT industry_name, COUNT(*) as stock_count, 
               MAX(update_date) as latest_update
        FROM stock_industry
        WHERE industry_name IS NOT NULL
        GROUP BY industry_name
        ORDER BY stock_count DESC
        """)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        return {"count": len(rows), "data": _rows_to_dicts(rows, columns)}
    finally:
        conn.close()


@app.get("/api/industry/{industry_name}/stocks")
def get_industry_stocks(industry_name: str):
    conn = _get_conn()
    try:
        result = conn.execute("""
        SELECT s.stock_code, s.industry_name, s.source, s.update_date
        FROM stock_industry s
        WHERE s.industry_name = ?
        ORDER BY s.stock_code
        """, (industry_name,))
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        return {"industry_name": industry_name, "count": len(rows), "data": _rows_to_dicts(rows, columns)}
    finally:
        conn.close()


@app.get("/api/industry/{stock_code}")
def get_industry(stock_code: str):
    conn = _get_conn()
    try:
        result = conn.execute(
            "SELECT * FROM stock_industry WHERE stock_code = ?",
            (stock_code,),
        )
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        return {"stock_code": stock_code, "count": len(rows), "data": _rows_to_dicts(rows, columns)}
    finally:
        conn.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "db_path": str(DB_PATH)}


# ==================== 主数据接口 ====================

@app.get("/api/master")
def get_stock_master():
    """获取所有股票的主数据"""
    conn = _get_conn()
    try:
        result = conn.execute("SELECT * FROM stock_master ORDER BY stock_code")
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return {"count": len(rows), "data": _rows_to_dicts(rows, columns)}
    except Exception:
        raise HTTPException(status_code=500, detail="stock_master 表不存在,请先运行初始化脚本")
    finally:
        conn.close()


@app.get("/api/master/{stock_code}")
def get_stock_detail(stock_code: str):
    """获取单只股票的主数据及关联统计"""
    conn = _get_conn()
    try:
        master = conn.execute(
            "SELECT * FROM stock_master WHERE stock_code = ?", (stock_code,)
        ).fetchone()
        if not master:
            raise HTTPException(status_code=404, detail=f"股票 '{stock_code}' 未找到")

        desc = conn.execute("SELECT * FROM stock_master LIMIT 0").description
        columns = [d[0] for d in desc]
        result = dict(zip(columns, [
            str(v) if v is not None else None for v in master
        ]))

        # 关联统计
        stats = conn.execute("""
            SELECT
                (SELECT MAX(trade_date) FROM stock_daily WHERE stock_code = ?) AS latest_daily,
                (SELECT COUNT(*) FROM stock_daily WHERE stock_code = ?) AS daily_count,
                (SELECT MAX(report_date) FROM financial_statements WHERE stock_code = ?) AS latest_financial,
                (SELECT COUNT(*) FROM announcements WHERE stock_code = ?) AS announcement_count
        """, (stock_code,) * 4).fetchone()

        result["latest_daily"] = str(stats[0]) if stats[0] else None
        result["daily_count"] = stats[1]
        result["latest_financial"] = str(stats[2]) if stats[2] else None
        result["announcement_count"] = stats[3]

        return result
    finally:
        conn.close()


# ==================== 元数据接口 ====================

@app.get("/api/metadata/tables")
def get_metadata_tables():
    """返回所有数据表的元数据定义(字段名、含义、来源、计算公式等)"""
    result = []
    for table in ALL_TABLES:
        fields = []
        for f in table.fields:
            fields.append({
                "column_name": f.column_name,
                "display_name": f.display_name,
                "description": f.description,
                "data_type": f.data_type,
                "nullable": f.nullable,
                "source": f.source.value,
                "category": f.category.value,
                "calculation": f.calculation,
                "unit": f.unit,
                "example": f.example,
            })

        result.append({
            "table_name": table.table_name,
            "display_name": table.display_name,
            "description": table.description,
            "primary_key": table.primary_key,
            "refresh_frequency": table.refresh_frequency,
            "field_count": len(fields),
            "fields": fields,
        })

    return {"count": len(result), "tables": result}


@app.get("/api/metadata/tables/{table_name}")
def get_metadata_table(table_name: str):
    """返回指定数据表的元数据定义"""
    for table in ALL_TABLES:
        if table.table_name.lower() == table_name.lower():
            fields = []
            for f in table.fields:
                fields.append({
                    "column_name": f.column_name,
                    "display_name": f.display_name,
                    "description": f.description,
                    "data_type": f.data_type,
                    "nullable": f.nullable,
                    "source": f.source.value,
                    "category": f.category.value,
                    "calculation": f.calculation,
                    "unit": f.unit,
                    "example": f.example,
                })

            return {
                "table_name": table.table_name,
                "display_name": table.display_name,
                "description": table.description,
                "primary_key": table.primary_key,
                "refresh_frequency": table.refresh_frequency,
                "field_count": len(fields),
                "fields": fields,
            }

    raise HTTPException(status_code=404, detail=f"表 '{table_name}' 未找到")


@app.get("/api/metadata/search")
def search_metadata(q: str = Query(..., description="搜索关键词,匹配表名/字段名/字段描述/计算公式")):
    """搜索元数据。例如: ?q=PE → 返回所有包含PE的字段定义"""
    q_lower = q.lower()
    results = []

    for table in ALL_TABLES:
        matched_fields = []
        for f in table.fields:
            if (q_lower in f.column_name.lower()
                or q_lower in f.display_name
                or q_lower in f.description
                or (f.calculation and q_lower in f.calculation)):
                matched_fields.append({
                    "column_name": f.column_name,
                    "display_name": f.display_name,
                    "description": f.description,
                    "table_name": table.table_name,
                    "source": f.source.value,
                    "calculation": f.calculation,
                })
        if matched_fields:
            results.append({
                "table_name": table.table_name,
                "display_name": table.display_name,
                "matched_fields": matched_fields,
            })

    total_hits = sum(len(r["matched_fields"]) for r in results)
    return {"query": q, "match_count": total_hits, "results": results}


# ==================== 质量检查接口 ====================

@app.get("/api/quality")
def run_quality_check():
    """执行全部质量规则检查,返回评分和违规明细"""
    from src.quality import QualityChecker
    checker = QualityChecker(str(DB_PATH))
    return checker.run_all()


@app.get("/api/quality/history")
def get_quality_history(limit: int = Query(30, ge=1, le=100)):
    """获取历史质量检查报告摘要"""
    from src.quality import QualityChecker
    checker = QualityChecker(str(DB_PATH))
    return {"history": checker.get_report_history(limit)}


if __name__ == "__main__":
    import uvicorn
    import socket

    DEFAULT_PORT = 8001
    FALLBACK_PORTS = [8002, 8003, 8004, 8005]

    def _port_available(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return True
            except OSError:
                return False

    port = DEFAULT_PORT
    if not _port_available(port):
        for p in FALLBACK_PORTS:
            if _port_available(p):
                port = p
                break
        else:
            print(f"错误: 端口 {DEFAULT_PORT}-{FALLBACK_PORTS[-1]} 均被占用")
            exit(1)

    print(f"启动 API 服务: http://localhost:{port}")
    print(f"Swagger 文档: http://localhost:{port}/docs")
    uvicorn.run(app, host="0.0.0.0", port=port)