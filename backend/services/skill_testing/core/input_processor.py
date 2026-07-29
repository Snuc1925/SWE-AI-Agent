from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from services.skill_testing.state import AgentState

def process_initial_input(code: str, stacktrace: Optional[str], message: str, user_input: str) -> AgentState:
    """ Chuan hoa du lieu dau vao thanh state ban dau"""
    return AgentState(
        user_context={
        "code": code,
        "stacktrace": stacktrace or "",
        "message": message,
        "user_input": user_input},
        plan=[],
        history=[],
        reflection=[]
)