"""
SkillExecutor — orchestrates the full skill execution lifecycle:
  1. Validate input (JSON Schema)
  2. Check constraints (host / resources / safety)
  3. Dispatch:  atomic  → call LLM and parse output
               composite → recursively execute sub-skills (+ cycle detection)
  4. Emit structured LogEvents at every step so consumers (CLI / UI) can track progress.
  5. Collect ExecutionTelemetry (token_usage, latency_ms, retry_count) per run.
"""
import json
import os
import re
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ..models.skill import Skill
from ..registry.registry import SkillRegistry
from ..registry.validator import InputValidator
from .constraint import ConstraintChecker


# ─────────────────────────────────────────────────────────────────────────────
# Log Event
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class LogEvent:
    """A single execution log entry emitted during skill execution."""
    step: str          # "identify_skill"|"validate_input"|"check_constraint"|
                       # "call_llm"|"parse_output"|"compose"|"safety_approval"
    status: str        # "start"|"success"|"error"|"info"
    message: str
    data: Optional[Dict[str, Any]] = None
    skill_name: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "status": self.status,
            "message": self.message,
            "skill_name": self.skill_name,
            "data": self.data,
            "timestamp": self.timestamp,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────
class ExecutionError(Exception):
    def __init__(self, step: str, message: str):
        self.step = step
        super().__init__(f"[{step}] {message}")


class CyclicSkillError(ExecutionError):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry  (Layer 4 — Monitor)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class ExecutionTelemetry:
    """Runtime metrics collected during a single top-level skill execution."""
    skill_name: str
    latency_ms: float = 0.0
    token_usage: Dict[str, int] = field(
        default_factory=lambda: {"prompt": 0, "completion": 0, "total": 0}
    )
    retry_count: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Executor
