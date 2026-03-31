"""Phase 3 — Cloud & Infrastructure Planning."""

from dataclasses import dataclass
from cmbagent.phases.rfp.base import RfpPhaseBase, RfpPhaseConfig, PhaseContext


@dataclass
class RfpCloudConfig(RfpPhaseConfig):
    phase_type: str = "rfp_cloud"


class RfpCloudPhase(RfpPhaseBase):
    config_class = RfpCloudConfig

    def __init__(self, config=None):
        super().__init__(config or RfpCloudConfig())

    @property
    def phase_type(self) -> str:
        return "rfp_cloud"

    @property
    def display_name(self) -> str:
        return "Cloud & Infrastructure"

    @property
    def shared_output_key(self) -> str:
        return "cloud_infrastructure"

    @property
    def output_filename(self) -> str:
        return "cloud.md"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a cloud infrastructure architect with 20+ years of expertise across "
            "AWS, Microsoft Azure, and Google Cloud Platform.  You have led cloud migrations "
            "and greenfield deployments for Fortune 500 enterprises.  You produce detailed, "
            "data-driven infrastructure designs with professional pricing tables, comparison "
            "matrices, and clear justifications for every architectural decision."
        )

    @property
    def specialist_system_prompt(self) -> str:
        return (
            "You are a cloud cost optimization specialist and FinOps practitioner with deep "
            "expertise across AWS, Azure, and GCP pricing models.  You will receive a cloud "
            "infrastructure plan. Validate and enrich it:\n"
            "1. Validate cost estimates against current cloud provider pricing (reserved, on-demand, spot)\n"
            "2. Identify cost optimization opportunities \u2014 right-sizing, savings plans, committed use\n"
            "3. Verify the provider comparison is fair and uses equivalent service tiers\n"
            "4. Check for missing services or architectural gaps (CDN, WAF, secrets manager)\n"
            "5. Validate disaster recovery design \u2014 RPO/RTO targets, multi-region failover\n"
            "6. Ensure security architecture follows cloud provider best practices (landing zones, IAM)\n"
            "7. Verify all cost tables have Monthly + Annual columns with correct math\n"
            "Return the COMPLETE improved document \u2014 not a commentary. Output clean markdown only."
        )

    def build_user_prompt(self, context: PhaseContext) -> str:
        reqs = context.shared_state.get("requirements_analysis", "(Not yet generated)")
        tools = context.shared_state.get("tools_technology", "(Not yet generated)")
        return f"""Based on the following requirements and tools selection, design the cloud infrastructure and provide detailed cost analysis.

Requirements Analysis:
{reqs}

Tools & Technology:
{tools}

IMPORTANT — BUDGET AWARENESS:
Carefully review the Budget Analysis and Constraints from the Requirements Analysis above.  If the RFP specifies a budget, ALL cloud infrastructure recommendations MUST fit within that budget (combined with tool costs from Stage 2).  If the budget is tight, prefer reserved instances, spot instances, smaller instance types, or managed services that reduce operational cost.  Always show how cloud costs fit within the overall budget.

You MUST cover ALL of the following sections in depth:

## 1. Cloud Provider Comparison Matrix
Create a detailed comparison table evaluating **all three major cloud providers** (AWS, Azure, GCP) against the project requirements.  The table MUST include columns for:
- Service availability for each required capability
- Pricing comparison (compute, storage, networking, managed services)
- Compliance & certification coverage
- Regional availability relevant to the project
- Managed service maturity for the required tech stack
- Enterprise support and SLA guarantees

## 2. Recommended Cloud Provider — Selection & Justification
- Clearly state which cloud provider (or multi-cloud strategy) is recommended
- Provide **specific, data-backed reasons** for the selection tied to project requirements
- Reference the comparison matrix scores

## 3. Why Other Providers Were Not Selected
For EACH provider that was NOT chosen, provide a dedicated subsection explaining:
- Specific gaps or weaknesses relative to this project's requirements
- Cost disadvantages (with numbers)
- Missing managed services or weaker ecosystem fit
- Any compliance, regional, or integration limitations
- Be fair and objective — acknowledge strengths while explaining why they were outweighed

## 4. Compute Resources — Instance types, sizing, auto-scaling rules with pricing
## 5. Storage — Block storage, object storage, database storage with capacity planning
## 6. Networking — VPC design, subnets, load balancers, CDN, DNS, bandwidth estimates
## 7. Security Architecture & Comparison
- For EACH major security service (IAM, encryption, WAF, DDoS, compliance), compare the offering across all three cloud providers in a table
- Include: feature set, pricing, compliance certifications covered, ease of integration
- Explain why the chosen provider's security stack is best for this project
- Cover: IAM & RBAC, encryption at rest/transit, WAF, DDoS protection, key management (KMS), secrets management, compliance controls, audit logging
## 8. Managed Services Comparison
- For EACH managed service category (databases, caching, message queues, search, AI/ML), provide a comparison table across providers
- Show pricing, performance benchmarks, managed vs. self-hosted trade-offs
- Justify why the recommended managed service is the best fit
## 9. DevOps Infrastructure — CI/CD pipelines, container orchestration, monitoring, logging
## 10. Disaster Recovery — Backup strategy, RPO/RTO targets, multi-region failover design
## 11. Detailed Cost Breakdown
- Itemized monthly cost per service in a professional table format
- Annual projection with growth assumptions
- Cost by category (compute, storage, networking, managed services, support)
## 12. Cost Optimization Strategy — Reserved instances, savings plans, spot/preemptible instances, right-sizing
## 13. Utilization Projections — Expected usage patterns, scaling triggers, capacity planning for 1/2/3 years

{self.get_currency_rule(context)}

Produce a detailed markdown document with cost tables."""
