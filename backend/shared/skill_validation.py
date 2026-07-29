from __future__ import annotations

from shared.schemas import SkillLevel


REQUIRED_FIELDS = ["name", "version", "level", "category"]


def validate_skill_format(metadata: dict, instruction: str) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in metadata or not str(metadata[field]).strip():
            errors.append(f"Missing required field: {field}")
    if "level" in metadata and metadata.get("level") not in SkillLevel.__args__:
        errors.append("Level must be 'atomic' or 'composite'")
    if "category" in metadata and not str(metadata.get("category", "")).strip():
        errors.append("Category is required")
    if not instruction or not str(instruction).strip():
        errors.append("Instruction content is required")
    return errors
