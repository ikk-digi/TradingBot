"""
Binance Futures API connector using python-binance.
Handles order placement, position management, and market data.
"""

import os
import time
import logging
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class BinanceFuturesConnector:
    def __init__(self):
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.api_secret = os.getenv("BINANCE_API_SECRET", "")
        self.testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

        self.client = Client(self.api_key, self.api_secret, testnet=self.testnet)

        if self.testnet:
            self.client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"
            logger.info("🧪 Using Binance Futures TESTNET")
        else:
            logger.warning("⚠️  Using LIVE trading - be careful!")

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
        """Fetch OHLCV candle data."""
        try:
            klines = self.client.futures_klines(
                symbol=symbol, interval=interval, limit=limit
            )
            df = pd.DataFrame(
                klines,
                columns=[
                    "timestamp", "open", "high", "low", "close", "volume",
                    "close_time", "quote_volume", "trades",
                    "taker_buy_base", "taker_buy_quote", "ignore",
                ],
            )
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            return df
        except BinanceAPIException as e:
            logger.error(f"Failed to get klines: {e}")
            raise

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current futures position for a symbol."""
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            for pos in positions:
                amt = float(pos["positionAmt"])
                if abs(amt) > 0:
                    return {
                        "symbol": pos["symbol"],
                        "side": "LONG" if amt > 0 else "SHORT",
                        "size": abs(amt),
                        "entry_price": float(pos["entryPrice"]),
                        "unrealized_pnl": float(pos["unRealizedProfit"]),
                        "leverage": int(pos["leverage"]),
                    }
            return None
        except BinanceAPIException as e:
            logger.error(f"Failed to get position: {e}")
            return None

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol."""
        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            logger.info(f"Set leverage {leverage}x for {symbol}")
            return True
        except BinanceAPIException as e:
            logger.error(f"Failed to set leverage: {e}")
            return False

    def place_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> Optional[Dict]:
        """Place a market order. side: 'BUY' or 'SELL'"""
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity,
            )
            logger.info(f"✅ Market order placed: {side} {quantity} {symbol}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Failed to place market order: {e}")
            return None

    def place_stop_loss(
        self, symbol: str, side: str, quantity: float, stop_price: float
    ) -> Optional[Dict]:
        """Place stop-loss order. side should be opposite of position."""
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="STOP_MARKET",
                quantity=quantity,
                stopPrice=round(stop_price, 2),
                closePosition=True,
            )
            logger.info(f"🛡️ Stop-loss set at {stop_price}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Failed to place stop-loss: {e}")
            return None

    def place_take_profit(
        self, symbol: str, side: str, quantity: float, stop_price: float
    ) -> Optional[Dict]:
        """Place take-profit order."""
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="TAKE_PROFIT_MARKET",
                quantity=quantity,
                stopPrice=round(stop_price, 2),
                closePosition=True,
            )
            logger.info(f"🎯 Take-profit set at {stop_price}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Failed to place take-profit: {e}")
            return None

    def cancel_all_orders(self, symbol: str) -> bool:
        """Cancel all open orders for a symbol."""
        try:
            self.client.futures_cancel_all_open_orders(symbol=symbol)
            logger.info(f"Cancelled all orders for {symbol}")
            return True
        except BinanceAPIException as e:
            logger.error(f"Failed to cancel orders: {e}")
            return False

    def get_account_balance(self) -> float:
        """Get USDT futures wallet balance."""
        try:
            account = self.client.futures_account_balance()
            for asset in account:
                if asset["asset"] == "USDT":
                    return float(asset["balance"])
            return 0.0
        except BinanceAPIException as e:
            logger.error(f"Failed to get balance: {e}")
            return 0.0

    def close_position(self, symbol: str, position: Dict) -> bool:
        """Close an existing position."""
        self.cancel_all_orders(symbol)
        side = "SELL" if position["side"] == "LONG" else "BUY"
        result = self.place_market_order(symbol, side, position["size"])
        return result is not None
