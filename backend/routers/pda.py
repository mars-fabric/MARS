"""
PDA (Product Discovery Assistant) API Router.

Exposes REST endpoints that the PDA frontend calls instead of the
direct Infosys LLM API. Each endpoint delegates to pda_service.py
which uses cmbagent's infrastructure (create_openai_client / one_shot).

Endpoints:
  POST /api/pda/client-details     → Step 0: auto-detect client info
  POST /api/pda/research-summary   → Step 1: research (direct LLM + optional researcher)
  POST /api/pda/problem-definition → Step 2: problem definition (direct LLM)
  POST /api/pda/opportunities      → Step 3: opportunity areas
  POST /api/pda/solution-archetypes→ Step 4: solution archetypes
  POST /api/pda/features           → Step 5: feature set
  POST /api/pda/prompts            → Step 6: builder prompts
  POST /api/pda/slide-content      → Step 7: slide content
  POST /api/pda/deep-research      → Optional: full P&C deep research
  GET  /api/pda/health             → Health check
"""

import logging
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pda", tags=["PDA"])


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class IntakeData(BaseModel):
    clientName: str = ""
    industry: str = ""
    subIndustry: str = ""
    clientContext: str = ""
    businessFunction: str = ""
    discoveryType: str = ""
    processType: str = "new"
    existingFunctionality: Optional[str] = ""
    problemKeywords: str = ""
    expectedOutput: List[str] = Field(default_factory=list)


class ClientDetailsRequest(BaseModel):
    clientName: str


class ClientDetailsResponse(BaseModel):
    industry: str
    subIndustry: str
    businessFunctions: List[str]


class ResearchSummaryRequest(BaseModel):
    intakeData: IntakeData


class ResearchSummaryResponse(BaseModel):
    marketTrends: List[str] = Field(default_factory=list)
    competitorMoves: List[str] = Field(default_factory=list)
    industryPainPoints: List[str] = Field(default_factory=list)
    workshopAngles: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)


class ProblemDefinitionRequest(BaseModel):
    intakeData: IntakeData
    researchSummary: Dict[str, Any]


class ProblemDefinitionResponse(BaseModel):
    problemStatement: str = ""
    supportingPoints: Any = Field(default_factory=list)
    personasAffected: Any = Field(default_factory=list)
    kpisImpacted: Any = Field(default_factory=list)
    rootCause: str = ""
    reframingExamples: Any = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)


class OpportunitiesRequest(BaseModel):
    intakeData: IntakeData
    problemDefinition: str


class OpportunityItem(BaseModel):
    id: str = ""
    title: str = ""
    explanation: str = ""
    valueCategory: str = ""
    kpis: List[str] = Field(default_factory=list)
    whyNow: str = ""
    references: List[str] = Field(default_factory=list)


class SolutionArchetypesRequest(BaseModel):
    selectedOpportunity: Dict[str, Any]
    intakeData: IntakeData


class SolutionArchetypeItem(BaseModel):
    id: str = ""
    title: str = ""
    summary: str = ""
    personas: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)


class FeaturesRequest(BaseModel):
    selectedArchetype: Dict[str, Any]
    opportunity: Dict[str, Any]
    intakeData: IntakeData


