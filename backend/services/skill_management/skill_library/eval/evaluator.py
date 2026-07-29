"""
SkillEvaluator — Layer 5: Evaluate skill performance via test cases.

Two evaluation dimensions:
  1. Test Case Execution  → Pass Rate, Accuracy, Latency, Token Usage, etc.
  2. Doc Score            → see doc_reviewer.py
"""
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..models.skill import Skill, TestCase
from ..registry.registry import SkillRegistry
from ..execution.executor import SkillExecutor


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclasses
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class CriterionResult:
    expression: str
    passed: bool
    error: str = ""          # error message if evaluation itself failed


@dataclass
class TestCaseResult:
    tc_id: str
    tc_name: str
    tags: List[str]
    passed: bool
    criteria_results: List[CriterionResult]
    output: Optional[Dict[str, Any]]
    expected: Dict[str, Any]
    latency_ms: float
    token_usage: Dict[str, int]
    retry_count: int
    error: str = ""          # execution error (not criterion failure)


@dataclass
class EvaluationReport:
    skill_name: str
    skill_version: str
    mock_mode: bool
    total: int
    passed: int
    failed: int

    # Aggregated metrics
    pass_rate: float         # %
    accuracy: float          # avg per-field accuracy %
    latency_p50: float       # ms
    latency_p95: float       # ms
    avg_tokens: float
    retry_rate: float        # %
    consistency_score: Optional[float] = None   # set by consistency run

    test_results: List[TestCaseResult] = field(default_factory=list)

    # Metric target checks
    metric_checks: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "skill_version": self.skill_version,
            "mock_mode": self.mock_mode,
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "pass_rate_pct": round(self.pass_rate, 1),
            },
            "metrics": {
                "accuracy_pct": round(self.accuracy, 1),
                "latency_p50_ms": round(self.latency_p50, 0),
                "latency_p95_ms": round(self.latency_p95, 0),
                "avg_tokens": round(self.avg_tokens, 0),
                "retry_rate_pct": round(self.retry_rate, 1),
            },
            "metric_checks": self.metric_checks,
            "test_results": [
                {
                    "id": r.tc_id,
                    "name": r.tc_name,
                    "passed": r.passed,
                    "latency_ms": round(r.latency_ms, 0),
                    "tokens": r.token_usage.get("total", 0),
                    "retries": r.retry_count,
                    "error": r.error,
                    "criteria": [
                        {"expr": c.expression, "passed": c.passed, "error": c.error}
                        for c in r.criteria_results
                    ],
                }
                for r in self.test_results
            ],
        }


