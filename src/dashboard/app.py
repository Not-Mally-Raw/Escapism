import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json

# Adjust sys.path to import src modules if needed
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.core.types import FailureClass, ActionType, PaymentRail, ConsentStatus
from src.core.models import MandateStateRecord
from src.diagnosis.classifier import diagnose_failure
from src.decision.optimizer import optimize_decision
from src.ml.inference import predict_recovery_probability
from src.core.taxonomy import CODE_TO_CLASS

st.set_page_config(page_title="AI Revenue Recovery", layout="wide")

st.title("AI Revenue Recovery: Compliance-Constrained Engine")

tab1, tab2 = st.tabs(["Static Analytics (Monte Carlo)", "Live Decision Simulator"])

# --- TAB 1: STATIC ANALYTICS ---
with tab1:
    st.header("Monte Carlo 3-Policy Benchmark (1,000 Iterations)")
    st.markdown("Comparing Naive Blind Retry vs. AI Orchestrator on 5,000 synthetic Indian mandate failures.")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Policy 1: Do Nothing", "₹23.88M")
    col2.metric("Policy 2: Naive Blind Retry", "₹23.84M", "-₹33,803 (Net Loss)")
    col3.metric("Policy 3: AI Orchestrator", "₹27.73M", "+₹3.89M (Uplift)")
    
    st.subheader("Segment-Level Net Revenue Recovery (NRR)")
    
    # Existing generated data from the benchmark
    segment_data = pd.DataFrame({
        "Failure Class": ["SOFT_LIQUIDITY", "TECHNICAL_RETRYABLE", "AMBIGUOUS_DECLINE", "HARD_TERMINAL", "LEGAL_HOLD"],
        "Base Recovery (₹)": [18.23e6, 3.65e6, 1.99e6, 0.0, 0.0],
        "Blind Retry NRR (₹)": [18.59e6, 3.73e6, 1.52e6, -5577.0, -983.0],
        "AI Orchestrator NRR (₹)": [20.06e6, 5.12e6, 2.54e6, 0.0, 0.0]
    })
    
    # Calculate uplift
    segment_data["AI Uplift vs Blind Retry"] = segment_data["AI Orchestrator NRR (₹)"] - segment_data["Blind Retry NRR (₹)"]
    
    fig = px.bar(
        segment_data, 
        x="Failure Class", 
        y="AI Uplift vs Blind Retry",
        title="Uplift (Net Revenue) by Segment: AI vs Blind Retry",
        color="AI Uplift vs Blind Retry",
        color_continuous_scale=px.colors.diverging.RdYlGn
    )
    st.plotly_chart(fig, use_container_width=True)

