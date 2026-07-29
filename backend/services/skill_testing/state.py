from typing import TypedDict, Annotated, List, Optional, Any, Dict
import operator

from pydantic import BaseModel, ConfigDict, Field


class AgentState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    user_context: Dict[str, Any] = Field(default_factory=dict)
    plan: list[str] = Field(default_factory=list)
    history: list[Dict[str, Any]] = Field(default_factory=list)
    reflection: list[str] = Field(default_factory=list)
    
    current_step_idx: int = 0
    current_task: Optional[str] = None
    
    selected_skill: Optional[str] = None
    last_thought: Optional[str] = None
    last_observation: Optional[str] = None
    is_finished: bool = False
    retry_count: int = 0
    final_answer: Optional[str] = None
    
    goal: Optional[str] = None  
    missing_skills_log: list[str] = Field(default_factory=list)
    # exception
    replan_count: int = 0
    max_replans: int = 3
    
    max_total_steps: int = 12
    step_count: int = 0
    