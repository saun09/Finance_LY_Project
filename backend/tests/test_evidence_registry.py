import ast
from pathlib import Path

from app.evidence.registry import (
    IGNORED_NUMERIC_CONFIG_ROOTS,
    TRACKED_CONFIG_ROOTS,
    collect_config_values,
    load_evidence_registry,
    registry_issues,
)


CONFIG_DIRECTORY = Path(__file__).parents[1] / "app" / "services"


def _contains_numeric_config_value(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, (int, float)):
            if not isinstance(child.value, bool):
                return True
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "Decimal"
            and child.args
            and isinstance(child.args[0], ast.Constant)
            and isinstance(child.args[0].value, str)
        ):
            try:
                float(child.args[0].value)
            except ValueError:
                continue
            return True
    return False


def _numeric_module_constants(config_file: str) -> set[str]:
    module = ast.parse((CONFIG_DIRECTORY / config_file).read_text(encoding="utf-8"))
    constants: set[str] = set()
    for statement in module.body:
        if isinstance(statement, ast.Assign):
            names = [target.id for target in statement.targets if isinstance(target, ast.Name)]
            value = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            names = [statement.target.id]
            value = statement.value
        else:
            continue
        if value is not None and _contains_numeric_config_value(value):
            constants.update(names)
    return constants


def test_all_numeric_config_roots_are_tracked_or_explicitly_excluded():
    for config_file in TRACKED_CONFIG_ROOTS:
        declared = set(TRACKED_CONFIG_ROOTS[config_file])
        declared.update(IGNORED_NUMERIC_CONFIG_ROOTS.get(config_file, {}))
        assert _numeric_module_constants(config_file) == declared


def test_registry_covers_all_live_values_without_drift():
    assert registry_issues() == []
    assert len(load_evidence_registry().entries) == len(collect_config_values())


def test_registry_validation_reports_changed_values_and_stale_paths():
    registry = load_evidence_registry()
    registry.entries[0].value += 1
    registry.entries[1].constant_name = "REMOVED_CONFIG_PATH"

    issues = registry_issues(registry)

    assert any("registry value mismatch" in issue for issue in issues)
    assert any("missing or untracked config constant" in issue for issue in issues)


def test_unverified_entries_keep_sources_unfilled_and_searchable():
    registry = load_evidence_registry()
    assert registry.entries
    for entry in registry.entries:
        assert entry.verification_status == "unverified"
        assert entry.source_citation == "TO_FILL"
        assert entry.source_url == "TO_FILL"
        assert entry.retrieved_date == "TO_FILL"
        assert 2 <= len(entry.suggested_search_queries) <= 3
