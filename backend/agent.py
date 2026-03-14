import os
from typing import List, Dict, Optional
from langchain_google_vertexai import (
    VertexAIEmbeddings,
    ChatVertexAI,
)
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# ==========================================
# STEP 1: DEFINE COMPLEX TOOLSETS
# ==========================================

# --- Agent 1 Tools: Risk & Compliance ---
@tool
def check_sanctions_list(vendor_name: str) -> str:
    """Checks if a vendor is on global restricted/sanctioned entities lists."""
    restricted = ["BlacklistCorp", "ShadowTrade LLC"]
    if vendor_name in restricted:
        return "RED ALERT: Vendor is on the Global Sanctions List. DO NOT PROCEED."
    return "SUCCESS: Vendor cleared for trade."

@tool
def get_vendor_credit_score(vendor_name: str) -> int:
    """Retrieves vendor creditworthiness from external databases (e.g., Dun & Bradstreet)."""
    return 85 if len(vendor_name) > 5 else 40

# --- Agent 2 Tools: Tax & Treasury ---
@tool
def calculate_cross_border_tax(amount: float, origin: str, destination: str) -> Dict:
    """Calculates VAT/GST and Import Duties for cross-border transactions."""
    tax_rates = {"DE_IN": 0.18, "US_IN": 0.12, "UK_IN": 0.20}
    key = f"{origin}_{destination}"
    rate = tax_rates.get(key, 0.15)
    return {"tax_amount": amount * rate, "rate": rate, "route": key}

@tool
def validate_fx_hedge(currency_pair: str, rate_used: float) -> str:
    """Checks if the FX rate used matches the MNC's internal hedged rate for the month."""
    hedged_rates = {"EUR_INR": 91.5, "USD_INR": 83.2}
    market_rate = hedged_rates.get(currency_pair, 0)
    if market_rate == 0:
        return f"FX WARNING: No hedged rate found for '{currency_pair}'."
    variance = abs(rate_used - market_rate) / market_rate
    if variance > 0.05:
        return f"FX ALERT: Variance {variance:.2%} exceeds 5% limit. Audit required."
    return "FX SUCCESS: Rate within acceptable hedge variance."

# --- Agent 3 Tools: Financial Control ---
@tool
def categorize_expense(amount: float, item_description: str) -> str:
    """Determines if the expense is Capital Expenditure (CapEx) or Operational (OpEx)."""
    if amount > 50000 or "server" in item_description.lower():
        return "CLASSIFICATION: CapEx (Depreciate over 3 years)"
    return "CLASSIFICATION: OpEx (Immediate deduction)"


# ==========================================
# STEP 2: LLM & AGENT CREATION
# ==========================================

llm = ChatVertexAI(model_name="gemini-2.5-pro")


def create_specialized_agent(tools, system_prompt):
    """Creates a LangGraph react agent with the given tools and system prompt."""
    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
    )


# ==========================================
# STEP 3: DEFINE SPECIALIZED AGENTS (IMPROVED PROMPTS)
# ==========================================

RISK_AGENT_PROMPT = """
You are a Senior Risk & Compliance Officer at a multinational corporation, responsible for \
protecting the company from financial crime, reputational damage, and regulatory penalties.

RESPONSIBILITIES:
- Screen every vendor against global sanctions and restricted-entity lists before any payment is approved.
- Assess vendor financial health using their credit score to determine payment risk and recommended terms.

DECISION FRAMEWORK:
1. Run `check_sanctions_list` first — this is a hard blocker. A RED ALERT means immediate rejection; no further analysis is needed.
2. Run `get_vendor_credit_score` next. Apply the following thresholds:
   - Score ≥ 75 → LOW RISK: Standard Net-30 payment terms acceptable.
   - Score 50–74 → MODERATE RISK: Require upfront deposit (25–50%) or a letter of credit.
   - Score < 50  → HIGH RISK: Escalate to CFO. Consider rejecting or requiring full prepayment + guarantees.

OUTPUT FORMAT — always respond in this exact structure:
---
SANCTIONS CHECK: [CLEARED / RED ALERT — reason]
CREDIT SCORE: [score] → [LOW / MODERATE / HIGH] RISK
RECOMMENDED PAYMENT TERMS: [specific terms]
OVERALL RISK VERDICT: [APPROVED / CONDITIONAL APPROVAL / REJECTED]
RISK NOTES: [Any caveats, flags, or escalation instructions]
---

Be precise and decisive. Do not hedge your verdict — the CFO needs a clear action item.
"""

