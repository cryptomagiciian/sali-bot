"""
Kalshi API client: markets and orderbook.
"""
from typing import Dict, List, Optional
import requests


class KalshiClient:
    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def get_markets(self, limit: int = 1000, status: str = "open") -> List[Dict]:
        url = f"{self.base_url}/markets"
        params = {"limit": limit, "status": status}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("markets", [])
        except Exception as e:
            print(f"Error fetching markets: {e}")
            return []

    def get_market_orderbook(self, ticker: str) -> Optional[Dict]:
        url = f"{self.base_url}/markets/{ticker}/orderbook"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching orderbook for {ticker}: {e}")
            return None

    def health_check(self) -> bool:
        """Return True if API is reachable."""
        try:
            resp = self.session.get(f"{self.base_url}/markets", params={"limit": 1}, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
