import os
from cmbagent.base_agent import BaseAgent
from pydantic import BaseModel, Field
from typing import List, Literal, Dict, Any
import json
from pathlib import Path


class Subtasks(BaseModel):
    sub_task: str = Field(..., description="The sub-task to be performed")
    sub_task_agent: Literal["engineer", "researcher", "idea_maker", "idea_hater", "classy_sz_agent", "camb_agent", "classy_context", "camb_context"] =  Field(..., description="The name of the agent in charge of the sub-task")
    bullet_points: List[str] = Field(
        ..., description="A list of bullet points explaining what the sub-task should do"
    )

class PlannerResponse(BaseModel):
    # main_task: str = Field(..., description="The exact main task to solve.")
    sub_tasks: List[Subtasks]

    def format(self) -> str:
        plan_output = ""
        for i, step in enumerate(self.sub_tasks):
            plan_output += f"\n- Step {i + 1}:\n\t* sub-task: {step.sub_task}\n\t* agent in charge: {step.sub_task_agent}\n"
            if step.bullet_points:
                plan_output += "\n\t* instructions:\n"
                for bullet in step.bullet_points:
                    plan_output += f"\t\t- {bullet}\n"
        message = f"""
**PLAN**
{plan_output}
        """
        return message


class PlannerResponseFormatterAgent(BaseAgent):

    def __init__(self, llm_config=None, **kwargs):

        agent_id = os.path.splitext(os.path.abspath(__file__))[0]

        llm_config['config_list'][0]['response_format'] = PlannerResponse

        super().__init__(llm_config=llm_config, agent_id=agent_id, **kwargs)


    def set_agent(self,**kwargs):

        super().set_assistant_agent(**kwargs)







def _parse_plan_string(plan_str: str) -> List[Dict[str, Any]]:
    """
    Convert the markdown-style plan string produced by PlannerResponse.format()
    back into a list[dict] matching the Subtasks model.

    Handles both the formatted output style (lowercase, no bold) and the raw
    LLM output style (uppercase field names, bold step headers).
    """
    lines = [ln.rstrip() for ln in plan_str.splitlines()]
    subtasks: List[Dict[str, Any]] = []
    current: Dict[str, Any] | None = None
    in_instr = False

    for ln in lines:
        ln_stripped = ln.lstrip()
        ln_lower = ln_stripped.lower()

        # --- step header: "- Step N:" or "- **Step N:**" -------------------
        if ln_lower.startswith("- step") or ln_lower.startswith("- **step"):
            if current:
                subtasks.append(current)
            current = {"bullet_points": []}
            in_instr = False
            continue

        # --- sub-task -------------------------------------------------------
        if ln_lower.startswith("* sub-task:"):
            if current is None:    # defensive
                current = {"bullet_points": []}
            current["sub_task"] = ln_stripped[len("* sub-task:"):].strip()
            in_instr = False
            continue

        # --- agent in charge (formatted style) -----------------------------
        if ln_lower.startswith("* agent in charge:"):
            if current is None:
                current = {"bullet_points": []}
            current["sub_task_agent"] = (
                ln_stripped[len("* agent in charge:"):].strip().lower()
            )
            in_instr = False
            continue

        # --- agent (raw LLM style) -----------------------------------------
        if ln_lower.startswith("* agent:"):
            if current is None:
                current = {"bullet_points": []}
            current["sub_task_agent"] = (
                ln_stripped[len("* agent:"):].strip().lower()
            )
            in_instr = False
            continue

        # --- instructions / bullet points block start ----------------------
        if (ln_lower.startswith("* instructions:")
                or ln_lower.startswith("* bullet points:")
                or ln_lower.startswith("* bullet point:")):
            in_instr = True
            continue

        # --- bullet points --------------------------------------------------
        if in_instr and ln_stripped.startswith("-"):
            current["bullet_points"].append(ln_stripped[1:].strip())

    # add last task if any
    if current:
        subtasks.append(current)

    return subtasks


def save_final_plan(final_context: Dict[str, Any], work_dir: str) -> Path:
    """
    Save `final_context["final_plan"]` as structured JSON at
    <work_dir>/planning/final_plan.json.

    The JSON structure complies with:
        {
            "sub_tasks": [
                {
                    "sub_task": "...",
                    "sub_task_agent": "...",
                    "bullet_points": [...]
                },
                ...
            ]
        }
    """
    planning_dir = work_dir


    if "final_plan" not in final_context:
        raise KeyError('"final_plan" key missing from final_context')

    plan_obj = final_context["final_plan"]

    # ---- Case 1: a Pydantic object ----------------------------------------
    if hasattr(plan_obj, "model_dump"):          # Pydantic v2
        plan_dict = plan_obj.model_dump()
    elif hasattr(plan_obj, "dict"):              # Pydantic v1
        plan_dict = plan_obj.dict()

    # ---- Case 2: already a dict / list ------------------------------------
    elif isinstance(plan_obj, (dict, list)):
        plan_dict = {"sub_tasks": plan_obj} if isinstance(plan_obj, list) else plan_obj

    # ---- Case 3: string (JSON or formatted markdown) ----------------------
    elif isinstance(plan_obj, str):
        # Try JSON first (structured output from planner_response_formatter)
        try:
            parsed = json.loads(plan_obj)
            if isinstance(parsed, dict) and "sub_tasks" in parsed:
                plan_dict = parsed
            elif isinstance(parsed, list):
                plan_dict = {"sub_tasks": parsed}
            else:
                # Valid JSON but unexpected structure, fall back to markdown parse
                plan_dict = {"sub_tasks": _parse_plan_string(plan_obj)}
        except (json.JSONDecodeError, TypeError):
            # Not JSON, try markdown format
            plan_dict = {"sub_tasks": _parse_plan_string(plan_obj)}
    else:
        raise TypeError(
            '"final_plan" must be a PlannerResponse, dict/list, or formatted string'
        )

    # ---- Write the JSON ----------------------------------------------------
    json_path = os.path.join(planning_dir, "final_plan.json")
    with open(json_path, "w", encoding="utf-8") as fp:
        json.dump(plan_dict, fp, ensure_ascii=False, indent=4)

    return json_path
