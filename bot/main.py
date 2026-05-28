"""
Main trading bot runner.
Runs on a schedule, checks signals, manages positions with SL/TP.
"""

import os
import time
import logging
import json
from datetime import datetime
from pathlib import Path

from strategy import BBVolumeStrategy as EMARSIStrategy
from exchange import BinanceFuturesConnector

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/app/logs/bot.log"),
    ],
)
logger = logging.getLogger(__name__)

# State file for dashboard
STATE_FILE = "/app/data/bot_state.json"
TRADES_FILE = "/app/data/trades.json"


def save_state(state: dict):
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def load_trades() -> list:
    if Path(TRADES_FILE).exists():
        with open(TRADES_FILE) as f:
            return json.load(f)
    return []


def save_trade(trade: dict):
    trades = load_trades()
    trades.append(trade)
    # Keep last 500 trades
    trades = trades[-500:]
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2, default=str)


def calculate_position_size(balance: float, risk_pct: float, sl_distance: float, price: float) -> float:
    """Risk-based position sizing."""
    risk_amount = balance * (risk_pct / 100)
    sl_pct = sl_distance / price
    quantity = risk_amount / (price * sl_pct)
    return round(quantity, 3)


def run_bot():
    # Config from environment
    symbol = os.getenv("SYMBOL", "BTCUSDT")
    interval = os.getenv("INTERVAL", "15m")
    leverage = int(os.getenv("LEVERAGE", "5"))
    risk_pct = float(os.getenv("RISK_PCT", "1.0"))  # 1% risk per trade

    exchange = BinanceFuturesConnector()
    strategy = EMARSIStrategy()

    logger.info(f"🚀 Bot started | {symbol} | {interval} | Leverage: {leverage}x | Risk: {risk_pct}%")

    # Set leverage
    exchange.set_leverage(symbol, leverage)

    while True:
        try:
            # Get market data
            df = exchange.get_klines(symbol, interval, limit=100)
            position = exchange.get_position(symbol)
            balance = exchange.get_account_balance()

            current_side = position["side"] if position else None
            signal = strategy.generate_signal(df, current_side)

            latest_price = df["close"].iloc[-1]
            timestamp = datetime.utcnow().isoformat()

            logger.info(
                f"Signal: {signal.action} | Price: {latest_price:.2f} | "
                f"RSI: {signal.rsi:.1f} | EMA({strategy.ema_fast}): {signal.ema_fast:.2f} | "
                f"EMA({strategy.ema_slow}): {signal.ema_slow:.2f}"
            )

            # Save state for dashboard
            save_state({
                "timestamp": timestamp,
                "symbol": symbol,
                "interval": interval,
                "price": latest_price,
                "signal": signal.action,
                "reason": signal.reason,
                "rsi": round(signal.rsi, 2),
                "ema_fast": round(signal.ema_fast, 2),
                "ema_slow": round(signal.ema_slow, 2),
                "atr": round(signal.atr, 4),
                "balance": round(balance, 2),
                "position": position,
                "leverage": leverage,
                "risk_pct": risk_pct,
            })

            # Execute trades
            if signal.action in ("CLOSE_LONG", "CLOSE_SHORT") and position:
                logger.info(f"🔄 Closing {position['side']} position: {signal.reason}")
                exchange.close_position(symbol, position)
                save_trade({
                    "timestamp": timestamp, "type": signal.action,
                    "symbol": symbol, "price": latest_price,
                    "reason": signal.reason, "pnl": position.get("unrealized_pnl", 0),
                })

            elif signal.action in ("LONG", "SHORT") and not position:
                sl_dist = abs(latest_price - signal.stop_loss)
                qty = calculate_position_size(balance, risk_pct, sl_dist, latest_price)

                if qty <= 0:
                    logger.warning("Insufficient balance for trade")
                else:
                    order_side = "BUY" if signal.action == "LONG" else "SELL"
                    sl_side = "SELL" if signal.action == "LONG" else "BUY"

                    logger.info(f"📈 Opening {signal.action} | Qty: {qty} | SL: {signal.stop_loss:.2f} | TP: {signal.take_profit:.2f}")

                    exchange.place_market_order(symbol, order_side, qty)
                    time.sleep(1)  # Wait for fill
                    exchange.place_stop_loss(symbol, sl_side, qty, signal.stop_loss)
                    exchange.place_take_profit(symbol, sl_side, qty, signal.take_profit)

                    save_trade({
                        "timestamp": timestamp, "type": signal.action,
                        "symbol": symbol, "price": latest_price,
                        "stop_loss": signal.stop_loss, "take_profit": signal.take_profit,
                        "quantity": qty, "reason": signal.reason, "pnl": 0,
                    })

        except Exception as e:
            logger.error(f"❌ Error in main loop: {e}", exc_info=True)

        # Wait for next candle (interval in seconds)
        interval_seconds = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}.get(interval, 900)
        logger.info(f"⏳ Next check in {interval_seconds}s...")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_bot()