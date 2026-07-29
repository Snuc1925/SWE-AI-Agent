"""ConstraintChecker — verifies host, resource, and safety constraints before skill execution."""
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Tuple

import psutil

from ..models.skill import SkillConstraints


@dataclass
class ConstraintCheckResult:
    ok: bool
    passed: List[Tuple[str, str]] = field(default_factory=list)
    failed: List[Tuple[str, str]] = field(default_factory=list)


class ConstraintChecker:
    def check(self, constraints: SkillConstraints) -> ConstraintCheckResult:
        passed: List[Tuple[str, str]] = []
        failed: List[Tuple[str, str]] = []

        # ── OS check ────────────────────────────────────────────────────
        if constraints.host.os:
            curr_os = platform.system().lower()  # "linux" / "darwin" / "windows"
            allowed = [o.lower() for o in constraints.host.os]
            if curr_os in allowed:
                passed.append(("host.os", curr_os))
            else:
                failed.append(("host.os", f"need {allowed}, got {curr_os}"))

        # ── Binary check ─────────────────────────────────────────────────
        for binary in constraints.host.binaries:
            if shutil.which(binary) is not None:
                passed.append((f"binary:{binary}", "found in PATH"))
            else:
                failed.append((f"binary:{binary}", "NOT found in PATH"))

        # ── Runtime check ────────────────────────────────────────────────
        for runtime in constraints.host.runtimes:
            name = runtime.get("name", "")
            req_ver = runtime.get("version", "")
            ok, detail = self._check_runtime(name, req_ver)
            if ok:
                passed.append((f"runtime:{name}", detail))
            else:
                failed.append((f"runtime:{name}", detail))

        # ── Memory check ─────────────────────────────────────────────────
        if constraints.resources.memory:
            avail_gb = psutil.virtual_memory().available / (1024 ** 3)
            need_gb = self._parse_memory_gb(constraints.resources.memory)
            if avail_gb >= need_gb:
                passed.append(("resources.memory", f"{avail_gb:.1f} GB available"))
            else:
                failed.append((
                    "resources.memory",
                    f"need {need_gb} GB, only {avail_gb:.1f} GB available",
                ))

        return ConstraintCheckResult(ok=len(failed) == 0, passed=passed, failed=failed)

    # ── Helpers ──────────────────────────────────────────────────────────
    _RUNTIME_CMDS: dict = {
        "java":   ["java", "-version"],
        "python": ["python3", "--version"],
        "node":   ["node", "--version"],
        "go":     ["go", "version"],
        "ruby":   ["ruby", "--version"],
    }

    def _check_runtime(self, name: str, version_req: str) -> Tuple[bool, str]:
        cmd = self._RUNTIME_CMDS.get(name.lower())
        if cmd is None:
            return True, f"{name} (version check not implemented, assumed OK)"
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5
            )
            output = (result.stdout + result.stderr).strip().split("\n")[0]
            return True, output
        except FileNotFoundError:
            return False, f"{name} executable not found"
        except subprocess.TimeoutExpired:
            return False, f"{name} version check timed out"

    def _parse_memory_gb(self, mem_str: str) -> float:
        s = mem_str.upper().strip()
        if s.endswith("GB"):
            return float(s[:-2])
        if s.endswith("MB"):
            return float(s[:-2]) / 1024
        return 0.0
