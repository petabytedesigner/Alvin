from __future__ import annotations

import os
from typing import Any, Dict, Tuple

import requests
from dotenv import load_dotenv


class OandaClient:
    def __init__(self) -> None:
        load_dotenv()
        self.api_url = os.getenv("OANDA_API_URL", "").rstrip("/")
        self.account_id = os.getenv("OANDA_ACCOUNT_ID", "")
        self.api_token = os.getenv("OANDA_API_TOKEN", "")

    def is_configured(self) -> bool:
        return all([self.api_url, self.account_id, self.api_token])

    def account_details(self, timeout: int = 15) -> Tuple[int, Dict[str, Any]]:
        return self._request("GET", f"/v3/accounts/{self.account_id}", timeout=timeout)

    def account_summary(self, timeout: int = 15) -> Tuple[int, Dict[str, Any]]:
        return self._request("GET", f"/v3/accounts/{self.account_id}/summary", timeout=timeout)

    def fetch_order(self, order_id: str, timeout: int = 15) -> Tuple[int, Dict[str, Any]]:
        return self._request("GET", f"/v3/accounts/{self.account_id}/orders/{order_id}", timeout=timeout)

    def submit_order(self, payload: Dict[str, Any], timeout: int = 15) -> Tuple[int, Dict[str, Any]]:
        return self._request("POST", f"/v3/accounts/{self.account_id}/orders", json_payload=payload, timeout=timeout)

    def health_check(self, timeout: int = 15) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "configured": False,
                "ok": False,
                "status_code": 0,
                "reason": "oanda_not_configured",
                "details": {},
            }

        try:
            status_code, payload = self.account_summary(timeout=timeout)
        except Exception as exc:
            return {
                "configured": True,
                "ok": False,
                "status_code": 0,
                "reason": "broker_health_exception",
                "details": {"error": str(exc)},
            }

        ok = 200 <= status_code < 300
        account = payload.get("account", {}) if isinstance(payload, dict) else {}
        return {
            "configured": True,
            "ok": ok,
            "status_code": status_code,
            "reason": "broker_health_ok" if ok else "broker_health_not_ok",
            "details": {
                "alias": account.get("alias"),
                "currency": account.get("currency"),
                "openTradeCount": account.get("openTradeCount"),
                "pendingOrderCount": account.get("pendingOrderCount"),
                "lastTransactionID": account.get("lastTransactionID"),
            },
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_payload: Dict[str, Any] | None = None,
        timeout: int = 15,
    ) -> Tuple[int, Dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("OANDA environment is not fully configured")

        url = f"{self.api_url}{path}"
        response = requests.request(
            method=method.upper(),
            url=url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            json=json_payload,
            timeout=timeout,
        )
        return response.status_code, self._safe_json(response)

    def _safe_json(self, response: requests.Response) -> Dict[str, Any]:
        try:
            payload = response.json()
            return payload if isinstance(payload, dict) else {"raw": payload}
        except Exception:
            return {"raw_text": response.text}
