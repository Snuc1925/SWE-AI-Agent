from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.skill_markdown import SkillMarkdownError, parse_skill_markdown


ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"
FORMAT_CRITERIA_FILE = Path(__file__).parent / "config" / "format_scoring.xml"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file(ENV_FILE)


@dataclass
class FormatCriterionResult:
    criterion: str
    score: int
    max_score: int
    explanation: str


@dataclass
class FormatReviewResult:
    score: int
    max_score: int
    passed: bool
    threshold: int
    frontmatter_valid: bool
    errors: list[str] = field(default_factory=list)
    criteria: list[FormatCriterionResult] = field(default_factory=list)


@dataclass
class ContentCriterionResult:
    criterion: str
    score: float
    max_score: float
    explanation: str


@dataclass
class ContentReviewResult:
    model: str
    total_score: float
    max_score: float
    criteria: list[ContentCriterionResult] = field(default_factory=list)


class FormatReviewer:
    def __init__(self, criteria_file: Path = FORMAT_CRITERIA_FILE):
        self.criteria_file = criteria_file

    def review(self, markdown: str) -> FormatReviewResult:
        metadata: dict[str, Any] = {}
        errors: list[str] = []
        frontmatter_valid = True

        try:
            metadata, _ = parse_skill_markdown(markdown)
        except SkillMarkdownError as exc:
            frontmatter_valid = False
            errors.append(str(exc))

        if not self.criteria_file.exists():
            return FormatReviewResult(
                score=0,
                max_score=100,
                passed=False,
                threshold=70,
                frontmatter_valid=frontmatter_valid,
                errors=errors or ["Format criteria file not found"],
            )

        root = ET.parse(self.criteria_file).getroot()
        threshold = int(root.get("threshold", "70"))
        criteria: list[FormatCriterionResult] = []
        total_score = 0
        total_max = 0

        for item in root.findall("Criterion"):
            rule = item.get("rule", "exists")
            criterion_id = item.get("id", "unknown")
            description = (item.findtext("Description") or criterion_id).strip()
            path = item.find("Field").get("path", "") if item.find("Field") is not None else ""
            value = metadata.get(path) if path else None

            if rule == "exists":
                max_points = int(item.get("points", "0"))
                score = max_points if _is_present(value) else 0
                explanation = (
                    description if score else f'Missing or empty "{path}" in front matter'
                )
            elif rule == "input_with_required":
                full_points = int(item.get("full_points", "0"))
                partial_points = int(item.get("partial_points", "0"))
                max_points = full_points
                if not _is_present(value):
                    score = 0
                    explanation = 'Missing or empty "input" in front matter'
                elif _contains_required_key(value):
                    score = full_points
                    explanation = 'Input exists and declares at least one nested "required" field'
                else:
                    score = partial_points
                    explanation = 'Input exists but no nested "required" field was found'
            else:
                max_points = int(item.get("points", "0"))
                score = 0
                explanation = f"Unsupported rule: {rule}"

            criteria.append(
                FormatCriterionResult(
                    criterion=criterion_id,
                    score=score,
                    max_score=max_points,
                    explanation=explanation,
                )
            )
            total_score += score
            total_max += max_points

        return FormatReviewResult(
            score=total_score,
            max_score=total_max,
            passed=frontmatter_valid and total_score >= threshold,
            threshold=threshold,
            frontmatter_valid=frontmatter_valid,
            errors=errors,
            criteria=criteria,
        )


