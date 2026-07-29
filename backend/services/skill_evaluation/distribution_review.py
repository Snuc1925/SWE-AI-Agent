from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from statistics import quantiles
from typing import Any

from shared.skill_markdown import SkillMarkdownError, parse_skill_markdown


DOMAIN_PATTERN = re.compile(
    r"\b("
    r"frontend|backend|fullstack|react|vue|angular|svelte|javascript|typescript|node|python|java|golang|rust|"
    r"c\+\+|cpp|c#|csharp|dotnet|aspnet|spring|django|flask|fastapi|sql|database|postgres|mysql|redis|orm|"
    r"api|graphql|testing|pytest|jest|debug|debugging|security|devops|docker|kubernetes|terraform|ci/cd|pipeline|"
    r"observability|performance|refactor|migration|build|deploy|cloud|aws|gcp|azure|android|ios|swift|kotlin|"
    r"microservices|sre|playwright|cli|git|github|notebook|mcp"
    r")\b",
    re.IGNORECASE,
)
ACTION_PATTERN = re.compile(
    r"\b("
    r"build|create|design|implement|debug|fix|test|review|refactor|migrate|secure|deploy|monitor|profile|"
    r"plan|document|analyze|generate|optimize|triage|diagnose|validate|instrument|ship|prototype|scaffold"
    r")\b",
    re.IGNORECASE,
)
TRIGGER_PATTERN = re.compile(
    r"\b(use when|use this skill when|when to use|whenever|before opening|if the user|when the user|"
    r"for tasks involving|read before|trigger)\b",
    re.IGNORECASE,
)
BOUNDARY_PATTERN = re.compile(
    r"\b(do not|don't|avoid|skip when|not for|not the right fit|out of scope|unless|only when|never)\b",
    re.IGNORECASE,
)
ANALYSIS_PATTERN = re.compile(
    r"\b(analyze|inspect|understand|research|plan|triage|investigate|reproduce|assess)\b",
    re.IGNORECASE,
)
EXECUTION_PATTERN = re.compile(
    r"\b(implement|write|change|edit|build|run|execute|apply|create|generate|fix|ship)\b",
    re.IGNORECASE,
)
VERIFICATION_PATTERN = re.compile(
    r"\b(test|verify|validate|check|confirm|review|measure|benchmark|assert|observe)\b",
    re.IGNORECASE,
)
ARTIFACT_PATTERN = re.compile(
    r"\b(api|endpoint|component|migration|query|schema|database|service|file|test|pipeline|dockerfile|"
    r"helm|terraform|workflow|issue|pr|repository|sdk|command|script|ui|page|hook|model)\b",
    re.IGNORECASE,
)


@dataclass
class DistributionCriterionResult:
    criterion: str
    score: float
    max_score: float
    explanation: str


@dataclass
class DistributionReviewResult:
    reviewer: str
    total_score: float
    max_score: float
    criteria: list[DistributionCriterionResult] = field(default_factory=list)
    features: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillFeatureSet:
    metadata_present: bool
    features: dict[str, Any]
    metadata_fields: list[str]
    parse_error: str | None = None


def percentile_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0}
    if len(values) == 1:
        single = float(values[0])
        return {"p25": single, "p50": single, "p75": single, "p90": single}
    quartiles = quantiles(values, n=4, method="inclusive")
    deciles = quantiles(values, n=10, method="inclusive")
    return {
        "p25": float(quartiles[0]),
        "p50": float(quartiles[1]),
        "p75": float(quartiles[2]),
        "p90": float(deciles[8]),
    }


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9_+-]+", text))


def _normalize_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _collect_schema_terms(value: Any) -> set[str]:
    terms: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key != "required":
                terms.update(re.findall(r"[a-z0-9_+-]+", key.lower()))
            terms.update(_collect_schema_terms(nested))
    elif isinstance(value, list):
        for nested in value:
            terms.update(_collect_schema_terms(nested))
    elif isinstance(value, str):
        terms.update(re.findall(r"[a-z0-9_+-]+", value.lower()))
    return terms


def _count_schema_fields(value: Any) -> int:
    if isinstance(value, dict):
        count = 0
        for key, nested in value.items():
            if key == "required":
                continue
            count += 1
            count += _count_schema_fields(nested)
        return count
    if isinstance(value, list):
        return sum(_count_schema_fields(item) for item in value)
    return 0


