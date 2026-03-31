"""Phase 1 — Requirements Analysis."""

from dataclasses import dataclass
from cmbagent.phases.rfp.base import RfpPhaseBase, RfpPhaseConfig, PhaseContext


@dataclass
class RfpRequirementsConfig(RfpPhaseConfig):
    phase_type: str = "rfp_requirements"


class RfpRequirementsPhase(RfpPhaseBase):
    config_class = RfpRequirementsConfig

    def __init__(self, config=None):
        super().__init__(config or RfpRequirementsConfig())

    @property
    def phase_type(self) -> str:
        return "rfp_requirements"

    @property
    def display_name(self) -> str:
        return "Requirements Analysis"

    @property
    def shared_output_key(self) -> str:
        return "requirements_analysis"

    @property
    def output_filename(self) -> str:
        return "requirements.md"

    @property
    def system_prompt(self) -> str:
        return (
            "You are an expert business analyst with 15+ years of experience analyzing "
            "RFPs for enterprise software projects. Extract comprehensive, actionable "
            "requirements that leave no ambiguity for downstream architects and engineers."
        )

    @property
    def specialist_system_prompt(self) -> str:
        return (
            "You are a senior domain validation expert and RFP strategist with deep "
            "cross-industry experience.  You will receive a requirements analysis document. "
            "Validate and enrich it:\n"
            "1. Identify any implicit requirements not explicitly captured\n"
            "2. Validate completeness of stakeholder mapping — are any decision-makers missing?\n"
            "3. Cross-reference constraints with industry standards (ISO, SOC 2, GDPR, etc.)\n"
            "4. Verify risk factors are realistic and mitigation strategies are actionable\n"
            "5. Ensure budget analysis accounts for hidden costs (training, migration, support)\n"
            "6. Validate the currency identification is correct and consistent\n"
            "7. Add any missing deliverables or success criteria\n"
            "Return the COMPLETE improved document with your enhancements integrated — "
            "not a commentary. Output clean markdown only."
        )

    def build_user_prompt(self, context: PhaseContext) -> str:
        rfp_content = context.task or "(No RFP content)"
        rfp_context = context.shared_state.get("rfp_context", "")
        ctx_block = f"\nAdditional Context:\n{rfp_context}" if rfp_context else ""
        return f"""Given the following RFP (Request for Proposal), perform a thorough requirements analysis. Extract and structure:

1. **Functional Requirements** — What the system must do
2. **Non-Functional Requirements** — Performance, security, scalability, compliance
3. **Stakeholders** — Who is involved, who benefits
4. **Constraints** — Budget, timeline, technology, regulatory
5. **Success Criteria** — How success will be measured
6. **Risk Factors** — Potential risks and mitigation strategies
7. **Assumptions** — Key assumptions being made
8. **Deliverables** — Expected outputs
9. **Budget Analysis** — Extract any budget figures, price ranges, cost constraints, or financial limits mentioned in the RFP. If a specific budget is stated, note the exact amount. If implied through scope or similar projects, provide a reasonable estimate. This budget will guide all downstream tool selection, cloud planning, and cost decisions.
10. **Currency** — Identify the currency used in the RFP (e.g., USD, EUR, GBP, INR, AUD, CAD, etc.). Look for currency symbols ($, €, £, ₹, etc.), currency codes, or country context. Output a dedicated section:

## Currency
**Primary Currency:** <CURRENCY_CODE> (<SYMBOL>)

If no currency is explicitly stated, infer from the country/region of the client. If still unclear, default to USD ($).

RFP Content:
{rfp_content}

{ctx_block}

Produce a well-structured markdown document with all the above sections."""
