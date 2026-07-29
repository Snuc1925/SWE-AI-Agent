from __future__ import annotations

import datetime as dt
import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from services.skill_management.skill_library.registry.registry import SkillRegistry
from shared.config import get_skills_dir
from shared.db import get_session, init_db
from shared.models import Skill as SkillORM
from shared.schemas import (
    SkillList,
    SkillPayload,
    SkillRead,
    SkillSearchResponse,
    SkillSearchResult,
    SkillSummary,
    SkillUpdate,
    SkillExecutionRequest,
    SkillExecutionResponse,
    SkillToolDefinition,
)
from services.skill_management.skill_library.execution.executor import SkillExecutor
from services.skill_management.skill_library.models.skill import Skill as SkillLibModel
from shared.skill_markdown import (
    SkillMarkdownError,
    generate_skill_markdown,
    parse_skill_markdown,
)

CORE_FIELDS = {"name", "version", "category", "level", "tags"}

REGISTRY: SkillRegistry | None = None
SKILLS_DIR: Path = get_skills_dir()
USE_JSON_STORE = os.getenv("SKILL_STORE", "").lower() == "json"
JSON_DATABASE_DIR = Path(os.getenv("JSON_DATABASE_DIR", "/database"))
SKILL_JSON_DB_PATH = Path(os.getenv("SKILL_JSON_DB_PATH", str(JSON_DATABASE_DIR / "skills.json")))


def get_registry() -> SkillRegistry:
    global REGISTRY
    if REGISTRY is None:
        REGISTRY = SkillRegistry(SKILLS_DIR)
        reload_registry()
    return REGISTRY


def reload_registry() -> int:
    global REGISTRY
    if REGISTRY is None:
        REGISTRY = SkillRegistry(SKILLS_DIR)

    if USE_JSON_STORE:
        return REGISTRY.load_from_markdowns([s["raw_content"] for s in _read_json_skills()])
    
    with get_session() as session:
        skills = session.execute(select(SkillORM)).scalars().all()
        count = REGISTRY.load_from_markdowns([s.raw_content for s in skills])
    return count


def _normalize_tags(tags: Any) -> list[str]:
    if tags is None:
        return []
    if not isinstance(tags, list):
        raise HTTPException(status_code=400, detail="'tags' must be a list")
    return [str(tag).strip() for tag in tags if str(tag).strip()]