class FeatureItem(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    strategicGoal: str = ""
    userStories: List[str] = Field(default_factory=list)
    successMetrics: List[str] = Field(default_factory=list)
    bucket: str = ""
    priority: str = "Should"
    selected: bool = False


class PromptsRequest(BaseModel):
    intakeData: IntakeData
    opportunity: Dict[str, Any]
    archetype: Dict[str, Any]
    selectedFeatures: List[Dict[str, Any]]


class PromptsResponse(BaseModel):
    lovable: str = ""
    googleAI: str = ""
    general: str = ""


class SlideContentRequest(BaseModel):
    intakeData: IntakeData
    research: str
    problem: str
    opportunity: Dict[str, Any]
    archetype: Dict[str, Any]
    features: List[Dict[str, Any]]


class SlideContentResponse(BaseModel):
    content: str


class DeepResearchRequest(BaseModel):
    intakeData: IntakeData


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def pda_health():
    """Health check for PDA service."""
    try:
        from cmbagent.llm_provider import get_provider_config
        config = get_provider_config()
        return {
            "status": "ok",
            "provider": config.active_provider,
            "is_azure": config.is_azure,
        }
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


@router.post("/client-details", response_model=ClientDetailsResponse)
async def api_client_details(request: ClientDetailsRequest):
    """Step 0: Auto-detect client industry and business functions."""
    try:
        from services.pda_service import get_client_details
        result = await get_client_details(request.clientName)
        return ClientDetailsResponse(**result)
    except Exception as e:
        logger.error("client-details failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to detect client details: {e}",
        )


@router.post("/research-summary", response_model=ResearchSummaryResponse)
async def api_research_summary(request: ResearchSummaryRequest):
    """Step 1: Generate research summary (direct LLM with optional researcher)."""
    try:
        from services.pda_service import generate_research_summary
        result = await generate_research_summary(request.intakeData.dict())
        return ResearchSummaryResponse(**result)
    except Exception as e:
        logger.error("research-summary failed: %s\n%s", e, traceback.format_exc())
        # Return a degraded response rather than 500 so the UI can still proceed
        return ResearchSummaryResponse(
            marketTrends=[f"Research generation encountered an error: {e}. Please retry."],
            competitorMoves=[],
            industryPainPoints=[],
            workshopAngles=[],
            references=[],
        )


@router.post("/problem-definition", response_model=ProblemDefinitionResponse)
async def api_problem_definition(request: ProblemDefinitionRequest):
    """Step 2: Generate problem definition via direct LLM."""
    try:
        from services.pda_service import generate_problem_definition
        result = await generate_problem_definition(
            request.intakeData.dict(),
            request.researchSummary,
        )
        return ProblemDefinitionResponse(**result)
    except Exception as e:
        logger.error("problem-definition failed: %s\n%s", e, traceback.format_exc())
        return ProblemDefinitionResponse(
            problemStatement=f"Problem definition generation encountered an error: {e}. Please retry.",
        )


@router.post("/opportunities")
async def api_opportunities(request: OpportunitiesRequest):
    """Step 3: Generate opportunity areas."""
    try:
        from services.pda_service import generate_opportunities
        result = await generate_opportunities(
            request.intakeData.dict(),
            request.problemDefinition,
        )
        return result
    except Exception as e:
        logger.error("opportunities failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate opportunities: {e}")


@router.post("/solution-archetypes")
async def api_solution_archetypes(request: SolutionArchetypesRequest):
    """Step 4: Generate solution archetypes."""
    try:
        from services.pda_service import generate_solution_archetypes
        result = await generate_solution_archetypes(
            request.selectedOpportunity,
            request.intakeData.dict(),
        )
        return result
    except Exception as e:
        logger.error("solution-archetypes failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate solution archetypes: {e}")


@router.post("/features")
async def api_features(request: FeaturesRequest):
    """Step 5: Generate feature set."""
    try:
        from services.pda_service import generate_features
        result = await generate_features(
            request.selectedArchetype,
            request.opportunity,
            request.intakeData.dict(),
        )
        return result
    except Exception as e:
        logger.error("features failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate features: {e}")


@router.post("/prompts", response_model=PromptsResponse)
async def api_prompts(request: PromptsRequest):
    """Step 6: Generate builder prompts."""
    try:
        from services.pda_service import generate_prompts
        result = await generate_prompts(
            request.intakeData.dict(),
            request.opportunity,
            request.archetype,
            request.selectedFeatures,
        )
        return PromptsResponse(**result)
    except Exception as e:
        logger.error("prompts failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate prompts: {e}")


@router.post("/slide-content", response_model=SlideContentResponse)
async def api_slide_content(request: SlideContentRequest):
    """Step 7: Generate slide content."""
    try:
        from services.pda_service import generate_slide_content
        result = await generate_slide_content(
            request.intakeData.dict(),
            request.research,
            request.problem,
            request.opportunity,
            request.archetype,
            request.features,
        )
        return SlideContentResponse(content=result)
    except Exception as e:
        logger.error("slide-content failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate slide content: {e}")


@router.post("/deep-research")
async def api_deep_research(request: DeepResearchRequest):
    """Optional: Full Planning & Control deep research pipeline."""
    try:
        from services.pda_service import deep_research
        result = await deep_research(request.intakeData.dict())
        return result
    except Exception as e:
        logger.error("deep-research failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Deep research failed: {e}")
