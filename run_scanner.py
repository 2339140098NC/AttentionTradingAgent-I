"""
Attention Scanner — 持续扫描全市场找买入机会
=============================================
两阶段策略:
  Stage 1: 快速扫描所有 ticker（只用 Forum 数据，不调 Claude，免费）
  Stage 2: 对 top 候选人跑完整五维 Alpha Model（调 Claude，贵）

当找到置信度 >= 阈值的机会 → 打印报告，可选自动下单。

用法:
    python run_scanner.py                   # 默认扫描，只报告不下单
    python run_scanner.py --auto-trade      # 找到机会自动下单
    python run_scanner.py --threshold 80    # 设置置信度阈值
    python run_scanner.py --interval 120    # 每 120 秒扫描一次
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv
from anthropic import Anthropic

from forum_client import ForumClient
from agent.alpha_model import AttentionAlphaModel
from agent.voice_agent import VoiceAgent

load_dotenv()

# ─── Quick screener (Stage 1, no Claude, free) ───────────────────

def quick_screen(client: ForumClient, ticker: str) -> dict | None:
    """
    Quick screen a ticker using only Forum data.
    Returns a dict with a quick_score (0-100) or None if data unavailable.
    No Claude API call = free & fast (~0.5s per ticker).
    """
    try:
        market = client.get_market(ticker)
    except Exception:
        return None

    if not market.get("live", False):
        return None

    score = 0.0
    reasons = []

    # ── 1. Price change (is something happening?) ──
    day_change = market.get("changePercentPastDay") or 0
    abs_change = abs(day_change)
    # Continuous: bigger move = higher score, max 30
    price_score = min(30, abs_change * 6)
    score += price_score
    if abs_change >= 2:
        reasons.append(f"24h move: {day_change:+.1f}%")

    # ── 2. Volume (more volume = more interesting) ──
    volume = market.get("volumePastDay", 0)
    # Log-scale: 100k=5, 500k=13, 1M=15, 5M=18, 10M=20
    import math
    if volume > 0:
        vol_score = min(20, math.log10(volume) * 3.3 - 12)
        vol_score = max(0, vol_score)
        score += vol_score
        if volume > 100000:
            reasons.append(f"Volume: {volume:,}")
    else:
        score -= 10
        reasons.append("Zero volume")

    # ── 3. Order book imbalance (continuous) ──
    try:
        book = client.get_order_book(ticker, depth=10)
        bids = sum(b["qty"] for b in book.get("bids", []))
        asks = sum(a["qty"] for a in book.get("asks", []))
        total = bids + asks
        if total > 0:
            imbalance = (bids - asks) / total
            # Bigger imbalance = more interesting, max 25
            imb_score = min(25, abs(imbalance) * 50)
            score += imb_score
            if abs(imbalance) > 0.2:
                side = "bid-heavy" if imbalance > 0 else "ask-heavy"
                reasons.append(f"Book: {imbalance:+.0%} ({side})")
    except Exception:
        pass

    # ── 4. Index divergence (attention vs price) ──
    index_change = market.get("changeIndexPercentPastDay")
    if index_change is not None:
        # Attention up + price down (or vice versa) = divergence alpha
        if day_change != 0:
            divergence = abs(index_change - day_change)
            div_score = min(25, divergence * 5)
            score += div_score
            if divergence > 2:
                reasons.append(f"Divergence: idx {index_change:+.1f}% vs price {day_change:+.1f}%")
        # Even without price change, big index moves are interesting
        elif abs(index_change) > 3:
            score += 10
            reasons.append(f"Index move: {index_change:+.1f}%")

    # ── 5. Funding rate signal ──
    funding = market.get("lastSettledFundingRate")
    if funding is not None:
        fund_score = min(10, abs(funding) * 2000)
        score += fund_score
        if abs(funding) > 0.003:
            reasons.append(f"Funding: {funding:.4f}")

    # ── 6. Weekly index change (longer trend) ──
    week_change = market.get("changeIndexPercentPastWeek")
    if week_change is not None and abs(week_change) > 5:
        score += min(10, abs(week_change))
        reasons.append(f"Week idx: {week_change:+.1f}%")

    return {
        "ticker": ticker,
        "quick_score": round(score, 1),
        "price": market.get("lastPrice", 0),
        "day_change": day_change,
        "volume": volume,
        "reasons": reasons,
        "market": market,
    }


# ─── Main scanner loop ───────────────────────────────────────────

def discover_tickers(client: ForumClient) -> list[str]:
    """Get all available tickers from Forum."""
    try:
        markets = client.list_markets()
        # Handle both list and dict responses
        if isinstance(markets, list):
            tickers = [m.get("ticker") for m in markets if m.get("live")]
        elif isinstance(markets, dict):
            data = markets.get("data", markets.get("markets", []))
            if isinstance(data, list):
                tickers = [m.get("ticker") for m in data if m.get("live")]
            else:
                tickers = []
        else:
            tickers = []
        return [t for t in tickers if t]
    except Exception as e:
        print(f"  [!] Could not list markets: {e}")
        print(f"  [!] Falling back to default watchlist")
        return ["OPENAI", "NVIDIA", "TESLA", "BITCOIN", "DOGECOIN",
                "ETHEREUM", "APPLE", "GOOGLE", "META", "AMAZON"]


def run_scanner(
    forum: ForumClient,
    claude: Anthropic,
    threshold: int = 70,
    auto_trade: bool = False,
    call_user: bool = False,
    scan_interval: int = 60,
    top_n: int = 2,
):
    """
    Main scanner loop.

    1. Discover all tickers
    2. Quick screen each (free)
    3. Full alpha analysis on top candidates (uses Claude)
    4. If good opportunity found → call user / auto-trade / report
    5. Sleep and repeat
    """
    model = AttentionAlphaModel(forum_client=forum, claude_client=claude)

    # Initialize voice agent if calling is enabled
    voice = None
    if call_user:
        voice = VoiceAgent(forum_client=forum)

    round_num = 0
    recently_analyzed: set[str] = set()

    print(f"\n{'='*60}")
    print(f"  ATTENTION MARKET SCANNER")
    print(f"  Confidence threshold: {threshold}%")
    if call_user:
        print(f"  Phone call: {'READY' if voice and voice.enabled else 'NOT CONFIGURED (set VAPI_* env vars)'}")
    else:
        print(f"  Phone call: OFF (use --call to enable)")
    print(f"  Auto-trade: {'ON' if auto_trade else 'OFF'}")
    print(f"  Scan interval: {scan_interval}s")
    print(f"  Top candidates per round: {top_n}")
    print(f"{'='*60}\n")

    # Discover tickers once (refresh every 10 rounds)
    tickers = discover_tickers(forum)
    print(f"  Found {len(tickers)} markets: {', '.join(tickers)}\n")

    while True:
        round_num += 1
        now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        print(f"\n{'─'*60}")
        print(f"  Round #{round_num}  |  {now}")
        print(f"{'─'*60}")

        # Refresh tickers every 10 rounds
        if round_num % 10 == 0:
            tickers = discover_tickers(forum)

        # ── Stage 1: Quick screen all tickers ──
        print(f"\n  Stage 1: Quick screening {len(tickers)} markets...")
        screens = []
        for ticker in tickers:
            result = quick_screen(forum, ticker)
            if result and result["quick_score"] > 0:
                screens.append(result)

        if not screens:
            print(f"  No interesting activity. Sleeping {scan_interval}s...")
            time.sleep(scan_interval)
            continue

        # Sort by quick_score descending, tiebreak: prefer tickers NOT recently analyzed
        screens.sort(
            key=lambda x: (x["quick_score"], x["ticker"] not in recently_analyzed),
            reverse=True,
        )

        # Show results
        print(f"\n  {'Ticker':<12} {'Score':>6}  {'24h':>7}  {'Volume':>10}  Signals")
        print(f"  {'─'*70}")
        for i, s in enumerate(screens[:12]):
            vol_str = f"{s['volume']:>10,}" if s['volume'] else "       N/A"
            reasons_short = "; ".join(s["reasons"][:2]) if s["reasons"] else "-"
            marker = " <<<" if i < top_n else ""
            print(f"  {s['ticker']:<12} {s['quick_score']:>6.1f}  {s['day_change']:>+6.1f}%  {vol_str}  {reasons_short}{marker}")

        # ── Stage 2: Full analysis on top candidates ──
        candidates = screens[:top_n]
        recently_analyzed = {c["ticker"] for c in candidates}
        print(f"\n  Stage 2: Deep analysis on top {len(candidates)}: "
              f"{', '.join(c['ticker'] for c in candidates)}")

        best_signal = None

        for candidate in candidates:
            ticker = candidate["ticker"]
            print(f"\n  Analyzing {ticker}...", end="", flush=True)

            try:
                signal = model.analyze(
                    ticker,
                    trigger_reason=f"Scanner round #{round_num}, quick_score={candidate['quick_score']}",
                )
                print(f" {signal.direction.upper()} @ {signal.confidence}% "
                      f"(score {signal.weighted_score:.1f}/10)")

                if best_signal is None or signal.confidence > best_signal.confidence:
                    best_signal = signal

            except Exception as e:
                print(f" ERROR: {e}")
                continue

        # ── Check if we found something good ──
        if best_signal and best_signal.confidence >= threshold and best_signal.direction != "hold":
            print(f"\n{'='*60}")
            print(f"  🚨 OPPORTUNITY FOUND!")
            print(f"{'='*60}")
            print(f"  Ticker:     {best_signal.ticker}")
            print(f"  Direction:  {'LONG' if best_signal.direction == 'long' else 'SHORT'}")
            print(f"  Confidence: {best_signal.confidence}%")
            print(f"  Score:      {best_signal.weighted_score:.1f}/10")
            print(f"  Qty:        {best_signal.suggested_qty} contracts")
            print()

            for d in best_signal.dimensions:
                icons = {"momentum": "📈", "catalyst": "⚡", "cross_platform": "🌐",
                         "cultural_context": "🎭", "market_positioning": "📊"}
                bar = "█" * d.score + "░" * (10 - d.score)
                print(f"  {icons.get(d.name, '•')} {d.name:20s} [{bar}] {d.score}/10")

            print(f"\n  Phone script:")
            print(f"  {best_signal.phone_script}")
            print()

            # Save signal
            out_file = f"signal_{best_signal.ticker.lower()}_{int(best_signal.timestamp)}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(best_signal.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"  Signal saved to: {out_file}")

            # Phone call if enabled
            if voice and voice.enabled:
                print(f"\n  CALLING YOU NOW...")
                report_id = f"rpt_{int(best_signal.timestamp)}"
                voice.trigger_call(best_signal, report_id)
            elif call_user:
                print(f"\n  (Call requested but Vapi not configured. Set VAPI_* env vars)")

            # Auto-trade if enabled (skip if calling — trade happens via phone)
            if auto_trade and not (voice and voice.enabled):
                print(f"\n  AUTO-TRADE: Executing {best_signal.direction} "
                      f"{best_signal.suggested_qty}x {best_signal.ticker}...")
                try:
                    if best_signal.direction == "long":
                        result = forum.go_long(best_signal.ticker, best_signal.suggested_qty)
                    else:
                        result = forum.go_short(best_signal.ticker, best_signal.suggested_qty)
                    print(f"  Order filled! ID: {result.get('id')}, "
                          f"Status: {result.get('status')}")
                except Exception as e:
                    print(f"  Trade failed: {e}")

            if not auto_trade and not (voice and voice.enabled):
                print(f"\n  (Use --call to get a phone call, or --auto-trade to execute)")

            print(f"\n  Continuing scan...\n")

        else:
            conf = best_signal.confidence if best_signal else 0
            print(f"\n  No opportunity above {threshold}% threshold "
                  f"(best: {conf}%). Sleeping {scan_interval}s...")

        time.sleep(scan_interval)


# ─── Entry point ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Attention Market Scanner")
    parser.add_argument("--threshold", type=int, default=70,
                        help="Minimum confidence to trigger alert (default: 70)")
    parser.add_argument("--call", action="store_true",
                        help="Call your phone via Vapi when opportunity found")
    parser.add_argument("--auto-trade", action="store_true",
                        help="Automatically execute trades (no call, just trade)")
    parser.add_argument("--interval", type=int, default=60,
                        help="Seconds between scan rounds (default: 60)")
    parser.add_argument("--top-n", type=int, default=2,
                        help="Number of top candidates for deep analysis (default: 2)")
    args = parser.parse_args()

    forum = ForumClient(
        api_key=os.environ["FORUM_API_KEY"],
        api_secret=os.environ["FORUM_API_SECRET"],
    )
    claude = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    try:
        run_scanner(
            forum=forum,
            claude=claude,
            threshold=args.threshold,
            auto_trade=args.auto_trade,
            call_user=args.call,
            scan_interval=args.interval,
            top_n=args.top_n,
        )
    except KeyboardInterrupt:
        print(f"\n\n  Scanner stopped. Bye!")


if __name__ == "__main__":
    main()
