"""
Skill Evaluation Service (port 8002)
====================================
Evaluates raw SKILL.md content in two dimensions:
  1. Format Review  → front matter scoring via configurable XML rules
  2. Content Review → LLM-based review of the full markdown content
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import html
import json
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from shared.db import init_db
from shared.schemas import (
    ContentEvaluationRead,
    ContentCriterionScore,
    FormatCriterionScore,
    FormatEvaluationRead,
    SkillEvaluationHtmlExportRequest,
    SkillFeatureExtractionRead,
    SkillFeatureExtractionRequest,
    SkillFeatureScoreRequest,
    SkillMarkdownEvaluationRead,
    SkillMarkdownEvaluationRequest,
)
from services.skill_evaluation.configurable_review import (
    ConfigurableDistributionReviewer,
    FeatureSet,
    load_profile,
    save_profile,
    validate_profile,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("skill_evaluation.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Skill Evaluation Service", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "service": "skill-evaluation"}


@app.post("/evaluate/markdown", response_model=SkillMarkdownEvaluationRead)
def evaluate_markdown(payload: SkillMarkdownEvaluationRequest) -> SkillMarkdownEvaluationRead:
    try:
        profile = load_profile(payload.profile_id)
        reviewer = ConfigurableDistributionReviewer(profile)
        extraction = _extract_all(payload.markdown, reviewer)
        return _build_evaluation_read(reviewer, extraction)
    except Exception as exc:
        logger.exception("Evaluation failed")
        raise HTTPException(status_code=_status_for_exception(exc), detail=f"Evaluation failed: {exc}") from exc


@app.post("/evaluate/features", response_model=SkillFeatureExtractionRead)
def extract_features(payload: SkillFeatureExtractionRequest) -> SkillFeatureExtractionRead:
    try:
        profile = load_profile(payload.profile_id)
        reviewer = ConfigurableDistributionReviewer(profile)
        extraction = _extract_all(payload.markdown, reviewer)
        content_features = extraction["content_feature_set"]
        format_features = extraction["format_feature_set"]
        return SkillFeatureExtractionRead(
            model=reviewer.model,
            profile_id=reviewer.profile_id,
            profile_hash=reviewer.profile_hash,
            content_features=content_features.features,
            content_feature_evidence=content_features.evidence,
            format_features=format_features.features,
            format_feature_evidence=format_features.evidence,
            calibration=extraction["calibration"],
            metadata_fields=content_features.metadata_fields or format_features.metadata_fields,
            frontmatter_parse_error=content_features.parse_error or format_features.parse_error,
        )
    except Exception as exc:
        logger.exception("Feature extraction failed")
        raise HTTPException(status_code=_status_for_exception(exc), detail=f"Feature extraction failed: {exc}") from exc


@app.post("/evaluate/features/sync", response_model=SkillFeatureExtractionRead)
def sync_features(payload: SkillFeatureExtractionRequest) -> SkillFeatureExtractionRead:
    try:
        profile = load_profile(payload.profile_id)
        reviewer = ConfigurableDistributionReviewer(profile)
        content_features, sync_log = reviewer.extract_features_with_sync_log(payload.markdown)
        format_features = reviewer.extract_format_features(payload.markdown)
        return SkillFeatureExtractionRead(
            model=reviewer.model,
            profile_id=reviewer.profile_id,
            profile_hash=reviewer.profile_hash,
            content_features=content_features.features,
            content_feature_evidence=content_features.evidence,
            format_features=format_features.features,
            format_feature_evidence=format_features.evidence,
            calibration={},
            metadata_fields=content_features.metadata_fields or format_features.metadata_fields,
            frontmatter_parse_error=content_features.parse_error or format_features.parse_error,
            sync_log=sync_log,
        )
    except Exception as exc:
        logger.exception("Feature sync failed")
        raise HTTPException(status_code=_status_for_exception(exc), detail=f"Feature sync failed: {exc}") from exc


@app.post("/evaluate/features/cache", response_model=SkillFeatureExtractionRead)
def get_cached_features(payload: SkillFeatureExtractionRequest) -> SkillFeatureExtractionRead:
    try:
        profile = load_profile(payload.profile_id)
        reviewer = ConfigurableDistributionReviewer(profile)
        content_features, sync_log = reviewer.extract_cached_features(payload.markdown)
        format_features = reviewer.extract_format_features(payload.markdown)
        if content_features is None:
            return SkillFeatureExtractionRead(
                model=reviewer.model,
                profile_id=reviewer.profile_id,
                profile_hash=reviewer.profile_hash,
                content_features={},
                content_feature_evidence={},
                format_features=format_features.features,
                format_feature_evidence=format_features.evidence,
                calibration={},
                metadata_fields=format_features.metadata_fields,
                frontmatter_parse_error=format_features.parse_error,
                sync_log=sync_log,
                cache_complete=False,
            )
        return SkillFeatureExtractionRead(
            model=reviewer.model,
            profile_id=reviewer.profile_id,
            profile_hash=reviewer.profile_hash,
            content_features=content_features.features,
            content_feature_evidence=content_features.evidence,
            format_features=format_features.features,
            format_feature_evidence=format_features.evidence,
            calibration={},
            metadata_fields=content_features.metadata_fields or format_features.metadata_fields,
            frontmatter_parse_error=content_features.parse_error or format_features.parse_error,
            sync_log=sync_log,
            cache_complete=True,
        )
    except Exception as exc:
        logger.exception("Feature cache lookup failed")
        raise HTTPException(status_code=_status_for_exception(exc), detail=f"Feature cache lookup failed: {exc}") from exc


@app.post("/evaluate/score-features", response_model=SkillMarkdownEvaluationRead)
def score_features(payload: SkillFeatureScoreRequest) -> SkillMarkdownEvaluationRead:
    try:
        profile = load_profile(payload.profile_id)
        reviewer = ConfigurableDistributionReviewer(profile)
        content_feature_set = FeatureSet(
            features=payload.content_features,
            evidence=payload.content_feature_evidence,
            metadata_fields=[],
        )
        format_feature_set = FeatureSet(
            features=payload.format_features,
            evidence=payload.format_feature_evidence,
            metadata_fields=[],
        )
        content_result = reviewer.review(feature_set=content_feature_set, calibration=payload.calibration)
        format_result = reviewer.review(feature_set=format_feature_set, calibration={}, criteria_key="format_criteria")
        return _result_to_read(format_result=format_result, content_result=content_result)
    except Exception as exc:
        logger.exception("Feature scoring failed")
        raise HTTPException(status_code=_status_for_exception(exc), detail=f"Feature scoring failed: {exc}") from exc


@app.post("/evaluate/export-html")
def export_evaluation_html(payload: SkillEvaluationHtmlExportRequest) -> HTMLResponse:
    return HTMLResponse(
        content=_render_evaluation_html(payload.evaluation),
        headers={"Content-Disposition": "attachment; filename=skill-evaluation-report.html"},
    )


def _extract_all(markdown: str, reviewer: ConfigurableDistributionReviewer, sync: bool = False) -> dict:
    logger.info("Evaluation extraction started: profile=%s source_chars=%d sync=%s", reviewer.profile_id, len(markdown), sync)
    logger.info("Calibration extraction started")
    corpus_feature_sets = reviewer.extract_corpus_features()
    logger.info("Calibration extraction completed: corpus_count=%d", len(corpus_feature_sets))
    calibration = reviewer.build_calibration(corpus_feature_sets)
    logger.info("Target feature extraction started")
    if sync:
        content_feature_set, sync_log = reviewer.extract_features_with_sync_log(markdown)
    else:
        content_feature_set = reviewer.extract_features(markdown)
        sync_log = []
    logger.info("Target feature extraction completed")
    return {
        "calibration": calibration,
        "content_feature_set": content_feature_set,
        "format_feature_set": reviewer.extract_format_features(markdown),
        "reviewer": reviewer,
        "sync_log": sync_log,
    }


def _build_evaluation_read(reviewer: ConfigurableDistributionReviewer, extraction: dict) -> SkillMarkdownEvaluationRead:
    content_result = reviewer.review(
        feature_set=extraction["content_feature_set"],
        calibration=extraction["calibration"],
    )
    format_result = reviewer.review(
        feature_set=extraction["format_feature_set"],
        calibration={},
        criteria_key="format_criteria",
    )
    return _result_to_read(format_result=format_result, content_result=content_result)


def _result_to_read(*, format_result, content_result) -> SkillMarkdownEvaluationRead:
    format_score = int(round(format_result.total_score))
    format_max = int(round(format_result.max_score))
    frontmatter_valid = bool(format_result.features.get("format_frontmatter_valid", True))

    return SkillMarkdownEvaluationRead(
        format_review=FormatEvaluationRead(
            score=format_score,
            max_score=format_max,
            passed=frontmatter_valid and format_score >= 70,
            frontmatter_valid=frontmatter_valid,
            errors=[] if frontmatter_valid else ["Front matter could not be parsed"],
            criteria=[
                FormatCriterionScore(
                    criterion=item.criterion,
                    label=item.label,
                    score=int(round(item.score)),
                    max_score=int(round(item.max_score)),
                    explanation=item.explanation,
                    applied_steps=item.applied_steps,
                )
                for item in format_result.criteria
            ],
            features=format_result.features,
            feature_evidence=format_result.feature_evidence,
        ),
        content_review=ContentEvaluationRead(
            model=content_result.model,
            profile_id=content_result.profile_id,
            profile_hash=content_result.profile_hash,
            total_score=content_result.total_score,
            max_score=content_result.max_score,
            criteria=[
                ContentCriterionScore(
                    criterion=item.criterion,
                    label=item.label,
                    score=item.score,
                    max_score=item.max_score,
                    explanation=item.explanation,
                    applied_steps=item.applied_steps,
                )
                for item in content_result.criteria
            ],
            features=content_result.features,
            feature_evidence=content_result.feature_evidence,
            calibration=content_result.calibration,
        ),
    )


def _render_evaluation_html(evaluation: dict) -> str:
    title = "Skill Evaluation Report"
    escaped_json = html.escape(json.dumps(evaluation, indent=2, ensure_ascii=False))
    format_review = evaluation.get("format_review", {})
    content_review = evaluation.get("content_review", {})
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <style>
    body {{ font-family: Inter, Arial, sans-serif; margin: 32px; color: #172033; }}
    h1 {{ margin-bottom: 8px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .card {{ border: 1px solid #d7deea; border-radius: 8px; padding: 16px; margin: 16px 0; }}
    .score {{ font-size: 32px; font-weight: 800; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ border-bottom: 1px solid #e5eaf2; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ font-size: 12px; text-transform: uppercase; color: #667085; }}
    pre {{ white-space: pre-wrap; background: #f6f8fb; border: 1px solid #d7deea; padding: 16px; border-radius: 8px; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="grid">
    <section class="card">
      <h2>Format</h2>
      <div class="score">{format_review.get("score", 0)} / {format_review.get("max_score", 0)}</div>
      {_criteria_table(format_review.get("criteria", []))}
    </section>
    <section class="card">
      <h2>Content</h2>
      <div class="score">{content_review.get("total_score", 0)} / {content_review.get("max_score", 0)}</div>
      {_criteria_table(content_review.get("criteria", []))}
    </section>
  </div>
  <section class="card">
    <h2>Raw JSON</h2>
    <pre>{escaped_json}</pre>
  </section>
</body>
</html>"""


