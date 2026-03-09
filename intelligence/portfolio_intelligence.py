from dataclasses import dataclass

@dataclass(slots=True)
class PortfolioPressureResult:
    allowed: bool
    pressure_score: float
    reasons: list[str]
    details: dict

class PortfolioIntelligence:
    def assess(self, *, existing_themes, proposed_theme: str, open_risk_pct: float, max_open_risk_pct: float) -> PortfolioPressureResult:
        existing_themes = list(existing_themes)
        reasons = []
        pressure = 0.0
        if proposed_theme in existing_themes:
            reasons.append("theme_clustering")
            pressure += 0.45
        if open_risk_pct >= max_open_risk_pct:
            reasons.append("open_risk_limit_reached")
            pressure += 0.75
        elif open_risk_pct >= max_open_risk_pct * 0.75:
            reasons.append("open_risk_elevated")
            pressure += 0.25
        if not reasons:
            reasons.append("portfolio_clear")
        return PortfolioPressureResult(pressure < 0.75, round(min(1.0, pressure), 4), reasons, {
            "existing_themes": existing_themes,
            "proposed_theme": proposed_theme,
            "open_risk_pct": open_risk_pct,
            "max_open_risk_pct": max_open_risk_pct,
        })
