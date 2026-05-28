"""
Flask web dashboard for trading bot monitoring.
Shows live bot state, trade history, and backtest results.
"""

import json
import os
from pathlib import Path
from flask import Flask, jsonify, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

STATE_FILE = "/app/data/bot_state.json"
TRADES_FILE = "/app/data/trades.json"
BACKTEST_FILE = "/app/data/backtest_result.json"


def read_json(path: str) -> dict | list | None:
    if Path(path).exists():
        with open(path) as f:
            return json.load(f)
    return None


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Trading Bot Dashboard</title>
  <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0a0e17;
      --surface: #111827;
      --border: #1e2d40;
      --accent: #00d4ff;
      --green: #00ff9d;
      --red: #ff4757;
      --yellow: #ffd32a;
      --text: #e2e8f0;
      --muted: #64748b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; min-height: 100vh; }
    .grid-bg {
      position: fixed; inset: 0; z-index: 0; pointer-events: none;
      background-image: linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px);
      background-size: 40px 40px;
    }
    .container { max-width: 1400px; margin: 0 auto; padding: 24px; position: relative; z-index: 1; }
    header { display: flex; align-items: center; gap: 16px; margin-bottom: 32px; }
    .logo { width: 40px; height: 40px; background: var(--accent); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 20px; }
    h1 { font-family: 'Space Mono', monospace; font-size: 20px; color: var(--accent); }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 10px var(--green); animation: pulse 2s infinite; margin-left: auto; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
    .card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 12px; padding: 20px;
      transition: border-color 0.2s;
    }
    .card:hover { border-color: var(--accent); }
    .card-label { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin-bottom: 8px; }
    .card-value { font-family: 'Space Mono', monospace; font-size: 24px; font-weight: 700; }
    .card-value.green { color: var(--green); }
    .card-value.red { color: var(--red); }
    .card-value.accent { color: var(--accent); }
    .card-value.yellow { color: var(--yellow); }

    .main-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
    @media (max-width: 900px) { .main-grid { grid-template-columns: 1fr; } }

    .panel { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
    .panel-header { padding: 16px 20px; border-bottom: 1px solid var(--border); font-family: 'Space Mono', monospace; font-size: 13px; color: var(--accent); display: flex; justify-content: space-between; align-items: center; }
    .panel-body { padding: 20px; }

    .signal-badge {
      display: inline-block; padding: 4px 12px; border-radius: 20px;
      font-family: 'Space Mono', monospace; font-size: 12px; font-weight: 700;
    }
    .signal-LONG { background: rgba(0,255,157,0.15); color: var(--green); border: 1px solid var(--green); }
    .signal-SHORT { background: rgba(255,71,87,0.15); color: var(--red); border: 1px solid var(--red); }
    .signal-HOLD { background: rgba(255,211,42,0.15); color: var(--yellow); border: 1px solid var(--yellow); }
    .signal-CLOSE_LONG, .signal-CLOSE_SHORT { background: rgba(100,116,139,0.2); color: var(--muted); border: 1px solid var(--muted); }

    .indicator-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid rgba(30,45,64,0.6); }
    .indicator-row:last-child { border-bottom: none; }
    .indicator-label { color: var(--muted); font-size: 13px; }
    .indicator-value { font-family: 'Space Mono', monospace; font-size: 14px; }

    .trade-list { max-height: 320px; overflow-y: auto; }
    .trade-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid rgba(30,45,64,0.5); font-size: 13px; }
    .trade-item:last-child { border-bottom: none; }
    .trade-side { font-family: 'Space Mono', monospace; font-size: 11px; }
    .trade-pnl { font-family: 'Space Mono', monospace; }
    .pnl-pos { color: var(--green); }
    .pnl-neg { color: var(--red); }

    .refresh-btn {
      background: transparent; border: 1px solid var(--accent); color: var(--accent);
      padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 12px;
      font-family: 'Space Mono', monospace; transition: all 0.2s;
    }
    .refresh-btn:hover { background: var(--accent); color: var(--bg); }

    .backtest-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .bt-stat { padding: 12px; background: rgba(0,212,255,0.05); border-radius: 8px; border: 1px solid rgba(0,212,255,0.1); }
    .bt-label { font-size: 11px; color: var(--muted); margin-bottom: 4px; }
    .bt-value { font-family: 'Space Mono', monospace; font-size: 16px; }

    .position-box { background: rgba(0,255,157,0.05); border: 1px solid rgba(0,255,157,0.2); border-radius: 8px; padding: 16px; margin-bottom: 16px; }
    .position-box.short { background: rgba(255,71,87,0.05); border-color: rgba(255,71,87,0.2); }
    .no-position { color: var(--muted); font-size: 13px; text-align: center; padding: 20px; }

    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
  </style>
