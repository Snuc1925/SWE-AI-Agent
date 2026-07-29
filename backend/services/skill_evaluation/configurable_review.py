from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from statistics import quantiles
from typing import Any

from shared.config import get_skills_dir
from shared.skill_markdown import SkillMarkdownError, parse_skill_markdown


ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"
BUNDLED_CONFIG_DIR = Path(__file__).parent / "config" / "evaluation_profiles"
CONFIG_DIR = Path(
    os.getenv(
        "EVALUATION_PROFILE_DIR",
        str(BUNDLED_CONFIG_DIR),
    )
)
DEFAULT_PROFILE_ID = "default"
DEFAULT_PROFILE_PATH = CONFIG_DIR / "default_distribution.json"
FEATURE_CACHE_PATH = Path(
    os.getenv(
        "EVALUATION_FEATURE_CACHE_PATH",
        str(CONFIG_DIR.parent / "evaluation_feature_cache.json"),
    )
)

logger = logging.getLogger("skill_evaluation.configurable_review")


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
class ConfigurableCriterionResult:
    criterion: str
    label: str
    score: float
    max_score: float
    explanation: str
    applied_steps: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ConfigurableReviewResult:
    model: str
    profile_id: str
    profile_hash: str
    total_score: float
    max_score: float
    criteria: list[ConfigurableCriterionResult] = field(default_factory=list)
    features: dict[str, Any] = field(default_factory=dict)
    feature_evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    calibration: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class FeatureSet:
    features: dict[str, Any]
    metadata_fields: list[str]
    evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    parse_error: str | None = None


_FEATURE_CACHE: dict[tuple[str, str], FeatureSet] = {}
_PERSISTENT_FEATURE_CACHE: dict[str, dict[str, Any]] | None = None