# ─────────────────────────────────────────────────────────────────────────────
class SkillExecutor:
    DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL = "deepseek-chat"

    def __init__(
        self,
        registry: SkillRegistry,
        api_key: Optional[str] = None,
        mock_mode: bool = False,
        log_callback: Optional[Callable[[LogEvent], None]] = None,
    ):
        self.registry = registry
        self.mock_mode = mock_mode
        self.log_callback: Callable[[LogEvent], None] = log_callback or (lambda _: None)
        self._validator = InputValidator()
        self._constraint_checker = ConstraintChecker()
        self._last_telemetry: Optional[ExecutionTelemetry] = None

        if not mock_mode:
            from openai import OpenAI
            key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
            base_url = os.environ.get("LLM_BASE_URL", self.DEEPSEEK_BASE_URL)
            model = os.environ.get("LLM_MODEL", self.DEEPSEEK_MODEL)
            self._llm = OpenAI(api_key=key, base_url=base_url)
            self.model_name = model
        else:
            self._llm = None
            self.model_name = "mock-model"
            
        # ── Action Registry ──
        self.actions: Dict[str, Callable[[dict], dict]] = {
            "read-code-context": self._action_read_code_context,
            "execute-command": self._action_execute_command,
        }

    @property
    def last_telemetry(self) -> Optional[ExecutionTelemetry]:
        """Telemetry from the most recent top-level run() call."""
        return self._last_telemetry

    # ── Public entry point ───────────────────────────────────────────────────
    def run(
        self,
        skill: Skill,
        input_data: dict,
        _call_stack: Optional[Set[str]] = None,
        _telem: Optional[ExecutionTelemetry] = None,
    ) -> Dict[str, Any]:
        """
        Execute a skill end-to-end and return the structured output.
        _call_stack: cycle detection (internal).
        _telem: accumulated telemetry threaded through nested calls.
        """
        if _call_stack is None:
            # Top-level call — create fresh telemetry
            _call_stack = set()
            _telem = ExecutionTelemetry(skill_name=skill.name)
            self._last_telemetry = _telem

        # ── Step 1: Validate input ───────────────────────────────────────
        self._emit("validate_input", "start",
                   f"Validating input against schema for '{skill.name}'",
                   skill_name=skill.name)
        result = self._validator.validate(skill, input_data)
        if not result.valid:
            self._emit("validate_input", "error",
                       f"Input invalid: {result.errors}", skill_name=skill.name)
            raise ExecutionError("validate_input", str(result.errors))
        self._emit("validate_input", "success",
                   "Input schema OK",
                   data={"fields_provided": list(input_data.keys())},
                   skill_name=skill.name)

        # ── Step 2: Check constraints ────────────────────────────────────
        self._emit("check_constraint", "start",
                   f"Checking host / resource / safety constraints for '{skill.name}'",
                   skill_name=skill.name)
        check = self._constraint_checker.check(skill.constraints)
        for name, detail in check.passed:
            self._emit("check_constraint", "info", f"✓ {name}: {detail}",
                       skill_name=skill.name)
        for name, detail in check.failed:
             self._emit("check_constraint", "error", f"✗ {name}: {detail}",
                       skill_name=skill.name)
        if not check.ok:
            raise ExecutionError("check_constraint",
                                 f"Constraint violations: {check.failed}")
        self._emit("check_constraint", "success",
                   f"All {len(check.passed)} constraint(s) satisfied",
                   skill_name=skill.name)

        # ── Step 3: Safety approval ──────────────────────────────────────
        if skill.constraints.safety.requires_approval:
            self._emit("safety_approval", "info",
                       "Skill requires human approval → auto-approved (demo mode)",
                       skill_name=skill.name)

        # ── Step 4: Dispatch ─────────────────────────────────────────────
        if skill.level == "composite":
            return self._run_composite(skill, input_data, _call_stack, _telem)
        return self._run_atomic(skill, input_data, _telem)

    # ── Atomic execution (LLM call + telemetry) ───────────────────────────────
    def _run_atomic(
        self,
        skill: Skill,
        input_data: dict,
        _telem: Optional[ExecutionTelemetry] = None,
    ) -> dict:
        # 1. Check if this is an Action Skill (Tool-based)
        if skill.name in self.actions:
            self._emit("execute_action", "start",
                       f"Executing system tool for atomic skill '{skill.name}'",
                       skill_name=skill.name)
            t0 = time.time()
            try:
                result = self.actions[skill.name](input_data)
                latency = (time.time() - t0) * 1000
                if _telem: _telem.latency_ms += latency
                
                self._emit("execute_action", "success",
                           f"Tool '{skill.name}' completed successfully",
                           data={"latency_ms": round(latency, 0)},
                           skill_name=skill.name)
                return result
            except Exception as e:
                raise ExecutionError("execute_action", f"Tool '{skill.name}' failed: {str(e)}")

        # 2. LLM-based execution
        prompt = self._build_prompt(skill, input_data)

        self._emit("call_llm", "start",
                   f"Calling {'MockLLM' if self.mock_mode else self.DEEPSEEK_MODEL}"
                   f" for atomic skill '{skill.name}'",
                   skill_name=skill.name)

        t0 = time.time()
        if self.mock_mode:
            raw = self._mock_response(skill)
            time.sleep(0.05)
        else:
            response = self._llm.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert AI assistant. "
                            "Always respond with valid JSON ONLY — no markdown, no explanation."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            raw = response.choices[0].message.content.strip()
            # Collect token telemetry
            if _telem is not None and hasattr(response, "usage") and response.usage:
                _telem.token_usage["prompt"]     += response.usage.prompt_tokens
                _telem.token_usage["completion"] += response.usage.completion_tokens
                _telem.token_usage["total"]      += response.usage.total_tokens

        llm_ms = (time.time() - t0) * 1000
        if _telem is not None:
            _telem.latency_ms += llm_ms

        self._emit("call_llm", "success",
                   "LLM responded",
                   data={
                       "raw_response": raw,
                       "preview": raw[:120] + ("..." if len(raw) > 120 else ""),
                       "latency_ms": round(llm_ms, 0),
                   },
                   skill_name=skill.name)

        # ── Parse output with retry ──────────────────────────────────────
        self._emit("parse_output", "start",
                   "Parsing LLM response into structured JSON output",
                   skill_name=skill.name)
        output, retries = self._parse_json_with_retry(raw)
        if _telem is not None:
            _telem.retry_count += retries
        self._emit("parse_output", "success",
                   "Output parsed successfully",
                   data={"output_keys": list(output.keys()), "retries": retries},
                   skill_name=skill.name)
        return output

    # ── Composite execution (sub-skill pipeline) ──────────────────────────────
    def _run_composite(
        self,
        skill: Skill,
        input_data: dict,
        call_stack: Set[str],
        _telem: Optional[ExecutionTelemetry] = None,
    ) -> dict:
        # Cycle detection
        if skill.name in call_stack:
            raise CyclicSkillError(
                "compose",
                f"Cyclic call detected! '{skill.name}' is already executing. "
                f"Current call stack: {call_stack}",
            )
        call_stack.add(skill.name)

        self._emit("compose", "start",
                   f"Composite skill '{skill.name}' → "
                   f"will execute {len(skill.sub_skills)} sub-skill(s) in sequence",
                   data={"sub_skills": skill.sub_skills},
                   skill_name=skill.name)

        accumulated: Dict[str, Any] = dict(input_data)

        for idx, sub_name in enumerate(skill.sub_skills, start=1):
            self._emit("compose", "info",
                       f"  [{idx}/{len(skill.sub_skills)}] Running sub-skill: '{sub_name}'",
                       skill_name=skill.name)

            sub_skill = self.registry.get(sub_name)
            if sub_skill is None:
                call_stack.discard(skill.name)
                raise ExecutionError(
                    "compose",
                    f"Sub-skill '{sub_name}' not found in registry. "
                    f"Available: {list(self.registry.skills.keys())}",
                )

            required_fields = sub_skill.input.get("required", [])
            input_props = sub_skill.input.get("properties", {})
            sub_input = {k: accumulated[k] for k in input_props if k in accumulated}

            self._emit("compose", "info",
                       f"     Input to '{sub_name}': {list(sub_input.keys())}",
                       data={k: str(v)[:80] for k, v in sub_input.items()
                             if not isinstance(v, str) or len(v) < 80},
                       skill_name=skill.name)

            # Pass telemetry through to nested runs
            sub_output = self.run(sub_skill, sub_input, call_stack, _telem)
            accumulated.update(sub_output)

            self._emit("compose", "info",
                       f"     '{sub_name}' returned: {list(sub_output.keys())}",
                       data={k: str(v)[:80] for k, v in sub_output.items()},
                       skill_name=skill.name)

        call_stack.discard(skill.name)

        output_props = skill.output.get("properties", {})
        final_output = {k: accumulated[k] for k in output_props if k in accumulated}

        self._emit("compose", "success",
                   f"Composite skill '{skill.name}' completed",
                   data={"output_keys": list(final_output.keys())},
                   skill_name=skill.name)
        return final_output

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _emit(
        self,
        step: str,
        status: str,
        message: str,
        data: Optional[dict] = None,
        skill_name: str = "",
    ) -> LogEvent:
        event = LogEvent(step=step, status=status, message=message,
                         data=data, skill_name=skill_name)
        self.log_callback(event)
        return event

    def _build_prompt(self, skill: Skill, input_data: dict) -> str:
        return (
            f"You are executing the AI agent skill: **{skill.name}**\n\n"
            f"## Instructions\n{skill.instructions}\n\n"
            f"## Input\n```json\n{json.dumps(input_data, indent=2, ensure_ascii=False)}\n```\n\n"
            f"## Required Output Format\n"
            f"Respond ONLY with a valid JSON object matching this schema:\n"
            f"```json\n{json.dumps(skill.output, indent=2)}\n```\n\n"
            f"Do NOT include any markdown fences, explanation, or text outside the JSON."
        )

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Strip optional markdown code fences, then JSON-parse."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        return json.loads(text.strip())

    def _parse_json_with_retry(self, text: str) -> Tuple[dict, int]:
        """
        Parse JSON from LLM response. On failure, attempt regex extraction.
        Returns (result_dict, retry_count).
        """
        try:
            return self._parse_json(text), 0
        except json.JSONDecodeError:
            pass
        # Retry: extract first {...} block
        m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0)), 1
            except json.JSONDecodeError:
                pass
        raise ExecutionError("parse_output",
                             f"Cannot parse LLM response as JSON: {text[:200]}")

    def _mock_response(self, skill: Skill) -> str:
        """Generates a generic valid JSON response based on the skill's output schema."""
        mock_data = {}
        props = skill.output.get("properties", {})
        for name, info in props.items():
            ptype = info.get("type", "string")
            if ptype == "string": mock_data[name] = f"Mock {name} for {skill.name}"
            elif ptype == "integer": mock_data[name] = 42
            elif ptype == "boolean": mock_data[name] = True
            elif ptype == "array": mock_data[name] = []
            else: mock_data[name] = {}
        return json.dumps(mock_data)

    # ── Built-in Actions (Tools) ──────────────────────────────────────────────
    def _action_read_code_context(self, input_data: dict) -> dict:
        """Reads source code lines around a specific location."""
        file_path = input_data.get("file")
        line_num = int(input_data.get("line", 0))
        window = int(input_data.get("window", 5))
        
        if not file_path:
            raise ValueError("Missing 'file' parameter for read-code-context")
            
        path = Path(file_path)
        if not path.exists():
            source_path = input_data.get("source_path")
            if source_path:
                candidate = Path(source_path)
                if candidate.is_dir():
                    path = candidate / file_path
                else:
                    path = candidate
            
        try:
            lines = path.read_text().splitlines()
            start = max(0, line_num - window - 1)
            end = min(len(lines), line_num + window)
            
            context = "\n".join([
                f"{i+1}: {lines[i]}" for i in range(start, end)
            ])
            
            return {
                "code_context": context,
                "file_found": str(path.absolute())
            }
        except Exception as e:
            return {"error": f"Could not read file {file_path}: {str(e)}"}

    def _action_execute_command(self, input_data: dict) -> dict:
        """Executes a shell command and returns output."""
        command = input_data.get("command")
        if not command:
            raise ValueError("Missing 'command' parameter for execute-command")
            
        import subprocess
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "status": "success" if result.returncode == 0 else "failed"
            }
        except Exception as e:
            return {"error": str(e), "status": "error"}
