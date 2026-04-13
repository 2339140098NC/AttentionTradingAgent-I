"""
Voice Agent — Vapi.ai 电话触发 + 交易执行
==========================================
Forum.market Hackathon · Layer 4

Triggers Vapi to call the user with the analysis pitch,
handles function call webhooks for trade execution.

Setup:
    1. Register at vapi.ai, get API key
    2. Create an Assistant in Vapi Dashboard:
       - Model: Claude (or GPT-4)
       - Voice: Pick a young, energetic male voice
       - Add function tools: execute_trade, get_market_data
       - Set server URL to your ngrok URL + /api/vapi/function-call
    3. Buy or import a phone number in Vapi
    4. Set env vars: VAPI_API_KEY, VAPI_PHONE_NUMBER_ID,
       VAPI_ASSISTANT_ID, USER_PHONE_NUMBER

Usage:
    from agent.voice_agent import VoiceAgent
    voice = VoiceAgent(forum_client)
    voice.trigger_call(signal)
"""

from __future__ import annotations

import os
import requests
from typing import Any

from agent.prompts import VOICE_AGENT_SYSTEM_PROMPT


class VoiceAgent:
    """Vapi.ai phone call controller."""

    VAPI_BASE = "https://api.vapi.ai"

    def __init__(self, forum_client: Any):
        self.api_key = os.environ.get("VAPI_API_KEY", "")
        self.phone_number_id = os.environ.get("VAPI_PHONE_NUMBER_ID", "")
        self.assistant_id = os.environ.get("VAPI_ASSISTANT_ID", "")
        self.user_phone = os.environ.get("USER_PHONE_NUMBER", "")
        self.forum = forum_client
        self._enabled = all([
            self.api_key, self.phone_number_id,
            self.assistant_id, self.user_phone,
        ])

        if not self._enabled:
            missing = []
            if not self.api_key: missing.append("VAPI_API_KEY")
            if not self.phone_number_id: missing.append("VAPI_PHONE_NUMBER_ID")
            if not self.assistant_id: missing.append("VAPI_ASSISTANT_ID")
            if not self.user_phone: missing.append("USER_PHONE_NUMBER")
            print(f"[VoiceAgent] DISABLED — missing env vars: {', '.join(missing)}")
            print(f"[VoiceAgent] Phone calls won't work until these are set.")
        else:
            print(f"[VoiceAgent] Ready. Will call {self.user_phone}")

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ─── Trigger a call ──────────────────────────────────────────

    def trigger_call(self, signal: Any, report_id: str = "") -> dict:
        """
        Trigger Vapi to call the user with the analysis pitch.

        Args:
            signal: AlphaSignal with phone_script and analysis data
            report_id: Report ID for tracking

        Returns:
            Vapi API response dict, or error dict
        """
        if not self._enabled:
            print("[VoiceAgent] Cannot call — not configured.")
            return {"error": "Voice agent not configured"}

        payload = {
            "assistantId": self.assistant_id,
            "assistantOverrides": {
                "firstMessage": signal.phone_script,
            },
            "phoneNumberId": self.phone_number_id,
            "customer": {
                "number": self.user_phone,
            },
        }

        print(f"[VoiceAgent] Calling {self.user_phone}...")
        print(f"[VoiceAgent] Pitch: {signal.phone_script[:80]}...")

        try:
            resp = requests.post(
                f"{self.VAPI_BASE}/call/phone",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            call_id = result.get("id", "?")
            print(f"[VoiceAgent] Call initiated! ID: {call_id}")
            return result

        except requests.exceptions.HTTPError as e:
            error_body = ""
            try:
                error_body = e.response.text
            except Exception:
                pass
            print(f"[VoiceAgent] Vapi API error: {e}")
            print(f"[VoiceAgent] Response: {error_body}")
            return {"error": str(e), "details": error_body}

        except Exception as e:
            print(f"[VoiceAgent] Call failed: {e}")
            return {"error": str(e)}

    # ─── Build call context ──────────────────────────────────────

    def _build_call_context(self, signal: Any, report_id: str) -> str:
        """Build system prompt context for Vapi assistant during the call."""
        dim_summary = "\n".join(
            f"- {d.name}: {d.score}/10 — {d.reasoning[:120]}"
            for d in signal.dimensions
        )

        return f"""{VOICE_AGENT_SYSTEM_PROMPT}

--- CURRENT ANALYSIS ---

Ticker: {signal.ticker}
Direction: {signal.direction}
Confidence: {signal.confidence}%
Weighted score: {signal.weighted_score:.1f}/10
Suggested quantity: {signal.suggested_qty} contracts
Report ID: {report_id}

Five-factor scores:
{dim_summary}

Cultural narrative:
{signal.cultural_narrative}

Summary:
{signal.summary}

--- RULES ---
1. User says "buy" / "do it" / "let's go" / "send it" -> call execute_trade
2. User asks follow-up questions -> answer with data + cultural context
3. User says "no" / "pass" / "nah" -> respect their decision
4. Keep initial pitch under 30 seconds
5. After trade executes, confirm result and say something hype
"""

    # ─── Handle Vapi function calls ──────────────────────────────

    def handle_function_call(self, function_name: str, params: dict) -> dict:
        """
        Handle function call webhooks from Vapi.

        Vapi POSTs to your server when the AI triggers a function.
        """
        if function_name == "execute_trade":
            return self._execute_trade(
                ticker=params.get("ticker", ""),
                side=params.get("side", "buy"),
                qty=params.get("qty", 1),
            )
        elif function_name == "get_market_data":
            return self._get_market_data(params.get("ticker", ""))
        else:
            return {"error": f"Unknown function: {function_name}"}

    def _execute_trade(self, ticker: str, side: str, qty: int) -> dict:
        """Execute a trade on Forum.market."""
        try:
            if side == "buy":
                result = self.forum.go_long(ticker, qty)
            else:
                result = self.forum.go_short(ticker, qty)

            order_id = result.get("id", "?")
            status = result.get("status", "?")
            print(f"[VoiceAgent] TRADE EXECUTED: {side} {qty}x {ticker} "
                  f"— order #{order_id} ({status})")

            return {
                "success": True,
                "order_id": order_id,
                "status": status,
                "message": f"Done! {side.upper()} {qty} contracts of {ticker}. "
                           f"Order #{order_id}, status: {status}.",
            }
        except Exception as e:
            print(f"[VoiceAgent] Trade failed: {e}")
            return {"success": False, "message": f"Trade failed: {e}"}

    def _get_market_data(self, ticker: str) -> dict:
        """Get current market data for follow-up questions."""
        try:
            market = self.forum.get_market(ticker)
            return {
                "success": True,
                "ticker": ticker,
                "price": market.get("lastPrice"),
                "bid": market.get("bestBid"),
                "ask": market.get("bestAsk"),
                "day_change": market.get("changePercentPastDay"),
                "volume": market.get("volumePastDay"),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}