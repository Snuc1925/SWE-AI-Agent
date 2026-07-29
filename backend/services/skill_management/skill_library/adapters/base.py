"""Abstract interface that every framework adapter must implement."""
from abc import ABC, abstractmethod
from typing import Any

from ..models.skill import Skill


class ISkillAdapter(ABC):
    """
    Universal adapter interface.

    Each AI framework (LangChain, LangGraph, CrewAI, …) must implement
    this interface to convert a universal Skill into the framework's native
    callable/tool representation.
    """

    @abstractmethod
    def to_tool(self, skill: Skill) -> Any:
        """Convert a Skill into the framework's native tool object."""

    @abstractmethod
    def get_all_tools(self) -> list:
        """Convert all skills in the attached registry to framework tools."""
