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
        if not self.is_configured():
            raise RuntimeError("OANDA environment is not fully configured")

        url = f"{self.api_url}/v3/accounts/{self.account_id}"
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {self.api_token}"},
            timeout=timeout,
        )
        return response.status_code, response.json()
