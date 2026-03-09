from dataclasses import dataclass

@dataclass(slots=True)
class RegimeAssessment:
    regime: str
    confidence: float
    details: dict

class RegimeClassifier:
    def classify(self, *, atr_ratio: float, trend_strength: float, range_tightness: float, post_news: bool = False) -> RegimeAssessment:
        details = {"atr_ratio": atr_ratio, "trend_strength": trend_strength, "range_tightness": range_tightness, "post_news": post_news}
        if post_news:
            return RegimeAssessment("post_news_disorder", 0.85, details)
        if atr_ratio >= 1.35 and trend_strength >= 0.65:
            return RegimeAssessment("expansion_trend", min(0.95, (atr_ratio + trend_strength) / 2), details)
        if range_tightness >= 0.75 and atr_ratio <= 0.85:
            return RegimeAssessment("compression", min(0.95, (range_tightness + (1 - atr_ratio)) / 2), details)
        if trend_strength >= 0.6:
            return RegimeAssessment("trend", min(0.9, trend_strength), details)
        if range_tightness >= 0.6:
            return RegimeAssessment("range", min(0.9, range_tightness), details)
        return RegimeAssessment("mixed", 0.5, details)
