"""Phase 4 — Implementation Plan."""

from dataclasses import dataclass
from cmbagent.phases.rfp.base import RfpPhaseBase, RfpPhaseConfig, PhaseContext


@dataclass
class RfpImplementationConfig(RfpPhaseConfig):
    phase_type: str = "rfp_implementation"


class RfpImplementationPhase(RfpPhaseBase):
    config_class = RfpImplementationConfig

    def __init__(self, config=None):
        super().__init__(config or RfpImplementationConfig())

    @property
    def phase_type(self) -> str:
        return "rfp_implementation"

    @property
    def display_name(self) -> str:
        return "Implementation Plan"

    @property
    def shared_output_key(self) -> str:
        return "implementation_plan"

    @property
    def output_filename(self) -> str:
        return "implementation.md"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior project manager and delivery lead.  Create detailed, "
            "actionable implementation plans with realistic timelines, resource "
            "allocations, and quality gates."
        )

    @property
    def specialist_system_prompt(self) -> str:
        return (
            "You are a senior delivery assurance analyst and resource planning expert "
            "with experience validating project plans for enterprise IT programmes.  "
            "You will receive an implementation plan. Validate and enrich it:\n"
            "1. Validate timeline feasibility given team size, technology complexity, and dependencies\n"
            "2. Check for missing dependencies, unrealistic milestones, or compressed phases\n"
            "3. Verify resource allocation is balanced \u2014 no single-person bottlenecks\n"
            "4. Validate budget breakdown against industry benchmarks for similar projects\n"
            "5. Ensure quality gates, acceptance criteria, and communication cadence are defined\n"
            "6. Check sprint capacities and velocity assumptions are realistic\n"
            "7. Verify cost calculations (Monthly \u00d7 12 = Annual)\n"
            "Return the COMPLETE improved document \u2014 not a commentary. Output clean markdown only."
        )

    def build_user_prompt(self, context: PhaseContext) -> str:
        ss = context.shared_state
        return f"""Based on all previous analysis, create a comprehensive implementation plan.

Requirements Analysis:
{ss.get("requirements_analysis", "(Not yet generated)")}

Tools & Technology:
{ss.get("tools_technology", "(Not yet generated)")}

Cloud & Infrastructure:
{ss.get("cloud_infrastructure", "(Not yet generated)")}

Create an implementation plan covering:
1. **Project Phases** — Discovery, Design, Development, Testing, Deployment, Hypercare
2. **Timeline** — Gantt-chart-style breakdown with milestones
3. **Sprint Planning** — Sprint structure, velocity assumptions, backlog prioritization
4. **Team Composition** — Required roles, headcount per phase
5. **Resource Allocation** — Who does what, when
6. **Dependencies** — Critical path, inter-team dependencies
7. **Risk Mitigation Plan** — Phase-specific risks and contingencies
8. **Quality Gates** — What must pass before proceeding to next phase
9. **Communication Plan** — Standup cadence, reporting structure, escalation path
10. **Budget Breakdown** — Cost per phase (people + tools + cloud)

{self.get_currency_rule(context)}

Produce a detailed markdown document with timeline tables."""
