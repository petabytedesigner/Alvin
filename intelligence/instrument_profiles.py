from dataclasses import dataclass

@dataclass(slots=True)
class InstrumentProfile:
    instrument: str
    asset_class: str
    max_spread_ratio: float
    session_priority: str
    volatility_profile: str
    news_sensitivity: str

DEFAULT_PROFILES = {
    "EUR_USD": InstrumentProfile("EUR_USD", "fx_major", 1.00, "london_newyork", "balanced", "high"),
    "GBP_USD": InstrumentProfile("GBP_USD", "fx_major", 1.10, "london_newyork", "elevated", "high"),
    "USD_JPY": InstrumentProfile("USD_JPY", "fx_major", 1.00, "tokyo_london", "balanced", "high"),
    "USD_CHF": InstrumentProfile("USD_CHF", "fx_major", 1.00, "london_newyork", "balanced", "medium"),
    "USD_CAD": InstrumentProfile("USD_CAD", "fx_major", 1.05, "newyork", "balanced", "high"),
    "XAU_USD": InstrumentProfile("XAU_USD", "metal", 1.25, "london_newyork", "high", "high"),
    "BTC_USD": InstrumentProfile("BTC_USD", "crypto", 1.40, "always_on", "extreme", "medium"),
    "NAS100_USD": InstrumentProfile("NAS100_USD", "index", 1.30, "newyork", "high", "high"),
    "SPX500_USD": InstrumentProfile("SPX500_USD", "index", 1.25, "newyork", "balanced", "high"),
    "US30_USD": InstrumentProfile("US30_USD", "index", 1.25, "newyork", "balanced", "high"),
}

class InstrumentProfileResolver:
    def __init__(self, profiles=None):
        self._profiles = profiles or DEFAULT_PROFILES

    def get(self, instrument: str) -> InstrumentProfile:
        if instrument not in self._profiles:
            raise KeyError(f"Unknown instrument profile: {instrument}")
        return self._profiles[instrument]
