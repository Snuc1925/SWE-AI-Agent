"""InputValidator — validates user-supplied JSON against a skill's input schema."""
from dataclasses import dataclass, field
from typing import List

import jsonschema

from ..models.skill import Skill


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


class InputValidator:
    def validate(self, skill: Skill, user_input: dict) -> ValidationResult:
        """
        Validate `user_input` against `skill.input` JSON Schema.
        Returns ValidationResult(valid=True) if the schema is empty (no constraints).
        """
        schema = skill.input
        if not schema:
            return ValidationResult(valid=True)
        try:
            jsonschema.validate(instance=user_input, schema=schema)
            return ValidationResult(valid=True)
        except jsonschema.ValidationError as exc:
            return ValidationResult(valid=False, errors=[exc.message])
        except jsonschema.SchemaError as exc:
            return ValidationResult(valid=False, errors=[f"Schema error: {exc.message}"])
