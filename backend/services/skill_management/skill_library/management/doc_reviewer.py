import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Tuple

from ..models.skill import Skill


@dataclass
class DocCriterion:
    id: str
    layer: str
    description: str
    points: int
    passed: bool = False
    note: str = ""


@dataclass
class DocScoreResult:
    skill_name: str
    total_score: int
    max_score: int = 100
    passed: bool = False            # score >= threshold
    threshold: int = 80
    criteria: List[DocCriterion] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "doc_score": self.total_score,
            "max_score": self.max_score,
            "passed": self.passed,
            "threshold": self.threshold,
            "criteria": [
                {
                    "id": c.id,
                    "layer": c.layer,
                    "description": c.description,
                    "points": c.points,
                    "passed": c.passed,
                    "note": c.note,
                }
                for c in self.criteria
            ],
        }


class SkillDocReviewer:
    """
    Data-driven Skill Reviewer.
    Uses a Rule Engine to evaluate criteria defined in XML.
    """
    THRESHOLD = 80
    CRITERIA_FILE = Path(__file__).parent.parent / "config" / "review_criteria.xml"

    def __init__(self):
        # Maps rule type to internal checker logic
        self.rule_handlers = {
            "not_empty": self._rule_not_empty,
            "min_words": self._rule_min_words,
            "min_items": self._rule_min_items,
            "exists": self._rule_exists,
        }

    def _get_value_by_path(self, obj: Any, path: str) -> Any:
        """Navigates through object attributes/dicts using dot notation (e.g. 'input.required')"""
        parts = path.split(".")
        current = obj
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        return current

    def review(self, skill: Skill) -> DocScoreResult:
        if not self.CRITERIA_FILE.exists():
            return DocScoreResult(skill.name, 0, passed=False)

        tree = ET.parse(self.CRITERIA_FILE)
        root = tree.getroot()
        
        results: List[DocCriterion] = []
        total_points = 0
        max_possible = 0

        for item in root.findall('Criterion'):
            crit_id = item.get('id')
            layer = item.get('layer')
            points = int(item.get('points'))
            desc = item.find('Description').text
            max_possible += points

            # Execute all rules for this criterion
            crit_passed = True
            notes = []
            
            rules = item.findall('Rule')
            for r in rules:
                r_type = r.get('type')
                path = r.get('path')
                target = r.get('value')
                
                handler = self.rule_handlers.get(r_type)
                if not handler:
                    notes.append(f"Unknown rule type: {r_type}")
                    crit_passed = False
                    continue
                
                val = self._get_value_by_path(skill, path)
                ok, msg = handler(val, target)
                if not ok:
                    crit_passed = False
                    notes.append(msg)

            results.append(DocCriterion(
                id=crit_id, layer=layer, description=desc,
                points=points, passed=crit_passed, note="; ".join(notes)
            ))
            if crit_passed:
                total_points += points

        return DocScoreResult(
            skill_name=skill.name,
            total_score=total_points,
            max_score=max_possible,
            passed=total_points >= self.THRESHOLD,
            threshold=self.THRESHOLD,
            criteria=results
        )

    # ── Rule Handlers ────────────────────────────────────────────────────────
    def _rule_not_empty(self, val: Any, target: Any) -> Tuple[bool, str]:
        if not val:
            return False, "Value is empty or missing"
        return True, ""

    def _rule_min_words(self, val: Any, target: Any) -> Tuple[bool, str]:
        if not isinstance(val, str):
            return False, "Target is not a string"
        words = len(re.findall(r'\w+', val))
        min_v = int(target)
        if words < min_v:
            return False, f"Word count {words} < {min_v}"
        return True, ""

    def _rule_min_items(self, val: Any, target: Any) -> Tuple[bool, str]:
        if not isinstance(val, (list, dict)):
            return False, "Target is not a list/dict"
        count = len(val)
        min_v = int(target)
        if count < min_v:
            return False, f"Item count {count} < {min_v}"
        return True, ""

    def _rule_exists(self, val: Any, target: Any) -> Tuple[bool, str]:
        if val is None:
            return False, "Field missing"
        return True, ""

    # ── Pretty print ──────────────────────────────────────────────────────────
    @staticmethod
    def print_result(result: DocScoreResult, use_color: bool = True) -> None:
        C = {
            "green": "\033[32m", "red": "\033[31m", "yellow": "\033[33m",
            "cyan": "\033[36m", "dim": "\033[2m", "bold": "\033[1m", "reset": "\033[0m",
        } if use_color else {k: "" for k in ["green", "red", "yellow", "cyan", "dim", "bold", "reset"]}

        verdict = (f"{C['green']}✅ PASS{C['reset']}" if result.passed
                   else f"{C['red']}❌ FAIL{C['reset']}")
        print(f"\n  📄 Doc Score: {C['bold']}{result.total_score}/{result.max_score}{C['reset']}  {verdict}")
        print(f"     (threshold: {result.threshold}/100)\n")

        prev_layer = ""
        for c in result.criteria:
            if c.layer != prev_layer:
                print(f"  {C['dim']}── Layer: {c.layer} ──────────────────────────────{C['reset']}")
                prev_layer = c.layer
            sym = f"{C['green']}✓{C['reset']}" if c.passed else f"{C['red']}✗{C['reset']}"
            pts = f"+{c.points}pts" if c.passed else f" {c.points}pts"
            note = f"  {C['dim']}{c.note}{C['reset']}" if c.note else ""
            print(f"  {sym} [{pts:>5}]  {c.description}{note}")