# ─────────────────────────────────────────────────────────────────────────────
# SkillEvaluator
# ─────────────────────────────────────────────────────────────────────────────
class SkillEvaluator:
    """
    Runs a skill's test_cases and computes evaluation metrics.

    Usage:
        evaluator = SkillEvaluator(registry, mock_mode=False)
        report = evaluator.evaluate(skill)
        print(json.dumps(report.to_dict(), indent=2))
    """

    def __init__(
        self,
        registry: SkillRegistry,
        api_key: Optional[str] = None,
        mock_mode: bool = False,
        verbose: bool = True,
    ):
        self.registry = registry
        self.api_key = api_key
        self.mock_mode = mock_mode
        self.verbose = verbose

    # ── Public API ────────────────────────────────────────────────────────────
    def evaluate(self, skill: Skill) -> EvaluationReport:
        """Run all test_cases for a skill and return an EvaluationReport."""
        if not skill.test_cases:
            raise ValueError(
                f"Skill '{skill.name}' has no test_cases defined in SKILL.md. "
                "Add a 'test_cases:' section to evaluate it."
            )

        executor = SkillExecutor(
            registry=self.registry,
            api_key=self.api_key,
            mock_mode=self.mock_mode,
            log_callback=None,
        )

        results: List[TestCaseResult] = []
        for tc in skill.test_cases:
            result = self._run_test_case(executor, skill, tc)
            results.append(result)
            if self.verbose:
                self._print_tc_result(result)

        return self._aggregate(skill, results)

    def consistency_check(self, skill: Skill, tc: TestCase, runs: int = 3) -> float:
        """
        Run a single test_case N times, return consistency score (%).
        Consistency = fraction of runs that produce the same output as the first run.
        """
        executor = SkillExecutor(
            registry=self.registry,
            api_key=self.api_key,
            mock_mode=self.mock_mode,
            log_callback=None,
        )
        outputs = []
        for _ in range(runs):
            try:
                out = executor.run(skill, dict(tc.input))
                outputs.append(json.dumps(out, sort_keys=True))
            except Exception:
                outputs.append("__ERROR__")

        if not outputs:
            return 0.0
        reference = outputs[0]
        matches = sum(1 for o in outputs if o == reference)
        return round(matches / runs * 100, 1)

    # ── Internals ─────────────────────────────────────────────────────────────
    def _run_test_case(
        self, executor: SkillExecutor, skill: Skill, tc: TestCase
    ) -> TestCaseResult:
        t0 = time.time()
        output = None
        error = ""
        try:
            output = executor.run(skill, dict(tc.input))
        except Exception as exc:
            error = str(exc)

        latency_ms = (time.time() - t0) * 1000
        telem = executor.last_telemetry

        # Evaluate acceptance criteria
        criteria_results = []
        all_passed = True
        if error:
            all_passed = False
        else:
            for expr in tc.acceptance:
                ok, err = _eval_criterion(expr, output or {}, tc.expected_output)
                criteria_results.append(CriterionResult(expr, ok, err))
                if not ok:
                    all_passed = False

        # Per-field accuracy (exact match between output and expected)
        field_accuracy = _field_accuracy(output or {}, tc.expected_output)

        return TestCaseResult(
            tc_id=tc.id,
            tc_name=tc.name,
            tags=tc.tags,
            passed=all_passed,
            criteria_results=criteria_results,
            output=output,
            expected=tc.expected_output,
            latency_ms=latency_ms,
            token_usage=telem.token_usage if telem else {"prompt": 0, "completion": 0, "total": 0},
            retry_count=telem.retry_count if telem else 0,
            error=error,
        )

    def _aggregate(self, skill: Skill, results: List[TestCaseResult]) -> EvaluationReport:
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        latencies = [r.latency_ms for r in results if r.latency_ms > 0]
        tokens = [r.token_usage.get("total", 0) for r in results]
        retries = [r.retry_count for r in results]
        per_field_acc = [_field_accuracy(r.output or {}, r.expected) for r in results]

        pass_rate = (passed / total * 100) if total else 0.0
        accuracy = (sum(per_field_acc) / len(per_field_acc) * 100) if per_field_acc else 0.0

        sorted_lat = sorted(latencies) if latencies else [0]
        p50 = sorted_lat[len(sorted_lat) // 2]
        p95 = sorted_lat[int(len(sorted_lat) * 0.95)] if len(sorted_lat) > 1 else sorted_lat[-1]
        avg_tok = sum(tokens) / len(tokens) if tokens else 0
        retry_rate = (sum(retries) / total * 100) if total else 0.0

        # Check against skill-defined metric targets
        metric_checks = _check_metric_targets(skill.metrics, {
            "pass_rate": pass_rate,
            "latency_p95": p95,
            "avg_tokens": avg_tok,
            "retry_rate": retry_rate,
            "accuracy": accuracy,
        })

        return EvaluationReport(
            skill_name=skill.name,
            skill_version=skill.version,
            mock_mode=self.mock_mode,
            total=total,
            passed=passed,
            failed=total - passed,
            pass_rate=pass_rate,
            accuracy=accuracy,
            latency_p50=p50,
            latency_p95=p95,
            avg_tokens=avg_tok,
            retry_rate=retry_rate,
            test_results=results,
            metric_checks=metric_checks,
        )

    def _print_tc_result(self, r: TestCaseResult):
        icon = "✅" if r.passed else "❌"
        tok = r.token_usage.get("total", 0)
        print(f"  {icon} {r.tc_id:<10} {r.tc_name:<35} {r.latency_ms:>6.0f}ms  {tok:>5} tokens")
        if not r.passed:
            for c in r.criteria_results:
                if not c.passed:
                    sym = "❌" if not c.error else "⚠️"
                    print(f"       {sym} FAIL: {c.expression}")
                    if c.error:
                        print(f"           └─ {c.error}")
            if r.error:
                print(f"       ✗ Execution error: {r.error}")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _eval_criterion(expression: str, output: dict, expected: dict) -> Tuple[bool, str]:
    """
    Safely evaluate a criterion expression.
    Variables available: output (dict), expected (dict).
    Example: "output['file'] == expected['file']"
    Also supports dot notation: "output.file == expected.file"
    """
    # Convert dot-notation to subscript for eval safety
    expr = _dot_to_subscript(expression)
    safe_ns = {
        "__builtins__": {},
        "output": output,
        "expected": expected,
        "abs": abs, "len": len, "str": str, "int": int,
        "float": float, "any": any, "all": all, "round": round,
    }
    try:
        result = eval(expr, safe_ns)  # noqa: S307 — controlled environment
        return bool(result), ""
    except Exception as exc:
        return False, f"eval error: {exc}"


def _dot_to_subscript(expr: str) -> str:
    """Convert 'output.file' → "output['file']" for safe eval."""
    import re
    return re.sub(
        r"\b(output|expected)\.([a-zA-Z_][a-zA-Z0-9_]*)\b",
        lambda m: f"{m.group(1)}['{m.group(2)}']",
        expr,
    )


def _field_accuracy(output: dict, expected: dict) -> float:
    """Fraction of expected fields that match exactly in output (0.0–1.0)."""
    if not expected:
        return 1.0
    matches = 0
    for k, v in expected.items():
        if k in output and str(output[k]).strip() == str(v).strip():
            matches += 1
    return matches / len(expected)


def _check_metric_targets(metric_spec: dict, actual: dict) -> Dict[str, bool]:
    """
    Compare actual metric values against target specs from SKILL.md.
    target strings like "≥ 80%", "< 5000", "≤ 10%"
    """
    import re
    results = {}
    for metric_name, spec in metric_spec.items():
        target_str = spec.get("target", "") if isinstance(spec, dict) else str(spec)
        actual_val = actual.get(metric_name)
        if actual_val is None or not target_str:
            continue
        # Parse "≥ 80%", "< 5000", "≤ 10%" etc.
        m = re.match(r"([≥≤<>]=?|>=|<=)\s*([\d.]+)", target_str.replace("%", ""))
        if not m:
            continue
        op, tgt = m.group(1), float(m.group(2))
        av = float(actual_val)
        if op in ("≥", ">="):
            results[metric_name] = av >= tgt
        elif op in ("≤", "<="):
            results[metric_name] = av <= tgt
        elif op == ">":
            results[metric_name] = av > tgt
        elif op == "<":
            results[metric_name] = av < tgt
    return results
