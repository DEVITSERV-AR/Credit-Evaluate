import streamlit as st
import pandas as pd
from credit_scoring import evaluate_customer

# -------------------------------------------------------------------
#                         MOCK MCA DATABASE
# -------------------------------------------------------------------
MOCK_MCA_DATA = {
    "U12345MH2010PTC123456": {
        "cin": "U12345MH2010PTC123456",
        "company_name": "Test Manufacturing Pvt Ltd",
        "latest_fy": "2023-24",
        "authorised_capital": 5000000,
        "paidup_capital": 4000000,
        "company_age": 14,
        "registered_address": "123 Industrial Estate, Pune, Maharashtra, 411001",
        "city": "Pune",
        "state": "Maharashtra",
        "pincode": "411001",
        "pan_no": "AAACT1234A",
        "gst_no": "27AAACT1234A1Z5",
        "directors_details": "1. Rakesh Sharma, Pune\n2. Neha Sharma, Pune",
        "revenue_growth": 18.5,
        "profit_growth": 15.2,
        "employee_count": 220,
        "ownership_structure": "Promoter Family: 65%\nPE Investor: 25%\nESOP / Others: 10%",
        "key_members": "MD: Rakesh Sharma\nCFO: Anita Gupta\nCOO: Sandeep Verma",
    },
    "L99999DL2015PLC000001": {
        "cin": "L99999DL2015PLC000001",
        "company_name": "Metro Retail India Ltd",
        "latest_fy": "2023-24",
        "authorised_capital": 100000000,
        "paidup_capital": 75000000,
        "company_age": 9,
        "registered_address": "7th Floor, Tower A, Business Park, New Delhi, 110001",
        "city": "New Delhi",
        "state": "Delhi",
        "pincode": "110001",
        "pan_no": "AAACM5678L",
        "gst_no": "07AAACM5678L1Z9",
        "directors_details": "1. Ajay Mehta, New Delhi\n2. Priya Nair, Mumbai\n3. Independent: Rahul Jain, Bangalore",
        "revenue_growth": 22.0,
        "profit_growth": 19.3,
        "employee_count": 1200,
        "ownership_structure": "Promoters: 51%\nFIIs: 20%\nDIIs: 15%\nPublic: 14%",
        "key_members": "Chairman: Ajay Mehta\nCEO: Priya Nair\nIndependent Director: Rahul Jain",
    },
}

# -------------------------------------------------------------------
#                      BANK STATEMENT ANALYZER
# -------------------------------------------------------------------
def analyze_bank_statement(df: pd.DataFrame):
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    required_cols = ["date", "description", "debit", "credit", "balance"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column '{col}' in bank statement file.")

    df["description"] = df["description"].astype(str).str.upper()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0)
    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0)
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")

    bounce_keywords = ["RETURN", "BOUNCE", "REJECT", "RET CHQ", "CHQ RET", "NACH RETURN"]
    bounce_flag = df["description"].apply(lambda x: any(k in x for k in bounce_keywords))
    bounce_count = int(bounce_flag.sum())

    negative_days = int((df["balance"] < 0).sum())

    emi_mask = df["description"].str.contains("EMI")
    if df["date"].notna().any() and emi_mask.any():
        emi_months = int(df.loc[emi_mask, "date"].dt.to_period("M").nunique())
    else:
        emi_months = 0

    inflows = float(df[df["credit"] > 0]["credit"].sum())
    outflows = float(df[df["debit"] > 0]["debit"].sum())
    cashflow_ratio = round(inflows / outflows, 2) if outflows else 1.0

    if bounce_count == 0 and negative_days == 0:
        avg_days_to_pay = 30
    elif bounce_count <= 2 and negative_days <= 3:
        avg_days_to_pay = 45
    elif bounce_count <= 5 or negative_days < 10:
        avg_days_to_pay = 60
    else:
        avg_days_to_pay = 90

    past_default_flag = bounce_count > 3 or negative_days > 10

    return {
        "avg_days_to_pay": avg_days_to_pay,
        "bounced_cheques_last_12m": bounce_count,
        "past_default_flag": past_default_flag,
        "cashflow_ratio": cashflow_ratio,
        "negative_days": negative_days,
        "emi_months": emi_months,
    }

# -------------------------------------------------------------------
#                       STREAMLIT APP LAYOUT
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Customer Credit Worthiness",
    layout="wide"
)

st.title("Customer Credit Worthiness Evaluation")
st.write("Fill Customer Info, Financials, and upload bank statement for new customers. Tool will compute ratios and give a credit decision.")

