"""
LangChainAdapter — converts universal Skill objects into LangChain StructuredTools.

Key design decisions:
- Constraints are NOT passed to LangChain directly (LangChain has no concept of
  host/resource constraints). Instead, the constraint check runs INSIDE the
  skill_runner wrapper before LangChain ever invokes the underlying function.
- The JSON Schema from SKILL.md is dynamically converted to a Pydantic v2 model
  so LangChain can perform argument validation.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, create_model

from ..models.skill import Skill
from ..core.executor import SkillExecutor
from .base import ISkillAdapter

try:
    from langchain_core.tools import StructuredTool
except ImportError:
    from langchain.tools import StructuredTool  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# Schema → Pydantic model builder
# ─────────────────────────────────────────────────────────────────────────────
_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


def _schema_to_pydantic(skill: Skill) -> type[BaseModel]:
    """Dynamically build a Pydantic BaseModel from a skill's JSON Schema input."""
    props: dict = skill.input.get("properties", {})
    required: list = skill.input.get("required", [])
    fields: Dict[str, Any] = {}

    for field_name, field_schema in props.items():
        py_type = _TYPE_MAP.get(field_schema.get("type", "string"), str)
        desc = field_schema.get("description", "")
        # Required fields: use Ellipsis as default; optional: None
        from pydantic import Field as PField
        if field_name in required:
            fields[field_name] = (py_type, PField(..., description=desc))
        else:
            fields[field_name] = (Optional[py_type], PField(default=None, description=desc))

    model_name = skill.name.replace("-", "_").title().replace("_", "") + "Input"
    return create_model(model_name, **fields)


# ─────────────────────────────────────────────────────────────────────────────
# Adapter
# ─────────────────────────────────────────────────────────────────────────────
class LangChainAdapter(ISkillAdapter):
    """
    Converts Skill → LangChain StructuredTool.

    The constraint checking middleware is embedded INSIDE the tool function,
    which runs before the actual LLM call — LangChain is unaware of constraints.
    """

    def __init__(self, executor: SkillExecutor):
        self.executor = executor

    def to_tool(self, skill: Skill) -> StructuredTool:
        input_schema = _schema_to_pydantic(skill)
        _executor = self.executor   # capture for closure

        def skill_runner(**kwargs) -> dict:
            # Constraints are checked inside executor.run() — no extra middleware needed.
            return _executor.run(skill, kwargs)

        return StructuredTool(
            name=skill.name.replace("-", "_"),
            description=(
                f"{skill.description} "
                f"[category={skill.category}, level={skill.level}]"
            ),
            args_schema=input_schema,
            func=skill_runner,
        )

    def get_all_tools(self) -> List[StructuredTool]:
        return [self.to_tool(skill) for skill in self.executor.registry.all_skills()]
