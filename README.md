# 📞 Attention Trading Agent

**An AI agent that reads culture, not just data.**

It monitors [Forum.market](https://forum.market) attention futures, runs a five-factor cultural analysis, and **calls your phone** to pitch trades in real-time.

> *“Other trading bots read numbers. Our agent reads culture.”*

Built at **SDxUCSD Agent Hackathon** · Forum Track · April 2026

-----

## Demo

1. Agent scans 39 attention markets every 60 seconds
1. Finds an opportunity (e.g. SPACEX IPO filing + bid-heavy order book)
1. **Your phone rings** — AI pitches the trade in gen-Z casual voice
1. You say “buy 5 contracts” → trade executes on Forum.market instantly
1. Dashboard shows the full five-factor analysis with radar chart

-----

## Five-Factor Attention Alpha Model

|Dimension           |Weight|Data Source          |What It Measures                 |
|--------------------|------|---------------------|---------------------------------|
|📈 Momentum          |25%   |Forum candles        |Multi-timeframe price trend      |
|⚡ Catalyst          |25%   |Web search (Claude)  |What event is driving attention  |
|🌐 Cross-Platform    |20%   |Forum index breakdown|Twitter vs Reddit vs Google lag  |
|🎭 Cultural Context  |20%   |Claude analysis      |WHY it’s trending, meme lifecycle|
|📊 Market Positioning|10%   |Forum order book     |Smart money vs retail positioning|

The cross-platform divergence is the killer signal: **Twitter exploded but Google Trends hasn’t moved? You’re early.**

-----

## Architecture

```
┌──────────────────────────────────────┐
│  Scanner (run_scanner.py)            │
│  Scans 39 markets every 60s          │
│  Stage 1: Quick screen (free)        │
│  Stage 2: Deep analysis (Claude)     │
└──────────────┬───────────────────────┘
               │ Opportunity found
               ▼
┌──────────────────────────────────────┐
│  Alpha Model (agent/alpha_model.py)  │
│  Five-factor scoring + web search    │
│  Outputs: direction, confidence,     │
│  cultural narrative, phone script    │
└──────────────┬───────────────────────┘
               │ Confidence >= 70%
               ▼
┌──────────────────────────────────────┐
│  Voice Agent (agent/voice_agent.py)  │
│  Vapi.ai calls your phone            │
│  Real-time conversation              │
│  "Buy 5 contracts" → executes trade  │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│  Forum.market API                    │
│  Trade executed, position opened     │
│  Dashboard updated in real-time      │
└──────────────────────────────────────┘
```

-----

## Project Structure

```
AttentionTradingAgent/
├── .env                        # API keys (git ignored)
├── forum_client.py             # Forum.market API SDK
├── run_analysis.py             # Single ticker analysis
├── run_scanner.py              # Continuous market scanner
├── agent/
│   ├── alpha_model.py          # Five-factor scoring engine
│   ├── prompts.py              # Claude system prompts
│   ├── monitor.py              # Anomaly detection
│   ├── voice_agent.py          # Vapi phone call controller
│   └── report_generator.py     # Report creation
├── server/
│   └── main.py                 # FastAPI webhooks + demo triggers
└── dashboard/                  # React frontend
    └── src/App.jsx             # Live dashboard with radar chart
```

-----

## Setup

### 1. Install dependencies

```bash
pip install fastapi uvicorn requests anthropic python-dotenv httpx
```

### 2. Configure `.env`

```env
# Forum.market
FORUM_API_KEY=fk_your_key
FORUM_API_SECRET=your_secret

# Claude
ANTHROPIC_API_KEY=sk-ant-your_key

# Vapi.ai
VAPI_API_KEY=your_vapi_key
VAPI_PHONE_NUMBER_ID=your_phone_id
VAPI_ASSISTANT_ID=your_assistant_id
USER_PHONE_NUMBER=+1your_phone
```

### 3. Run

```bash
# Terminal 1: Expose webhooks
ngrok http 8000

# Terminal 2: Start API server
python -m server.main

# Terminal 3: Start scanner with phone calls
python run_scanner.py --call
```

### 4. Demo trigger

```bash
curl -X POST http://localhost:8000/api/trigger-call?ticker=SPACEX
```

-----

## Usage

```bash
# Single analysis
python run_analysis.py OPENAI

# Continuous scanning (report only)
python run_scanner.py

# Scanning + phone calls
python run_scanner.py --call

# Scanning + auto-trade (no phone, just executes)
python run_scanner.py --auto-trade

# Adjust settings
python run_scanner.py --call --threshold 80 --interval 120 --top-n 3
```

-----

## Tech Stack

- **Python** — Backend, analysis engine, API client
- **Claude API** (Anthropic) — Five-factor analysis + web search + cultural narrative
- **Vapi.ai** — AI phone calls with real-time voice conversation
- **Forum.market API** — Attention futures trading (HMAC-SHA256 auth)
- **FastAPI** — Webhook server for Vapi function calls
- **React + Recharts + TailwindCSS** — Live dashboard
- **ngrok** — Expose local server for Vapi callbacks

-----

## Key Design Decisions

**Two-stage scanning** — Stage 1 screens all 39 tickers using only Forum data (free, ~0.5s each). Stage 2 runs full Claude analysis only on top 2-3 candidates. Saves API credits.

**Human-in-the-loop** — The agent is fully autonomous in perception and analysis. The only thing it asks is a final yes or no. Because when it comes to your money, you should always have the last word.

**Culture over data** — The agent doesn’t just see that a topic is trending. It understands WHY — meme lifecycle, ironic vs genuine engagement, narrative arcs, cultural momentum.

-----

## Team

Built at SDxUCSD Agent Hackathon, April 12, 2026

**Forum Track** — Build something at the intersection of finance and culture.
