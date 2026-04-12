"""
Attention Monitor — 监控 Forum 指数异常波动
============================================
Forum.market Hackathon · Layer 1

Polls Forum API for price/index changes, triggers AlphaModel when thresholds hit.

Usage:
    monitor = AttentionMonitor(forum_client, on_anomaly_callback)
    asyncio.run(monitor.start())
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable


class AttentionMonitor:
    """
    Monitors Forum attention indices for anomalies.

    Trigger conditions (any one triggers analysis):
    - 15-min price change > 15%
    - 1-hour price change > 30%
    - Volume spike > 3x average

    For hackathon demo: use trigger_manual() to bypass thresholds.
    """

    WATCHLIST = ["OPENAI", "NVIDIA", "TESLA", "BITCOIN", "DOGECOIN"]
    POLL_INTERVAL = 60          # seconds
    SPIKE_THRESHOLD_15M = 0.15  # 15% in 15 min
    SPIKE_THRESHOLD_1H = 0.30   # 30% in 1 hour
    VOLUME_MULTIPLIER = 3.0

    def __init__(self, forum_client: Any, on_anomaly: Callable):
        self.client = forum_client
        self.on_anomaly = on_anomaly
        self.running = False
        self._avg_volumes: dict[str, float] = {}

    async def start(self):
        """Start the monitoring loop."""
        self.running = True
        print(f"[Monitor] Started. Watching: {', '.join(self.WATCHLIST)}")
        print(f"[Monitor] Poll interval: {self.POLL_INTERVAL}s")
        while self.running:
            for ticker in self.WATCHLIST:
                try:
                    await self._check_ticker(ticker)
                except Exception as e:
                    print(f"[Monitor] Error checking {ticker}: {e}")
            await asyncio.sleep(self.POLL_INTERVAL)

    def stop(self):
        self.running = False
        print("[Monitor] Stopped.")

    async def _check_ticker(self, ticker: str):
        """Check a single ticker for anomalies."""
        try:
            market = self.client.get_market(ticker)
            candles = self.client.get_candles(ticker, interval="5m", limit=20)
        except Exception as e:
            print(f"[Monitor] Error fetching {ticker}: {e}")
            return

        anomaly = self._detect_anomaly(ticker, market, candles)
        if anomaly:
            print(f"[Monitor] 🚨 ANOMALY: {ticker} — {anomaly['trigger_reason']}")
            await self.on_anomaly(anomaly)

    def _detect_anomaly(self, ticker: str, market: dict, candles: list) -> dict | None:
        """Check if price movements exceed thresholds."""
        if len(candles) < 4:
            return None

        current = candles[-1].get("close", 0)
        price_15m = candles[-4].get("close", 0)  # 3 bars * 5min = 15min
        price_1h = candles[0].get("close", 0) if len(candles) >= 12 else candles[0].get("close", 0)

        if not current or not price_15m or not price_1h:
            return None

        change_15m = (current - price_15m) / price_15m
        change_1h = (current - price_1h) / price_1h

        triggered = False
        reasons = []

        if abs(change_15m) >= self.SPIKE_THRESHOLD_15M:
            triggered = True
            reasons.append(f"15m change: {change_15m:+.1%}")

        if abs(change_1h) >= self.SPIKE_THRESHOLD_1H:
            triggered = True
            reasons.append(f"1h change: {change_1h:+.1%}")

        # Volume spike check
        volumes = [c.get("volume", 0) for c in candles]
        nonzero_vols = [v for v in volumes if v > 0]
        if nonzero_vols:
            avg_vol = sum(nonzero_vols) / len(nonzero_vols)
            latest_vol = candles[-1].get("volume", 0)
            if avg_vol > 0 and latest_vol > avg_vol * self.VOLUME_MULTIPLIER:
                triggered = True
                reasons.append(f"Volume spike: {latest_vol:,} vs avg {avg_vol:,.0f}")

        if not triggered:
            return None

        return {
            "ticker": ticker,
            "current_price": current,
            "change_15m": change_15m,
            "change_1h": change_1h,
            "trigger_reason": " | ".join(reasons),
            "market_data": market,
            "timestamp": time.time(),
        }

    def trigger_manual(self, ticker: str = "OPENAI") -> dict:
        """
        Manually create an anomaly for demo purposes.
        Bypasses thresholds — always triggers.
        """
        try:
            market = self.client.get_market(ticker)
            candles = self.client.get_candles(ticker, interval="5m", limit=20)
        except Exception as e:
            return {"ticker": ticker, "error": str(e)}

        # Compute actual changes for context
        current = market.get("lastPrice") or market.get("bestAsk") or 0
        change_15m, change_1h = 0.0, 0.0

        if candles and len(candles) >= 4:
            p15 = candles[-4].get("close", current)
            change_15m = (current - p15) / p15 if p15 else 0

        if candles and len(candles) >= 12:
            p1h = candles[-12].get("close", current)
            change_1h = (current - p1h) / p1h if p1h else 0

        return {
            "ticker": ticker,
            "current_price": current,
            "change_15m": change_15m,
            "change_1h": change_1h,
            "trigger_reason": f"Manual demo trigger (actual 15m: {change_15m:+.1%}, 1h: {change_1h:+.1%})",
            "market_data": market,
            "timestamp": time.time(),
        }
