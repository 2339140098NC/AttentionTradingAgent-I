"""
Forum.market API Client
========================
Python SDK for the Forum attention futures exchange.
Hackathon-ready: covers auth, market data, indices, orders, positions, and account.

Usage:
    from forum_client import ForumClient

    client = ForumClient(api_key="fk_...", api_secret="your_secret")

    # Public endpoints (no auth needed)
    markets = client.get_market("OPENAI")
    index = client.get_index("OPENAI-IDX")

    # Private endpoints (auth required)
    order = client.place_order(ticker="OPENAI", side="buy", qty=10, order_type="market")
    positions = client.list_positions()
    account = client.get_account()
"""

import hashlib
import hmac
import base64
import json
import time
from typing import Optional
from urllib.parse import urlencode

import requests


BASE_URL = "https://api.forum.market/v1"


class ForumAPIError(Exception):
    """Raised when the Forum API returns an error response."""

    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(f"[{status_code}] {code}: {message}")


class ForumClient:
    """
    Forum.market REST API client.

    Args:
        api_key:    Your API key ID (e.g. "fk_a1b2c3d4e5f6...")
        api_secret: Your API secret for HMAC signing
        base_url:   API base URL (default: production)
    """

    def __init__(self, api_key: str = "", api_secret: str = "", base_url: str = BASE_URL):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    # ─── Auth helpers ─────────────────────────────────────────────────

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """Generate HMAC-SHA256 signature per Forum spec."""
        prehash = timestamp + method.upper() + path + body
        sig = hmac.new(
            self.api_secret.encode(),
            prehash.encode(),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(sig).decode()

    def _auth_headers(self, method: str, path: str, body: str = "") -> dict:
        ts = str(int(time.time()))
        return {
            "FORUM-ACCESS-KEY": self.api_key,
            "FORUM-ACCESS-TIMESTAMP": ts,
            "FORUM-ACCESS-SIGN": self._sign(ts, method, path, body),
        }

    def _request(self, method: str, path: str, params: dict | None = None,
                 json_body: dict | None = None, auth: bool = False) -> dict | list:
        url = self.base_url + path
        headers = {"Content-Type": "application/json"}
        body_str = ""

        if json_body is not None:
            body_str = json.dumps(json_body, separators=(",", ":"))

        # Build full path with query string for signature
        full_path = path
        if params:
            full_path += "?" + urlencode(params)

        if auth:
            headers.update(self._auth_headers(method, full_path, body_str))

        resp = self.session.request(
            method, url, headers=headers, params=params,
            data=body_str if body_str else None,
        )

        if resp.status_code >= 400:
            try:
                err = resp.json().get("error", {})
            except Exception:
                err = {}
            raise ForumAPIError(
                status_code=resp.status_code,
                code=err.get("code", "UNKNOWN"),
                message=err.get("message", resp.text),
                details=err.get("details"),
            )

        return resp.json()

    # ─── Exchange ─────────────────────────────────────────────────────

    def get_server_time(self) -> dict:
        """GET /time — server clock (use for HMAC clock skew check)."""
        return self._request("GET", "/time")

    def get_exchange_status(self) -> dict:
        """GET /exchange/status — maintenance status & windows."""
        return self._request("GET", "/exchange/status")

    # ─── Markets (public) ────────────────────────────────────────────

    def list_markets(self) -> list:
        """GET /markets — list all available markets/tickers."""
        return self._request("GET", "/markets")

    def get_market(self, ticker: str) -> dict:
        """GET /markets/{ticker} — market details, prices, stats."""
        return self._request("GET", f"/markets/{ticker}")

    def get_order_book(self, ticker: str, depth: int = 20) -> dict:
        """GET /markets/{ticker}/book — order book snapshot."""
        return self._request("GET", f"/markets/{ticker}/book", params={"depth": depth})

    def get_recent_trades(self, ticker: str, limit: int = 50) -> list:
        """GET /markets/{ticker}/trades — recent trade history."""
        return self._request("GET", f"/markets/{ticker}/trades", params={"limit": limit})

    def get_candles(self, ticker: str, interval: str = "5m",
                    start: str | None = None, end: str | None = None,
                    limit: int = 2500) -> list:
        """
        GET /markets/{ticker}/candles — OHLCV candlestick data.

        Args:
            interval: "1m", "5m", "1d"  (only these three are supported)
            start:    ISO 8601 datetime (required by API)
            end:      ISO 8601 datetime (default: now)
            limit:    max 2500
        """
        params = {"interval": interval, "limit": limit}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return self._request("GET", f"/markets/{ticker}/candles", params=params)

    # ─── Indices (public) ────────────────────────────────────────────

    def get_index(self, name: str) -> dict:
        """
        GET /indices/{name} — current attention index value & source breakdown.

        Returns index value, sources (youtube, x, reddit, google_trends),
        weights, per-source percent changes, and metric details.
        """
        return self._request("GET", f"/indices/{name}")

    def get_index_history(self, name: str, start: str,
                          end: str | None = None, interval: str = "raw",
                          limit: int = 2500) -> list:
        """
        GET /indices/{name}/history — historical index values.

        Args:
            start:    ISO 8601 datetime (required)
            end:      ISO 8601 datetime (default: now)
            interval: "raw", "8h", "1d"
        """
        params = {"start": start, "interval": interval, "limit": limit}
        if end:
            params["end"] = end
        return self._request("GET", f"/indices/{name}/history", params=params)

    # ─── Funding (public) ────────────────────────────────────────────

    def get_funding_rate(self, ticker: str) -> dict:
        """GET /markets/{ticker}/funding-rate — current & estimated next funding rate."""
        return self._request("GET", f"/markets/{ticker}/funding-rate")

    def get_funding_history(self, ticker: str, start: str | None = None,
                            end: str | None = None, limit: int = 100) -> list:
        """GET /markets/{ticker}/funding-rate/history — historical funding rates."""
        params = {"limit": limit}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return self._request("GET", f"/markets/{ticker}/funding-rate/history", params=params)

    # ─── Orders (auth required) ──────────────────────────────────────

    def list_orders(self, ticker: str | None = None, side: str | None = None,
                    limit: int = 100) -> dict:
        """GET /orders — list open orders."""
        params = {"limit": limit}
        if ticker:
            params["ticker"] = ticker
        if side:
            params["side"] = side
        return self._request("GET", "/orders", params=params, auth=True)

    def place_order(
        self,
        ticker: str,
        side: str,          # "buy" or "sell"
        qty: int,
        order_type: str,    # "market" or "limit"
        price: int | None = None,           # cents, required for limit
        time_in_force: str | None = None,   # required for limit
        client_order_id: str | None = None,
        post_only: bool = False,
        reduce_only: bool = False,
    ) -> dict:
        """
        POST /orders — place a new order.

        Args:
            ticker:         Market ticker (e.g. "OPENAI")
            side:           "buy" (long) or "sell" (short)
            qty:            Number of contracts
            order_type:     "market" or "limit"
            price:          Limit price in cents (required for limit orders)
            time_in_force:  "goodTillCancel" | "fillOrKill" | "fillAndKill"
            client_order_id: Optional idempotency key
            post_only:      Maker-only (limit + GTC only)
            reduce_only:    Can only reduce existing position

        Returns:
            OrderRecord dict with id, status, ticker, side, etc.
        """
        body: dict = {
            "ticker": ticker,
            "side": side,
            "qty": qty,
            "orderType": order_type,
        }
        if price is not None:
            body["price"] = price
        if time_in_force:
            body["timeInForce"] = time_in_force
        if client_order_id:
            body["clientOrderId"] = client_order_id
        if post_only:
            body["postOnly"] = True
        if reduce_only:
            body["reduceOnly"] = True
        return self._request("POST", "/orders", json_body=body, auth=True)

    def get_order(self, order_id: int) -> dict:
        """GET /orders/{orderId} — get order by ID."""
        return self._request("GET", f"/orders/{order_id}", auth=True)

    def cancel_order(self, order_id: int) -> dict:
        """DELETE /orders/{orderId} — cancel order by ID."""
        return self._request("DELETE", f"/orders/{order_id}", auth=True)

    def get_order_by_client_id(self, client_order_id: str) -> dict:
        """GET /orders/client/{clientOrderId}."""
        return self._request("GET", f"/orders/client/{client_order_id}", auth=True)

    def cancel_order_by_client_id(self, client_order_id: str) -> dict:
        """DELETE /orders/client/{clientOrderId}."""
        return self._request("DELETE", f"/orders/client/{client_order_id}", auth=True)

    def place_batch_orders(self, orders: list[dict]) -> list:
        """POST /orders/batch — place multiple orders at once."""
        return self._request("POST", "/orders/batch", json_body={"orders": orders}, auth=True)

    def cancel_batch_orders(self, order_ids: list[int]) -> list:
        """DELETE /orders/batch — cancel multiple orders."""
        return self._request("DELETE", "/orders/batch", json_body={"orderIds": order_ids}, auth=True)

    # ─── Fills (auth required) ───────────────────────────────────────

    def list_fills(self, ticker: str | None = None, limit: int = 100) -> dict:
        """GET /fills — trade execution history."""
        params = {"limit": limit}
        if ticker:
            params["ticker"] = ticker
        return self._request("GET", "/fills", params=params, auth=True)

    # ─── Positions (auth required) ───────────────────────────────────

    def list_positions(self) -> dict:
        """GET /positions — all open positions."""
        return self._request("GET", "/positions", auth=True)

    def get_position(self, ticker: str) -> dict:
        """GET /positions/{ticker} — position for a specific market."""
        return self._request("GET", f"/positions/{ticker}", auth=True)

    # ─── Account (auth required) ─────────────────────────────────────

    def get_account(self) -> dict:
        """
        GET /account — account summary.

        Returns equity, free margin, unrealized/realized PnL,
        margin ratio, and account health status.
        Note: all monetary values are in cents.
        """
        return self._request("GET", "/account", auth=True)

    # ─── Convenience helpers for the agent ───────────────────────────

    def go_long(self, ticker: str, qty: int) -> dict:
        """Quick market buy (go long on attention)."""
        return self.place_order(ticker=ticker, side="buy", qty=qty, order_type="market")

    def go_short(self, ticker: str, qty: int) -> dict:
        """Quick market sell (go short on attention)."""
        return self.place_order(ticker=ticker, side="sell", qty=qty, order_type="market")

    def close_position(self, ticker: str) -> dict | None:
        """Close an existing position entirely with a market order."""
        pos = self.get_position(ticker)
        qty = pos.get("qty", 0)
        if qty == 0:
            return None
        side = "sell" if qty > 0 else "buy"
        return self.place_order(
            ticker=ticker, side=side, qty=abs(qty),
            order_type="market", reduce_only=True,
        )


# ─── Quick test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import os

    client = ForumClient(
        api_key=os.environ.get("FORUM_API_KEY", ""),
        api_secret=os.environ.get("FORUM_API_SECRET", ""),
    )

    # Test public endpoints (no auth needed)
    print("=== Server Time ===")
    print(client.get_server_time())

    print("\n=== Exchange Status ===")
    print(client.get_exchange_status())

    # Uncomment after you get your API key from the Forum booth:
    # print("\n=== Account ===")
    # print(client.get_account())
    #
    # print("\n=== Place Market Buy ===")
    # order = client.go_long("OPENAI", 5)
    # print(order)