TAX_AGENT_PROMPT = """
You are a Tax & Treasury Specialist at a multinational corporation, responsible for ensuring \
cross-border transactions are tax-compliant and currency-hedged correctly.

RESPONSIBILITIES:
- Calculate the exact tax liability (VAT/GST + import duties) for every international transaction.
- Validate that the FX rate used is within the company's approved monthly hedge band (±5% variance).

DECISION FRAMEWORK:
1. Run `calculate_cross_border_tax` using the transaction amount, origin country code (e.g., US, DE, UK), \
   and destination country code (e.g., IN). Report the effective tax rate and total tax burden.
2. Run `validate_fx_hedge` using the currency pair (e.g., USD_INR) and the rate used in the invoice. \
   - FX SUCCESS → rate is within policy; no action needed.
   - FX ALERT → variance exceeds 5%; flag for mandatory audit before payment release.
   - FX WARNING → unknown currency pair; escalate to Treasury for manual rate approval.

OUTPUT FORMAT — always respond in this exact structure:
---
TAX ROUTE: [origin → destination]
EFFECTIVE TAX RATE: [X%]
TAX LIABILITY: [INR / $ / EUR amount]
TOTAL COST (Invoice + Tax): [amount]
FX VALIDATION: [SUCCESS / ALERT / WARNING — details]
TREASURY VERDICT: [APPROVED / HOLD FOR AUDIT / ESCALATE TO TREASURY]
TAX NOTES: [Any compliance flags, treaty benefits, or audit triggers]
---

Be precise with numbers. Round to 2 decimal places. Always state the full cost impact clearly.
"""

CONTROL_AGENT_PROMPT = """
You are the Financial Controller at a multinational corporation, responsible for ensuring every \
expense is correctly classified for accounting, tax, and budget reporting purposes.

RESPONSIBILITIES:
- Classify each expense as CapEx or OpEx using GAAP/IFRS standards.
- Assess the budget impact and flag any anomalies (e.g., unusually large OpEx that should be CapEx).

DECISION FRAMEWORK:
1. Run `categorize_expense` with the invoice amount and a clear item description extracted from the request.
2. Apply this interpretive layer on top of the tool result:
   - CapEx: Asset must be capitalized on the balance sheet. Verify useful life (default: 3 years unless \
     stated otherwise). Flag if amount > INR 5,00,000 for additional CFO sign-off.
   - OpEx: Deducted immediately in the P&L. Flag if a single OpEx item exceeds INR 1,00,000 — \
     this may indicate misclassification and warrants a second review.
3. Suggest the correct GL (General Ledger) account code category: e.g., 1500s (Fixed Assets) for CapEx, \
   6000s (Operating Expenses) for OpEx.

OUTPUT FORMAT — always respond in this exact structure:
---
EXPENSE AMOUNT: [amount]
ITEM DESCRIPTION: [description]
CLASSIFICATION: [CapEx / OpEx]
GL ACCOUNT RANGE: [e.g., 1500–1599 Fixed Assets]
DEPRECIATION SCHEDULE: [if CapEx: years and annual charge | if OpEx: N/A]
CFO SIGN-OFF REQUIRED: [Yes / No — reason]
ANOMALY FLAGS: [None / description of any concerns]
CONTROL VERDICT: [APPROVED / FLAGGED FOR REVIEW / REJECTED]
---

Be thorough but concise. A misclassification costs the company money — accuracy is paramount.
"""

# ==========================================
# STEP 4: INSTANTIATE AGENTS
# ==========================================

risk_agent = create_specialized_agent(
    [check_sanctions_list, get_vendor_credit_score],
    RISK_AGENT_PROMPT,
)

tax_agent = create_specialized_agent(
    [calculate_cross_border_tax, validate_fx_hedge],
    TAX_AGENT_PROMPT,
)

control_agent = create_specialized_agent(
    [categorize_expense],
    CONTROL_AGENT_PROMPT,
)


# ==========================================
# STEP 5: ORCHESTRATION (THE SUPERVISOR)
# ==========================================

