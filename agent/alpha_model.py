"""
Attention Alpha Model — 五维结构化评分引擎
==========================================
Forum.market Hackathon · Layer 2

Takes raw Forum API data (candles, index, order book) + Claude analysis
to produce a structured AlphaSignal with trading recommendation.

Usage:
    from agent.alpha_model import AttentionAlphaModel, AlphaSignal
    from anthropic import Anthropic
    from forum_client import ForumClient

    model = AttentionAlphaModel(
        forum_client=ForumClient(api_key="fk_...", api_secret="sk_..."),
        claude_client=Anthropic(),
    )
    signal = model.analyze("OPENAI", trigger_reason="Manual demo trigger")
    print(signal.direction, signal.confidence, signal.should_call)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic

from agent.prompts import ALPHA_MODEL_SYSTEM_PROMPT, ANALYSIS_PROMPT_TEMPLATE

# Try importing ForumClient — allow running without it for tests
try:
    from forum_client import ForumClient
except ImportError:
    ForumClient = None  # type: ignore


# ─── Data classes ─────────────────────────────────────────────────────

@dataclass
class DimensionScore:
    """Single dimension score."""
    name: str
    score: int           # 1-10
    weight: float        # fractional weight
    reasoning: str
    data_points: list[str] = field(default_factory=list)


@dataclass
class AlphaSignal:
    """Complete five-factor analysis output."""
    ticker: str
    timestamp: float
    dimensions: list[DimensionScore]
    weighted_score: float        # 1-10 weighted average
    direction: str               # "long" | "short" | "hold"
    confidence: float            # 0-100
    summary: str
    cultural_narrative: str
    suggested_qty: int
    phone_script: str

    # Raw data snapshots (for report / dashboard)
    raw_market: dict = field(default_factory=dict)
    raw_index: dict = field(default_factory=dict)
    raw_order_book: dict = field(default_factory=dict)

    @property
    def should_call(self) -> bool:
        """Whether confidence is high enough to trigger a phone call."""
        return self.confidence >= 70 and self.direction != "hold"

    def to_dict(self) -> dict:
        """Serialize for JSON / dashboard."""
        return {
            "ticker": self.ticker,
            "timestamp": self.timestamp,
            "dimensions": [
                {
                    "name": d.name,
                    "score": d.score,
                    "weight": d.weight,
                    "reasoning": d.reasoning,
                    "data_points": d.data_points,
                }
                for d in self.dimensions
            ],
            "weighted_score": round(self.weighted_score, 2),
            "direction": self.direction,
            "confidence": self.confidence,
            "summary": self.summary,
            "cultural_narrative": self.cultural_narrative,
            "suggested_qty": self.suggested_qty,
            "phone_script": self.phone_script,
        }


# ─── Alpha Model ──────────────────────────────────────────────────────

class AttentionAlphaModel:
    """
    Five-factor Attention Alpha Model.

    Dimensions & weights:
        1. Momentum           25%  — Forum candles (multi-timeframe)
        2. Catalyst            25%  — Web search via Claude
        3. Cross-platform      20%  — Forum index source breakdown
        4. Cultural Context    20%  — Claude cultural analysis
        5. Market Positioning  10%  — Forum order book
    """

    DIMENSION_WEIGHTS = {
        "momentum": 0.25,
        "catalyst": 0.25,
        "cross_platform": 0.20,
        "cultural_context": 0.20,
        "market_positioning": 0.10,
    }

    def __init__(
        self,
        forum_client: Any,       # ForumClient instance
        claude_client: Anthropic,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.forum = forum_client
        self.claude = claude_client
        self.model = model

    # ─── Public API ───────────────────────────────────────────────

    def analyze(
        self,
        ticker: str,
        trigger_reason: str = "Manual trigger",
        change_15m: float = 0.0,
        change_1h: float = 0.0,
    ) -> AlphaSignal:
        """
        Run full five-factor analysis on a ticker.

        Args:
            ticker:         Market ticker (e.g. "OPENAI")
            trigger_reason: Why this analysis was triggered
            change_15m:     15-minute price change ratio (e.g. 0.05 = +5%)
            change_1h:      1-hour price change ratio

        Returns:
            AlphaSignal with scores, direction, confidence, phone script
        """
        # ── Step 1: Gather data from Forum API ──
        data = self._gather_data(ticker)

        # ── Step 2: Build analysis prompt ──
        prompt = self._build_prompt(
            ticker=ticker,
            trigger_reason=trigger_reason,
            change_15m=change_15m,
            change_1h=change_1h,
            data=data,
        )

        # ── Step 3: Call Claude with web search for catalyst/culture ──
        response = self.claude.messages.create(
            model=self.model,
            max_tokens=4096,
            system=ALPHA_MODEL_SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )

        # ── Step 4: Parse structured response ──
        return self._parse_response(ticker, response, data)

    # ─── Data gathering ───────────────────────────────────────────

    def _gather_data(self, ticker: str) -> dict:
        """Fetch all required data from Forum API."""
        from datetime import datetime, timedelta, timezone

        data = {}
        now = datetime.now(timezone.utc)

        # Market overview
        try:
            data["market"] = self.forum.get_market(ticker)
        except Exception as e:
            print(f"[AlphaModel] Error fetching market: {e}")
            data["market"] = {}

        # Candles — Forum API only supports: 1m, 5m, 1d
        # Both 'interval' and 'start' are required params
        start_8h = (now - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
        start_30d = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            data["candles_5m"] = self.forum.get_candles(
                ticker, interval="5m", start=start_8h, limit=100
            )
        except Exception as e:
            print(f"[AlphaModel] Error fetching 5m candles: {e}")
            data["candles_5m"] = []

        try:
            data["candles_1d"] = self.forum.get_candles(
                ticker, interval="1d", start=start_30d, limit=30
            )
        except Exception as e:
            print(f"[AlphaModel] Error fetching 1d candles: {e}")
            data["candles_1d"] = []

        # Attention index
        index_name = f"{ticker}-IDX"
        try:
            data["index"] = self.forum.get_index(index_name)
        except Exception as e:
            print(f"[AlphaModel] Error fetching index: {e}")
            data["index"] = {}

        # Order book
        try:
            data["order_book"] = self.forum.get_order_book(ticker, depth=20)
        except Exception as e:
            print(f"[AlphaModel] Error fetching order book: {e}")
            data["order_book"] = {}

        # Funding rate
        try:
            data["funding"] = self.forum.get_funding_rate(ticker)
        except Exception as e:
            print(f"[AlphaModel] Error fetching funding: {e}")
            data["funding"] = {}

        return data

    # ─── Prompt building ──────────────────────────────────────────

    def _build_prompt(
        self,
        ticker: str,
        trigger_reason: str,
        change_15m: float,
        change_1h: float,
        data: dict,
    ) -> str:
        """Build the analysis prompt from raw data."""

        market = data.get("market", {})
        candles = data.get("candles_5m", [])
        candles_daily = data.get("candles_1d", [])
        index = data.get("index", {})
        order_book = data.get("order_book", {})

        current_price = market.get("lastPrice") or market.get("bestAsk") or 0

        # ── Compute changes from candles if not provided ──
        if candles and (change_15m == 0 and change_1h == 0):
            change_15m, change_1h = self._compute_changes(candles)

        # ── Candles summary (only bars with actual trades) ──
        candles_summary = self._summarize_candles(candles)
        daily_candles_summary = self._summarize_candles(candles_daily)

        # ── Price trajectory ──
        price_trajectory = self._price_trajectory(candles)

        # ── Index breakdown ──
        index_name = index.get("name", f"{ticker}-IDX")
        index_value = index.get("currentValue", "N/A")

        source_breakdown = self._format_source_breakdown(index)
        index_day_change = self._format_index_changes(index)

        # ── Order book ──
        order_book_summary = self._format_order_book(order_book)

        return ANALYSIS_PROMPT_TEMPLATE.format(
            ticker=ticker,
            trigger_reason=trigger_reason,
            current_price=current_price,
            current_price_dollars=current_price / 100,
            change_15m=change_15m,
            change_1h=change_1h,
            candles_summary=candles_summary,
            daily_candles_summary=daily_candles_summary,
            price_trajectory=price_trajectory,
            index_name=index_name,
            index_value=index_value,
            index_day_change=index_day_change,
            source_breakdown=source_breakdown,
            order_book_summary=order_book_summary,
        )

    def _compute_changes(self, candles: list[dict]) -> tuple[float, float]:
        """Compute 15m and 1h price changes from 5m candles."""
        if not candles:
            return 0.0, 0.0

        current = candles[-1].get("close", 0)
        if current == 0:
            return 0.0, 0.0

        # 15 min ago = 3 bars back in 5m candles
        idx_15m = max(0, len(candles) - 4)
        price_15m = candles[idx_15m].get("close", current)
        change_15m = (current - price_15m) / price_15m if price_15m else 0

        # 1 hour ago = 12 bars back
        idx_1h = max(0, len(candles) - 13)
        price_1h = candles[idx_1h].get("close", current)
        change_1h = (current - price_1h) / price_1h if price_1h else 0

        return change_15m, change_1h

    def _summarize_candles(self, candles: list[dict]) -> str:
        """Show only candles with volume (actual trades happened)."""
        active_bars = [c for c in candles if c.get("volume", 0) > 0]

        if not active_bars:
            return "No recent trading activity in candles."

        lines = []
        for c in active_bars[-20:]:  # Last 20 active bars
            t = c.get("start", "?")[:16]  # Trim to minute
            lines.append(
                f"  {t}  O:{c['open']} H:{c['high']} L:{c['low']} "
                f"C:{c['close']} Vol:{c['volume']:,}"
            )
        return "\n".join(lines)

    def _price_trajectory(self, candles: list[dict]) -> str:
        """Extract key price levels for trend description."""
        if not candles:
            return "No data"

        closes = [c["close"] for c in candles if c.get("close")]
        if not closes:
            return "No data"

        first, last = closes[0], closes[-1]
        high, low = max(closes), min(closes)
        change_pct = (last - first) / first * 100 if first else 0

        return (
            f"Start: {first} -> End: {last} ({change_pct:+.2f}%), "
            f"Range: {low}-{high}, Spread: {high - low} cents"
        )

    def _format_source_breakdown(self, index: dict) -> str:
        """Format index source configs into readable text."""
        configs = index.get("sourceConfigs", [])
        if not configs:
            return "No source data available."

        lines = []
        for src in configs:
            name = src.get("displayName", src.get("name", "?"))
            weight = src.get("weight", 0)
            curr = src.get("currValue", "N/A")
            day_chg = src.get("dayPercentChangeSigned")
            week_chg = src.get("weekPercentChangeSigned")

            day_str = f"{day_chg:+.2%}" if day_chg is not None else "N/A"
            week_str = f"{week_chg:+.2%}" if week_chg is not None else "N/A"

            lines.append(
                f"  - {name} (weight: {weight:.0%}): "
                f"value={curr}, day={day_str}, week={week_str}"
            )

            # Show individual metrics if available
            for metric in src.get("metrics", []):
                m_name = metric.get("displayName", metric.get("shortName", "?"))
                m_curr = metric.get("curr", {})
                m_val = m_curr.get("value", "?")
                m_diff = m_curr.get("diff")
                diff_str = f" (Δ{m_diff:+,})" if m_diff is not None else ""
                lines.append(f"      • {m_name}: {m_val:,}{diff_str}" if isinstance(m_val, (int, float)) else f"      • {m_name}: {m_val}{diff_str}")

        return "\n".join(lines)

    def _format_index_changes(self, index: dict) -> str:
        """Get index percent changes from sourceConfigs or market data."""
        configs = index.get("sourceConfigs", [])
        parts = []
        for src in configs:
            name = src.get("name", "?")
            day = src.get("dayPercentChangeSigned")
            if day is not None:
                parts.append(f"{name}: {day:+.2%}")

        return ", ".join(parts) if parts else "N/A"

    def _format_order_book(self, book: dict) -> str:
        """Summarize order book imbalance."""
        bids = book.get("bids", [])
        asks = book.get("asks", [])

        if not bids and not asks:
            return "No order book data."

        bid_vol = sum(b.get("qty", 0) for b in bids)
        ask_vol = sum(a.get("qty", 0) for a in asks)
        total = bid_vol + ask_vol

        best_bid = bids[0]["price"] if bids else 0
        best_ask = asks[0]["price"] if asks else 0
        spread = best_ask - best_bid if best_ask and best_bid else 0

        imbalance = (bid_vol - ask_vol) / total * 100 if total else 0

        lines = [
            f"Best bid: {best_bid} cents  |  Best ask: {best_ask} cents  |  Spread: {spread} cents",
            f"Total bid depth: {bid_vol} contracts ({len(bids)} levels)",
            f"Total ask depth: {ask_vol} contracts ({len(asks)} levels)",
            f"Book imbalance: {imbalance:+.1f}% ({'bid-heavy = bullish' if imbalance > 0 else 'ask-heavy = bearish'})",
            "",
            "Top 5 bids:",
        ]
        for b in bids[:5]:
            lines.append(f"  {b['price']}  x {b['qty']}")
        lines.append("Top 5 asks:")
        for a in asks[:5]:
            lines.append(f"  {a['price']}  x {a['qty']}")

        return "\n".join(lines)

    # ─── Response parsing ─────────────────────────────────────────

    def _parse_response(
        self,
        ticker: str,
        response: Any,
        data: dict,
    ) -> AlphaSignal:
        """Parse Claude's response into an AlphaSignal."""

        # Extract text from response (may have tool_use blocks from web search)
        text = ""
        for block in response.content:
            if hasattr(block, "text") and block.text:
                text = block.text

        # Clean potential markdown wrapping
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # Remove "json" prefix if present
        if text.startswith("json"):
            text = text[4:].strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[AlphaModel] JSON parse error: {e}")
            print(f"[AlphaModel] Raw text: {text[:500]}")
            return self._fallback_signal(ticker)

        # Build dimension scores
        dimensions = []
        for dim_data in result.get("dimensions", []):
            name = dim_data["name"]
            dimensions.append(DimensionScore(
                name=name,
                score=dim_data["score"],
                weight=self.DIMENSION_WEIGHTS.get(name, 0.10),
                reasoning=dim_data["reasoning"],
                data_points=dim_data.get("data_points", []),
            ))

        weighted_score = sum(d.score * d.weight for d in dimensions)

        return AlphaSignal(
            ticker=ticker,
            timestamp=time.time(),
            dimensions=dimensions,
            weighted_score=weighted_score,
            direction=result.get("direction", "hold"),
            confidence=result.get("confidence", 0),
            summary=result.get("summary", ""),
            cultural_narrative=result.get("cultural_narrative", ""),
            suggested_qty=result.get("suggested_qty", 1),
            phone_script=result.get("phone_script", ""),
            raw_market=data.get("market", {}),
            raw_index=data.get("index", {}),
            raw_order_book=data.get("order_book", {}),
        )

    def _fallback_signal(self, ticker: str) -> AlphaSignal:
        """Return a safe hold signal if parsing fails."""
        return AlphaSignal(
            ticker=ticker,
            timestamp=time.time(),
            dimensions=[
                DimensionScore(n, 5, w, "Analysis parsing failed")
                for n, w in self.DIMENSION_WEIGHTS.items()
            ],
            weighted_score=5.0,
            direction="hold",
            confidence=0,
            summary="Analysis failed — defaulting to hold.",
            cultural_narrative="Unable to assess.",
            suggested_qty=0,
            phone_script="Yooo boss! Something went wrong with my analysis. Sit tight, I'll try again.",
        )


