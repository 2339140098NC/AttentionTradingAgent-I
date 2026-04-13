"""
FastAPI Server — Vapi Webhooks + Demo Triggers
================================================
Forum.market Hackathon

Endpoints:
    GET  /api/health              — server status
    POST /api/trigger-call        — demo: trigger analysis + phone call
    POST /api/vapi/function-call  — Vapi webhook for trade execution
    GET  /api/reports             — list all analysis reports

Run:
    python -m server.main

    Then expose with ngrok:
    ngrok http 8000

    Copy the ngrok URL to Vapi function tool server URL:
    https://xxxx.ngrok.io/api/vapi/function-call
"""

import os
import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from anthropic import Anthropic

from forum_client import ForumClient
from agent.alpha_model import AttentionAlphaModel
from agent.voice_agent import VoiceAgent

load_dotenv()

# ─── Initialize components ──────────────────────────────────────

forum = ForumClient(
    api_key=os.environ.get("FORUM_API_KEY", ""),
    api_secret=os.environ.get("FORUM_API_SECRET", ""),
)
claude = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
alpha_model = AttentionAlphaModel(forum_client=forum, claude_client=claude)
voice = VoiceAgent(forum_client=forum)

# Store reports in memory
reports: list[dict] = []


# ─── FastAPI app ─────────────────────────────────────────────────

app = FastAPI(title="Attention Trading Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routes ──────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    """Server health check."""
    return {
        "status": "running",
        "voice_enabled": voice.enabled,
        "reports_count": len(reports),
    }


@app.post("/api/trigger-call")
async def trigger_call(request: Request):
    """
    Demo trigger: run analysis on a ticker, then call the user.

    Usage (from another terminal, or teammate's phone):
        curl -X POST http://localhost:8000/api/trigger-call?ticker=OPENAI
        curl -X POST https://YOUR_NGROK_URL/api/trigger-call?ticker=SPACEX
    """
    # Get ticker from query params or body
    ticker = request.query_params.get("ticker", "OPENAI")

    try:
        body = await request.json()
        ticker = body.get("ticker", ticker)
    except Exception:
        pass

    print(f"\n[Server] Manual trigger: analyzing {ticker}...")

    # Step 1: Run Alpha Model analysis
    try:
        signal = alpha_model.analyze(
            ticker,
            trigger_reason="Manual demo trigger via /api/trigger-call",
        )
    except Exception as e:
        return {"error": f"Analysis failed: {e}"}

    # Step 2: Create report
    report = {
        "id": f"rpt_{int(time.time())}",
        "ticker": signal.ticker,
        "timestamp": signal.timestamp,
        "signal": signal.to_dict(),
        "status": "pending_confirmation",
    }
    reports.append(report)

    print(f"[Server] Analysis complete: {signal.direction} @ {signal.confidence}%")
    print(f"[Server] Score: {signal.weighted_score:.1f}/10, Qty: {signal.suggested_qty}")

    # Step 3: Trigger phone call if confidence is high enough
    call_result = None
    if signal.should_call and voice.enabled:
        print(f"[Server] Confidence {signal.confidence}% >= 70%, triggering call...")
        call_result = voice.trigger_call(signal, report["id"])
        report["status"] = "call_initiated"
    elif not voice.enabled:
        print(f"[Server] Voice agent not configured, skipping call.")
        report["status"] = "no_voice"
    else:
        print(f"[Server] Confidence {signal.confidence}% too low, skipping call.")
        report["status"] = "low_confidence"

    return {
        "status": "triggered",
        "ticker": ticker,
        "direction": signal.direction,
        "confidence": signal.confidence,
        "score": signal.weighted_score,
        "phone_script": signal.phone_script,
        "call_result": call_result,
        "report_id": report["id"],
    }


@app.post("/api/vapi/function-call")
async def vapi_function_call(request: Request):
    """
    Vapi function call webhook.

    Vapi POSTs here when the AI triggers execute_trade or get_market_data
    during a phone call with the user.
    """
    body = await request.json()

    # Debug: log full payload to see actual structure
    import json as _json
    print(f"[Server] Vapi raw payload: {_json.dumps(body, indent=2, default=str)[:2000]}")

    # Try multiple Vapi payload formats
    function_name = ""
    parameters = {}

    # Format 1: message.functionCall (older Vapi)
    message = body.get("message", {})
    if "functionCall" in message:
        fc = message["functionCall"]
        function_name = fc.get("name", "")
        parameters = fc.get("parameters", {})

    # Format 2: message.toolCalls (newer Vapi)
    elif "toolCalls" in message:
        tool_calls = message["toolCalls"]
        if tool_calls and len(tool_calls) > 0:
            tc = tool_calls[0]
            function_name = tc.get("function", {}).get("name", "")
            parameters = tc.get("function", {}).get("arguments", {})
            if isinstance(parameters, str):
                import json as _j
                parameters = _j.loads(parameters)

    # Format 3: top-level toolCalls
    elif "toolCalls" in body:
        tool_calls = body["toolCalls"]
        if tool_calls and len(tool_calls) > 0:
            tc = tool_calls[0]
            function_name = tc.get("function", {}).get("name", "")
            parameters = tc.get("function", {}).get("arguments", {})

    # Format 4: message.tool_calls
    elif "tool_calls" in message:
        tool_calls = message["tool_calls"]
        if tool_calls and len(tool_calls) > 0:
            tc = tool_calls[0]
            function_name = tc.get("function", {}).get("name", "")
            parameters = tc.get("function", {}).get("arguments", {})

    print(f"[Server] Parsed: function={function_name}, params={parameters}")

    if not function_name:
        print(f"[Server] WARNING: Could not parse function name from Vapi payload!")
        return {"result": {"error": "Could not parse function call"}}

    result = voice.handle_function_call(function_name, parameters)

    # Update report status if trade was executed
    if function_name == "execute_trade" and result.get("success"):
        for report in reports:
            if report["status"] == "call_initiated":
                report["status"] = "trade_executed"
                report["trade_result"] = result
                break

    return {"result": result}


@app.get("/api/reports")
def get_reports():
    """Get all analysis reports."""
    return {"reports": reports}


@app.get("/api/reports/latest")
def get_latest_report():
    """Get the most recent report."""
    if reports:
        return reports[-1]
    return {"error": "No reports yet"}


# ─── Run server ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("SERVER_PORT", 8000))
    print(f"\n{'='*60}")
    print(f"  Attention Trading Agent — API Server")
    print(f"  http://localhost:{port}")
    print(f"  Voice: {'ENABLED' if voice.enabled else 'DISABLED'}")
    print(f"{'='*60}")
    print(f"\n  Demo trigger:")
    print(f"    curl -X POST http://localhost:{port}/api/trigger-call?ticker=OPENAI")
    print(f"\n  For Vapi webhooks, expose with ngrok:")
    print(f"    ngrok http {port}")
    print(f"    Then set Vapi function URL to: https://xxxx.ngrok.io/api/vapi/function-call")
    print()

    uvicorn.run(app, host="0.0.0.0", port=port)