def _split_metadata(metadata: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    missing = [field for field in ["name", "version", "category", "level"] if not metadata.get(field)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required metadata fields: {', '.join(missing)}")

    name = str(metadata["name"]).strip()
    version = str(metadata["version"]).strip()
    category = str(metadata["category"]).strip()
    level = str(metadata["level"]).strip()

    if not name or len(name) > 255:
        raise HTTPException(status_code=400, detail="'name' must be 1..255 characters")
    if not version or len(version) > 50:
        raise HTTPException(status_code=400, detail="'version' must be 1..50 characters")
    if not category or len(category) > 100:
        raise HTTPException(status_code=400, detail="'category' must be 1..100 characters")
    if not level or len(level) > 15:
        raise HTTPException(status_code=400, detail="'level' must be 1..15 characters")

    tags = _normalize_tags(metadata.get("tags", []))

    core = {"name": name, "version": version, "category": category, "level": level, "tags": tags}
    extras = {k: v for k, v in metadata.items() if k not in CORE_FIELDS}
    return core, extras


def _split_metadata_for_filesystem(metadata: dict[str, Any], md_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = dict(metadata)
    if not normalized.get("name"):
        normalized["name"] = md_path.parent.name
    if not normalized.get("version"):
        normalized["version"] = "1.0.0"
    if not normalized.get("level"):
        normalized["level"] = "atomic"
    if not normalized.get("category"):
        try:
            relative_parent = md_path.parent.relative_to(SKILLS_DIR).as_posix()
        except ValueError:
            relative_parent = md_path.parent.name
        normalized["category"] = relative_parent if relative_parent != "." else "uncategorized"
    return _split_metadata(normalized)


def _full_metadata(core: dict[str, Any], extras: dict[str, Any]) -> dict[str, Any]:
    return {**core, **(extras or {})}


def _skill_dir_for(name: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_\-/]", "-", name).lower()
    return SKILLS_DIR / safe


def _write_skill_md(name: str, raw_content: str) -> Path:
    skill_dir = _skill_dir_for(name)
    skill_dir.mkdir(parents=True, exist_ok=True)
    md_path = skill_dir / "SKILL.md"
    md_path.write_text(raw_content.strip() + "\n", encoding="utf-8")
    return md_path


def _instruction_from_raw(raw_content: str) -> str:
    try:
        _, instruction = parse_skill_markdown(raw_content)
        return instruction
    except SkillMarkdownError:
        return raw_content.strip()


def _orm_to_summary(skill: SkillORM) -> SkillSummary:
    return SkillSummary(
        id=skill.id,
        name=skill.name,
        version=skill.version,
        level=skill.level,
        category=skill.category,
        tags=skill.tags or [],
        metadata=skill.metadata_json or {},
        updated_at=skill.updated_at,
    )


def _orm_to_read(skill: SkillORM) -> SkillRead:
    return SkillRead(
        id=skill.id,
        name=skill.name,
        version=skill.version,
        level=skill.level,
        category=skill.category,
        tags=skill.tags or [],
        metadata=skill.metadata_json or {},
        raw_content=skill.raw_content,
        full_markdown=skill.raw_content,
        updated_at=skill.updated_at,
    )


def _json_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _read_json_skills() -> list[dict[str, Any]]:
    if not SKILL_JSON_DB_PATH.exists():
        return []
    data = json.loads(SKILL_JSON_DB_PATH.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        items = data.get("skills", [])
    else:
        items = data
    return [item for item in items if isinstance(item, dict)]


def _write_json_skills(skills: list[dict[str, Any]]) -> None:
    SKILL_JSON_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "updated_at": _json_now(), "skills": skills}
    SKILL_JSON_DB_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _json_to_summary(skill: dict[str, Any]) -> SkillSummary:
    return SkillSummary(
        id=skill["id"],
        name=skill["name"],
        version=skill["version"],
        level=skill["level"],
        category=skill["category"],
        tags=skill.get("tags") or [],
        metadata=skill.get("metadata_json") or {},
        updated_at=skill.get("updated_at") or _json_now(),
    )


def _json_to_read(skill: dict[str, Any]) -> SkillRead:
    summary = _json_to_summary(skill)
    return SkillRead(
        **summary.model_dump(),
        raw_content=skill["raw_content"],
        full_markdown=skill["raw_content"],
    )


def _json_find_by_id(skills: list[dict[str, Any]], skill_id: str) -> dict[str, Any] | None:
    return next((skill for skill in skills if skill.get("id") == skill_id), None)


def _json_find_by_name(skills: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((skill for skill in skills if skill.get("name") == name), None)


def sync_skills_to_db() -> None:
    """Scan filesystem and sync all SKILL.md files into the database."""
    if USE_JSON_STORE:
        existing_by_name = {skill.get("name"): skill for skill in _read_json_skills()}
        synced: list[dict[str, Any]] = []
        seen_names = set()
        for md_path in SKILLS_DIR.rglob("SKILL.md"):
            try:
                raw_content = md_path.read_text(encoding="utf-8")
                raw_meta, _ = parse_skill_markdown(raw_content)
                core, extras = _split_metadata_for_filesystem(raw_meta, md_path)
            except Exception as exc:
                print(f"[skill-sync] skip {md_path}: {exc}")
                continue
            if core["name"] in seen_names:
                print(f"[skill-sync] duplicate skipped: {core['name']}")
                continue
            seen_names.add(core["name"])
            previous = existing_by_name.get(core["name"], {})
            synced.append(
                {
                    "id": previous.get("id") or str(uuid.uuid4()),
                    "name": core["name"],
                    "version": core["version"],
                    "category": core["category"],
                    "level": core["level"],
                    "tags": core["tags"],
                    "metadata_json": extras,
                    "raw_content": raw_content.strip() + "\n",
                    "updated_at": previous.get("updated_at") or _json_now(),
                }
            )
        _write_json_skills(synced)
        return

    seen_names = set()
    with get_session() as session:
        for md_path in SKILLS_DIR.rglob("SKILL.md"):
            try:
                raw_content = md_path.read_text(encoding="utf-8")
                raw_meta, _ = parse_skill_markdown(raw_content)
                core, extras = _split_metadata_for_filesystem(raw_meta, md_path)
            except Exception as exc:
                print(f"[skill-sync] skip {md_path}: {exc}")
                continue
            skill_name = core["name"]
            # ===== FIX DUPLICATE IN SAME RUN =====
            if skill_name in seen_names:
                print(f"[skill-sync] duplicate skipped: {skill_name}")
                continue

            seen_names.add(skill_name)
            
            existing = session.execute(
                select(SkillORM).where(SkillORM.name == core["name"])
            ).scalar_one_or_none()
            
            if existing:
                existing.version = core["version"]
                existing.category = core["category"]
                existing.level = core["level"]
                existing.tags = core["tags"]
                existing.metadata_json = extras
                existing.raw_content = raw_content.strip() + "\n"
                session.add(existing)
            else:
                session.add(
                    SkillORM(
                        name=core["name"],
                        version=core["version"],
                        category=core["category"],
                        level=core["level"],
                        tags=core["tags"],
                        metadata_json=extras,
                        raw_content=raw_content.strip() + "\n",
                    )
                )


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not USE_JSON_STORE:
        init_db()
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    JSON_DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    sync_skills_to_db()
    reload_registry()
    yield


app = FastAPI(title="Skill Management Service", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/skills", response_model=SkillRead, status_code=201)
def create_skill(payload: SkillPayload) -> SkillRead:
    metadata = payload.metadata.model_dump(exclude_none=True)
    core, extras = _split_metadata(metadata)
    instruction = payload.instruction.strip()
    raw_content = generate_skill_markdown(_full_metadata(core, extras), instruction)

    if USE_JSON_STORE:
        skills = _read_json_skills()
        if _json_find_by_name(skills, core["name"]):
            raise HTTPException(status_code=409, detail=f"Skill '{core['name']}' already exists")
        record = {
            "id": str(uuid.uuid4()),
            "name": core["name"],
            "version": core["version"],
            "category": core["category"],
            "level": core["level"],
            "tags": core["tags"],
            "metadata_json": extras,
            "raw_content": raw_content,
            "updated_at": _json_now(),
        }
        skills.append(record)
        _write_json_skills(skills)
        _write_skill_md(core["name"], raw_content)
        reload_registry()
        return _json_to_read(record)

    with get_session() as session:
        existing = session.execute(
            select(SkillORM).where(SkillORM.name == core["name"])
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail=f"Skill '{core['name']}' already exists")

        skill = SkillORM(
            name=core["name"],
            version=core["version"],
            category=core["category"],
            level=core["level"],
            tags=core["tags"],
            metadata_json=extras,
            raw_content=raw_content,
        )
        session.add(skill)
        session.flush()
        session.refresh(skill)
        result = _orm_to_read(skill)

    _write_skill_md(core["name"], raw_content)
    reload_registry()
    return result


@app.get("/skills", response_model=SkillList)
def list_skills(
    category: str | None = Query(default=None, description="Filter by category prefix"),
    level: str | None = Query(default=None, description="Filter by level"),
    tag: str | None = Query(default=None, description="Filter by tag"),
) -> SkillList:
    if USE_JSON_STORE:
        summaries = [_json_to_summary(skill) for skill in _read_json_skills()]
        summaries.sort(key=lambda item: item.updated_at, reverse=True)
        if category:
            summaries = [s for s in summaries if s.category.startswith(category)]
        if level:
            summaries = [s for s in summaries if s.level == level]
        if tag:
            summaries = [s for s in summaries if tag in s.tags]
        return SkillList(items=summaries, total=len(summaries))

    with get_session() as session:
        stmt = select(SkillORM).order_by(SkillORM.updated_at.desc())
        skills = session.execute(stmt).scalars().all()
        summaries = [_orm_to_summary(s) for s in skills]
        if category:
            summaries = [s for s in summaries if s.category.startswith(category)]
        if level:
            summaries = [s for s in summaries if s.level == level]
        if tag:
            summaries = [s for s in summaries if tag in s.tags]
        return SkillList(items=summaries, total=len(summaries))


@app.get("/skills/search", response_model=SkillSearchResponse)
def search_skills(
    q: str = Query(..., min_length=1, description="Search query"),
    top_k: int = Query(default=5, ge=1, le=20),
) -> SkillSearchResponse:
    registry = get_registry()
    raw_results = registry.search(q, top_k=top_k)
    results = []
    if USE_JSON_STORE:
        skills = _read_json_skills()
        for skill_model, score in raw_results:
            record = _json_find_by_name(skills, skill_model.name)
            if record:
                results.append(SkillSearchResult(skill=_json_to_summary(record), score=round(score, 4)))
        return SkillSearchResponse(query=q, results=results)

    with get_session() as session:
        for skill_model, score in raw_results:
            orm = session.execute(
                select(SkillORM).where(SkillORM.name == skill_model.name)
            ).scalar_one_or_none()
            if orm:
                results.append(SkillSearchResult(skill=_orm_to_summary(orm), score=round(score, 4)))
    return SkillSearchResponse(query=q, results=results)


@app.post("/skills/{skill_id}/execute", response_model=SkillExecutionResponse)
def execute_skill(skill_id: str, payload: SkillExecutionRequest) -> SkillExecutionResponse:
    """Execute a skill with arbitrary input data (mock or real LLM)."""
    if USE_JSON_STORE:
        skill_record = _json_find_by_id(_read_json_skills(), skill_id)
        if not skill_record:
            raise HTTPException(status_code=404, detail="Skill not found")
        try:
            skill_lib_model = SkillLibModel.from_markdown(skill_record["raw_content"])
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Failed to parse skill markdown: {exc}")
        skill_name = skill_record["name"]
    else:
        with get_session() as session:
            skill_orm = session.get(SkillORM, skill_id)
            if not skill_orm:
                raise HTTPException(status_code=404, detail="Skill not found")
            
            try:
                skill_lib_model = SkillLibModel.from_markdown(skill_orm.raw_content)
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"Failed to parse skill markdown: {exc}")
            skill_name = skill_orm.name

    registry = get_registry()
    executor = SkillExecutor(
        registry=registry,
        api_key=payload.api_key,
        mock_mode=payload.mock_mode
    )

    try:
        output = executor.run(skill_lib_model, payload.input)
        telemetry = None
        if executor.last_telemetry:
            telemetry = {
                "latency_ms": round(executor.last_telemetry.latency_ms, 2),
                "token_usage": executor.last_telemetry.token_usage,
                "retry_count": executor.last_telemetry.retry_count
            }
        
        return SkillExecutionResponse(
            skill_id=skill_id,
            skill_name=skill_name,
            output=output,
            telemetry=telemetry
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/skills/tools", response_model=list[SkillToolDefinition])
def list_skill_tools() -> list[SkillToolDefinition]:
    """Return all skills as LangChain-compatible tool definitions."""
    if USE_JSON_STORE:
        results = []
        for s in _read_json_skills():
            try:
                m = SkillLibModel.from_markdown(s["raw_content"])
                results.append(SkillToolDefinition(
                    name=m.name,
                    description=m.description,
                    input_schema=m.input,
                    output_schema=m.output,
                    skill_id=s["id"]
                ))
            except Exception:
                continue
        return results

    with get_session() as session:
        skills = session.execute(select(SkillORM)).scalars().all()
        results = []
        for s in skills:
            try:
                m = SkillLibModel.from_markdown(s.raw_content)
                results.append(SkillToolDefinition(
                    name=m.name,
                    description=m.description,
                    input_schema=m.input,
                    output_schema=m.output,
                    skill_id=s.id
                ))
            except:
                continue
        return results


@app.get("/skills/{skill_id}/tool", response_model=SkillToolDefinition)
def get_skill_tool(skill_id: str) -> SkillToolDefinition:
    """Return a single skill as a LangChain-compatible tool definition."""
    if USE_JSON_STORE:
        skill = _json_find_by_id(_read_json_skills(), skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        try:
            m = SkillLibModel.from_markdown(skill["raw_content"])
            return SkillToolDefinition(
                name=m.name,
                description=m.description,
                input_schema=m.input,
                output_schema=m.output,
                skill_id=skill["id"]
            )
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    with get_session() as session:
        skill = session.get(SkillORM, skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        try:
            m = SkillLibModel.from_markdown(skill.raw_content)
            return SkillToolDefinition(
                name=m.name,
                description=m.description,
                input_schema=m.input,
                output_schema=m.output,
                skill_id=skill.id
            )
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc))


@app.get("/skills/{skill_id}", response_model=SkillRead)
def get_skill(skill_id: str) -> SkillRead:
    if USE_JSON_STORE:
        skill = _json_find_by_id(_read_json_skills(), skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        return _json_to_read(skill)

    with get_session() as session:
        skill = session.get(SkillORM, skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        return _orm_to_read(skill)


@app.put("/skills/{skill_id}", response_model=SkillRead)
def update_skill(skill_id: str, payload: SkillUpdate) -> SkillRead:
    if USE_JSON_STORE:
        skills = _read_json_skills()
        skill = _json_find_by_id(skills, skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")

        previous_name = skill["name"]
        current_full_meta = _full_metadata(
            {
                "name": skill["name"],
                "version": skill["version"],
                "category": skill["category"],
                "level": skill["level"],
                "tags": skill.get("tags") or [],
            },
            skill.get("metadata_json") or {},
        )

        if payload.full_markdown is not None or payload.raw_content is not None:
            raw_content = (payload.raw_content or payload.full_markdown or "").strip()
            if not raw_content:
                raise HTTPException(status_code=400, detail="'raw_content' cannot be empty")
            try:
                raw_meta, _ = parse_skill_markdown(raw_content)
                core, extras = _split_metadata(raw_meta)
            except SkillMarkdownError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid markdown: {exc}") from exc
            new_raw_content = raw_content + "\n"
        else:
            merged_meta = dict(current_full_meta)
            if payload.metadata:
                merged_meta.update(payload.metadata)
            core, extras = _split_metadata(merged_meta)
            instruction = payload.instruction if payload.instruction is not None else _instruction_from_raw(skill["raw_content"])
            new_raw_content = generate_skill_markdown(_full_metadata(core, extras), instruction)

        if core["name"] != previous_name and _json_find_by_name(skills, core["name"]):
            raise HTTPException(status_code=409, detail=f"Skill '{core['name']}' already exists")

        skill.update(
            {
                "name": core["name"],
                "version": core["version"],
                "category": core["category"],
                "level": core["level"],
                "tags": core["tags"],
                "metadata_json": extras,
                "raw_content": new_raw_content,
                "updated_at": _json_now(),
            }
        )
        _write_json_skills(skills)
        new_path = _write_skill_md(core["name"], new_raw_content)
        if previous_name != core["name"]:
            old_path = _skill_dir_for(previous_name) / "SKILL.md"
            if old_path.exists() and old_path != new_path:
                old_path.unlink()
        reload_registry()
        return _json_to_read(skill)

    with get_session() as session:
        skill = session.get(SkillORM, skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")

        previous_name = skill.name
        current_full_meta = _full_metadata(
            {
                "name": skill.name,
                "version": skill.version,
                "category": skill.category,
                "level": skill.level,
                "tags": skill.tags or [],
            },
            skill.metadata_json or {},
        )

        if payload.full_markdown is not None or payload.raw_content is not None:
            raw_content = (payload.raw_content or payload.full_markdown or "").strip()
            if not raw_content:
                raise HTTPException(status_code=400, detail="'raw_content' cannot be empty")
            try:
                raw_meta, _ = parse_skill_markdown(raw_content)
                core, extras = _split_metadata(raw_meta)
            except SkillMarkdownError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid markdown: {exc}") from exc
            new_raw_content = raw_content + "\n"
        else:
            merged_meta = dict(current_full_meta)
            if payload.metadata:
                merged_meta.update(payload.metadata)
            core, extras = _split_metadata(merged_meta)
            instruction = payload.instruction if payload.instruction is not None else _instruction_from_raw(skill.raw_content)
            new_raw_content = generate_skill_markdown(_full_metadata(core, extras), instruction)

        if core["name"] != previous_name:
            existing = session.execute(
                select(SkillORM).where(SkillORM.name == core["name"], SkillORM.id != skill_id)
            ).scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=409, detail=f"Skill '{core['name']}' already exists")

        skill.name = core["name"]
        skill.version = core["version"]
        skill.category = core["category"]
        skill.level = core["level"]
        skill.tags = core["tags"]
        skill.metadata_json = extras
        skill.raw_content = new_raw_content
        session.add(skill)
        session.flush()
        session.refresh(skill)
        result = _orm_to_read(skill)

    new_path = _write_skill_md(core["name"], new_raw_content)
    if previous_name != core["name"]:
        old_path = _skill_dir_for(previous_name) / "SKILL.md"
        if old_path.exists() and old_path != new_path:
            old_path.unlink()
    reload_registry()
    return result


@app.delete("/skills/{skill_id}", status_code=200)
def delete_skill(skill_id: str, remove_file: bool = Query(default=False)) -> dict:
    if USE_JSON_STORE:
        skills = _read_json_skills()
        skill = _json_find_by_id(skills, skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        name = skill["name"]
        if remove_file:
            md_path = _skill_dir_for(name) / "SKILL.md"
            if md_path.exists():
                md_path.unlink()
        _write_json_skills([item for item in skills if item.get("id") != skill_id])
        reload_registry()
        return {"status": "deleted", "skill_id": skill_id, "name": name}

    with get_session() as session:
        skill = session.get(SkillORM, skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        name = skill.name
        if remove_file:
            md_path = _skill_dir_for(name) / "SKILL.md"
            if md_path.exists():
                md_path.unlink()
        session.delete(skill)

    reload_registry()
    return {"status": "deleted", "skill_id": skill_id, "name": name}


@app.post("/skills/import", response_model=SkillRead, status_code=201)
def import_skill(file: UploadFile = File(...)) -> SkillRead:
    raw_content = file.file.read().decode("utf-8")
    try:
        raw_meta, _ = parse_skill_markdown(raw_content)
        core, extras = _split_metadata(raw_meta)
    except SkillMarkdownError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if USE_JSON_STORE:
        skills = _read_json_skills()
        if _json_find_by_name(skills, core["name"]):
            raise HTTPException(status_code=409, detail=f"Skill '{core['name']}' already exists")
        record = {
            "id": str(uuid.uuid4()),
            "name": core["name"],
            "version": core["version"],
            "category": core["category"],
            "level": core["level"],
            "tags": core["tags"],
            "metadata_json": extras,
            "raw_content": raw_content.strip() + "\n",
            "updated_at": _json_now(),
        }
        skills.append(record)
        _write_json_skills(skills)
        _write_skill_md(core["name"], raw_content)
        reload_registry()
        return _json_to_read(record)

    with get_session() as session:
        existing = session.execute(
            select(SkillORM).where(SkillORM.name == core["name"])
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail=f"Skill '{core['name']}' already exists")

        orm = SkillORM(
            name=core["name"],
            version=core["version"],
            category=core["category"],
            level=core["level"],
            tags=core["tags"],
            metadata_json=extras,
            raw_content=raw_content.strip() + "\n",
        )
        session.add(orm)
        session.flush()
        session.refresh(orm)
        result = _orm_to_read(orm)

    _write_skill_md(core["name"], raw_content)
    reload_registry()
    return result


@app.get("/skills/{skill_id}/export")
def export_skill(skill_id: str) -> PlainTextResponse:
    if USE_JSON_STORE:
        skill = _json_find_by_id(_read_json_skills(), skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        return PlainTextResponse(
            skill["raw_content"],
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={skill['name']}.md"},
        )

    with get_session() as session:
        skill = session.get(SkillORM, skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        return PlainTextResponse(
            skill.raw_content,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={skill.name}.md"},
        )


@app.get("/registry/status")
def registry_status() -> dict:
    registry = get_registry()
    return {
        "loaded_skills": len(registry),
        "skills_dir": str(SKILLS_DIR),
        "skill_names": list(registry.skills.keys()),
    }


@app.post("/registry/reload")
def registry_reload() -> dict:
    count = reload_registry()
    return {"status": "reloaded", "loaded_skills": count}