SYNTHESIS_PROMPT_TEMPLATE = """
You are the Chief Financial Officer (CFO) of a multinational corporation.
Three specialist agents have audited a procurement request and submitted their reports below.
Your job is to synthesize these into a single, authoritative CFO Audit Memo.

═══════════════════════════════════════════════
INCOMING AUDIT REPORTS
═══════════════════════════════════════════════

[REPORT 1 — Risk & Compliance]
{risk_result}

[REPORT 2 — Tax & Treasury]
{tax_result}

[REPORT 3 — Financial Control]
{control_result}

═══════════════════════════════════════════════
YOUR INSTRUCTIONS
═══════════════════════════════════════════════

1. FINAL DECISION RULE (non-negotiable):
   - If ANY report contains 'RED ALERT' → Final verdict MUST be REJECTED. State why.
   - If ANY report contains 'FX ALERT' or 'HOLD FOR AUDIT' → Final verdict is CONDITIONAL HOLD. \
     List exact conditions that must be resolved before payment can proceed.
   - If ALL reports show APPROVED or SUCCESS → Final verdict is APPROVED TO PAY.

2. Write the memo in professional CFO language — concise, structured, and actionable.
   Avoid restating every detail from each report; synthesize the key findings only.

3. End with a clear NEXT ACTIONS section — name the team responsible and the deadline.

OUTPUT FORMAT:
════════════════════════════════════════════
CFO AUDIT MEMO
Date: [today]
RE: Procurement Request Audit Summary
════════════════════════════════════════════

EXECUTIVE SUMMARY:
[A brief summary on what was audited and the overall outcome of 1. Risk Results 2. Tax Results  3. Control Results]

KEY FINDINGS:
• Risk & Compliance: [one-line verdict]
• Tax & Treasury: [one-line verdict with cost impact]
• Financial Control: [one-line verdict with classification]

FINAL DECISION: [APPROVED TO PAY / CONDITIONAL HOLD / REJECTED]
Reason: [1-2 sentences justifying the decision]

NEXT ACTIONS:
1. [Team] — [Action] — [Deadline]
2. [Team] — [Action] — [Deadline]
(add as many as needed)

Signed,
CFO Office
════════════════════════════════════════════
"""


class ProcurementSupervisor:
    def __init__(self):
        self.llm = llm

    def _invoke_agent(self, agent, request: str) -> str:
        """Invoke a LangGraph agent and extract the final AI message content."""
        result = agent.invoke(
            {"messages": [{"role": "user", "content": request}]}
        )
        content = result["messages"][-1].content
        # create_react_agent may return content as a list of content blocks
        # e.g. [{'type': 'text', 'text': '...'}, ...]
        if isinstance(content, list):
            return "\n".join(
                block.get("text", "") for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        return content

    def run_audit(self, request: str) -> dict:
        print("\n--- PHASE 1: Risk & Compliance ---")
        risk_result = self._invoke_agent(risk_agent, request)
        print(f"Risk Result:\n{risk_result}")

        print("\n--- PHASE 2: Tax & Treasury ---")
        tax_result = self._invoke_agent(tax_agent, request)
        print(f"Tax Result:\n{tax_result}")

        print("\n--- PHASE 3: Financial Control ---")
        control_result = self._invoke_agent(control_agent, request)
        print(f"Control Result:\n{control_result}")

        # Final Synthesis by the Supervisor (CFO)
        synthesis_prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
            risk_result=risk_result,
            tax_result=tax_result,
            control_result=control_result,
        )

        print("\n--- PHASE 4: CFO Synthesis ---")
        cfo_memo = self.llm.invoke(synthesis_prompt).content
        print(cfo_memo)
        return {
            "risk_result": risk_result,
            "tax_result": tax_result,
            "control_result": control_result,
            "cfo_memo": cfo_memo,
        }



# ==========================================
# STEP 5: EXECUTION
# ==========================================

if __name__ == "__main__":
    supervisor = ProcurementSupervisor()

    complex_request = """
    Purchase Request:
    - Vendor: ShadowTrade LLC
    - Item: High-performance AI GPU Servers
    - Total Cost: 120,000 EUR
    - Destination: India Branch
    - FX Rate quoted: 1 EUR = 98 INR
    """

    final_memo = supervisor.run_audit(complex_request)
    print("\n" + "="*50)
    print("FINAL CFO MEMO")
    print("="*50)
    print(final_memo)