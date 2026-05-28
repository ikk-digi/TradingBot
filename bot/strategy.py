"""
Bollinger Band + Volume Strategy for BTC Futures
- Long: ราคา breakout เหนือ upper band + volume spike + RSI < 70
- Short: ราคา breakdown ต่ำกว่า lower band + volume spike + RSI > 30
- Filter: ไม่เทรดตอน bandwidth แคบ (sideways)
- Stop Loss: ATR x 1.5
- Take Profit: RR 1:2
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    action: str
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str
    rsi: float
    bb_upper: float
    bb_lower: float
    bb_width: float
    volume_ratio: float
    atr: float
    ema_fast: float
    ema_slow: float


class BBVolumeStrategy:
    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        volume_ma: int = 20,
        volume_spike: float = 1.5,   # volume ต้องมากกว่าค่าเฉลี่ย 1.5x
        bb_width_min: float = 0.02,  # bandwidth ขั้นต่ำ 2% — กรอง sideways
        rsi_period: int = 14,
        rsi_long_max: float = 70,
        rsi_short_min: float = 30,
        atr_period: int = 14,
        atr_multiplier_sl: float = 1.5,
        rr_ratio: float = 2.0,
        ema_fast: int = 21,
        ema_slow: int = 50,
    ):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.volume_ma = volume_ma
        self.volume_spike = volume_spike
        self.bb_width_min = bb_width_min
        self.rsi_period = rsi_period
        self.rsi_long_max = rsi_long_max
        self.rsi_short_min = rsi_short_min
        self.atr_period = atr_period
        self.atr_multiplier_sl = atr_multiplier_sl
        self.rr_ratio = rr_ratio
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Bollinger Bands
        df["bb_mid"]   = df["close"].rolling(self.bb_period).mean()
        bb_std         = df["close"].rolling(self.bb_period).std()
        df["bb_upper"] = df["bb_mid"] + self.bb_std * bb_std
        df["bb_lower"] = df["bb_mid"] - self.bb_std * bb_std
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

        # Volume ratio vs MA
        df["vol_ma"]    = df["volume"].rolling(self.volume_ma).mean()
        df["vol_ratio"] = df["volume"] / df["vol_ma"]

        # RSI
        delta    = df["close"].diff()
        avg_gain = delta.clip(lower=0).ewm(alpha=1/self.rsi_period, adjust=False).mean()
        avg_loss = (-delta.clip(upper=0)).ewm(alpha=1/self.rsi_period, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

        # ATR
        hl  = df["high"] - df["low"]
        hc  = (df["high"] - df["close"].shift()).abs()
        lc  = (df["low"]  - df["close"].shift()).abs()
        tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df["atr"] = tr.ewm(alpha=1/self.atr_period, adjust=False).mean()

        # EMA trend
        df["ema_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()

        # Candle closed outside band (ใช้ close ไม่ใช่ high/low)
        df["close_above_upper"] = df["close"] > df["bb_upper"]
        df["close_below_lower"] = df["close"] < df["bb_lower"]
        df["prev_close_inside"] = (
            (df["close"].shift(1) <= df["bb_upper"].shift(1)) &
            (df["close"].shift(1) >= df["bb_lower"].shift(1))
        )

        return df

    def generate_signal(
        self, df: pd.DataFrame, current_position: Optional[str] = None
    ) -> TradeSignal:
        df     = self.calculate_indicators(df)
        latest = df.iloc[-1]
        prev   = df.iloc[-2]

        price       = latest["close"]
        rsi         = latest["rsi"]
        bb_upper    = latest["bb_upper"]
        bb_lower    = latest["bb_lower"]
        bb_width    = latest["bb_width"]
        vol_ratio   = latest["vol_ratio"]
        atr         = latest["atr"]
        ema_f       = latest["ema_fast"]
        ema_s       = latest["ema_slow"]

        sl_dist = atr * self.atr_multiplier_sl
        tp_dist = sl_dist * self.rr_ratio

        # Breakout conditions
        breakout_up   = (latest["close_above_upper"] and
                         latest["prev_close_inside"])
        breakout_down = (latest["close_below_lower"] and
                         latest["prev_close_inside"])

        # Filters
        enough_volatility = bb_width > self.bb_width_min
        volume_confirmed  = vol_ratio >= self.volume_spike
        uptrend           = ema_f > ema_s
        downtrend         = ema_f < ema_s

        def make_signal(action, reason):
            sl = price - sl_dist if action == "LONG" else price + sl_dist
            tp = price + tp_dist if action == "LONG" else price - tp_dist
            return TradeSignal(
                action=action, entry_price=price,
                stop_loss=sl, take_profit=tp, reason=reason,
                rsi=rsi, bb_upper=bb_upper, bb_lower=bb_lower,
                bb_width=round(bb_width, 4), volume_ratio=round(vol_ratio, 2),
                atr=atr, ema_fast=ema_f, ema_slow=ema_s,
            )

        def hold(reason):
            return TradeSignal(
                action="HOLD", entry_price=price,
                stop_loss=0, take_profit=0, reason=reason,
                rsi=rsi, bb_upper=bb_upper, bb_lower=bb_lower,
                bb_width=round(bb_width, 4), volume_ratio=round(vol_ratio, 2),
                atr=atr, ema_fast=ema_f, ema_slow=ema_s,
            )

        # Exit — ราคากลับเข้า middle band
        if current_position == "LONG" and price <= latest["bb_mid"]:
            return make_signal("CLOSE_LONG", "ราคากลับต่ำกว่า middle band")
        if current_position == "SHORT" and price >= latest["bb_mid"]:
            return make_signal("CLOSE_SHORT", "ราคากลับสูงกว่า middle band")

        # ไม่เทรดตอน sideways
        if not enough_volatility:
            return hold(f"BB width {bb_width:.3f} แคบเกิน — ตลาด sideways")

        # Entry LONG
        if breakout_up and volume_confirmed and uptrend and rsi < self.rsi_long_max and current_position != "LONG":
            return make_signal("LONG", f"BB breakout ↑ | Vol {vol_ratio:.1f}x | RSI {rsi:.1f}")

        # Entry SHORT
        if breakout_down and volume_confirmed and downtrend and rsi > self.rsi_short_min and current_position != "SHORT":
            return make_signal("SHORT", f"BB breakdown ↓ | Vol {vol_ratio:.1f}x | RSI {rsi:.1f}")

        # บอกเหตุผลที่ไม่เทรด
        if breakout_up and not volume_confirmed:
            return hold(f"Breakout ↑ แต่ volume แค่ {vol_ratio:.1f}x (ต้องการ {self.volume_spike}x)")
        if breakout_up and not uptrend:
            return hold("Breakout ↑ แต่ EMA21 < EMA50 — ไม่มี trend รองรับ")
        if breakout_down and not volume_confirmed:
            return hold(f"Breakdown ↓ แต่ volume แค่ {vol_ratio:.1f}x (ต้องการ {self.volume_spike}x)")

        return hold("รอสัญญาณ")