def source_hash(markdown: str) -> str:
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def profile_hash(profile: dict[str, Any]) -> str:
    hashed_profile = json.loads(json.dumps(profile, ensure_ascii=False))
    if isinstance(hashed_profile.get("llm"), dict):
        hashed_profile["llm"]["api_key"] = ""
    payload = json.dumps(hashed_profile, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def feature_definition_hash(feature: dict[str, Any]) -> str:
    payload = json.dumps(feature, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_persistent_feature_cache() -> dict[str, dict[str, Any]]:
    global _PERSISTENT_FEATURE_CACHE
    if _PERSISTENT_FEATURE_CACHE is not None:
        return _PERSISTENT_FEATURE_CACHE
    if not FEATURE_CACHE_PATH.exists():
        _PERSISTENT_FEATURE_CACHE = {}
        return _PERSISTENT_FEATURE_CACHE
    try:
        data = json.loads(FEATURE_CACHE_PATH.read_text(encoding="utf-8"))
        _PERSISTENT_FEATURE_CACHE = data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Could not read feature cache %s: %s", FEATURE_CACHE_PATH, exc)
        _PERSISTENT_FEATURE_CACHE = {}
    return _PERSISTENT_FEATURE_CACHE


def _save_persistent_feature_cache() -> None:
    if _PERSISTENT_FEATURE_CACHE is None:
        return
    try:
        FEATURE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FEATURE_CACHE_PATH.write_text(
            json.dumps(_PERSISTENT_FEATURE_CACHE, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("Could not write feature cache %s: %s", FEATURE_CACHE_PATH, exc)


def normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(profile, ensure_ascii=False))
    normalized.setdefault(
        "llm",
        {
            "provider": "openai-compatible",
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            "api_key": "",
        },
    )
    for feature in normalized.get("features", []):
        if isinstance(feature, dict):
            feature.pop("description", None)
    normalized.setdefault("format_features", _default_format_features())
    normalized.setdefault("format_criteria", _default_format_criteria())
    return normalized


def _default_format_features() -> list[dict[str, Any]]:
    return [
        {"id": "format_frontmatter_valid", "type": "boolean", "extractor": "parser"},
        {"id": "format_has_name", "type": "boolean", "extractor": "parser"},
        {"id": "format_has_description", "type": "boolean", "extractor": "parser"},
        {"id": "format_has_input_schema", "type": "boolean", "extractor": "parser"},
        {"id": "format_input_has_required", "type": "boolean", "extractor": "parser"},
        {"id": "format_has_output_schema", "type": "boolean", "extractor": "parser"},
    ]


def _default_format_criteria() -> list[dict[str, Any]]:
    return [
        {
            "id": "format_name",
            "label": "Name field",
            "max_score": 25,
            "steps": [
                {
                    "id": "name_exists",
                    "description": "Front matter has a non-empty name field",
                    "condition": {"feature": "format_has_name", "operator": "eq", "value": True},
                    "action": "add",
                    "value": 25,
                }
            ],
        },
        {
            "id": "format_description",
            "label": "Description field",
            "max_score": 25,
            "steps": [
                {
                    "id": "description_exists",
                    "description": "Front matter has a non-empty description field",
                    "condition": {"feature": "format_has_description", "operator": "eq", "value": True},
                    "action": "add",
                    "value": 25,
                }
            ],
        },
        {
            "id": "format_input",
            "label": "Input schema",
            "max_score": 25,
            "steps": [
                {
                    "id": "input_exists_partial",
                    "description": "Front matter has a non-empty input schema",
                    "condition": {"feature": "format_has_input_schema", "operator": "eq", "value": True},
                    "action": "add",
                    "value": 15,
                },
                {
                    "id": "input_required_bonus",
                    "description": "Input schema declares at least one required field",
                    "condition": {"feature": "format_input_has_required", "operator": "eq", "value": True},
                    "action": "add",
                    "value": 10,
                },
            ],
        },
        {
            "id": "format_output",
            "label": "Output schema",
            "max_score": 25,
            "steps": [
                {
                    "id": "output_exists",
                    "description": "Front matter has a non-empty output schema",
                    "condition": {"feature": "format_has_output_schema", "operator": "eq", "value": True},
                    "action": "add",
                    "value": 25,
                }
            ],
        },
    ]


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


def load_profile(profile_id: str = DEFAULT_PROFILE_ID) -> dict[str, Any]:
    if profile_id != DEFAULT_PROFILE_ID:
        raise ValueError(f"Unsupported profile_id: {profile_id}")
    if not DEFAULT_PROFILE_PATH.exists():
        bundled = BUNDLED_CONFIG_DIR / "default_distribution.json"
        if bundled.exists() and bundled != DEFAULT_PROFILE_PATH:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            DEFAULT_PROFILE_PATH.write_text(bundled.read_text(encoding="utf-8"), encoding="utf-8")
    if not DEFAULT_PROFILE_PATH.exists():
        raise FileNotFoundError(f"Evaluation profile not found: {DEFAULT_PROFILE_PATH}")
    return normalize_profile(json.loads(DEFAULT_PROFILE_PATH.read_text(encoding="utf-8")))


def save_profile(profile: dict[str, Any], profile_id: str = DEFAULT_PROFILE_ID) -> dict[str, Any]:
    if profile_id != DEFAULT_PROFILE_ID:
        raise ValueError(f"Unsupported profile_id: {profile_id}")
    profile = normalize_profile(profile)
    validate_profile(profile)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_PROFILE_PATH.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _FEATURE_CACHE.clear()
    return profile


def validate_profile(profile: dict[str, Any]) -> None:
    if not isinstance(profile, dict):
        raise ValueError("Profile must be a JSON object")
    features = profile.get("features")
    criteria = profile.get("criteria")
    bucket = profile.get("bucket_scheme")
    if not isinstance(features, list) or not features:
        raise ValueError("Profile must define at least one feature")
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("Profile must define at least one criterion")
    if not isinstance(bucket, dict):
        raise ValueError("Profile must define bucket_scheme")
    llm = profile.get("llm", {})
    if llm and not isinstance(llm, dict):
        raise ValueError("Profile llm must be an object")
    if isinstance(llm, dict):
        for key in ["provider", "base_url", "model", "api_key"]:
            if key in llm and llm[key] is not None and not isinstance(llm[key], str):
                raise ValueError(f"Profile llm.{key} must be a string")

    feature_ids: set[str] = set()
    for feature in [*features, *profile.get("format_features", [])]:
        if not isinstance(feature, dict):
            raise ValueError("Each feature must be an object")
        feature_id = str(feature.get("id", "")).strip()
        feature_type = feature.get("type")
        if not feature_id:
            raise ValueError("Feature id is required")
        if feature_id in feature_ids:
            raise ValueError(f"Duplicate feature id: {feature_id}")
        if feature_type not in {"boolean", "integer"}:
            raise ValueError(f"Unsupported feature type for {feature_id}: {feature_type}")
        feature_ids.add(feature_id)

    for key in ["p25", "p50", "p75", "p90", "above"]:
        if key not in bucket:
            raise ValueError(f"bucket_scheme missing {key}")
        _as_float(bucket[key])

    for criterion in [*criteria, *profile.get("format_criteria", [])]:
        if not isinstance(criterion, dict):
            raise ValueError("Each criterion must be an object")
        if not str(criterion.get("id", "")).strip():
            raise ValueError("Criterion id is required")
        _as_float(criterion.get("max_score", 10))
        steps = criterion.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError(f"Criterion {criterion.get('id')} steps must be a list")
        for step in steps:
            _validate_step(step, feature_ids)


def _validate_step(step: Any, feature_ids: set[str]) -> None:
    if not isinstance(step, dict):
        raise ValueError("Rule step must be an object")
    action = step.get("action")
    if action not in {"force_score", "set_score_from_bucket", "add", "subtract", "cap_max", "set_baseline"}:
        raise ValueError(f"Unsupported rule action: {action}")
    if "condition" in step:
        _validate_condition(step["condition"], feature_ids)
    feature = step.get("feature")
    if feature and feature not in feature_ids:
        raise ValueError(f"Rule step references unknown feature: {feature}")
    source = step.get("source")
    if source and source != "percentile_bonus":
        raise ValueError(f"Unsupported rule step source: {source}")


def _validate_condition(condition: Any, feature_ids: set[str]) -> None:
    if not isinstance(condition, dict):
        raise ValueError("Condition must be an object")
    if "all" in condition:
        items = condition["all"]
        if not isinstance(items, list) or not items:
            raise ValueError("Condition all must be a non-empty list")
        for item in items:
            _validate_condition(item, feature_ids)
        return
    if "any" in condition:
        items = condition["any"]
        if not isinstance(items, list) or not items:
            raise ValueError("Condition any must be a non-empty list")
        for item in items:
            _validate_condition(item, feature_ids)
        return
    if "not" in condition:
        _validate_condition(condition["not"], feature_ids)
        return
    feature = condition.get("feature")
    operator = condition.get("operator")
    if feature not in feature_ids:
        raise ValueError(f"Condition references unknown feature: {feature}")
    if operator not in {"exists", "missing", "eq", "neq", "lt", "lte", "gt", "gte"}:
        raise ValueError(f"Unsupported condition operator: {operator}")


class ConfigurableDistributionReviewer:
    def __init__(self, profile: dict[str, Any] | None = None):
        self.profile = profile or load_profile()
        validate_profile(self.profile)
        self.profile_id = str(self.profile.get("id", DEFAULT_PROFILE_ID))
        self.profile_hash = profile_hash(self.profile)
        llm = self.profile.get("llm", {})
        self.provider = str(llm.get("provider") or "openai-compatible").strip()
        self.api_key = str(llm.get("api_key") or os.getenv("DEEPSEEK_API_KEY", "")).strip()
        self.base_url = str(llm.get("base_url") or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")).strip()
        self.model = str(llm.get("model") or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")).strip()

    def review_markdown(self, markdown: str) -> ConfigurableReviewResult:
        corpus_feature_sets = self.extract_corpus_features()
        calibration = self.build_calibration(corpus_feature_sets)
        feature_set = self.extract_features(markdown)
        return self.review(feature_set=feature_set, calibration=calibration)

    def review_format_markdown(self, markdown: str) -> ConfigurableReviewResult:
        feature_set = self.extract_format_features(markdown)
        return self.review(feature_set=feature_set, calibration={}, criteria_key="format_criteria")

    def extract_corpus_features(self) -> list[FeatureSet]:
        skills_dir = get_skills_dir()
        feature_sets: list[FeatureSet] = []
        if not skills_dir.exists():
            return feature_sets
        for skill_path in sorted(skills_dir.rglob("SKILL.md")):
            if skill_path.is_file():
                try:
                    markdown = skill_path.read_text(encoding="utf-8")
                    feature_sets.append(self.extract_features(markdown))
                except Exception as exc:
                    logger.warning("Skipping corpus skill during calibration: path=%s error=%s", skill_path, exc)
        return feature_sets

    def extract_features(self, markdown: str) -> FeatureSet:
        cache_key = (self.profile_hash, source_hash(markdown))
        cached = _FEATURE_CACHE.get(cache_key)
        if cached is not None:
            return cached

        feature_set, _ = self.extract_features_with_sync_log(markdown)
        _FEATURE_CACHE[cache_key] = feature_set
        return feature_set

    def extract_features_with_sync_log(self, markdown: str, force: bool = False) -> tuple[FeatureSet, list[dict[str, Any]]]:
        markdown_hash = source_hash(markdown)
        sync_log: list[dict[str, Any]] = []

        metadata_fields: list[str] = []
        parse_error: str | None = None
        try:
            metadata, _ = parse_skill_markdown(markdown)
            metadata_fields = sorted(str(key) for key in metadata)
        except SkillMarkdownError as exc:
            parse_error = str(exc)

        logger.info(
            "Feature sync started: profile=%s hash=%s source=%s features=%d force=%s",
            self.profile_id,
            self.profile_hash[:12],
            markdown_hash[:12],
            len(self.profile["features"]),
            force,
        )
        sync_log.append(
            {
                "level": "info",
                "message": "Feature sync started",
                "profile_hash": self.profile_hash,
                "source_sha256": markdown_hash,
                "feature_count": len(self.profile["features"]),
            }
        )

        persistent_cache = _load_persistent_feature_cache()
        raw_features: dict[str, Any] = {}
        missing_features: list[dict[str, Any]] = []
        for feature in self.profile["features"]:
            feature_id = str(feature["id"])
            feature_key = self._feature_cache_key(markdown_hash, feature)
            cached_feature = None if force else persistent_cache.get(feature_key)
            if isinstance(cached_feature, dict):
                raw_features[feature_id] = cached_feature
                sync_log.append({"level": "info", "feature": feature_id, "status": "cache_hit"})
                logger.info("Feature sync cache hit: feature=%s source=%s", feature_id, markdown_hash[:12])
            else:
                missing_features.append(feature)
                sync_log.append({"level": "info", "feature": feature_id, "status": "cache_miss"})
                logger.info("Feature sync cache miss: feature=%s source=%s", feature_id, markdown_hash[:12])

        if missing_features:
            if not self.api_key:
                raise RuntimeError("Missing LLM API key for configurable feature extraction")
            logger.info(
                "Feature sync requesting LLM: missing=%d model=%s base_url=%s",
                len(missing_features),
                self.model,
                self.base_url,
            )
            sync_log.append(
                {
                    "level": "info",
                    "message": "Requesting LLM for missing or changed features",
                    "missing_count": len(missing_features),
                    "model": self.model,
                }
            )
            llm_features = self._request_feature_extraction(markdown, missing_features)
            for feature in missing_features:
                feature_id = str(feature["id"])
                raw = llm_features.get(feature_id, {})
                raw_features[feature_id] = raw
                persistent_cache[self._feature_cache_key(markdown_hash, feature)] = raw
                sync_log.append({"level": "info", "feature": feature_id, "status": "llm_extracted"})
                logger.info("Feature sync LLM extracted: feature=%s source=%s", feature_id, markdown_hash[:12])
            _save_persistent_feature_cache()
        else:
            logger.info("Feature sync completed from cache: source=%s", markdown_hash[:12])

        feature_set = FeatureSet(
            features=self._coerce_features(raw_features),
            evidence=self._coerce_evidence(raw_features),
            metadata_fields=metadata_fields,
            parse_error=parse_error,
        )
        sync_log.append({"level": "info", "message": "Feature sync completed"})
        logger.info("Feature sync completed: source=%s", markdown_hash[:12])
        return feature_set, sync_log

    def extract_cached_features(self, markdown: str) -> tuple[FeatureSet | None, list[dict[str, Any]]]:
        markdown_hash = source_hash(markdown)
        sync_log: list[dict[str, Any]] = [
            {
                "level": "info",
                "message": "Cache lookup started",
                "profile_hash": self.profile_hash,
                "source_sha256": markdown_hash,
                "feature_count": len(self.profile["features"]),
            }
        ]

        metadata_fields: list[str] = []
        parse_error: str | None = None
        try:
            metadata, _ = parse_skill_markdown(markdown)
            metadata_fields = sorted(str(key) for key in metadata)
        except SkillMarkdownError as exc:
            parse_error = str(exc)

        persistent_cache = _load_persistent_feature_cache()
        raw_features: dict[str, Any] = {}
        missing_count = 0
        logger.info(
            "Feature cache lookup started: profile=%s hash=%s source=%s features=%d",
            self.profile_id,
            self.profile_hash[:12],
            markdown_hash[:12],
            len(self.profile["features"]),
        )
        for feature in self.profile["features"]:
            feature_id = str(feature["id"])
            cached_feature = persistent_cache.get(self._feature_cache_key(markdown_hash, feature))
            if isinstance(cached_feature, dict):
                raw_features[feature_id] = cached_feature
                sync_log.append({"level": "info", "feature": feature_id, "status": "cache_hit"})
            else:
                missing_count += 1
                sync_log.append({"level": "info", "feature": feature_id, "status": "cache_miss"})

        if missing_count:
            logger.info(
                "Feature cache lookup incomplete: source=%s missing=%d",
                markdown_hash[:12],
                missing_count,
            )
            sync_log.append(
                {
                    "level": "info",
                    "message": "Cache lookup incomplete",
                    "missing_count": missing_count,
                }
            )
            return None, sync_log

        logger.info("Feature cache lookup completed: source=%s", markdown_hash[:12])
        sync_log.append({"level": "info", "message": "Cache lookup completed"})
        return (
            FeatureSet(
                features=self._coerce_features(raw_features),
                evidence=self._coerce_evidence(raw_features),
                metadata_fields=metadata_fields,
                parse_error=parse_error,
            ),
            sync_log,
        )

    def _feature_cache_key(self, markdown_hash: str, feature: dict[str, Any]) -> str:
        payload = {
            "source_sha256": markdown_hash,
            "feature_id": feature.get("id"),
            "feature_hash": feature_definition_hash(feature),
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _request_feature_extraction(self, markdown: str, feature_definitions: list[dict[str, Any]]) -> dict[str, Any]:
        prompt = self._build_feature_extraction_prompt(markdown, feature_definitions)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You extract configured, measurable features from SKILL.md files. "
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
            raise RuntimeError(f"LLM API returned HTTP {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach LLM API: {exc}") from exc

        try:
            raw = response_data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response: {response_data}") from exc

        data = _parse_json_block(raw)
        raw_features = data.get("features", {})
        if not isinstance(raw_features, dict):
            raise RuntimeError(f"Unexpected feature payload from LLM: {data}")
        return raw_features

    def extract_format_features(self, markdown: str) -> FeatureSet:
        metadata: dict[str, Any] = {}
        parse_error: str | None = None
        frontmatter_valid = True
        try:
            metadata, _ = parse_skill_markdown(markdown)
        except SkillMarkdownError as exc:
            frontmatter_valid = False
            parse_error = str(exc)

        features = {
            "format_frontmatter_valid": frontmatter_valid,
            "format_has_name": _is_present(metadata.get("name")),
            "format_has_description": _is_present(metadata.get("description")),
            "format_has_input_schema": _is_present(metadata.get("input")),
            "format_input_has_required": _contains_required_key(metadata.get("input")),
            "format_has_output_schema": _is_present(metadata.get("output")),
        }
        evidence = {
            key: {
                "evidence": "Computed by front matter parser.",
                "confidence": 1.0,
                "source": "parser",
            }
            for key in features
        }
        return FeatureSet(
            features=features,
            evidence=evidence,
            metadata_fields=sorted(str(key) for key in metadata),
            parse_error=parse_error,
        )

    def build_calibration(self, feature_sets: list[FeatureSet]) -> dict[str, dict[str, float]]:
        numeric_features = self._numeric_calibration_features()
        calibration: dict[str, dict[str, float]] = {}
        for feature_name in sorted(numeric_features):
            values = [float(item.features.get(feature_name, 0.0)) for item in feature_sets]
            calibration[feature_name] = percentile_summary(values)
        return calibration

    def review(
        self,
        *,
        feature_set: FeatureSet,
        calibration: dict[str, dict[str, float]],
        criteria_key: str = "criteria",
    ) -> ConfigurableReviewResult:
        criteria_results: list[ConfigurableCriterionResult] = []
        for criterion in self.profile[criteria_key]:
            score = 0.0
            applied_steps: list[dict[str, Any]] = []
            for step in criterion.get("steps", []):
                condition = step.get("condition")
                matched = True if condition is None else self._eval_condition(
                    condition,
                    feature_set.features,
                    calibration,
                )
                if not matched:
                    continue
                before = score
                score = self._apply_step(score, step, feature_set.features, calibration)
                max_score = float(criterion.get("max_score", 10))
                score = max(0.0, min(score, max_score))
                applied_steps.append(
                    {
                        "id": step.get("id", ""),
                        "description": step.get("description", ""),
                        "action": step.get("action"),
                        "before": round(before, 4),
                        "after": round(score, 4),
                    }
                )
                if step.get("stop"):
                    break

            max_score = float(criterion.get("max_score", 10))
            criteria_results.append(
                ConfigurableCriterionResult(
                    criterion=str(criterion["id"]),
                    label=str(criterion.get("label", criterion["id"])),
                    score=round(max(0.0, min(score, max_score)), 2),
                    max_score=max_score,
                    explanation=self._explain(applied_steps),
                    applied_steps=applied_steps,
                )
            )

        total = round(sum(item.score for item in criteria_results), 2)
        total_max = round(sum(item.max_score for item in criteria_results), 2)
        return ConfigurableReviewResult(
            model=self.model,
            profile_id=self.profile_id,
            profile_hash=self.profile_hash,
            total_score=total,
            max_score=total_max,
            criteria=criteria_results,
            features=feature_set.features,
            feature_evidence=feature_set.evidence,
            calibration=calibration,
        )

    def _build_feature_extraction_prompt(
        self,
        markdown: str,
        feature_definitions: list[dict[str, Any]] | None = None,
    ) -> str:
        feature_definitions = feature_definitions or self.profile["features"]
        feature_contract = {
            feature["id"]: {
                "type": feature["type"],
                "extraction_guidance": feature.get("extraction_guidance", ""),
            }
            for feature in feature_definitions
        }
        return f"""
Extract the configured feature set from this SKILL.md document.

Rules:
- Do not score the document.
- Return JSON only.
- Use only observable evidence from the document.
- Count conservatively. If unsure, choose the lower count or false.
- Return every configured feature key exactly once.
- For each feature, return an object with value, evidence, and confidence.
- Boolean values must be true/false.
- Integer values must be non-negative integers.
- Evidence must be a short quote or concise observable reason from the markdown.
- Confidence must be a number from 0 to 1.

Configured features:
{json.dumps(feature_contract, indent=2, ensure_ascii=False)}

Return JSON in exactly this shape:
{{
  "features": {{
    "feature_id": {{
      "value": "typed value",
      "evidence": "short supporting quote or reason",
      "confidence": 0.0
    }}
  }}
}}

SKILL.md content:
```md
{markdown}
```
""".strip()

    def _coerce_features(self, raw_features: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for feature in self.profile["features"]:
            feature_id = str(feature["id"])
            feature_type = feature["type"]
            value = _raw_feature_value(raw_features.get(feature_id))
            if feature_type == "boolean":
                result[feature_id] = _as_bool(value)
            elif feature_type == "integer":
                result[feature_id] = max(0, int(_as_float(value)))
            else:
                result[feature_id] = 0
        return result

    def _coerce_evidence(self, raw_features: dict[str, Any]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for feature in self.profile["features"]:
            feature_id = str(feature["id"])
            raw = raw_features.get(feature_id)
            if isinstance(raw, dict):
                result[feature_id] = {
                    "evidence": str(raw.get("evidence", "") or ""),
                    "confidence": round(max(0.0, min(1.0, _as_float(raw.get("confidence", 0.0)))), 4),
                    "source": "llm",
                }
            else:
                result[feature_id] = {"evidence": "", "confidence": 0.0, "source": "llm"}
        return result

    def _numeric_calibration_features(self) -> set[str]:
        feature_types = {feature["id"]: feature["type"] for feature in self.profile["features"]}
        numeric_features: set[str] = set()
        for criterion in self.profile["criteria"]:
            for step in criterion.get("steps", []):
                feature = step.get("feature")
                if feature and feature_types.get(feature) == "integer":
                    numeric_features.add(feature)
                if step.get("source") == "percentile_bonus":
                    feature = step.get("feature")
                    if feature:
                        numeric_features.add(feature)
                condition = step.get("condition")
                if condition:
                    numeric_features.update(self._condition_percentile_features(condition))
        return numeric_features

    def _condition_percentile_features(self, condition: dict[str, Any]) -> set[str]:
        if "all" in condition:
            return set().union(*(self._condition_percentile_features(item) for item in condition["all"]))
        if "any" in condition:
            return set().union(*(self._condition_percentile_features(item) for item in condition["any"]))
        if "not" in condition:
            return self._condition_percentile_features(condition["not"])
        value = condition.get("value")
        if isinstance(value, dict) and value.get("percentile") and value.get("feature"):
            return {str(value["feature"])}
        return set()

    def _eval_condition(
        self,
        condition: dict[str, Any],
        features: dict[str, Any],
        calibration: dict[str, dict[str, float]],
    ) -> bool:
        if "all" in condition:
            return all(self._eval_condition(item, features, calibration) for item in condition["all"])
        if "any" in condition:
            return any(self._eval_condition(item, features, calibration) for item in condition["any"])
        if "not" in condition:
            return not self._eval_condition(condition["not"], features, calibration)

        feature = str(condition["feature"])
        operator = condition["operator"]
        actual = features.get(feature)
        expected = self._resolve_value(condition.get("value"), calibration)
        if operator == "exists":
            return _is_present(actual)
        if operator == "missing":
            return not _is_present(actual)
        if operator == "eq":
            return actual == expected
        if operator == "neq":
            return actual != expected
        actual_num = _as_float(actual)
        expected_num = _as_float(expected)
        if operator == "lt":
            return actual_num < expected_num
        if operator == "lte":
            return actual_num <= expected_num
        if operator == "gt":
            return actual_num > expected_num
        if operator == "gte":
            return actual_num >= expected_num
        return False

    def _apply_step(
        self,
        score: float,
        step: dict[str, Any],
        features: dict[str, Any],
        calibration: dict[str, dict[str, float]],
    ) -> float:
        action = step["action"]
        value = self._step_value(step, features, calibration)
        if action == "force_score":
            return value
        if action == "set_baseline":
            return max(score, value) if step.get("mode") == "max" else value
        if action == "set_score_from_bucket":
            feature = str(step["feature"])
            return self._bucket_score(_as_float(features.get(feature)), calibration.get(feature, {}))
        if action == "add":
            return score + value
        if action == "subtract":
            return score - value
        if action == "cap_max":
            return min(score, value)
        return score

    def _step_value(
        self,
        step: dict[str, Any],
        features: dict[str, Any],
        calibration: dict[str, dict[str, float]],
    ) -> float:
        if step.get("source") == "percentile_bonus":
            feature = str(step["feature"])
            scores = step.get("scores", {"p50": 2, "p90": 4})
            value = _as_float(features.get(feature))
            thresholds = calibration.get(feature, {})
            if value >= _as_float(thresholds.get("p90")):
                return _as_float(scores.get("p90", 4))
            if value >= _as_float(thresholds.get("p50")):
                return _as_float(scores.get("p50", 2))
            return 0.0
        return _as_float(self._resolve_value(step.get("value", 0), calibration))

    def _resolve_value(self, value: Any, calibration: dict[str, dict[str, float]]) -> Any:
        if isinstance(value, dict) and value.get("percentile") and value.get("feature"):
            return calibration.get(str(value["feature"]), {}).get(str(value["percentile"]), 0.0)
        return value

    def _bucket_score(self, value: float, thresholds: dict[str, float]) -> float:
        bucket = self.profile["bucket_scheme"]
        if value < _as_float(thresholds.get("p25")):
            return _as_float(bucket["p25"])
        if value < _as_float(thresholds.get("p50")):
            return _as_float(bucket["p50"])
        if value < _as_float(thresholds.get("p75")):
            return _as_float(bucket["p75"])
        if value < _as_float(thresholds.get("p90")):
            return _as_float(bucket["p90"])
        return _as_float(bucket["above"])

    def _explain(self, applied_steps: list[dict[str, Any]]) -> str:
        if not applied_steps:
            return "No scoring rule matched; score remained 0."
        labels = [step.get("description") or step.get("id") or step.get("action") for step in applied_steps]
        return "Applied: " + "; ".join(str(label) for label in labels if label)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _raw_feature_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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
        if "required" in value and _is_present(value.get("required")):
            return True
        return any(_contains_required_key(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_required_key(item) for item in value)
    return False


def _parse_json_block(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)
