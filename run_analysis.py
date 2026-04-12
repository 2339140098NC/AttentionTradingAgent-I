"""
Alpha Model Demo — 一键运行分析
================================
确保 .env 里有 FORUM_API_KEY, FORUM_API_SECRET, ANTHROPIC_API_KEY

运行:
    python run_analysis.py
    python run_analysis.py NVIDIA
    python run_analysis.py TESLA
"""

import os
import sys
import json
from dotenv import load_dotenv
from anthropic import Anthropic

from forum_client import ForumClient
from agent.alpha_model import AttentionAlphaModel

load_dotenv()

def main():
    ticker = sys.argv[1] if len(sys.argv) > 1 else "OPENAI"

    forum = ForumClient(
        api_key=os.environ["FORUM_API_KEY"],
        api_secret=os.environ["FORUM_API_SECRET"],
    )
    claude = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    model = AttentionAlphaModel(forum_client=forum, claude_client=claude)

    print(f"\n{'='*60}")
    print(f"  🧠 ATTENTION ALPHA MODEL")
    print(f"  Analyzing: {ticker}")
    print(f"{'='*60}\n")
    print("  Fetching Forum data + running Claude analysis...")
    print("  (This takes ~10-15 seconds with web search)\n")

    signal = model.analyze(ticker, trigger_reason="Hackathon demo trigger")

    # ── Display results ──
    print(f"{'='*60}")
    print(f"  📊 RESULT: {signal.ticker}")
    print(f"{'='*60}")
    print(f"  Direction:  {'🟢 LONG' if signal.direction == 'long' else '🔴 SHORT' if signal.direction == 'short' else '⚪ HOLD'}")
    print(f"  Confidence: {signal.confidence}%")
    print(f"  Score:      {signal.weighted_score:.1f}/10")
    print(f"  Suggested:  {signal.suggested_qty} contracts")
    print(f"  Call user?  {'📞 YES' if signal.should_call else '❌ NO'}")
    print()

    icons = {
        "momentum": "📈", "catalyst": "⚡", "cross_platform": "🌐",
        "cultural_context": "🎭", "market_positioning": "📊",
    }
    for d in signal.dimensions:
        bar = "█" * d.score + "░" * (10 - d.score)
        print(f"  {icons.get(d.name, '•')} {d.name:20s}  [{bar}] {d.score}/10")
        # Wrap reasoning to ~80 chars
        reasoning = d.reasoning
        while len(reasoning) > 75:
            cut = reasoning[:75].rfind(" ")
            if cut == -1:
                cut = 75
            print(f"     {reasoning[:cut]}")
            reasoning = reasoning[cut:].lstrip()
        if reasoning:
            print(f"     {reasoning}")
        print()

    print(f"  📝 Summary:")
    print(f"     {signal.summary}\n")
    print(f"  🎭 Cultural Narrative:")
    print(f"     {signal.cultural_narrative}\n")
    print(f"  📞 Phone Script:")
    print(f"     {signal.phone_script}\n")
    print(f"{'='*60}")

    # ── Save to file ──
    os.makedirs("report", exist_ok=True)
    out_file = os.path.join("report", f"signal_{ticker.lower()}_{int(signal.timestamp)}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(signal.to_dict(), f, indent=2, ensure_ascii=False)
    print(f"  Full signal saved to: {out_file}")

    return signal


if __name__ == "__main__":
    main()
