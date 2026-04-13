# Frontend Dashboard Prompt for Claude Code

Copy the following prompt into Claude Code:

---

Build a React single-page dashboard for an "Attention Trading Agent" hackathon project. This agent monitors Forum.market (an attention futures exchange where you trade topic popularity), runs a five-factor analysis model, and calls the user's phone to pitch trades.

## Tech Stack
- React (Vite)
- TailwindCSS for styling
- Recharts for the radar chart
- Dark theme (zinc-900/950 background, zinc-800 borders)

## Data Source
The backend runs at http://localhost:8000. Two endpoints:
- `GET /api/reports` → returns `{ "reports": [...] }` 
- `GET /api/reports/latest` → returns the latest report

Each report looks like this (real example):
```json
{
  "id": "rpt_1776036024",
  "ticker": "SPACEX",
  "timestamp": 1776036024,
  "signal": {
    "ticker": "SPACEX",
    "dimensions": [
      { "name": "momentum", "score": 6, "weight": 0.25, "reasoning": "Clear downtrend from 5124 to 5050..." },
      { "name": "catalyst", "score": 8, "weight": 0.25, "reasoning": "Major IPO filing..." },
      { "name": "cross_platform", "score": 7, "weight": 0.20, "reasoning": "Reddit -37% but Google Trends only -5%..." },
      { "name": "cultural_context", "score": 9, "weight": 0.20, "reasoning": "Elon's private meme becomes public..." },
      { "name": "market_positioning", "score": 8, "weight": 0.10, "reasoning": "49% bid-heavy order book..." }
    ],
    "weighted_score": 7.5,
    "direction": "long",
    "confidence": 78,
    "summary": "SPACEX presents compelling opportunity...",
    "cultural_narrative": "We're witnessing the transition from private space cult to public mega-cap...",
    "suggested_qty": 12,
    "phone_script": "Yooo boss! SPACEX hitting different right now..."
  },
  "status": "trade_executed"
}
```

## Layout Design

Single page, three sections stacked vertically:

### Section 1: Header Bar (top)
- Title: "Attention Trading Agent" on the left
- Right side: green pulsing dot + "Agent Active" text
- Subtitle: "Five-Factor Attention Alpha Model"

### Section 2: Main Analysis (middle, two columns)

**Left column (60%):** Latest report details
- Ticker name large (e.g. "SPACEX")
- Direction badge: green "LONG" or red "SHORT" pill
- Confidence: big number with percent (e.g. "78%")
- Weighted score: "7.5 / 10"
- Status badge: "Pending" (yellow) / "Call Initiated" (blue) / "Trade Executed" (green)
- Summary paragraph
- Cultural Narrative paragraph (with 🎭 icon)
- Phone Script in a chat-bubble styled box (with 📞 icon)

**Right column (40%):** Radar Chart
- 5-axis radar chart using Recharts RadarChart
- Axes: Momentum, Catalyst, Cross-Platform, Cultural Context, Market Positioning
- Filled area with semi-transparent green
- Score labels on each axis showing the number

Below the radar chart: 5 individual score bars
- Each dimension: icon + name + progress bar (colored by score: green >= 7, yellow >= 4, red < 4) + score number
- Icons: 📈 Momentum, ⚡ Catalyst, 🌐 Cross-Platform, 🎭 Cultural Context, 📊 Market Position

### Section 3: Trade History (bottom)
- Simple table: Time | Ticker | Direction | Confidence | Score | Status
- Each row from the reports array
- Status column color-coded

## Behavior
- Poll `GET /api/reports/latest` every 5 seconds
- When new report arrives, update everything with a subtle fade animation
- If no reports yet, show a centered "Waiting for agent to find opportunities..." state with a spinning loader

## Style
- Professional dark trading terminal aesthetic
- Font: system mono for numbers, system sans for text
- Accent color: emerald/green for bullish, red for bearish
- Subtle borders, no harsh shadows
- Make it look like a Bloomberg terminal meets gen-Z design

## Important
- Everything in a single App.jsx file
- Use fetch() to poll the API, no external state management
- Make it responsive but optimize for a laptop screen (demo on projector)
- No login, no auth, just the dashboard
