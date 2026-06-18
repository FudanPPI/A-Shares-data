
import pandas as pd
import numpy as np
import logging
from .base import BaseIndicatorCalculator

logger = logging.getLogger(__name__)


class TechnicalIndicatorCalculator(BaseIndicatorCalculator):
    def calculate_for_stock(self, stock_code: str):
        logger.info(f"计算 {stock_code} 技术指标")

        df = self.db_ops.query("""
        SELECT stock_code, trade_date, open, high, low, close, volume, amount
        FROM stock_daily
        WHERE stock_code = ?
        ORDER BY trade_date
        """, (stock_code,))

        if len(df) < 2:
            logger.info(f"{stock_code} 数据不足")
            return

        df = df.sort_values('trade_date').reset_index(drop=True)
        n = len(df)

        df['ma5'] = df['close'].rolling(5, min_periods=1).mean()
        df['ma10'] = df['close'].rolling(10, min_periods=1).mean()
        df['ma20'] = df['close'].rolling(20, min_periods=1).mean()
        df['ma60'] = df['close'].rolling(60, min_periods=1).mean()

        df['ema12'] = df['close'].ewm(span=12, adjust=False, min_periods=1).mean()
        df['ema26'] = df['close'].ewm(span=26, adjust=False, min_periods=1).mean()

        df['macd_dif'] = df['ema12'] - df['ema26']
        df['macd_dea'] = df['macd_dif'].ewm(span=9, adjust=False, min_periods=1).mean()
        df['macd_hist'] = (df['macd_dif'] - df['macd_dea']) * 2

        df['boll_mid'] = df['ma20']
        df['boll_std'] = df['close'].rolling(20, min_periods=1).std()
        df['boll_upper'] = df['boll_mid'] + 2 * df['boll_std']
        df['boll_lower'] = df['boll_mid'] - 2 * df['boll_std']

        df['bias5'] = (df['close'] - df['ma5']) / df['ma5'].replace(0, np.nan) * 100
        df['bias10'] = (df['close'] - df['ma10']) / df['ma10'].replace(0, np.nan) * 100
        df['bias20'] = (df['close'] - df['ma20']) / df['ma20'].replace(0, np.nan) * 100
        df['bias60'] = (df['close'] - df['ma60']) / df['ma60'].replace(0, np.nan) * 100

        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)

        for period in [6, 12, 24]:
            avg_gain = gain.rolling(window=period, min_periods=1).mean()
            avg_loss = loss.rolling(window=period, min_periods=1).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            df[f'rsi{period}'] = 100 - (100 / (1 + rs))

        low_list = df['low'].rolling(9, min_periods=1).min()
        high_list = df['high'].rolling(9, min_periods=1).max()
        rsv = (df['close'] - low_list) / (high_list - low_list).replace(0, np.nan) * 100
        rsv = rsv.fillna(50)
        df['kdj_k'] = rsv.ewm(com=2, adjust=False, min_periods=1).mean()
        df['kdj_d'] = df['kdj_k'].ewm(com=2, adjust=False, min_periods=1).mean()
        df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']

        tp = (df['high'] + df['low'] + df['close']) / 3
        ma_tp = tp.rolling(20, min_periods=1).mean()
        md = tp.rolling(20, min_periods=1).apply(lambda x: (abs(x - x.mean())).mean(), raw=True)
        df['cci20'] = (tp - ma_tp) / (0.015 * md).replace(0, np.nan)
        df['cci20'] = df['cci20'].fillna(0)

        low14 = df['low'].rolling(14, min_periods=1).min()
        high14 = df['high'].rolling(14, min_periods=1).max()
        df['wr14'] = (high14 - df['close']) / (high14 - low14).replace(0, np.nan) * 100
        df['wr14'] = df['wr14'].fillna(50)

        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift(1))
        tr3 = abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr14'] = tr.rolling(14, min_periods=1).mean()

        df['std20'] = df['close'].rolling(20, min_periods=1).std()

        df['vol_ma5'] = df['volume'].rolling(5, min_periods=1).mean()
        df['vol_ma10'] = df['volume'].rolling(10, min_periods=1).mean()

        obv = (df['volume'] * ((df['close'] > df['close'].shift(1)).astype(int) -
                               (df['close'] < df['close'].shift(1)).astype(int))).fillna(0)
        df['obv'] = obv.cumsum()

        typical_price = (df['high'] + df['low'] + df['close']) / 3
        money_flow = typical_price * df['volume']
        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0)
        pos_sum = positive_flow.rolling(14, min_periods=1).sum()
        neg_sum = negative_flow.rolling(14, min_periods=1).sum()
        mfi_ratio = pos_sum / neg_sum.replace(0, np.nan)
        df['mfi14'] = 100 - (100 / (1 + mfi_ratio))
        df['mfi14'] = df['mfi14'].fillna(50)

        up_vol = df['volume'].where(df['close'] > df['close'].shift(1), 0)
        down_vol = df['volume'].where(df['close'] < df['close'].shift(1), 0)
        flat_vol = df['volume'].where(df['close'] == df['close'].shift(1), 0)
        up_sum = up_vol.rolling(24, min_periods=1).sum()
        down_sum = down_vol.rolling(24, min_periods=1).sum()
        flat_sum = flat_vol.rolling(24, min_periods=1).sum()
        df['vr'] = (up_sum + flat_sum / 2) / (down_sum + flat_sum / 2).replace(0, np.nan) * 100
        df['vr'] = df['vr'].fillna(100)

        high = df['high']
        low = df['low']
        close = df['close']
        plus_dm = high.diff().clip(lower=0)
        minus_dm = -low.diff().clip(upper=0)
        tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14, min_periods=1).mean()
        plus_di = 100 * (plus_dm.rolling(14, min_periods=1).mean() / atr.replace(0, np.nan))
        minus_di = 100 * (minus_dm.rolling(14, min_periods=1).mean() / atr.replace(0, np.nan))
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.rolling(14, min_periods=1).mean()
        adxr = (adx + adx.shift(14)).rolling(2, min_periods=1).mean()
        df['dmi_pdi'] = plus_di
        df['dmi_mdi'] = minus_di
        df['dmi_adx'] = adx
        df['dmi_adxr'] = adxr

        af_step = 0.02
        af_max = 0.2
        sar = pd.Series(index=df.index, dtype='float64')
        is_up_trend = True
        ep = df['high'][0] if n > 0 else 0
        af = af_step

        if n > 0:
            sar.iloc[0] = df['low'][0] if n > 0 else 0
            for i in range(1, n):
                sar.iloc[i] = sar.iloc[i-1] + af * (ep - sar.iloc[i-1])
                if is_up_trend:
                    if df['low'][i] < sar.iloc[i]:
                        is_up_trend = False
                        sar.iloc[i] = ep
                        ep = df['low'][i]
                        af = af_step
                    else:
                        if df['high'][i] > ep:
                            ep = df['high'][i]
                            af = min(af + af_step, af_max)
                else:
                    if df['high'][i] > sar.iloc[i]:
                        is_up_trend = True
                        sar.iloc[i] = ep
                        ep = df['high'][i]
                        af = af_step
                    else:
                        if df['low'][i] < ep:
                            ep = df['low'][i]
                            af = min(af + af_step, af_max)

        df['sar'] = sar
        wvad = ((df['close'] - df['open']) / (df['high'] - df['low']).replace(0, np.nan)) * df['volume']
        df['wvad'] = wvad.fillna(0)

        tech_cols = [
            'stock_code', 'trade_date', 'ma5', 'ma10', 'ma20', 'ma60',
            'ema12', 'ema26', 'boll_mid', 'boll_upper', 'boll_lower',
            'macd_dif', 'macd_dea', 'macd_hist',
            'bias5', 'bias10', 'bias20', 'bias60',
            'rsi6', 'rsi12', 'rsi24',
            'kdj_k', 'kdj_d', 'kdj_j',
            'cci20', 'wr14', 'atr14', 'std20',
            'vol_ma5', 'vol_ma10', 'obv', 'mfi14', 'vr',
            'dmi_pdi', 'dmi_mdi', 'dmi_adx', 'dmi_adxr',
            'sar', 'wvad'
        ]
        existing_cols = [c for c in tech_cols if c in df.columns]

        # 事务保证: DELETE + INSERT 原子化
        # 若无事务,DELETE 成功后 INSERT 失败会导致该股票所有技术指标丢失
        with self.db_ops.transaction():
            self.db_ops.conn.execute("DELETE FROM technical_indicators WHERE stock_code = ?", (stock_code,))
            self.db_ops.insert_dataframe("technical_indicators", df[existing_cols])

        logger.info(f"{stock_code} 技术指标完成")
