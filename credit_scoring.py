from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class RiskBand(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Decision(Enum):
    APPROVE = "APPROVE"
    CONDITIONAL_APPROVAL = "CONDITIONAL_APPROVAL"
    REJECT = "REJECT"


@dataclass
class ScoreResult:
    total_score: float
    risk_band: RiskBand
    decision: Decision
    category_scores: Dict[str, float]
    reasons: List[str]


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def evaluate_customer(data: Dict) -> ScoreResult:
    """
    Main scoring function.

    Expected keys in data:
    - net_profit_margin
    - current_ratio
    - debt_to_equity
    - banking_limit_utilisation
    - turnover_trend

    - avg_days_to_pay
    - bounced_cheques_last_12m
    - past_default_flag

    - gst_filing_timely (True/False/None)
    - active_litigation (True/False/None)
    - credit_rating (e.g. 'AAA','AA','A','BBB','BB','B','C' or None)

    - years_in_business
    - industry_risk ('low','medium','high', 'not sure')
    - top_5_customer_share
    - management_risk_flag (True/False)
    """

    reasons: List[str] = []

    # ---------------------------------------------------------
    # 1) Financial strength (40 points)
    # ---------------------------------------------------------
    npm = float(data.get("net_profit_margin", 0.0))
    curr_ratio = float(data.get("current_ratio", 0.0))
    d2e = float(data.get("debt_to_equity", 0.0))
    bank_util = float(data.get("banking_limit_utilisation", 0.0))
    trend = str(data.get("turnover_trend", "stable") or "").lower()

    # Net Profit Margin (10)
    if npm > 10:
        s_npm = 10
    elif npm > 5:
        s_npm = 8
    elif npm > 2:
        s_npm = 5
    elif npm > 0:
        s_npm = 2
    else:
        s_npm = 0
        reasons.append("Net profit margin is very low or negative.")

    # Current Ratio (8)
    if curr_ratio >= 1.5:
        s_cr = 8
    elif curr_ratio >= 1.2:
        s_cr = 6
    elif curr_ratio >= 1.0:
        s_cr = 4
    else:
        s_cr = 1
        reasons.append("Current ratio below 1.0 indicates tight liquidity.")

    # Debt-to-Equity (8)
    if d2e <= 1:
        s_d2e = 8
    elif d2e <= 2:
        s_d2e = 6
    elif d2e <= 3:
        s_d2e = 3
    else:
        s_d2e = 0
        reasons.append("Debt-to-equity is very high.")

    # Bank limit utilisation (8)
    if 40 <= bank_util <= 80:
        s_bank = 8
    elif bank_util < 40:
        s_bank = 6
        reasons.append("Bank limit utilisation is low; could indicate underutilisation of facilities.")
    elif bank_util <= 90:
        s_bank = 5
    else:
        s_bank = 2
        reasons.append("Bank limit utilisation consistently >90% indicates stress on working capital.")

    # Turnover trend (6)
    if trend == "improving":
        s_trend = 6
    elif trend == "stable":
        s_trend = 4
    elif trend == "declining":
        s_trend = 1
        reasons.append("Turnover trend is declining.")
    else:
        s_trend = 3

    financial_strength = s_npm + s_cr + s_d2e + s_bank + s_trend
    financial_strength = _clamp(financial_strength, 0, 40)

    # ---------------------------------------------------------
    # 2) Payment behaviour (30 points)
    # ---------------------------------------------------------
    avg_days = int(data.get("avg_days_to_pay", 45) or 45)
    bounces = int(data.get("bounced_cheques_last_12m", 0) or 0)
    past_default = bool(data.get("past_default_flag", False))

    # Days to pay (10)
    if avg_days <= 30:
        s_days = 10
    elif avg_days <= 45:
        s_days = 8
    elif avg_days <= 60:
        s_days = 5
    elif avg_days <= 90:
        s_days = 2
        reasons.append("Average payment days are on the higher side.")
    else:
        s_days = 0
        reasons.append("Very high average payment days.")

    # Bounced cheques (10)
    if bounces == 0:
        s_bounce = 10
    elif bounces <= 2:
        s_bounce = 7
        reasons.append("Some cheque bounces in last 12 months.")
    elif bounces <= 5:
        s_bounce = 3
        reasons.append("Multiple cheque bounces in last 12 months.")
    else:
        s_bounce = 0
        reasons.append("Frequent cheque bounces in last 12 months.")

    # Past default flag (up to -5)
    s_default_adj = 0
    if past_default:
        s_default_adj = -5
        reasons.append("History of default / write-off reported.")

    payment_behaviour = s_days + s_bounce + s_default_adj
    payment_behaviour = _clamp(payment_behaviour, 0, 30)

    # ---------------------------------------------------------
    # 3) External checks (15 points)
    # ---------------------------------------------------------
    gst_filing_timely: Optional[bool] = data.get("gst_filing_timely", None)
    active_litigation: Optional[bool] = data.get("active_litigation", None)
    credit_rating = data.get("credit_rating", None)

    # GST filing (5)
    if gst_filing_timely is True:
        s_gst = 5
    elif gst_filing_timely is False:
        s_gst = 1
        reasons.append("GST filing not timely.")
    else:
        s_gst = 3  # Unknown

    # Litigation (5)
    if active_litigation is False:
        s_lit = 5
    elif active_litigation is True:
        s_lit = 1
        reasons.append("Active litigation / legal disputes reported.")
    else:
        s_lit = 3

    # External rating (5)
    rating_score_map = {
        "AAA": 5,
        "AA": 4,
        "A": 3,
        "BBB": 2,
        "BB": 1,
        "B": 0,
        "C": 0,
    }
    s_rating = 1
    if credit_rating:
        cr_up = str(credit_rating).upper()
        s_rating = rating_score_map.get(cr_up, 1)
        if cr_up in ("B", "C"):
            reasons.append(f"Weak external rating ({cr_up}).")

    external_checks = s_gst + s_lit + s_rating
    external_checks = _clamp(external_checks, 0, 15)

    # ---------------------------------------------------------
    # 4) Business stability (15 points)
    # ---------------------------------------------------------
    years = float(data.get("years_in_business", 0.0) or 0.0)
    industry_risk = str(data.get("industry_risk", "medium") or "medium").lower()
    top5_share = float(data.get("top_5_customer_share", 0.0) or 0.0)
    mgmt_risk = bool(data.get("management_risk_flag", False))

    # Years in business (6)
    if years >= 10:
        s_years = 6
    elif years >= 5:
        s_years = 4
    elif years >= 2:
        s_years = 2
    else:
        s_years = 0
        reasons.append("Limited operating history.")

    # Industry risk (5)
    if industry_risk == "low":
        s_ind = 5
    elif industry_risk == "medium":
        s_ind = 3
    elif industry_risk == "high":
        s_ind = 1
        reasons.append("High-risk industry.")
    else:
        s_ind = 2

    # Concentration risk (4)
    if top5_share <= 40:
        s_conc = 4
    elif top5_share <= 60:
        s_conc = 3
    elif top5_share <= 80:
        s_conc = 2
        reasons.append("Moderate customer concentration.")
    else:
        s_conc = 0
        reasons.append("Very high dependence on few customers.")

    stability_raw = s_years + s_ind + s_conc

    # Management risk penalty (up to -3)
    if mgmt_risk:
        stability_raw -= 3
        reasons.append("Concerns flagged on management integrity / governance.")

    business_stability = _clamp(stability_raw, 0, 15)

    # ---------------------------------------------------------
    # Aggregate score & decision
    # ---------------------------------------------------------
    total_score = financial_strength + payment_behaviour + external_checks + business_stability
    total_score = _clamp(total_score, 0, 100)

    # Risk band
    if total_score >= 75:
        risk_band = RiskBand.LOW
    elif total_score >= 50:
        risk_band = RiskBand.MEDIUM
    else:
        risk_band = RiskBand.HIGH

    # Decision
    if risk_band == RiskBand.LOW:
        decision = Decision.APPROVE
    elif risk_band == RiskBand.MEDIUM:
        decision = Decision.CONDITIONAL_APPROVAL
    else:
        decision = Decision.REJECT

    category_scores = {
        "financial_strength": round(financial_strength, 1),
        "payment_behaviour": round(payment_behaviour, 1),
        "external_checks": round(external_checks, 1),
        "business_stability": round(business_stability, 1),
    }

    return ScoreResult(
        total_score=round(total_score, 1),
        risk_band=risk_band,
        decision=decision,
        category_scores=category_scores,
        reasons=reasons,
    )
