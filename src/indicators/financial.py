
import pandas as pd
import logging
from .base import BaseIndicatorCalculator

logger = logging.getLogger(__name__)


class FinancialIndicatorCalculator(BaseIndicatorCalculator):
    def calculate_for_stock(self, stock_code: str):
        logger.info(f"计算 {stock_code} 财务指标")

        df_finance = self.db_ops.query("""
            SELECT report_date, report_type, total_revenue, net_profit, total_assets, total_liabilities, 
                   eps, equity_parent, announcement_date, operating_cost, net_profit_deducted, 
                   inventory, accounts_receivable, accounts_payable, capex, interest_expense, operating_cash_flow,
                   current_assets, current_liabilities
            FROM financial_statements 
            WHERE stock_code = ? 
            ORDER BY report_date
        """, (stock_code,))

        if df_finance.empty:
            return

        total_shares = None
        capital_result = self.db_ops.conn.execute("""
            SELECT total_shares 
            FROM stock_capital 
            WHERE stock_code = ? 
            ORDER BY record_date DESC 
            LIMIT 1
        """, (stock_code,)).fetchone()
        if capital_result:
            total_shares = capital_result[0]

        df_finance = df_finance.sort_values('report_date').reset_index(drop=True)

        def get_quarter_type(report_date_val):
            dt = pd.to_datetime(report_date_val)
            month = dt.month
            day = dt.day
            if month == 3 and day == 31:
                return 'Q1'
            elif month == 6 and day == 30:
                return 'Q2'
            elif month == 9 and day == 30:
                return 'Q3'
            elif month == 12 and day == 31:
                return 'FY'
            else:
                if month <= 3:
                    return 'Q1'
                elif month <= 6:
                    return 'Q2'
                elif month <= 9:
                    return 'Q3'
                else:
                    return 'FY'

        df_finance['quarter_type'] = df_finance['report_date'].apply(get_quarter_type)

        intermediate_data = []
        n = len(df_finance)

        q_data_cache = {}
        for i in range(n):
            row = df_finance.iloc[i]
            qt = row['quarter_type']

            q_data = {}
            q_data['net_profit_q'] = self._calc_q_data(df_finance, i, qt, 'net_profit')
            q_data['total_revenue_q'] = self._calc_q_data(df_finance, i, qt, 'total_revenue')
            q_data['operating_cost_q'] = self._calc_q_data(df_finance, i, qt, 'operating_cost')
            q_data['net_profit_deducted_q'] = self._calc_q_data(df_finance, i, qt, 'net_profit_deducted')
            q_data['operating_cash_flow_q'] = self._calc_q_data(df_finance, i, qt, 'operating_cash_flow')
            q_data['capex_q'] = self._calc_q_data(df_finance, i, qt, 'capex')
            q_data['eps_q'] = self._calc_q_data(df_finance, i, qt, 'eps')
            q_data['interest_expense_q'] = self._calc_q_data(df_finance, i, qt, 'interest_expense')

            q_data_cache[i] = q_data

        for i in range(n):
            row = df_finance.iloc[i]
            report_date = row['report_date']
            quarter_type = row['quarter_type']
            report_type = row['report_type']

            net_profit = self._safe_float(row.get('net_profit'))
            total_revenue = self._safe_float(row.get('total_revenue'))
            total_assets = self._safe_float(row.get('total_assets'))
            total_liabilities = self._safe_float(row.get('total_liabilities'))
            eps = self._safe_float(row.get('eps'))
            equity_parent = self._safe_float(row.get('equity_parent'))
            announcement_date = row.get('announcement_date')
            operating_cost = self._safe_float(row.get('operating_cost'))
            net_profit_deducted = self._safe_float(row.get('net_profit_deducted'))
            inventory = self._safe_float(row.get('inventory'))
            accounts_receivable = self._safe_float(row.get('accounts_receivable'))
            accounts_payable = self._safe_float(row.get('accounts_payable'))
            capex = self._safe_float(row.get('capex'))
            interest_expense = self._safe_float(row.get('interest_expense'))
            operating_cash_flow = self._safe_float(row.get('operating_cash_flow'))
            current_assets = self._safe_float(row.get('current_assets'))
            current_liabilities = self._safe_float(row.get('current_liabilities'))

            equity = None
            equity_to_use = None
            bvps = None
            revenue_per_share = None

            if total_assets is not None and total_liabilities is not None:
                equity = total_assets - total_liabilities

            if equity_parent is not None and equity_parent > 0:
                equity_to_use = equity_parent
            elif equity is not None and equity > 0:
                equity_to_use = equity

            if equity_to_use is not None and total_shares is not None and total_shares > 0:
                bvps = round(float(equity_to_use) / float(total_shares), 4)

            if total_revenue is not None and total_shares is not None and total_shares > 0:
                revenue_per_share = round(float(total_revenue) / float(total_shares), 4)

            q_cache = q_data_cache[i]
            net_profit_q = q_cache['net_profit_q']
            total_revenue_q = q_cache['total_revenue_q']
            operating_cost_q = q_cache['operating_cost_q']
            net_profit_deducted_q = q_cache['net_profit_deducted_q']
            operating_cash_flow_q = q_cache['operating_cash_flow_q']
            capex_q = q_cache['capex_q']
            eps_q = q_cache['eps_q']
            interest_expense_q = q_cache['interest_expense_q']

            net_profit_ttm = self._calc_ttm(df_finance, i, 'net_profit')
            total_revenue_ttm = self._calc_ttm(df_finance, i, 'total_revenue')
            eps_ttm = self._calc_ttm_eps(df_finance, i)
            operating_cost_ttm = self._calc_ttm(df_finance, i, 'operating_cost')
            net_profit_deducted_ttm = self._calc_ttm(df_finance, i, 'net_profit_deducted')
            operating_cash_flow_ttm = self._calc_ttm(df_finance, i, 'operating_cash_flow')
            capex_ttm = self._calc_ttm(df_finance, i, 'capex')
            interest_expense_ttm = self._calc_ttm(df_finance, i, 'interest_expense')

            avg_equity_parent = None
            avg_total_assets = None
            avg_inventory = None
            avg_accounts_receivable = None
            avg_accounts_payable = None
            if quarter_type == 'FY':
                prev_row = self._find_prev_year_row(df_finance, i)
                if prev_row is not None:
                    avg_equity_parent = self._avg_two(df_finance.iloc[i], prev_row, 'equity_parent')
                    avg_total_assets = self._avg_two(df_finance.iloc[i], prev_row, 'total_assets')
                    avg_inventory = self._avg_two(df_finance.iloc[i], prev_row, 'inventory')
                    avg_accounts_receivable = self._avg_two(df_finance.iloc[i], prev_row, 'accounts_receivable')
                    avg_accounts_payable = self._avg_two(df_finance.iloc[i], prev_row, 'accounts_payable')

            avg_equity_parent_ttm = None
            avg_total_assets_ttm = None
            avg_inventory_ttm = None
            avg_accounts_receivable_ttm = None
            avg_accounts_payable_ttm = None
            prev_4q_row = self._find_prev_4q_row(df_finance, i)
            if prev_4q_row is not None:
                avg_equity_parent_ttm = self._avg_two(df_finance.iloc[i], prev_4q_row, 'equity_parent')
                avg_total_assets_ttm = self._avg_two(df_finance.iloc[i], prev_4q_row, 'total_assets')
                avg_inventory_ttm = self._avg_two(df_finance.iloc[i], prev_4q_row, 'inventory')
                avg_accounts_receivable_ttm = self._avg_two(df_finance.iloc[i], prev_4q_row, 'accounts_receivable')
                avg_accounts_payable_ttm = self._avg_two(df_finance.iloc[i], prev_4q_row, 'accounts_payable')

            roe_annual = None
            roa_annual = None
            gross_margin_annual = None
            net_margin_parent_annual = None
            net_margin_deducted_annual = None
            if quarter_type == 'FY' and avg_equity_parent is not None and avg_equity_parent != 0 and net_profit is not None:
                roe_annual = round(net_profit / avg_equity_parent * 100, 4)
            if quarter_type == 'FY' and avg_total_assets is not None and avg_total_assets != 0 and net_profit is not None:
                roa_annual = round(net_profit / avg_total_assets * 100, 4)
            if quarter_type == 'FY' and total_revenue is not None and total_revenue != 0 and operating_cost is not None:
                gross_margin_annual = round((total_revenue - operating_cost) / total_revenue * 100, 4)
            if quarter_type == 'FY' and total_revenue is not None and total_revenue != 0 and net_profit is not None:
                net_margin_parent_annual = round(net_profit / total_revenue * 100, 4)
            if quarter_type == 'FY' and total_revenue is not None and total_revenue != 0 and net_profit_deducted is not None:
                net_margin_deducted_annual = round(net_profit_deducted / total_revenue * 100, 4)

            roe_ttm = None
            roa_ttm = None
            gross_margin_ttm = None
            net_margin_parent_ttm = None
            net_margin_deducted_ttm = None
            if avg_equity_parent_ttm is not None and avg_equity_parent_ttm != 0 and net_profit_ttm is not None:
                roe_ttm = round(net_profit_ttm / avg_equity_parent_ttm * 100, 4)
            if avg_total_assets_ttm is not None and avg_total_assets_ttm != 0 and net_profit_ttm is not None:
                roa_ttm = round(net_profit_ttm / avg_total_assets_ttm * 100, 4)
            if total_revenue_ttm is not None and total_revenue_ttm != 0 and operating_cost_ttm is not None:
                gross_margin_ttm = round((total_revenue_ttm - operating_cost_ttm) / total_revenue_ttm * 100, 4)
            if total_revenue_ttm is not None and total_revenue_ttm != 0 and net_profit_ttm is not None:
                net_margin_parent_ttm = round(net_profit_ttm / total_revenue_ttm * 100, 4)
            if total_revenue_ttm is not None and total_revenue_ttm != 0 and net_profit_deducted_ttm is not None:
                net_margin_deducted_ttm = round(net_profit_deducted_ttm / total_revenue_ttm * 100, 4)

            revenue_yoy_annual = None
            net_profit_yoy_annual = None
            if quarter_type == 'FY':
                prev_row = self._find_prev_year_row(df_finance, i)
                if prev_row is not None:
                    rev_prev = self._safe_float(prev_row.get('total_revenue'))
                    np_prev = self._safe_float(prev_row.get('net_profit'))
                    if rev_prev is not None and rev_prev != 0 and total_revenue is not None:
                        revenue_yoy_annual = round((total_revenue - rev_prev) / rev_prev * 100, 4)
                    if np_prev is not None and np_prev != 0 and net_profit is not None:
                        net_profit_yoy_annual = round((net_profit - np_prev) / np_prev * 100, 4)

            revenue_yoy_qoq = None
            net_profit_yoy_qoq = None
            prev_year_q_row = self._find_prev_year_same_q_row(df_finance, i)
            if prev_year_q_row is not None:
                prev_qt = prev_year_q_row['quarter_type']
                prev_idx = df_finance.index[df_finance['report_date'] == prev_year_q_row['report_date']][0]
                prev_np_q = self._calc_q_data(df_finance, prev_idx, prev_qt, 'net_profit')
                prev_rev_q = self._calc_q_data(df_finance, prev_idx, prev_qt, 'total_revenue')
                if prev_rev_q is not None and prev_rev_q != 0 and total_revenue_q is not None:
                    revenue_yoy_qoq = round((total_revenue_q - prev_rev_q) / prev_rev_q * 100, 4)
                if prev_np_q is not None and prev_np_q != 0 and net_profit_q is not None:
                    net_profit_yoy_qoq = round((net_profit_q - prev_np_q) / prev_np_q * 100, 4)

            revenue_yoy_ttm = None
            net_profit_yoy_ttm = None
            prev_ttm_rev = self._calc_prev_ttm(df_finance, i, 'total_revenue')
            prev_ttm_np = self._calc_prev_ttm(df_finance, i, 'net_profit')
            if prev_ttm_rev is not None and prev_ttm_rev != 0 and total_revenue_ttm is not None:
                revenue_yoy_ttm = round((total_revenue_ttm - prev_ttm_rev) / prev_ttm_rev * 100, 4)
            if prev_ttm_np is not None and prev_ttm_np != 0 and net_profit_ttm is not None:
                net_profit_yoy_ttm = round((net_profit_ttm - prev_ttm_np) / prev_ttm_np * 100, 4)

            revenue_cagr_3y = None
            net_profit_cagr_3y = None
            net_profit_deducted_cagr_3y = None
            if quarter_type == 'FY':
                row_3y_ago = self._find_prev_nth_year_row(df_finance, i, 3)
                if row_3y_ago is not None:
                    rev_3y = self._safe_float(row_3y_ago.get('total_revenue'))
                    np_3y = self._safe_float(row_3y_ago.get('net_profit'))
                    npd_3y = self._safe_float(row_3y_ago.get('net_profit_deducted'))
                    if rev_3y is not None and rev_3y > 0 and total_revenue is not None and total_revenue > 0:
                        revenue_cagr_3y = round(((total_revenue / rev_3y) ** (1/3) - 1) * 100, 4)
                    if np_3y is not None and np_3y > 0 and net_profit is not None and net_profit > 0:
                        net_profit_cagr_3y = round(((net_profit / np_3y) ** (1/3) - 1) * 100, 4)
                    if npd_3y is not None and npd_3y > 0 and net_profit_deducted is not None and net_profit_deducted > 0:
                        net_profit_deducted_cagr_3y = round(((net_profit_deducted / npd_3y) ** (1/3) - 1) * 100, 4)

            dupont_net_margin_annual = net_margin_parent_annual
            dupont_asset_turnover_annual = None
            dupont_equity_multiplier_annual = None
            if quarter_type == 'FY' and avg_total_assets is not None and avg_total_assets != 0 and total_revenue is not None:
                dupont_asset_turnover_annual = round(total_revenue / avg_total_assets, 4)
            if quarter_type == 'FY' and equity_to_use is not None and equity_to_use != 0 and total_assets is not None:
                dupont_equity_multiplier_annual = round(total_assets / equity_to_use, 4)

            dupont_net_margin_ttm = net_margin_parent_ttm
            dupont_asset_turnover_ttm = None
            dupont_equity_multiplier_ttm = None
            if avg_total_assets_ttm is not None and avg_total_assets_ttm != 0 and total_revenue_ttm is not None:
                dupont_asset_turnover_ttm = round(total_revenue_ttm / avg_total_assets_ttm, 4)
            if equity_to_use is not None and equity_to_use != 0 and total_assets is not None:
                dupont_equity_multiplier_ttm = round(total_assets / equity_to_use, 4)

            inventory_turnover_annual = None
            inventory_days_annual = None
            accounts_receivable_turnover_annual = None
            accounts_receivable_days_annual = None
            accounts_payable_turnover_annual = None
            accounts_payable_days_annual = None
            cash_cycle_annual = None
            if quarter_type == 'FY' and avg_inventory is not None and avg_inventory != 0 and operating_cost is not None:
                inventory_turnover_annual = round(operating_cost / avg_inventory, 4)
                if inventory_turnover_annual != 0:
                    inventory_days_annual = round(365 / inventory_turnover_annual, 4)
            if quarter_type == 'FY' and avg_accounts_receivable is not None and avg_accounts_receivable != 0 and total_revenue is not None:
                accounts_receivable_turnover_annual = round(total_revenue / avg_accounts_receivable, 4)
                if accounts_receivable_turnover_annual != 0:
                    accounts_receivable_days_annual = round(365 / accounts_receivable_turnover_annual, 4)
            if quarter_type == 'FY' and avg_accounts_payable is not None and avg_accounts_payable != 0 and operating_cost is not None:
                accounts_payable_turnover_annual = round(operating_cost / avg_accounts_payable, 4)
                if accounts_payable_turnover_annual != 0:
                    accounts_payable_days_annual = round(365 / accounts_payable_turnover_annual, 4)
            if inventory_days_annual is not None and accounts_receivable_days_annual is not None and accounts_payable_days_annual is not None:
                cash_cycle_annual = round(inventory_days_annual + accounts_receivable_days_annual - accounts_payable_days_annual, 4)

            inventory_turnover_ttm = None
            inventory_days_ttm = None
            accounts_receivable_turnover_ttm = None
            accounts_receivable_days_ttm = None
            accounts_payable_turnover_ttm = None
            accounts_payable_days_ttm = None
            cash_cycle_ttm = None
            if avg_inventory_ttm is not None and avg_inventory_ttm != 0 and operating_cost_ttm is not None:
                inventory_turnover_ttm = round(operating_cost_ttm / avg_inventory_ttm, 4)
                if inventory_turnover_ttm != 0:
                    inventory_days_ttm = round(365 / inventory_turnover_ttm, 4)
            if avg_accounts_receivable_ttm is not None and avg_accounts_receivable_ttm != 0 and total_revenue_ttm is not None:
                accounts_receivable_turnover_ttm = round(total_revenue_ttm / avg_accounts_receivable_ttm, 4)
                if accounts_receivable_turnover_ttm != 0:
                    accounts_receivable_days_ttm = round(365 / accounts_receivable_turnover_ttm, 4)
            if avg_accounts_payable_ttm is not None and avg_accounts_payable_ttm != 0 and operating_cost_ttm is not None:
                accounts_payable_turnover_ttm = round(operating_cost_ttm / avg_accounts_payable_ttm, 4)
                if accounts_payable_turnover_ttm != 0:
                    accounts_payable_days_ttm = round(365 / accounts_payable_turnover_ttm, 4)
            if inventory_days_ttm is not None and accounts_receivable_days_ttm is not None and accounts_payable_days_ttm is not None:
                cash_cycle_ttm = round(inventory_days_ttm + accounts_receivable_days_ttm - accounts_payable_days_ttm, 4)

            cash_profit_coverage_ttm = None
            fcf_ttm = None
            fcf_profit_coverage_ttm = None
            cash_interest_coverage_ttm = None
            if net_profit_ttm is not None and net_profit_ttm != 0 and operating_cash_flow_ttm is not None:
                cash_profit_coverage_ttm = round(operating_cash_flow_ttm / net_profit_ttm, 4)
            if operating_cash_flow_ttm is not None and capex_ttm is not None:
                fcf_ttm = operating_cash_flow_ttm - capex_ttm
            if net_profit_ttm is not None and net_profit_ttm != 0 and fcf_ttm is not None:
                fcf_profit_coverage_ttm = round(fcf_ttm / net_profit_ttm, 4)
            if interest_expense_ttm is not None and interest_expense_ttm != 0 and operating_cash_flow_ttm is not None:
                cash_interest_coverage_ttm = round(operating_cash_flow_ttm / interest_expense_ttm, 4)

            # 流动比率 = 流动资产 / 流动负债
            # 速动比率 = (流动资产 - 存货) / 流动负债
            current_ratio = None
            quick_ratio = None
            if current_assets is not None and current_liabilities is not None and current_liabilities != 0:
                current_ratio = round(current_assets / current_liabilities, 4)
                quick_assets = current_assets - (inventory if inventory is not None else 0)
                quick_ratio = round(quick_assets / current_liabilities, 4)

            intermediate_data.append({
                'stock_code': stock_code,
                'report_date': report_date,
                'report_type': report_type,
                'eps': eps,
                'bvps': bvps,
                'revenue_per_share': revenue_per_share,
                'net_profit': net_profit,
                'total_revenue': total_revenue,
                'equity': equity,
                'equity_parent': equity_parent,
                'total_assets': total_assets,
                'total_shares': total_shares,
                'announcement_date': announcement_date,
                'operating_cost': operating_cost,
                'net_profit_deducted': net_profit_deducted,
                'inventory': inventory,
                'accounts_receivable': accounts_receivable,
                'accounts_payable': accounts_payable,
                'capex': capex,
                'interest_expense': interest_expense,
                'operating_cash_flow': operating_cash_flow,
                'net_profit_q': net_profit_q,
                'total_revenue_q': total_revenue_q,
                'eps_q': eps_q,
                'operating_cost_q': operating_cost_q,
                'net_profit_deducted_q': net_profit_deducted_q,
                'operating_cash_flow_q': operating_cash_flow_q,
                'capex_q': capex_q,
                'net_profit_ttm': net_profit_ttm,
                'total_revenue_ttm': total_revenue_ttm,
                'eps_ttm': eps_ttm,
                'operating_cost_ttm': operating_cost_ttm,
                'net_profit_deducted_ttm': net_profit_deducted_ttm,
                'operating_cash_flow_ttm': operating_cash_flow_ttm,
                'capex_ttm': capex_ttm,
                'interest_expense_ttm': interest_expense_ttm,
                'avg_equity_parent': avg_equity_parent,
                'avg_total_assets': avg_total_assets,
                'avg_inventory': avg_inventory,
                'avg_accounts_receivable': avg_accounts_receivable,
                'avg_accounts_payable': avg_accounts_payable,
                'avg_equity_parent_ttm': avg_equity_parent_ttm,
                'avg_total_assets_ttm': avg_total_assets_ttm,
                'avg_inventory_ttm': avg_inventory_ttm,
                'avg_accounts_receivable_ttm': avg_accounts_receivable_ttm,
                'avg_accounts_payable_ttm': avg_accounts_payable_ttm,
                'roe_annual': roe_annual,
                'roa_annual': roa_annual,
                'gross_margin_annual': gross_margin_annual,
                'net_margin_parent_annual': net_margin_parent_annual,
                'net_margin_deducted_annual': net_margin_deducted_annual,
                'roe_ttm': roe_ttm,
                'roa_ttm': roa_ttm,
                'gross_margin_ttm': gross_margin_ttm,
                'net_margin_parent_ttm': net_margin_parent_ttm,
                'net_margin_deducted_ttm': net_margin_deducted_ttm,
                'revenue_yoy_annual': revenue_yoy_annual,
                'net_profit_yoy_annual': net_profit_yoy_annual,
                'revenue_yoy_qoq': revenue_yoy_qoq,
                'net_profit_yoy_qoq': net_profit_yoy_qoq,
                'revenue_yoy_ttm': revenue_yoy_ttm,
                'net_profit_yoy_ttm': net_profit_yoy_ttm,
                'revenue_cagr_3y': revenue_cagr_3y,
                'net_profit_cagr_3y': net_profit_cagr_3y,
                'net_profit_deducted_cagr_3y': net_profit_deducted_cagr_3y,
                'dupont_net_margin_annual': dupont_net_margin_annual,
                'dupont_asset_turnover_annual': dupont_asset_turnover_annual,
                'dupont_equity_multiplier_annual': dupont_equity_multiplier_annual,
                'dupont_net_margin_ttm': dupont_net_margin_ttm,
                'dupont_asset_turnover_ttm': dupont_asset_turnover_ttm,
                'dupont_equity_multiplier_ttm': dupont_equity_multiplier_ttm,
                'inventory_turnover_annual': inventory_turnover_annual,
                'inventory_days_annual': inventory_days_annual,
                'accounts_receivable_turnover_annual': accounts_receivable_turnover_annual,
                'accounts_receivable_days_annual': accounts_receivable_days_annual,
                'accounts_payable_turnover_annual': accounts_payable_turnover_annual,
                'accounts_payable_days_annual': accounts_payable_days_annual,
                'cash_cycle_annual': cash_cycle_annual,
                'inventory_turnover_ttm': inventory_turnover_ttm,
                'inventory_days_ttm': inventory_days_ttm,
                'accounts_receivable_turnover_ttm': accounts_receivable_turnover_ttm,
                'accounts_receivable_days_ttm': accounts_receivable_days_ttm,
                'accounts_payable_turnover_ttm': accounts_payable_turnover_ttm,
                'accounts_payable_days_ttm': accounts_payable_days_ttm,
                'cash_cycle_ttm': cash_cycle_ttm,
                'cash_profit_coverage_ttm': cash_profit_coverage_ttm,
                'fcf_ttm': fcf_ttm,
                'fcf_profit_coverage_ttm': fcf_profit_coverage_ttm,
                'cash_interest_coverage_ttm': cash_interest_coverage_ttm,
                'current_ratio': current_ratio,
                'quick_ratio': quick_ratio,
            })

        df_inter = pd.DataFrame(intermediate_data)

        # 事务保证: DELETE + INSERT 原子化
        # 若无事务,DELETE 成功后 INSERT 失败会导致该股票所有财务指标丢失
        with self.db_ops.transaction():
            self.db_ops.conn.execute("DELETE FROM financial_intermediate WHERE stock_code = ?", (stock_code,))
            self.db_ops.insert_dataframe("financial_intermediate", df_inter, ["stock_code", "report_date", "report_type"])

        logger.info(f"{stock_code} 财务指标完成")

    def _calc_q_data(self, df, i, qt, col):
        if qt == 'Q1':
            return self._safe_float(df.iloc[i].get(col))
        if i == 0:
            return None
        prev_row = df.iloc[i-1]
        curr = self._safe_float(df.iloc[i].get(col))
        prev = self._safe_float(prev_row.get(col))
        if curr is None or prev is None:
            return None
        return curr - prev

    def _calc_ttm(self, df, i, col):
        if i < 4:
            return None
        qt0 = df.iloc[i]['quarter_type']
        qt1 = df.iloc[i-1]['quarter_type']
        qt2 = df.iloc[i-2]['quarter_type']
        qt3 = df.iloc[i-3]['quarter_type']
        q0 = self._calc_q_data(df, i, qt0, col)
        q1 = self._calc_q_data(df, i-1, qt1, col)
        q2 = self._calc_q_data(df, i-2, qt2, col)
        q3 = self._calc_q_data(df, i-3, qt3, col)
        if None in [q0, q1, q2, q3]:
            return None
        return q0 + q1 + q2 + q3

    def _calc_ttm_eps(self, df, i):
        if i < 4:
            return None
        qt0 = df.iloc[i]['quarter_type']
        qt1 = df.iloc[i-1]['quarter_type']
        qt2 = df.iloc[i-2]['quarter_type']
        qt3 = df.iloc[i-3]['quarter_type']
        q0 = self._calc_q_data(df, i, qt0, 'eps')
        q1 = self._calc_q_data(df, i-1, qt1, 'eps')
        q2 = self._calc_q_data(df, i-2, qt2, 'eps')
        q3 = self._calc_q_data(df, i-3, qt3, 'eps')
        if None in [q0, q1, q2, q3]:
            return None
        return q0 + q1 + q2 + q3

    def _calc_prev_ttm(self, df, i, col):
        if i < 8:
            return None
        qt0 = df.iloc[i-4]['quarter_type']
        qt1 = df.iloc[i-5]['quarter_type']
        qt2 = df.iloc[i-6]['quarter_type']
        qt3 = df.iloc[i-7]['quarter_type']
        q0 = self._calc_q_data(df, i-4, qt0, col)
        q1 = self._calc_q_data(df, i-5, qt1, col)
        q2 = self._calc_q_data(df, i-6, qt2, col)
        q3 = self._calc_q_data(df, i-7, qt3, col)
        if None in [q0, q1, q2, q3]:
            return None
        return q0 + q1 + q2 + q3

    def _find_prev_year_row(self, df, i):
        if i < 4:
            return None
        return df.iloc[i-4]

    def _find_prev_4q_row(self, df, i):
        if i < 4:
            return None
        return df.iloc[i-4]

    def _find_prev_year_same_q_row(self, df, i):
        if i < 4:
            return None
        return df.iloc[i-4]

    def _find_prev_nth_year_row(self, df, i, n):
        if i < 4*n:
            return None
        return df.iloc[i-4*n]

    def _avg_two(self, row1, row2, col):
        v1 = self._safe_float(row1.get(col))
        v2 = self._safe_float(row2.get(col))
        if v1 is None or v2 is None:
            return None
        return (v1 + v2) / 2