# ─── Standalone test / demo trigger ──────────────────────────────────

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    forum = ForumClient(
        api_key=os.environ["FORUM_API_KEY"],
        api_secret=os.environ["FORUM_API_SECRET"],
    )
    claude = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    model = AttentionAlphaModel(forum_client=forum, claude_client=claude)

    print("=" * 60)
    print("  ATTENTION ALPHA MODEL — Live Analysis")
    print("=" * 60)

    signal = model.analyze("OPENAI", trigger_reason="Manual hackathon demo")

    print(f"\n{'='*60}")
    print(f"  RESULT: {signal.ticker}")
    print(f"{'='*60}")
    print(f"  Direction:  {signal.direction.upper()}")
    print(f"  Confidence: {signal.confidence}%")
    print(f"  Score:      {signal.weighted_score:.1f}/10")
    print(f"  Qty:        {signal.suggested_qty} contracts")
    print(f"  Call?       {'YES' if signal.should_call else 'NO'}")
    print()

    for d in signal.dimensions:
        icon = {"momentum": "📈", "catalyst": "⚡", "cross_platform": "🌐",
                "cultural_context": "🎭", "market_positioning": "📊"}.get(d.name, "•")
        print(f"  {icon} {d.name:20s}  {d.score:2d}/10  (weight {d.weight:.0%})")
        print(f"     {d.reasoning[:100]}...")
        print()

    print(f"  📝 Summary: {signal.summary[:200]}...")
    print(f"\n  🎭 Culture: {signal.cultural_narrative[:200]}...")
    print(f"\n  📞 Phone script:\n     {signal.phone_script}")
    print(f"\n{'='*60}")

    # Dump full JSON
    import json as _json
    import os as _os
    _os.makedirs("report", exist_ok=True)
    _out = _os.path.join("report", "latest_signal.json")
    with open(_out, "w") as f:
        _json.dump(signal.to_dict(), f, indent=2, ensure_ascii=False)
    print(f"  Full signal saved to {_out}")
