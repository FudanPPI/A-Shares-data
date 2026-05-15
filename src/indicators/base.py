
import pandas as pd


class BaseIndicatorCalculator:
    def __init__(self, db_ops):
        self.db_ops = db_ops

    @staticmethod
    def _safe_float(val):
        if val is None:
            return None
        try:
            result = float(val)
            if pd.isna(result):
                return None
            return result
        except (ValueError, TypeError):
            return None
