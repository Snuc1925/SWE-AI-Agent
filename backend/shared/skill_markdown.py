from __future__ import annotations

from typing import Any

import yaml


class SkillMarkdownError(ValueError):
    pass


def parse_skill_markdown(markdown: str) -> tuple[dict[str, Any], str]:
    lines = markdown.strip().splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillMarkdownError("Missing or invalid YAML front matter")
    end_index = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break
    if end_index is None:
        raise SkillMarkdownError("Missing closing YAML front matter delimiter")
    metadata_raw = "\n".join(lines[1:end_index])
    instruction = "\n".join(lines[end_index + 1 :])
    try:
        metadata = yaml.safe_load(metadata_raw) or {}
    except yaml.YAMLError as exc:
        problem = getattr(exc, "problem", None) or str(exc)
        raise SkillMarkdownError(f"Invalid YAML front matter: {problem}") from exc
    if not isinstance(metadata, dict):
        raise SkillMarkdownError("Metadata must be a YAML mapping")
    instruction = instruction.strip()
    if not instruction:
        raise SkillMarkdownError("Instruction content is required")
    return metadata, instruction


def generate_skill_markdown(metadata: dict[str, Any], instruction: str) -> str:
    metadata_yaml = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
    instruction = instruction.strip()
    return f"---\n{metadata_yaml}\n---\n\n{instruction}\n"