class LLMContentReviewer:
    CRITERIA = [
        {
            "id": "name_description_clarity",
            "label": 'Fields "name" and "description" are present and sufficiently informative',
            "max_score": 10,
            "checks": [
                'The "name" field is present and non-empty',
                'The "description" field is present and non-empty',
                "The description states the main task or capability of the skill",
                "The description names the technical domain, artifact, or environment the skill applies to",
                "The description includes at least one trigger, constraint, or intended usage signal",
            ],
        },
        {
            "id": "input_output_fitness",
            "label": 'Input and output schema are present and structurally fit the skill intent',
            "max_score": 10,
            "checks": [
                'An "input" schema is present in front matter',
                'An "output" schema is present in front matter',
                'The input schema defines concrete fields, types, or required keys rather than being empty/generic',
                'The output schema defines a concrete result structure rather than being empty/generic',
                "The input/output schemas match what the body of the skill says the skill does",
            ],
        },
        {
            "id": "usage_scenarios",
            "label": "The skill states concrete situations where it should be used",
            "max_score": 10,
            "checks": [
                'The document contains an explicit "when to use", "use this skill when", or equivalent trigger section',
                "It provides at least two distinct usage scenarios",
                "At least one scenario names a concrete task, bug, workflow, or artifact",
                "The scenarios are specific enough to distinguish this skill from a generic domain reference",
                "The document includes at least one boundary, non-goal, or signal for when this skill is not the right fit",
            ],
        },
        {
            "id": "step_by_step_process",
            "label": "The skill provides an explicit process the AI can follow",
            "max_score": 10,
            "checks": [
                "The document contains at least three ordered steps or phases",
                "The steps are action-oriented and tell the AI what to do",
                "The process covers both analysis/planning and execution",
                "The process includes at least one verification, validation, or completion step",
                "The steps are connected as a usable workflow rather than a loose list of tips",
            ],
        },
        {
            "id": "examples_clarity",
            "label": "Examples contain enough structure and specificity to be reusable",
            "max_score": 10,
            "checks": [
                "The document contains at least one explicit example or worked case",
                "At least one example includes concrete input/context or a starting situation",
                "At least one example includes concrete output/result, command, code, or expected behavior",
                "At least one example is tied to a nearby rule, step, or recommendation in the document",
                "The example uses domain-specific details rather than only abstract placeholders",
            ],
        },
    ]

    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip()
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

    def review(self, markdown: str) -> ContentReviewResult:
        if not self.api_key:
            raise RuntimeError("Missing DEEPSEEK_API_KEY for content evaluation")

        prompt = self._build_prompt(markdown)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict reviewer of AI skill markdown files. "
                        "Return valid JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DeepSeek API returned HTTP {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach DeepSeek API: {exc}") from exc

        try:
            raw = response_data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected DeepSeek response: {response_data}") from exc
        data = _parse_json_block(raw)

        criteria_results: list[ContentCriterionResult] = []
        total_score = 0.0
        total_max = 0.0
        result_items = data.get("criteria", [])
        by_id = {item.get("criterion"): item for item in result_items if isinstance(item, dict)}

        for criterion in self.CRITERIA:
            item = by_id.get(criterion["id"], {})
            score = self._normalize_criterion_score(item, criterion)
            score = max(0.0, min(score, float(criterion["max_score"])))
            explanation = str(item.get("explanation", "No explanation provided")).strip()
            criteria_results.append(
                ContentCriterionResult(
                    criterion=criterion["id"],
                    score=score,
                    max_score=float(criterion["max_score"]),
                    explanation=explanation,
                )
            )
            total_score += score
            total_max += float(criterion["max_score"])

        return ContentReviewResult(
            model=self.model,
            total_score=round(total_score, 2),
            max_score=round(total_max, 2),
            criteria=criteria_results,
        )

    def _normalize_criterion_score(self, item: dict[str, Any], criterion: dict[str, Any]) -> float:
        checks = criterion.get("checks", [])
        max_score = float(criterion["max_score"])
        if checks:
            expected_count = len(checks)
            raw_count = item.get("passed_check_count")
            try:
                passed_count = int(raw_count)
            except (TypeError, ValueError):
                passed_count = -1
            if 0 <= passed_count <= expected_count:
                return round((passed_count / expected_count) * max_score, 2)

        raw_score = item.get("score", 0)
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 0.0

        # Keep legacy compatibility, but force scores onto the discrete rubric scale.
        return float(int(round(score / 2.0)) * 2)

    def _build_prompt(self, markdown: str) -> str:
        rubric_blocks = []
        for item in self.CRITERIA:
            check_lines = "\n".join(
                f'  - {index}. {check}'
                for index, check in enumerate(item.get("checks", []), start=1)
            )
            rubric_blocks.append(
                "\n".join(
                    [
                        f'- "{item["id"]}": {item["label"]}',
                        "  Scoring rule: 2 points for each satisfied check, 0 points otherwise.",
                        "  Allowed scores only: 0, 2, 4, 6, 8, 10.",
                        "  Checks:",
                        check_lines,
                    ]
                )
            )
        rubric_text = "\n".join(rubric_blocks)
        return f"""
Review the following SKILL.md content.

Score each criterion independently using only observable evidence from the document.
Do not use subjective phrases such as "pretty clear" or "somewhat specific" without tying them to a checklist item.
For each criterion:
- evaluate the 5 checks one by one
- count how many checks pass
- score = passed_check_count * 2
- use only these scores: 0, 2, 4, 6, 8, 10
- in the explanation, mention which checks passed and which failed

Criteria:
{rubric_text}

Return JSON in exactly this shape:
{{
  "criteria": [
    {{
      "criterion": "name_description_clarity",
      "passed_check_count": 0,
      "score": 0,
      "explanation": "Passed: ... Failed: ..."
    }}
  ]
}}

SKILL.md content:
```md
{markdown}
```
""".strip()


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def _contains_required_key(value: Any) -> bool:
    if isinstance(value, dict):
        if "required" in value:
            return True
        return any(_contains_required_key(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_required_key(v) for v in value)
    return False


def _parse_json_block(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)