def _count_required_fields(value: Any) -> int:
    if isinstance(value, dict):
        total = 0
        required = value.get("required")
        if isinstance(required, list):
            total += len(required)
        elif required:
            total += 1
        return total + sum(_count_required_fields(item) for item in value.values())
    if isinstance(value, list):
        return sum(_count_required_fields(item) for item in value)
    return 0


def _split_sections(instruction: str) -> list[tuple[str, list[str]]]:
    current_heading = "root"
    current_lines: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    for line in instruction.splitlines():
        heading_match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if heading_match:
            sections.append((current_heading, current_lines))
            current_heading = heading_match.group(1).strip().lower()
            current_lines = []
            continue
        current_lines.append(line)
    sections.append((current_heading, current_lines))
    return sections


def _list_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^[-*+]\s+", stripped):
            items.append(re.sub(r"^[-*+]\s+", "", stripped))
        elif re.match(r"^\d+[.)]\s+", stripped):
            items.append(re.sub(r"^\d+[.)]\s+", "", stripped))
    return items


def _ordered_step_lines(instruction: str, sections: list[tuple[str, list[str]]]) -> list[str]:
    step_lines: list[str] = []
    for line in instruction.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+[.)]\s+", stripped):
            step_lines.append(re.sub(r"^\d+[.)]\s+", "", stripped))
    for heading, lines in sections:
        if re.search(r"\b(process|workflow|steps?|checklist|phases?)\b", heading, re.IGNORECASE):
            for item in _list_items(lines):
                if item not in step_lines:
                    step_lines.append(item)
        if re.search(r"\b(step|phase)\b", heading, re.IGNORECASE) and heading != "root":
            step_lines.append(heading)
    return step_lines


def _fenced_code_blocks(lines: list[str]) -> list[tuple[int, int]]:
    blocks: list[tuple[int, int]] = []
    start: int | None = None
    for idx, line in enumerate(lines):
        if line.strip().startswith("```"):
            if start is None:
                start = idx
            else:
                blocks.append((start, idx))
                start = None
    return blocks


def _clamp_even_score(value: int) -> float:
    return float(max(0, min(10, value)))


def _bucket_score(value: float, thresholds: dict[str, float]) -> int:
    if value < thresholds["p25"]:
        return 2
    if value < thresholds["p50"]:
        return 4
    if value < thresholds["p75"]:
        return 6
    if value < thresholds["p90"]:
        return 8
    return 10


def _percentile_bonus(value: float, thresholds: dict[str, float]) -> int:
    if value >= thresholds["p90"]:
        return 4
    if value >= thresholds["p50"]:
        return 2
    return 0


