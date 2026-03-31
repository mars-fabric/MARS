"""Phase 6 — Execution Strategy."""

from dataclasses import dataclass
from cmbagent.phases.rfp.base import RfpPhaseBase, RfpPhaseConfig, PhaseContext


@dataclass
class RfpExecutionConfig(RfpPhaseConfig):
    phase_type: str = "rfp_execution"


class RfpExecutionPhase(RfpPhaseBase):
    config_class = RfpExecutionConfig

    def __init__(self, config=None):
        super().__init__(config or RfpExecutionConfig())

    @property
    def phase_type(self) -> str:
        return "rfp_execution"

    @property
    def display_name(self) -> str:
        return "Execution Strategy"

    @property
    def shared_output_key(self) -> str:
        return "execution_strategy"

    @property
    def output_filename(self) -> str:
        return "execution.md"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a delivery executive and program manager.  Define a "
            "comprehensive execution strategy from kickoff to go-live including "
            "testing, CI/CD, release management, and post-launch support."
        )

    @property
    def specialist_system_prompt(self) -> str:
        return (
            "You are a senior risk management and governance specialist with experience "
            "in enterprise programme delivery assurance.  You will receive an execution "
            "strategy document. Validate and enrich it:\n"
            "1. Validate go-live strategy and rollback / back-out plans\n"
            "2. Check risk register completeness \u2014 are probability, impact, and ownership assigned?\n"
            "3. Verify testing strategy covers functional, performance, security, and UAT scenarios\n"
            "4. Validate CI/CD pipeline design and release management gates\n"
            "5. Ensure governance structure, escalation paths, and RACI matrix are clear\n"
            "6. Check KPIs are measurable, time-bound, and aligned with business objectives\n"
            "7. Verify post-launch support model (SLA tiers, on-call rotation, knowledge transfer)\n"
            "Return the COMPLETE improved document \u2014 not a commentary. Output clean markdown only."
        )

    def build_user_prompt(self, context: PhaseContext) -> str:
        ss = context.shared_state
        return f"""Based on the complete analysis, tools, cloud plan, implementation plan, and architecture, define the execution strategy.

Requirements Analysis:
{ss.get("requirements_analysis", "(Not yet generated)")}

Tools & Technology:
{ss.get("tools_technology", "(Not yet generated)")}

Cloud & Infrastructure:
{ss.get("cloud_infrastructure", "(Not yet generated)")}

Implementation Plan:
{ss.get("implementation_plan", "(Not yet generated)")}

Architecture Design:
{ss.get("architecture_design", "(Not yet generated)")}

Cover the complete journey from kickoff to final product delivery:
1. **Kickoff & Onboarding** — Team ramp-up, environment setup, knowledge transfer
2. **Development Methodology** — Agile/Scrum/Kanban specifics
3. **Environment Strategy** — Dev, QA, Staging, Production pipeline
4. **Testing Strategy** — Unit, integration, E2E, performance, security testing
5. **CI/CD Pipeline** — Build, test, deploy automation
6. **Release Management** — Versioning, feature flags, rollback procedures
7. **Go-Live Plan** — Pre-launch checklist, data migration, cutover strategy
8. **Post-Launch Support** — Hypercare, SLA, incident response
9. **Knowledge Transfer** — Documentation, training, handover plan
10. **Success Metrics & KPIs** — How to measure project success
11. **Governance** — Steering committee, change management, escalation matrix

Produce a detailed markdown document."""