def _criteria_table(criteria: list[dict]) -> str:
    rows = []
    for item in criteria:
        label = html.escape(str(item.get("label") or item.get("criterion", "")))
        score = html.escape(str(item.get("score", 0)))
        max_score = html.escape(str(item.get("max_score", 0)))
        explanation = html.escape(str(item.get("explanation", "")))
        rows.append(f"<tr><td>{label}</td><td>{score}/{max_score}</td><td>{explanation}</td></tr>")
    return "<table><thead><tr><th>Criterion</th><th>Score</th><th>Explanation</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _status_for_exception(exc: Exception) -> int:
    message = str(exc)
    if "Missing LLM API key" in message:
        return 400
    if "LLM API returned HTTP" in message or "Could not reach LLM API" in message:
        return 502
    return 500


@app.get("/evaluation/profiles/default")
def get_default_evaluation_profile() -> dict:
    try:
        return load_profile("default")
    except Exception as exc:
        logger.exception("Could not load evaluation profile")
        raise HTTPException(status_code=500, detail=f"Could not load evaluation profile: {exc}") from exc


@app.put("/evaluation/profiles/default")
def put_default_evaluation_profile(profile: dict) -> dict:
    try:
        validate_profile(profile)
        return save_profile(profile, "default")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not save evaluation profile")
        raise HTTPException(status_code=500, detail=f"Could not save evaluation profile: {exc}") from exc
