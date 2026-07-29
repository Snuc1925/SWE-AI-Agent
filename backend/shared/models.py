from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    JSON,
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Skill
# ─────────────────────────────────────────────────────────────────────────────
class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Core indexed columns ─────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(15), nullable=False, index=True)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text).with_variant(JSON, "sqlite"), nullable=False, default=list
    )

    # ── Flexible metadata and source markdown ────────────────────────────────
    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Timestamps ───────────────────────────────────────────────────────────
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    # ── Relationships ────────────────────────────────────────────────────────
    evaluations = relationship(
        "SkillEvaluation", back_populates="skill", cascade="all, delete-orphan"
    )
    test_runs = relationship(
        "SkillTestRun", back_populates="skill", cascade="all, delete-orphan"
    )
    doc_reviews = relationship(
        "SkillDocReview", back_populates="skill", cascade="all, delete-orphan"
    )

# ─────────────────────────────────────────────────────────────────────────────
# SkillEvaluation  — result of SkillEvaluator.evaluate() (test-case run)
# ─────────────────────────────────────────────────────────────────────────────
class SkillEvaluation(Base):
    __tablename__ = "skill_evaluations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    skill_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("skills.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # ── Evaluation results ───────────────────────────────────────────────────
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0)
    pass_rate: Mapped[float] = mapped_column(Float, default=0.0)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    latency_p50: Mapped[float] = mapped_column(Float, default=0.0)
    latency_p95: Mapped[float] = mapped_column(Float, default=0.0)
    avg_tokens: Mapped[float] = mapped_column(Float, default=0.0)
    mock_mode: Mapped[bool] = mapped_column(Boolean, default=True)

    # Full JSON report from EvaluationReport.to_dict()
    report_json: Mapped[str] = mapped_column(Text, default="{}")

    # Legacy fields kept for compat
    format_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    content_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    errors: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    skill = relationship("Skill", back_populates="evaluations")


# ─────────────────────────────────────────────────────────────────────────────
# SkillDocReview  — result of SkillDocReviewer.review()
# ─────────────────────────────────────────────────────────────────────────────
class SkillDocReview(Base):
    __tablename__ = "skill_doc_reviews"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    skill_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("skills.id", ondelete="SET NULL"), nullable=True, index=True
    )

    doc_score: Mapped[int] = mapped_column(Integer, default=0)
    max_score: Mapped[int] = mapped_column(Integer, default=100)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    threshold: Mapped[int] = mapped_column(Integer, default=80)
    # Full criteria JSON
    criteria_json: Mapped[str] = mapped_column(Text, default="[]")

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    skill = relationship("Skill", back_populates="doc_reviews")


# ─────────────────────────────────────────────────────────────────────────────
# SkillTestRun  — result of a manual test run via the testing service
# ─────────────────────────────────────────────────────────────────────────────
class SkillTestRun(Base):
    __tablename__ = "skill_test_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    skill_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("skills.id", ondelete="SET NULL"), nullable=True, index=True
    )
    llm: Mapped[str] = mapped_column(String(100), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    results: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    skill = relationship("Skill", back_populates="test_runs")