# --- TAB 2: LIVE DECISION SIMULATOR ---
with tab2:
    st.header("Interactive Decision Simulator")
    
    # Pre-loaded examples
    st.markdown("**Load Example Case:**")
    col_ex1, col_ex2, col_ex3, col_ex4 = st.columns(4)
    
    if col_ex1.button("LEGAL_HOLD (07)"):
        st.session_state.update({"amount": 5000.0, "code": "07", "attempts": 1, "sms": True, "wa": True})
    if col_ex2.button("AFA-Gated (₹20K)"):
        st.session_state.update({"amount": 20000.0, "code": "04", "attempts": 1, "sms": True, "wa": True})
    if col_ex3.button("SOFT_LIQUIDITY (Z9)"):
        st.session_state.update({"amount": 500.0, "code": "Z9", "attempts": 1, "sms": True, "wa": True})
    if col_ex4.button("Attempt Cap Reached (4)"):
        st.session_state.update({"amount": 1000.0, "code": "Z9", "attempts": 4, "sms": True, "wa": True})
        
    amount = st.number_input("Amount (INR)", value=st.session_state.get("amount", 5000.0), step=100.0)
    failure_code = st.text_input("Failure Code (e.g., Z9, 04, 07)", value=st.session_state.get("code", "Z9"))
    attempt_count = st.number_input("Attempt Count", value=st.session_state.get("attempts", 1), min_value=1, max_value=4)
    
    # Current time or 12 hours ago
    t_minus_12 = datetime.now(timezone.utc) - timedelta(hours=12)
    failure_timestamp = st.text_input("Failure Timestamp (ISO8601)", value=t_minus_12.isoformat())
    
    sms_consent = st.checkbox("SMS Consent", value=st.session_state.get("sms", True))
    wa_consent = st.checkbox("WhatsApp Consent", value=st.session_state.get("wa", True))
    
    if st.button("Simulate Pipeline"):
        try:
            timestamp_dt = datetime.fromisoformat(failure_timestamp)
        except Exception:
            st.error("Invalid ISO timestamp format.")
            st.stop()
            
        with st.spinner("Running full pipeline..."):
            # 1. Diagnosis
            diagnosis = diagnose_failure(bank_code=failure_code, raw_error_text=None)
            f_class = diagnosis.failure_class
            st.success(f"**Diagnosis Layer:** {f_class.value} (confidence={diagnosis.confidence:.2f})")
            
            # 2. Build a real MandateStateRecord
            rail = PaymentRail.UPI_AUTOPAY if failure_code.startswith(("U", "Z")) else PaymentRail.ENACH
            
            consent_dict = {}
            consent_dict["SMS"] = ConsentStatus.OPTED_IN if sms_consent else ConsentStatus.OPTED_OUT
            consent_dict["WHATSAPP"] = ConsentStatus.OPTED_IN if wa_consent else ConsentStatus.OPTED_OUT
            consent_dict["PAYMENT_LINK"] = ConsentStatus.OPTED_IN
            
            # Clamp attempt_count to valid range for MandateStateRecord (1-4)
            clamped_attempts = max(1, min(4, int(attempt_count)))
            
            last_attempt_ts = timestamp_dt - timedelta(hours=25) if clamped_attempts > 1 else None
            
            state = MandateStateRecord(
                case_id="dashboard_live",
                mandate_id="man_dashboard",
                merchant_id="mer_001",
                customer_id="cust_0001",
                rail=rail,
                amount_inr=Decimal(str(amount)),
                attempt_count=clamped_attempts,
                failure_code=failure_code,
                failure_class=f_class,
                failure_timestamp=timestamp_dt,
                last_attempt_timestamp=last_attempt_ts,
                afa_required=(amount > 15000),
                pre_debit_notice_sent=True,
                customer_timezone="Asia/Kolkata",
                channel_consent=consent_dict,
            )
            
            # 3. Run the real optimizer (it internally calls guardrails + ML inference)
            decision = optimize_decision(state)
            
            # 4. Display guardrail results
            st.write("**Propensity Model (Track 1):**")
            if decision.p_hat is not None:
                st.info(f"P(recoverable) = {decision.p_hat:.4f}")
            else:
                st.info("P(recoverable) = N/A (mandatory routing)")
            
            # 5. Display decision results
            st.write("**Decision Layer (Track 3):**")
            
            if decision.candidate_scores:
                ev_table = []
                for cs in decision.candidate_scores:
                    ev_table.append({
                        "Action": cs.action.value,
                        "Multiplier": f"{cs.multiplier:.2f}",
                        "Cost (₹)": f"{cs.cost_inr:.2f}",
                        "Lift-EV (₹)": f"{cs.lift_ev_inr:.2f}",
                        "Cleared θ": "✅" if cs.cleared_threshold else "❌",
                    })
                st.table(pd.DataFrame(ev_table))
            
            # 6. Show final decision
            if decision.selected_action == ActionType.ABORT_COMPLIANT:
                st.error(f"**FINAL DECISION:** {decision.selected_action.value}")
            elif decision.selected_action == ActionType.ESCALATE_HUMAN:
                st.warning(f"**FINAL DECISION:** {decision.selected_action.value}")
            else:
                st.success(f"**FINAL DECISION:** {decision.selected_action.value}")
                
            st.caption(f"Audit Rationale: {decision.audit_step.rationale}")
