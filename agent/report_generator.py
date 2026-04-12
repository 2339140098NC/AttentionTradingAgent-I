"""
Report Generator — 分析报告 + 电话摘要
=======================================
Forum.market Hackathon · Layer 3

Converts AlphaSignal into a report dict for the dashboard
and extracts the phone script for the voice agent.
"""

from __future__ import annotations

import time
from typing import Any

from agent.alpha_model import AlphaSignal


class ReportGenerator:
    """Generates reports from AlphaSignals, pushes to dashboard via WebSocket."""

    def __init__(self, ws_manager: Any = None):
        self.ws_manager = ws_manager
        self.reports: list[dict] = []

    async def generate(self, signal: AlphaSignal) -> dict:
        """
        Create a report from an AlphaSignal.

        Returns a report dict ready for dashboard display.
        """
        report = {
            "id": f"rpt_{int(time.time())}",
            "ticker": signal.ticker,
            "timestamp": signal.timestamp,
            "signal": signal.to_dict(),
            "status": "pending_confirmation",
        }

        self.reports.append(report)

        # Push to dashboard if WebSocket manager available
        if self.ws_manager:
            import json
            try:
                await self.ws_manager.broadcast(json.dumps({
                    "type": "new_report",
                    "data": report,
                }))
            except Exception as e:
                print(f"[ReportGen] WS broadcast error: {e}")

        return report

    def update_status(
        self,
        report_id: str,
        status: str,
        trade_result: dict | None = None,
    ):
        """Update report status after user confirmation / rejection."""
        for report in self.reports:
            if report["id"] == report_id:
                report["status"] = status
                if trade_result:
                    report["trade_result"] = trade_result
                return report
        return None

    def get_latest(self) -> dict | None:
        """Get the most recent report."""
        return self.reports[-1] if self.reports else None

    def get_all(self) -> list[dict]:
        """Get all reports."""
        return self.reports