# --- Init session defaults for payment behaviour (so bank analysis can overwrite) ---
for key, default in [
    ("avg_days_to_pay", 45),
    ("bounced_cheques_last_12m", 0),
    ("past_default_flag", "No"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# -------------------------------------------------------------------
#                           CUSTOMER SECTION
# -------------------------------------------------------------------
st.markdown("### 🧾 Customer Basic Information")

col1, col2, col3 = st.columns(3)
with col1:
    cin_no = st.text_input("CIN")
with col2:
    customer_name = st.text_input("Customer Name (as per MCA)")
with col3:
    fetch_mca = st.button("Fetch from MCA (Mock)")

pan_no_col, gst_no_col = st.columns(2)
with pan_no_col:
    pan_no = st.text_input("PAN No")
with gst_no_col:
    gst_no = st.text_input("GST No")

addr1, addr2, addr3 = st.columns(3)
with addr1:
    registered_address = st.text_area("Registered Address", height=80)
with addr2:
    city = st.text_input("City")
    state = st.text_input("State")
    pincode = st.text_input("Pincode")
with addr3:
    directors_details = st.text_area("Director(s) Name & Address", height=80, placeholder="1. Name, Address\n2. Name, Address")

# If MCA mock button pressed
if fetch_mca and cin_no:
    data = MOCK_MCA_DATA.get(cin_no.strip().upper())
    if data:
        # use session_state to push values back into inputs
        st.session_state["customer_name"] = data["company_name"]
        st.session_state["pan_no"] = data["pan_no"]
        st.session_state["gst_no"] = data["gst_no"]
        registered_address = data["registered_address"]
        city = data["city"]
        state = data["state"]
        pincode = data["pincode"]
        directors_details = data["directors_details"]
        st.success("Loaded mock MCA data for this CIN.")
    else:
        st.warning("No mock data found for this CIN. Use test CINs given earlier.")

st.caption("Test CINs: `U12345MH2010PTC123456` or `L99999DL2015PLC000001` (mock data only).")

# -------------------------------------------------------------------
#                       KEY INDICATORS SECTION
# -------------------------------------------------------------------
st.markdown("### 📌 Key Indicators & Capital (Latest FY)")
kc1, kc2, kc3 = st.columns(3)
with kc1:
    latest_fy = st.text_input("Financial Year (e.g. 2023-24)")
    company_age = st.number_input("Company Age (years)", min_value=0.0, step=0.5, value=5.0)
with kc2:
    authorised_capital = st.number_input("Authorised Capital (₹)", min_value=0.0, step=100000.0, value=0.0)
    revenue_growth = st.number_input("Revenue Growth (3 yrs, %)", step=0.1, value=0.0)
with kc3:
    paidup_capital = st.number_input("Paid-up Capital (₹)", min_value=0.0, step=100000.0, value=0.0)
    profit_growth = st.number_input("Profit Growth (3 yrs, %)", step=0.1, value=0.0)

kc4, kc5 = st.columns(2)
with kc4:
    employee_count = st.number_input("Employee Count", min_value=0, step=1, value=0)
with kc5:
    ownership_structure = st.text_area("Ownership & Shareholding Structure", height=80)
key_members = st.text_area("Key Members / Board of Directors", height=80)

# -------------------------------------------------------------------
#                        BANK STATEMENT SECTION
# -------------------------------------------------------------------
st.markdown("### 📑 Upload Bank Statement (for New Customers)")
st.caption("Upload CSV / Excel with columns: date, description, debit, credit, balance.")

bank_file = st.file_uploader("Bank Statement File", type=["csv", "xls", "xlsx"])
analyze_bank_btn = st.button("Analyze Bank Statement")

bank_summary = None
if analyze_bank_btn:
    if bank_file is None:
        st.error("Please upload a file first.")
    else:
        try:
            fname = bank_file.name.lower()
            if fname.endswith((".xls", ".xlsx")):
                df_bank = pd.read_excel(bank_file)
            else:
                try:
                    df_bank = pd.read_csv(bank_file, encoding="utf-8")
                except UnicodeDecodeError:
                    df_bank = pd.read_csv(bank_file, encoding="latin1")

            bank_res = analyze_bank_statement(df_bank)
            st.session_state["avg_days_to_pay"] = bank_res["avg_days_to_pay"]
            st.session_state["bounced_cheques_last_12m"] = bank_res["bounced_cheques_last_12m"]
            st.session_state["past_default_flag"] = "Yes" if bank_res["past_default_flag"] else "No"

            bank_summary = (
                f"Bounce count: {bank_res['bounced_cheques_last_12m']}, "
                f"negative balance days: {bank_res['negative_days']}, "
                f"inflow/outflow ratio: {bank_res['cashflow_ratio']}, "
                f"proxy avg days to pay: {bank_res['avg_days_to_pay']}."
            )
            st.info("Bank statement analysed and payment behaviour fields updated below.")
            st.write(bank_summary)

        except Exception as e:
            st.error(f"Could not analyse bank file: {e}")

# -------------------------------------------------------------------
#                          FINANCIALS SECTION
# -------------------------------------------------------------------
st.markdown("### 1️⃣ Financials (Balance Sheet & P&L)")

f1, f2, f3 = st.columns(3)
with f1:
    turnover = st.number_input("Annual Turnover / Sales (₹)", min_value=0.0, step=100000.0, value=10000000.0)
    current_assets = st.number_input("Current Assets (₹)", min_value=0.0, step=100000.0, value=5000000.0)
    total_debt = st.number_input("Total Debt (₹)", min_value=0.0, step=100000.0, value=4000000.0)
with f2:
    net_profit = st.number_input("Net Profit (₹)", min_value=0.0, step=50000.0, value=800000.0)
    current_liabilities = st.number_input("Current Liabilities (₹)", min_value=0.0, step=100000.0, value=3500000.0)
    net_worth = st.number_input("Net Worth / Equity (₹)", min_value=0.0, step=100000.0, value=2500000.0)
with f3:
    bank_limit_sanctioned = st.number_input("Bank Limit Sanctioned (₹)", min_value=0.0, step=100000.0, value=5000000.0)
    bank_limit_avg_utilised = st.number_input("Average Utilisation of Limits (₹)", min_value=0.0, step=100000.0, value=3500000.0)
    turnover_trend_bs = st.selectbox("Turnover Trend (last 3 years)", ["Improving", "Stable", "Declining", "Not Sure"])

# -------------------------------------------------------------------
#                      PAYMENT BEHAVIOUR SECTION
# -------------------------------------------------------------------
st.markdown("### 2️⃣ Payment Behaviour")

p1, p2, p3 = st.columns(3)
with p1:
    avg_days_to_pay = st.number_input(
        "Average Days to Pay Vendors",
        min_value=0,
        max_value=365,
        value=int(st.session_state["avg_days_to_pay"]),
        key="avg_days_to_pay_input",
    )
with p2:
    bounced_cheques_last_12m = st.number_input(
        "Bounced Cheques (last 12 months)",
        min_value=0,
        value=int(st.session_state["bounced_cheques_last_12m"]),
        key="bounced_cheques_input",
    )
with p3:
    past_default_flag = st.selectbox(
        "Any Past Default / Write-off?",
        ["No", "Yes"],
        index=0 if st.session_state["past_default_flag"] == "No" else 1,
        key="past_default_flag_input",
    )

# -------------------------------------------------------------------
#                      EXTERNAL CHECKS SECTION
# -------------------------------------------------------------------
st.markdown("### 3️⃣ External Checks")

e1, e2, e3 = st.columns(3)
with e1:
    gst_filing_timely_str = st.selectbox("GST Filing Timely?", ["Yes", "No", "Unknown"], index=0)
with e2:
    active_litigation_str = st.selectbox("Active Litigation / Legal Disputes?", ["No", "Yes", "Unknown"], index=0)
with e3:
    credit_rating_val = st.selectbox(
        "External Credit Rating",
        ["Not Available", "AAA", "AA", "A", "BBB", "BB", "B", "C"],
        index=4,
    )

# -------------------------------------------------------------------
#                      BUSINESS STABILITY SECTION
# -------------------------------------------------------------------
st.markdown("### 4️⃣ Business Stability")

b1, b2, b3, b4 = st.columns(4)
with b1:
    years_in_business = st.number_input("Years in Business", min_value=0.0, step=0.5, value=5.0)
with b2:
    industry_risk_str = st.selectbox("Industry Risk", ["Low", "Medium", "High", "Not Sure"], index=1)
with b3:
    top_5_customer_share = st.number_input("Top 5 Customers' Share of Sales (%)", min_value=0.0, max_value=100.0, step=1.0, value=50.0)
with b4:
    management_risk_flag_str = st.selectbox("Concerns on Management Integrity / Governance?", ["No", "Yes"], index=0)

# -------------------------------------------------------------------
#                        CALCULATE BUTTON
# -------------------------------------------------------------------
st.markdown("---")
if st.button("Evaluate Credit Worthiness"):
    # Ratios
    net_profit_margin = round((net_profit / turnover) * 100, 2) if turnover else 0.0
    current_ratio = round((current_assets / current_liabilities), 2) if current_liabilities else 0.0
    debt_to_equity = round((total_debt / net_worth), 2) if net_worth else 0.0
    banking_limit_utilisation = round(
        (bank_limit_avg_utilised / bank_limit_sanctioned) * 100, 2
    ) if bank_limit_sanctioned else 0.0

    gst_filing_timely = True if gst_filing_timely_str == "Yes" else False if gst_filing_timely_str == "No" else None
    active_litigation = True if active_litigation_str == "Yes" else False if active_litigation_str == "No" else None
    credit_rating_clean = None if credit_rating_val == "Not Available" else credit_rating_val

    industry_risk = industry_risk_str.lower()
    management_risk_flag = management_risk_flag_str == "Yes"

    scoring_input = {
        "net_profit_margin": net_profit_margin,
        "current_ratio": current_ratio,
        "debt_to_equity": debt_to_equity,
        "banking_limit_utilisation": banking_limit_utilisation,
        "turnover_trend": turnover_trend_bs.lower(),
        "avg_days_to_pay": int(avg_days_to_pay),
        "bounced_cheques_last_12m": int(bounced_cheques_last_12m),
        "past_default_flag": (past_default_flag == "Yes"),
        "gst_filing_timely": gst_filing_timely,
        "active_litigation": active_litigation,
        "credit_rating": credit_rating_clean,
        "years_in_business": years_in_business,
        "industry_risk": industry_risk,
        "top_5_customer_share": top_5_customer_share,
        "management_risk_flag": management_risk_flag,
    }

    out = evaluate_customer(scoring_input)

    st.subheader("📋 Customer Summary")
    st.write(f"**Name:** {customer_name or '—'}")
    st.write(f"**CIN:** {cin_no or '—'}")
    st.write(f"**PAN:** {pan_no or '—'}")
    st.write(f"**GST:** {gst_no or '—'}")
    st.write(f"**Registered Address:** {registered_address or '—'}")
    st.write(f"**Location:** {city or ''} {state or ''} {pincode or ''}")
    st.write("**Director(s):**")
    st.code(directors_details or "—")

    st.subheader("🏢 Company Profile & Key Indicators")
    st.write(f"**Financial Year:** {latest_fy or '—'}")
    st.write(f"**Authorised Capital:** {authorised_capital or '—'}")
    st.write(f"**Paid-up Capital:** {paidup_capital or '—'}")
    st.write(f"**Company Age:** {company_age or '—'} years")
    st.write(f"**Revenue Growth (3 yrs):** {revenue_growth or '—'} %")
    st.write(f"**Profit Growth (3 yrs):** {profit_growth or '—'} %")
    st.write(f"**Employee Count:** {employee_count or '—'}")
    st.write("**Ownership / Shareholding:**")
    st.code(ownership_structure or "—")
    st.write("**Key Members / Board:**")
    st.code(key_members or "—")

    st.subheader("📊 Result")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Score", f"{out.total_score} / 100")
    with c2:
        st.metric("Risk Band", out.risk_band.value)
    with c3:
        st.metric("Decision", out.decision.value)

    st.markdown("#### Calculated Ratios")
    st.write(f"- Net Profit Margin: **{net_profit_margin} %**")
    st.write(f"- Current Ratio: **{current_ratio}**")
    st.write(f"- Debt-to-Equity: **{debt_to_equity}**")
    st.write(f"- Bank Limit Utilisation: **{banking_limit_utilisation} %**")
    st.write(f"- Turnover Trend: **{turnover_trend_bs}**")

    st.markdown("#### System Remarks")
    if out.reasons:
        for r in out.reasons:
            st.write(f"- {r}")
    else:
        st.write("No specific risk remarks.")

    st.markdown("#### Suggested Action")
    if out.decision.value == "APPROVE":
        st.success("✅ Onboard with normal credit terms.")
    elif out.decision.value == "CONDITIONAL_APPROVAL":
        st.warning("⚠️ Onboard with conditions (lower limit, advance, PDCs, etc.).")
    else:
        st.error("⛔ Do NOT offer open credit. Consider advance / security only.")
