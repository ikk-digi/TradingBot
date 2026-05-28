<<<<<<< HEAD
# 🤖 Binance Futures Trading Bot

กลยุทธ์: **EMA Crossover (9/21) + RSI (14) Filter**
พร้อม Stop Loss/Take Profit อัตโนมัติ, Backtesting และ Web Dashboard

---

## 📊 กลยุทธ์

| สัญญาณ | เงื่อนไข |
|--------|----------|
| **LONG** | EMA9 ตัดขึ้น EMA21 + RSI > 50 |
| **SHORT** | EMA9 ตัดลง EMA21 + RSI < 50 |
| **Stop Loss** | ATR × 1.5 |
| **Take Profit** | Stop Loss × 2.0 (Risk:Reward = 1:2) |
| **Position Size** | Risk 1% ของ Balance ต่อเทรด |

---

## 🚀 วิธีติดตั้ง

### 1. Clone และตั้งค่า

```bash
git clone <your-repo>
cd trading-bot

# คัดลอก env template
cp .env.example .env

# แก้ไขใส่ API Key
nano .env
```

### 2. สร้าง Binance API Key

1. ไปที่ [Binance Futures Testnet](https://testnet.binancefuture.com) สำหรับทดสอบ
2. หรือ [Binance](https://www.binance.com) > Account > API Management
3. Enable **Futures Trading** permission
4. ห้าม enable **Withdrawal** permission

### 3. รัน Backtest ก่อน

```bash
# รัน backtest ด้วย Docker
docker compose --profile backtest run backtest

# ดูผลใน /app/data/backtest_result.json
# หรือดูผ่าน Dashboard ที่ http://localhost:8080
```

### 4. เริ่ม Bot (Testnet)

```bash
# Build และรัน
docker compose up -d

# ดู logs
docker compose logs -f bot

# ดู Dashboard
open http://localhost:8080
```

### 5. เปลี่ยนเป็น Live Trading

⚠️ **ทดสอบกับ Testnet อย่างน้อย 2-4 สัปดาห์ก่อน!**

```bash
# แก้ .env
BINANCE_TESTNET=false

# Restart
docker compose down && docker compose up -d
```

---

## 📁 โครงสร้างไฟล์

```
trading-bot/
├── bot/
│   ├── main.py          # Main bot runner
│   ├── strategy.py      # EMA+RSI strategy logic
│   └── exchange.py      # Binance API connector
├── backtesting/
│   └── backtest.py      # Backtesting engine
├── dashboard/
│   └── app.py           # Web dashboard (Flask)
├── docker-compose.yml
├── Dockerfile.bot
├── Dockerfile.dashboard
├── .env.example         # ⚠️ Copy เป็น .env และใส่ credentials
└── .gitignore           # .env ถูก ignore แล้ว
```

---

## ⚙️ คำสั่งที่ใช้บ่อย

```bash
# เริ่มทั้งหมด
docker compose up -d

# หยุด bot (ไม่ปิด dashboard)
docker compose stop bot

# ดู logs realtime
docker compose logs -f bot

# รัน backtest อีกครั้ง
docker compose --profile backtest run --rm backtest

# ล้างข้อมูลทั้งหมด
docker compose down -v
```

---

## ⚠️ ข้อควรระวัง

- **อย่า commit ไฟล์ `.env`** ขึ้น Git เด็ดขาด
- เริ่มด้วย **Leverage ต่ำ (3-5x)** และ **Risk 0.5-1%**
- Futures trading มีความเสี่ยงสูง — อาจขาดทุนได้ทั้งหมด
- bot นี้เป็น **educational purpose** ไม่ใช่คำแนะนำการลงทุน
=======
# TradingBot
>>>>>>> 3cee1a2ef5704f88a881acbcd86f2fdf28d8e278