class DistributionContentReviewer:
    CRITERIA = [
        {
            "id": "name_description_clarity",
            "label": "Distribution-based score for name and description informativeness",
            "max_score": 10.0,
        },
        {
            "id": "input_output_fitness",
            "label": "Distribution-based score for input/output schema completeness and fit",
            "max_score": 10.0,
        },
        {
            "id": "usage_scenarios",
            "label": "Distribution-based score for usage scenarios",
            "max_score": 10.0,
        },
        {
            "id": "step_by_step_process",
            "label": "Distribution-based score for process structure",
            "max_score": 10.0,
        },
        {
            "id": "examples_clarity",
            "label": "Distribution-based score for example coverage and reuse value",
            "max_score": 10.0,
        },
    ]

    NUMERIC_FEATURES = [
        "description_word_count",
        "input_field_count",
        "output_field_count",
        "schema_term_overlap",
        "scenario_count",
        "ordered_step_count",
        "example_count",
    ]

    FEATURE_SCHEMA: dict[str, str] = {
        "has_name": "boolean",
        "has_description": "boolean",
        "description_word_count": "integer",
        "description_has_domain_term": "boolean",
        "description_has_action_verb": "boolean",
        "description_has_trigger_phrase": "boolean",
        "has_input_schema": "boolean",
        "has_output_schema": "boolean",
        "input_field_count": "integer",
        "output_field_count": "integer",
        "input_required_count": "integer",
        "output_required_count": "integer",
        "schema_term_overlap": "float_0_1",
        "scenario_section_present": "boolean",
        "scenario_count": "integer",
        "scenario_with_action_count": "integer",
        "scenario_with_artifact_count": "integer",
        "scenario_with_action_ratio": "float_0_1",
        "scenario_with_artifact_ratio": "float_0_1",
        "has_non_goal_or_boundary": "boolean",
        "ordered_step_count": "integer",
        "actionable_step_count": "integer",
        "actionable_step_ratio": "float_0_1",
        "has_analysis_step": "boolean",
        "has_execution_step": "boolean",
        "has_verification_step": "boolean",
        "example_count": "integer",
        "example_with_code_count": "integer",
        "example_with_context_count": "integer",
        "example_with_output_count": "integer",
        "example_linked_to_rule_count": "integer",
        "example_with_code_ratio": "float_0_1",
        "example_with_context_ratio": "float_0_1",
        "example_with_output_ratio": "float_0_1",
    }

    def __init__(self, extractor: str = "heuristic"):
        self.extractor = extractor
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip()
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

    def extract_features(self, markdown: str) -> SkillFeatureSet:
        if self.extractor == "llm":
            return self._extract_features_llm(markdown)
        return self._extract_features_heuristic(markdown)

    def _extract_features_heuristic(self, markdown: str) -> SkillFeatureSet:
        metadata: dict[str, Any] = {}
        instruction = ""
        parse_error: str | None = None
        try:
            metadata, instruction = parse_skill_markdown(markdown)
        except SkillMarkdownError as exc:
            parse_error = str(exc)
            metadata = {}
            instruction = markdown

        description = _normalize_text(metadata.get("description"))
        input_schema = metadata.get("input")
        output_schema = metadata.get("output")
        sections = _split_sections(instruction)
        instruction_lines = instruction.splitlines()
        step_lines = _ordered_step_lines(instruction, sections)
        code_blocks = _fenced_code_blocks(instruction_lines)

        scenario_lines: list[str] = []
        scenario_section_present = False
        for heading, lines in sections:
            if re.search(r"\b(when to use|use cases?|usage|scenarios?|triggers?)\b", heading, re.IGNORECASE):
                scenario_section_present = True
                scenario_lines.extend(_list_items(lines))
        if not scenario_section_present and TRIGGER_PATTERN.search(description):
            scenario_section_present = True
            scenario_lines = [clause.strip() for clause in re.split(r"[.;]\s+", description) if clause.strip()]

        scenario_count = len(scenario_lines)
        scenario_with_action_count = sum(1 for line in scenario_lines if ACTION_PATTERN.search(line))
        scenario_with_artifact_count = sum(1 for line in scenario_lines if ARTIFACT_PATTERN.search(line))

        actionable_step_count = sum(1 for line in step_lines if ACTION_PATTERN.search(line))
        step_blob = "\n".join(step_lines)

        explicit_example_sections = sum(
            1
            for heading, _ in sections
            if re.search(r"\b(example|examples|sample|demo|worked case)\b", heading, re.IGNORECASE)
        )
        example_count = max(explicit_example_sections, len(code_blocks))
        example_with_code_count = min(example_count, len(code_blocks))

        example_with_context_count = 0
        example_with_output_count = 0
        example_linked_to_rule_count = 0
        for start, end in code_blocks:
            before_lines = [line.strip() for line in instruction_lines[max(0, start - 5) : start] if line.strip()]
            after_lines = [line.strip() for line in instruction_lines[end + 1 : min(len(instruction_lines), end + 6)] if line.strip()]
            nearby = " ".join(before_lines + after_lines)
            if before_lines:
                example_with_context_count += 1
            if re.search(r"\b(output|result|expected|returns?|response|produces?)\b", nearby, re.IGNORECASE):
                example_with_output_count += 1
            if re.search(r"\b(rule|pattern|step|guideline|checklist|process|recommendation)\b", nearby, re.IGNORECASE):
                example_linked_to_rule_count += 1

        body_terms = set(re.findall(r"[a-z0-9_+-]+", f"{description}\n{instruction}".lower()))
        schema_terms = _collect_schema_terms(input_schema) | _collect_schema_terms(output_schema)
        overlap = 0.0
        if schema_terms:
            overlap = len(schema_terms & body_terms) / max(1, len(schema_terms))

        features: dict[str, Any] = {
            "has_name": bool(_normalize_text(metadata.get("name")).strip()),
            "has_description": bool(description.strip()),
            "description_word_count": _word_count(description),
            "description_has_domain_term": bool(DOMAIN_PATTERN.search(description)),
            "description_has_action_verb": bool(ACTION_PATTERN.search(description)),
            "description_has_trigger_phrase": bool(TRIGGER_PATTERN.search(description)),
            "has_input_schema": bool(input_schema not in (None, "", [], {})),
            "has_output_schema": bool(output_schema not in (None, "", [], {})),
            "input_field_count": _count_schema_fields(input_schema),
            "output_field_count": _count_schema_fields(output_schema),
            "input_required_count": _count_required_fields(input_schema),
            "output_required_count": _count_required_fields(output_schema),
            "schema_term_overlap": round(overlap, 4),
            "scenario_section_present": scenario_section_present,
            "scenario_count": scenario_count,
            "scenario_with_action_count": scenario_with_action_count,
            "scenario_with_artifact_count": scenario_with_artifact_count,
            "scenario_with_action_ratio": round(
                scenario_with_action_count / scenario_count, 4
            )
            if scenario_count
            else 0.0,
            "scenario_with_artifact_ratio": round(
                scenario_with_artifact_count / scenario_count, 4
            )
            if scenario_count
            else 0.0,
            "has_non_goal_or_boundary": bool(
                BOUNDARY_PATTERN.search(description) or BOUNDARY_PATTERN.search(instruction)
            ),
            "ordered_step_count": len(step_lines),
            "actionable_step_count": actionable_step_count,
            "actionable_step_ratio": round(
                actionable_step_count / len(step_lines), 4
            )
            if step_lines
            else 0.0,
            "has_analysis_step": bool(ANALYSIS_PATTERN.search(step_blob)),
            "has_execution_step": bool(EXECUTION_PATTERN.search(step_blob)),
            "has_verification_step": bool(VERIFICATION_PATTERN.search(step_blob)),
            "example_count": example_count,
            "example_with_code_count": example_with_code_count,
            "example_with_context_count": example_with_context_count,
            "example_with_output_count": example_with_output_count,
            "example_linked_to_rule_count": example_linked_to_rule_count,
            "example_with_code_ratio": round(example_with_code_count / example_count, 4)
            if example_count
            else 0.0,
            "example_with_context_ratio": round(example_with_context_count / example_count, 4)
            if example_count
            else 0.0,
            "example_with_output_ratio": round(example_with_output_count / example_count, 4)
            if example_count
            else 0.0,
        }

        return SkillFeatureSet(
            metadata_present=parse_error is None,
            features=features,
            metadata_fields=sorted(str(key) for key in metadata),
            parse_error=parse_error,
        )

    def _extract_features_llm(self, markdown: str) -> SkillFeatureSet:
        metadata: dict[str, Any] = {}
        parse_error: str | None = None
        try:
            metadata, _ = parse_skill_markdown(markdown)
        except SkillMarkdownError as exc:
            parse_error = str(exc)
            metadata = {}

        if not self.api_key:
            raise RuntimeError("Missing DEEPSEEK_API_KEY for LLM feature extraction")

        prompt = self._build_feature_extraction_prompt(markdown)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You extract structured features from SKILL.md files. "
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
            with urllib.request.urlopen(request, timeout=180) as response:
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

        data = json.loads(raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
        raw_features = data.get("features", {})
        if not isinstance(raw_features, dict):
            raise RuntimeError(f"Unexpected feature payload from DeepSeek: {data}")
        features = self._coerce_feature_payload(raw_features)

        return SkillFeatureSet(
            metadata_present=parse_error is None,
            features=features,
            metadata_fields=sorted(str(key) for key in metadata),
            parse_error=parse_error,
        )

    def _coerce_feature_payload(self, raw_features: dict[str, Any]) -> dict[str, Any]:
        features: dict[str, Any] = {}
        for feature_name, feature_type in self.FEATURE_SCHEMA.items():
            value = raw_features.get(feature_name)
            if feature_type == "boolean":
                features[feature_name] = bool(value)
            elif feature_type == "integer":
                try:
                    coerced = int(value)
                except (TypeError, ValueError):
                    coerced = 0
                features[feature_name] = max(0, coerced)
            elif feature_type == "float_0_1":
                try:
                    coerced = float(value)
                except (TypeError, ValueError):
                    coerced = 0.0
                features[feature_name] = round(max(0.0, min(1.0, coerced)), 4)
        return features

    def _build_feature_extraction_prompt(self, markdown: str) -> str:
        feature_lines = "\n".join(
            f'- "{feature_name}": {feature_type}'
            for feature_name, feature_type in self.FEATURE_SCHEMA.items()
        )
        return f"""
Extract measurable features from the following SKILL.md document.

Important rules:
- Do not score the document.
- Do not summarize the document.
- Return JSON only.
- Use only observable evidence from the document.
- Count conservatively. If unsure, choose the lower count.
- Ratios must be between 0 and 1.
- For ratio fields, compute them from the corresponding counts when possible.
- A "scenario" means a concrete situation where the skill should be used.
- An "ordered step" means a numbered step, named phase, checklist step, or explicit process step the AI can follow.
- An "example" means an explicit example section, worked example, sample, or code/command block that demonstrates usage.
- "action" means a concrete task verb such as build, test, debug, deploy, refactor, review, or implement.
- "artifact" means a concrete software artifact such as API, component, migration, database, file, command, workflow, schema, or test.
- "boundary/non-goal" means text that says when not to use the skill, what to avoid, what is out of scope, or a strict limitation.

Return JSON in exactly this shape:
{{
  "features": {{
    "has_name": true,
    "has_description": true,
    "description_word_count": 0,
    "description_has_domain_term": false,
    "description_has_action_verb": false,
    "description_has_trigger_phrase": false,
    "has_input_schema": false,
    "has_output_schema": false,
    "input_field_count": 0,
    "output_field_count": 0,
    "input_required_count": 0,
    "output_required_count": 0,
    "schema_term_overlap": 0.0,
    "scenario_section_present": false,
    "scenario_count": 0,
    "scenario_with_action_count": 0,
    "scenario_with_artifact_count": 0,
    "scenario_with_action_ratio": 0.0,
    "scenario_with_artifact_ratio": 0.0,
    "has_non_goal_or_boundary": false,
    "ordered_step_count": 0,
    "actionable_step_count": 0,
    "actionable_step_ratio": 0.0,
    "has_analysis_step": false,
    "has_execution_step": false,
    "has_verification_step": false,
    "example_count": 0,
    "example_with_code_count": 0,
    "example_with_context_count": 0,
    "example_with_output_count": 0,
    "example_linked_to_rule_count": 0,
    "example_with_code_ratio": 0.0,
    "example_with_context_ratio": 0.0,
    "example_with_output_ratio": 0.0
  }}
}}

Feature types:
{feature_lines}

SKILL.md content:
```md
{markdown}
```
""".strip()

    def build_calibration(self, feature_sets: list[SkillFeatureSet]) -> dict[str, dict[str, float]]:
        calibration: dict[str, dict[str, float]] = {}
        for feature_name in self.NUMERIC_FEATURES:
            values = [float(item.features.get(feature_name, 0.0)) for item in feature_sets]
            calibration[feature_name] = percentile_summary(values)
        return calibration

    def review(
        self,
        *,
        feature_set: SkillFeatureSet,
        calibration: dict[str, dict[str, float]],
    ) -> DistributionReviewResult:
        features = feature_set.features
        criteria: list[DistributionCriterionResult] = []

        def add(criterion: str, score: int, explanation: str) -> None:
            criteria.append(
                DistributionCriterionResult(
                    criterion=criterion,
                    score=_clamp_even_score(score),
                    max_score=10.0,
                    explanation=explanation,
                )
            )

        if not features["has_name"] or not features["has_description"]:
            add(
                "name_description_clarity",
                0,
                "Missing required name/description metadata, so the criterion is forced to 0.",
            )
        else:
            score = _bucket_score(
                float(features["description_word_count"]),
                calibration["description_word_count"],
            )
            deductions = []
            if not features["description_has_domain_term"]:
                score -= 2
                deductions.append("missing domain-specific term")
            if not features["description_has_action_verb"]:
                score -= 2
                deductions.append("missing action verb")
            if not features["description_has_trigger_phrase"]:
                score -= 2
                deductions.append("missing trigger phrase")
            add(
                "name_description_clarity",
                score,
                (
                    f"description_word_count={features['description_word_count']} vs corpus percentiles "
                    f"{calibration['description_word_count']}; deductions={deductions or ['none']}."
                ),
            )

        has_input = bool(features["has_input_schema"])
        has_output = bool(features["has_output_schema"])
        if not has_input and not has_output:
            add(
                "input_output_fitness",
                0,
                "Neither input nor output schema is present, so the criterion is forced to 0.",
            )
        else:
            score = 4 if has_input and has_output else 4
            if has_input and has_output:
                score += _percentile_bonus(
                    float(features["input_field_count"]),
                    calibration["input_field_count"],
                )
                score += _percentile_bonus(
                    float(features["output_field_count"]),
                    calibration["output_field_count"],
                )
                if features["input_required_count"] > 0 or features["output_required_count"] > 0:
                    score += 1
                if float(features["schema_term_overlap"]) >= calibration["schema_term_overlap"]["p75"]:
                    score += 1
            add(
                "input_output_fitness",
                score if has_input and has_output else min(score, 4),
                (
                    f"input_fields={features['input_field_count']}, output_fields={features['output_field_count']}, "
                    f"required=({features['input_required_count']},{features['output_required_count']}), "
                    f"schema_term_overlap={features['schema_term_overlap']}."
                ),
            )

        if not features["scenario_section_present"]:
            add(
                "usage_scenarios",
                0,
                "No trigger/usage-scenario section or equivalent trigger signal was detected.",
            )
        else:
            score = _bucket_score(float(features["scenario_count"]), calibration["scenario_count"])
            adjustments = []
            if float(features["scenario_with_action_ratio"]) < 0.5:
                score -= 2
                adjustments.append("action ratio below 0.5")
            if float(features["scenario_with_artifact_ratio"]) < 0.5:
                score -= 2
                adjustments.append("artifact ratio below 0.5")
            if features["has_non_goal_or_boundary"]:
                score += 2
                adjustments.append("has boundary/non-goal")
            add(
                "usage_scenarios",
                score,
                (
                    f"scenario_count={features['scenario_count']} vs corpus percentiles "
                    f"{calibration['scenario_count']}; adjustments={adjustments or ['none']}."
                ),
            )

        ordered_steps = int(features["ordered_step_count"])
        if ordered_steps == 0:
            add(
                "step_by_step_process",
                0,
                "No ordered/process-like steps were detected, so the criterion is forced to 0.",
            )
        else:
            score = _bucket_score(float(ordered_steps), calibration["ordered_step_count"])
            if ordered_steps < 3:
                score = min(score, 4)
            adjustments = []
            if float(features["actionable_step_ratio"]) < 0.6:
                score -= 2
                adjustments.append("actionable ratio below 0.6")
            if not features["has_analysis_step"]:
                score -= 2
                adjustments.append("missing analysis step")
            if not features["has_execution_step"]:
                score -= 2
                adjustments.append("missing execution step")
            if not features["has_verification_step"]:
                score -= 2
                adjustments.append("missing verification step")
            add(
                "step_by_step_process",
                score,
                (
                    f"ordered_step_count={ordered_steps} vs corpus percentiles "
                    f"{calibration['ordered_step_count']}; adjustments={adjustments or ['none']}."
                ),
            )

        example_count = int(features["example_count"])
        if example_count == 0:
            add(
                "examples_clarity",
                0,
                "No explicit example or code block was detected, so the criterion is forced to 0.",
            )
        else:
            score = min(
                4,
                _bucket_score(float(example_count), calibration["example_count"]),
            )
            adjustments = []
            if float(features["example_with_context_ratio"]) >= 0.5:
                score += 2
                adjustments.append("context ratio >= 0.5")
            if float(features["example_with_output_ratio"]) >= 0.5:
                score += 2
                adjustments.append("output ratio >= 0.5")
            if float(features["example_with_code_ratio"]) >= 0.5:
                score += 2
                adjustments.append("code ratio >= 0.5")
            if int(features["example_linked_to_rule_count"]) >= 1:
                score += 2
                adjustments.append("linked to rule/process")
            add(
                "examples_clarity",
                score,
                (
                    f"example_count={example_count} vs corpus percentiles "
                    f"{calibration['example_count']}; adjustments={adjustments or ['none']}."
                ),
            )

        total = round(sum(item.score for item in criteria), 2)
        return DistributionReviewResult(
            reviewer=f"distribution-v1-{self.extractor}",
            total_score=total,
            max_score=50.0,
            criteria=criteria,
            features=features,
        )
