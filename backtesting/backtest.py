"""
Backtesting engine for EMA+RSI strategy.
Run: python backtest.py --symbol BTCUSDT --interval 15m --days 90
"""

import argparse
import json
import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from binance.client import Client

# Add bot directory to path (works both locally and in Docker)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../bot"))
sys.path.insert(0, "/app/bot")
from strategy import BBVolumeStrategy as EMARSIStrategy


def fetch_historical_data(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """Fetch historical OHLCV data from Binance."""
    client = Client("", "")  # Public endpoint, no auth needed
    start = str(int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000))

    klines = client.get_historical_klines(symbol, interval, start)
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
    print(f"✅ Fetched {len(df)} candles for {symbol} ({interval})")
    return df


def run_backtest(
    df: pd.DataFrame,
    initial_balance: float = 1000.0,
    risk_pct: float = 1.0,
    leverage: int = 5,
) -> dict:
    """Run backtest simulation."""
    strategy = EMARSIStrategy()  # BBVolumeStrategy
    df = strategy.calculate_indicators(df)

    balance = initial_balance
    position = None
    trades = []
    equity_curve = []
    peak_balance = initial_balance
    max_drawdown = 0.0

    for i in range(50, len(df)):
        window = df.iloc[: i + 1]
        current = df.iloc[i]
        price = current["close"]
        timestamp = df.index[i]

        # Track equity
        equity = balance
        if position:
            if position["side"] == "LONG":
                equity += (price - position["entry"]) * position["qty"] * leverage
            else:
                equity += (position["entry"] - price) * position["qty"] * leverage
        equity_curve.append({"timestamp": str(timestamp), "equity": round(equity, 2)})

        # Max drawdown tracking
        if equity > peak_balance:
            peak_balance = equity
        dd = (peak_balance - equity) / peak_balance * 100
        if dd > max_drawdown:
            max_drawdown = dd

        signal = strategy.generate_signal(window, position["side"] if position else None)

        # Check SL/TP
        if position:
            hit_sl = hit_tp = False
            if position["side"] == "LONG":
                hit_sl = current["low"] <= position["sl"]
                hit_tp = current["high"] >= position["tp"]
            else:
                hit_sl = current["high"] >= position["sl"]
                hit_tp = current["low"] <= position["tp"]

            if hit_tp or hit_sl:
                exit_price = position["tp"] if hit_tp else position["sl"]
                pnl = (
                    (exit_price - position["entry"]) * position["qty"] * leverage
                    if position["side"] == "LONG"
                    else (position["entry"] - exit_price) * position["qty"] * leverage
                )
                balance += pnl
                trades.append({
                    "timestamp": str(timestamp),
                    "side": position["side"],
                    "entry": position["entry"],
                    "exit": exit_price,
                    "pnl": round(pnl, 4),
                    "pnl_pct": round(pnl / initial_balance * 100, 3),
                    "result": "WIN" if hit_tp else "LOSS",
                    "reason": "Take Profit" if hit_tp else "Stop Loss",
                })
                position = None
                continue

        # Execute signals
        if signal.action in ("CLOSE_LONG", "CLOSE_SHORT") and position:
            exit_price = price
            pnl = (
                (exit_price - position["entry"]) * position["qty"] * leverage
                if position["side"] == "LONG"
                else (position["entry"] - exit_price) * position["qty"] * leverage
            )
            balance += pnl
            trades.append({
                "timestamp": str(timestamp),
                "side": position["side"],
                "entry": position["entry"],
                "exit": exit_price,
                "pnl": round(pnl, 4),
                "pnl_pct": round(pnl / initial_balance * 100, 3),
                "result": "WIN" if pnl > 0 else "LOSS",
                "reason": signal.reason,
            })
            position = None

        elif signal.action in ("LONG", "SHORT") and not position:
            sl_dist = abs(price - signal.stop_loss)
            risk_amount = balance * (risk_pct / 100)
            qty = risk_amount / (price * (sl_dist / price))

            if qty > 0 and balance > 0:
                position = {
                    "side": signal.action,
                    "entry": price,
                    "qty": qty,
                    "sl": signal.stop_loss,
                    "tp": signal.take_profit,
                }

    # Compute stats
    wins = [t for t in trades if t["result"] == "WIN"]
    losses = [t for t in trades if t["result"] == "LOSS"]
    total_pnl = sum(t["pnl"] for t in trades)
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    avg_win = np.mean([t["pnl"] for t in wins]) if wins else 0
    avg_loss = abs(np.mean([t["pnl"] for t in losses])) if losses else 1
    profit_factor = (sum(t["pnl"] for t in wins) / abs(sum(t["pnl"] for t in losses))) if losses else float("inf")

    return {
        "summary": {
            "initial_balance": initial_balance,
            "final_balance": round(balance, 2),
            "total_return_pct": round((balance - initial_balance) / initial_balance * 100, 2),
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 3),
            "avg_win": round(avg_win, 4),
            "avg_loss": round(avg_loss, 4),
            "risk_reward": round(avg_win / avg_loss, 2) if avg_loss else 0,
            "max_drawdown_pct": round(max_drawdown, 2),
            "sharpe_ratio": round(
                np.mean([t["pnl"] for t in trades]) / (np.std([t["pnl"] for t in trades]) + 1e-9), 3
            ) if trades else 0,
        },
        "trades": trades[-100:],  # last 100 trades
        "equity_curve": equity_curve[-500:],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest EMA+RSI Strategy")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--balance", type=float, default=1000.0)
    parser.add_argument("--risk", type=float, default=1.0)
    parser.add_argument("--leverage", type=int, default=5)
    parser.add_argument("--output", default="/app/data/backtest_result.json")
    args = parser.parse_args()

    df = fetch_historical_data(args.symbol, args.interval, args.days)
    result = run_backtest(df, args.balance, args.risk, args.leverage)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    s = result["summary"]
    print("\n" + "="*50)
    print(f"📊 BACKTEST RESULTS: {args.symbol} ({args.interval}, {args.days}d)")
    print("="*50)
    print(f"Initial Balance : ${s['initial_balance']:,.2f}")
    print(f"Final Balance   : ${s['final_balance']:,.2f}")
    print(f"Total Return    : {s['total_return_pct']:+.2f}%")
    print(f"Total Trades    : {s['total_trades']}")
    print(f"Win Rate        : {s['win_rate']:.1f}%")
    print(f"Profit Factor   : {s['profit_factor']:.2f}")
    print(f"Max Drawdown    : {s['max_drawdown_pct']:.2f}%")
    print(f"Sharpe Ratio    : {s['sharpe_ratio']:.3f}")
    print(f"Results saved to: {args.output}")