</head>
<body>
  <div class="grid-bg"></div>
  <div class="container">
    <header>
      <div class="logo">⚡</div>
      <div>
        <h1>TRADING BOT DASHBOARD</h1>
        <div style="font-size:12px; color: var(--muted); margin-top:2px;">EMA Crossover + RSI Strategy</div>
      </div>
      <div class="status-dot" id="statusDot"></div>
    </header>

    <div class="cards" id="statsCards">
      <div class="card"><div class="card-label">Balance (USDT)</div><div class="card-value accent" id="balance">—</div></div>
      <div class="card"><div class="card-label">Current Price</div><div class="card-value" id="price">—</div></div>
      <div class="card"><div class="card-label">Signal</div><div id="signalBadge"><span class="signal-badge signal-HOLD">HOLD</span></div></div>
      <div class="card"><div class="card-label">RSI (14)</div><div class="card-value yellow" id="rsi">—</div></div>
      <div class="card"><div class="card-label">Symbol</div><div class="card-value accent" id="symbol">—</div></div>
      <div class="card"><div class="card-label">Last Update</div><div class="card-value" style="font-size:14px" id="lastUpdate">—</div></div>
    </div>

    <div class="main-grid">
      <div>
        <div class="panel" style="margin-bottom:24px">
          <div class="panel-header">
            📍 Current Position
            <button class="refresh-btn" onclick="loadState()">↻ Refresh</button>
          </div>
          <div class="panel-body" id="positionPanel">
            <div class="no-position">No open position</div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">📈 Indicators</div>
          <div class="panel-body" id="indicators">
            <div class="no-position">Loading...</div>
          </div>
        </div>
      </div>

      <div>
        <div class="panel" style="margin-bottom:24px">
          <div class="panel-header">📋 Recent Trades</div>
          <div class="panel-body">
            <div class="trade-list" id="tradeList">
              <div class="no-position">No trades yet</div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">🔬 Backtest Results</div>
          <div class="panel-body">
            <div class="backtest-grid" id="backtestGrid">
              <div class="no-position" style="grid-column:1/-1">Run backtest to see results</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    async function loadState() {
      try {
        const res = await fetch('/api/state');
        const d = await res.json();
        if (!d) return;

        document.getElementById('balance').textContent = d.balance ? `$${d.balance.toLocaleString()}` : '—';
        document.getElementById('price').textContent = d.price ? `$${d.price.toLocaleString()}` : '—';
        document.getElementById('symbol').textContent = d.symbol || '—';
        document.getElementById('rsi').textContent = d.rsi ? d.rsi.toFixed(1) : '—';

        if (d.timestamp) {
          const dt = new Date(d.timestamp);
          document.getElementById('lastUpdate').textContent = dt.toLocaleTimeString();
        }

        const sig = d.signal || 'HOLD';
        document.getElementById('signalBadge').innerHTML = `<span class="signal-badge signal-${sig}">${sig}</span>`;

        // Indicators
        if (d.ema_fast) {
          document.getElementById('indicators').innerHTML = `
            <div class="indicator-row"><span class="indicator-label">EMA Fast (9)</span><span class="indicator-value">$${d.ema_fast?.toLocaleString()}</span></div>
            <div class="indicator-row"><span class="indicator-label">EMA Slow (21)</span><span class="indicator-value">$${d.ema_slow?.toLocaleString()}</span></div>
            <div class="indicator-row"><span class="indicator-label">RSI (14)</span><span class="indicator-value" style="color:${d.rsi > 70 ? 'var(--red)' : d.rsi < 30 ? 'var(--green)' : 'var(--text)'}">${d.rsi?.toFixed(2)}</span></div>
            <div class="indicator-row"><span class="indicator-label">ATR (14)</span><span class="indicator-value">${d.atr?.toFixed(4)}</span></div>
            <div class="indicator-row"><span class="indicator-label">Interval</span><span class="indicator-value accent">${d.interval}</span></div>
            <div class="indicator-row"><span class="indicator-label">Leverage</span><span class="indicator-value">${d.leverage}x</span></div>
            <div class="indicator-row"><span class="indicator-label">Reason</span><span class="indicator-value" style="font-size:12px;color:var(--muted)">${d.reason}</span></div>
          `;
        }

        // Position
        const pos = d.position;
        if (pos) {
          const pnlColor = pos.unrealized_pnl >= 0 ? 'var(--green)' : 'var(--red)';
          document.getElementById('positionPanel').innerHTML = `
            <div class="position-box ${pos.side === 'SHORT' ? 'short' : ''}">
              <div style="display:flex;justify-content:space-between;margin-bottom:8px">
                <span class="signal-badge signal-${pos.side}">${pos.side}</span>
                <span style="font-family:'Space Mono',monospace;color:${pnlColor}">${pos.unrealized_pnl >= 0 ? '+' : ''}$${pos.unrealized_pnl?.toFixed(2)}</span>
              </div>
              <div class="indicator-row"><span class="indicator-label">Entry Price</span><span class="indicator-value">$${pos.entry_price?.toLocaleString()}</span></div>
              <div class="indicator-row"><span class="indicator-label">Size</span><span class="indicator-value">${pos.size}</span></div>
              <div class="indicator-row"><span class="indicator-label">Leverage</span><span class="indicator-value">${pos.leverage}x</span></div>
            </div>
          `;
        } else {
          document.getElementById('positionPanel').innerHTML = '<div class="no-position">No open position</div>';
        }
      } catch(e) {}
    }

    async function loadTrades() {
      try {
        const res = await fetch('/api/trades');
        const trades = await res.json();
        if (!trades || !trades.length) return;
        const html = trades.slice(-20).reverse().map(t => {
          const pnlClass = t.pnl >= 0 ? 'pnl-pos' : 'pnl-neg';
          const pnlSign = t.pnl >= 0 ? '+' : '';
          return `<div class="trade-item">
            <div>
              <span class="signal-badge signal-${t.type}" style="font-size:10px">${t.type}</span>
              <div style="font-size:11px;color:var(--muted);margin-top:4px">${new Date(t.timestamp).toLocaleString()}</div>
            </div>
            <div style="text-align:right">
              <div class="trade-pnl ${pnlClass}">${pnlSign}$${parseFloat(t.pnl || 0).toFixed(4)}</div>
              <div style="font-size:11px;color:var(--muted)">$${parseFloat(t.price).toFixed(2)}</div>
            </div>
          </div>`;
        }).join('');
        document.getElementById('tradeList').innerHTML = html;
      } catch(e) {}
    }

    async function loadBacktest() {
      try {
        const res = await fetch('/api/backtest');
        const d = await res.json();
        if (!d || !d.summary) return;
        const s = d.summary;
        const retColor = s.total_return_pct >= 0 ? 'var(--green)' : 'var(--red)';
        document.getElementById('backtestGrid').innerHTML = `
          <div class="bt-stat"><div class="bt-label">Total Return</div><div class="bt-value" style="color:${retColor}">${s.total_return_pct >= 0 ? '+' : ''}${s.total_return_pct}%</div></div>
          <div class="bt-stat"><div class="bt-label">Win Rate</div><div class="bt-value" style="color:var(--green)">${s.win_rate}%</div></div>
          <div class="bt-stat"><div class="bt-label">Total Trades</div><div class="bt-value">${s.total_trades}</div></div>
          <div class="bt-stat"><div class="bt-label">Profit Factor</div><div class="bt-value" style="color:var(--accent)">${s.profit_factor}</div></div>
          <div class="bt-stat"><div class="bt-label">Max Drawdown</div><div class="bt-value" style="color:var(--red)">${s.max_drawdown_pct}%</div></div>
          <div class="bt-stat"><div class="bt-label">Sharpe Ratio</div><div class="bt-value">${s.sharpe_ratio}</div></div>
        `;
      } catch(e) {}
    }

    loadState();
    loadTrades();
    loadBacktest();
    setInterval(() => { loadState(); loadTrades(); }, 30000);
  </script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/state")
def get_state():
    return jsonify(read_json(STATE_FILE))


@app.route("/api/trades")
def get_trades():
    return jsonify(read_json(TRADES_FILE) or [])


@app.route("/api/backtest")
def get_backtest():
    return jsonify(read_json(BACKTEST_FILE))


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
