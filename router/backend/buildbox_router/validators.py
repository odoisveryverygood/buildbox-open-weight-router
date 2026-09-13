"""Bounded deterministic validators. They never execute generated code or URLs."""

import ast
import re

from .execution_contracts import ValidationObservation, ValidationRule


def validate_rules(
    content: str | None, rules: tuple[ValidationRule, ...]
) -> tuple[ValidationObservation, ...]:
    result = []
    for rule in rules:
        text = content or ""
        valid = len(text.encode()) <= 65536
        detail = "Output exceeds validator byte bound"
        if valid and rule.kind == "required_terms":
            missing = [v for v in rule.values if v.casefold() not in text.casefold()]
            valid, detail = (
                not missing,
                f"{len(missing)} required literal terms missing; not semantic truth verification",
            )
        elif valid and rule.kind == "python_syntax":
            try:
                ast.parse(text)
                valid, detail = True, "Python syntax parsed; code was not executed or tested"
            except (SyntaxError, ValueError, RecursionError, MemoryError):
                valid, detail = False, "Python syntax invalid or parser bound exceeded"
        elif valid and rule.kind == "citation_allowlist":
            urls = re.findall(r"https?://[^\s<>\"\])]+", text)
            valid = bool(urls) and all(u in rule.values for u in urls)
            detail = (
                "Citations checked against exact approved URLs; source entailment not established"
            )
        result.append(ValidationObservation(kind=rule.kind, passed=valid, detail=detail))
    return tuple(result)
