"""Phase 2 — Tools & Technology Selection."""

from dataclasses import dataclass
from cmbagent.phases.rfp.base import RfpPhaseBase, RfpPhaseConfig, PhaseContext


@dataclass
class RfpToolsConfig(RfpPhaseConfig):
    phase_type: str = "rfp_tools"


class RfpToolsPhase(RfpPhaseBase):
    config_class = RfpToolsConfig

    def __init__(self, config=None):
        super().__init__(config or RfpToolsConfig())

    @property
    def phase_type(self) -> str:
        return "rfp_tools"

    @property
    def display_name(self) -> str:
        return "Tools & Technology"

    @property
    def shared_output_key(self) -> str:
        return "tools_technology"

    @property
    def output_filename(self) -> str:
        return "tools.md"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior solutions architect and technology evaluator with 20+ years "
            "of experience selecting enterprise technology stacks.  You specialize in "
            "head-to-head competitive analysis of tools and platforms.  You ALWAYS provide "
            "detailed comparison tables, security assessments, and cost-optimized recommendations "
            "that respect the client's stated budget.  You never recommend a tool without "
            "comparing it against at least 2–3 alternatives and explaining why it wins."
        )
    @property
    def specialist_system_prompt(self) -> str:
        return (
            "You are a senior security auditor and compliance specialist with expertise "
            "in enterprise software supply chains.  You will receive a tools & technology "
            "selection document. Validate and enrich it:\n"
            "1. Verify security assessments for each tool \u2014 CVE history accuracy, "
            "compliance certifications (SOC 2, ISO 27001, FedRAMP)\n"
            "2. Check encryption capabilities (at-rest, in-transit, key management)\n"
            "3. Identify supply chain risks and vendor lock-in concerns\n"
            "4. Validate license types and cost estimates against current market pricing\n"
            "5. Ensure comparison tables are fair \u2014 same criteria across all alternatives\n"
            "6. Add missing security considerations (OWASP, NIST, data residency)\n"
            "7. Verify cost calculations (Monthly \u00d7 12 = Annual)\n"
            "Return the COMPLETE improved document \u2014 not a commentary. Output clean markdown only."
        )
    def build_user_prompt(self, context: PhaseContext) -> str:
        reqs = context.shared_state.get("requirements_analysis", "(Not yet generated)")
        return f"""Based on the following requirements analysis, recommend the complete set of tools and technologies needed.

Requirements Analysis:
{reqs}

IMPORTANT — BUDGET AWARENESS:
Carefully review the Budget Analysis and Constraints sections above.  If the RFP specifies a budget (e.g., $500K, $1M), ALL tool and technology recommendations MUST fit within that budget.  Prefer open-source and cost-effective alternatives when the budget is tight.  Always show how the total tool cost fits within the stated budget.

For EACH tool/technology category, you MUST provide a **Comparison Table** with the following structure:

| Criteria | Recommended Tool | Alternative 1 | Alternative 2 |
|----------|-----------------|---------------|---------------|
| Licensing | ... | ... | ... |
| Annual Cost | ... | ... | ... |
| Security Features | ... | ... | ... |
| Why Chosen / Not Chosen | ... | ... | ... |

For each tool/technology, provide:
1. **Tool/Technology Name**
2. **Category** (Frontend, Backend, Database, DevOps, Testing, Monitoring, Security, etc.)
3. **Purpose** — Why this tool is needed and what problem it solves
4. **Comparison Table** — Head-to-head comparison against 2–3 alternatives (see format above)
5. **Why This Tool Was Chosen** — Specific, concrete reasons (performance benchmarks, community size, security track record, cost advantage, ecosystem fit)
6. **Why Alternatives Were NOT Chosen** — Specific weaknesses of each rejected alternative relative to this project
7. **Security Assessment** — For each chosen tool:
   - Known CVE history and security track record
   - Built-in security features (encryption, auth, audit logging, RBAC, etc.)
   - Compliance certifications (SOC2, ISO 27001, HIPAA, GDPR, etc.)
   - Data protection capabilities (encryption at rest/transit, key management)
   - Security comparison vs. the alternatives — why this tool is more secure or equally secure
8. **Licensing** — Open-source, commercial, freemium — with specific license type (MIT, Apache 2.0, proprietary, etc.)
9. **Cost Estimate** — Per month AND per year, including tier details; compare cost against alternatives
10. **Integration Notes** — How it fits with other selected tools in the stack

Additional required sections:

## Security Summary Matrix
Provide a consolidated security comparison table across ALL recommended tools:
| Tool | Auth & RBAC | Encryption | Compliance Certs | CVE History | Security Rating |
|------|------------|------------|------------------|-------------|----------------|

## Total Tool Cost Summary
Provide a cost summary table with monthly and annual estimates.
Show how the total fits within the RFP's stated budget (if any).
If total exceeds budget, flag it and suggest cost-reduction alternatives.

## Cost Optimization Recommendations
- Which tools have free tiers adequate for initial phases?
- Where can open-source alternatives save money?
- Volume discount or enterprise agreement opportunities

{self.get_currency_rule(context)}

Produce a detailed markdown document with comparison tables for every tool category."""
