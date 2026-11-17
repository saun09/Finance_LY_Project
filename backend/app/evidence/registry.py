from __future__ import annotations

import json
import math
from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services import (
    allocation_config,
    asset_classification_config,
    debt_leak_config,
    drift_detection_config,
    gamification_config,
    risk_profile_config,
)
from app.services.risk_profile import CapacityInputs, CapacityResult
from app.services.risk_profile_config import CapacityRuleTable

from app.evidence.schema import EvidenceEntry, EvidenceRegistry


REGISTRY_PATH = Path(__file__).with_name("evidence_registry.json")
BACKEND_ROOT = REGISTRY_PATH.parents[2]

_CONFIG_MODULES = {
    "risk_profile_config.py": risk_profile_config,
    "allocation_config.py": allocation_config,
    "asset_classification_config.py": asset_classification_config,
    "debt_leak_config.py": debt_leak_config,
    "gamification_config.py": gamification_config,
    "drift_detection_config.py": drift_detection_config,
}

TRACKED_CONFIG_ROOTS = {
    "risk_profile_config.py": (
        "_SCALE_5",
        "QUESTIONNAIRE_V1",
        "QUESTIONNAIRE_V2",
        "CAPACITY_RULE_TABLE_V1",
    ),
    "allocation_config.py": (
        "RISK_LADDER_BOUNDS_V1",
        "_EXPECTED_RETURN",
        "_VOLATILITY",
        "_CORRELATION",
        "RISK_FREE_RATE_V1",
    ),
    "asset_classification_config.py": ("HOLDING_TYPE_PROFILES_V1",),
    "debt_leak_config.py": (
        "DUPLICATE_CATEGORY_SIMILARITY_THRESHOLD",
        "IDLE_CASH_REFERENCE_RATE_ANNUAL_BPS",
        "IDLE_CASH_BUFFER_TARGET_MONTHS",
        "MAX_AMORTIZATION_MONTHS",
    ),
    "gamification_config.py": (
        "BUFFER_MONTHS_THRESHOLDS",
        "SUBSCRIPTION_CANCELLED_COUNT_THRESHOLDS",
        "CONSISTENCY_MONTH_THRESHOLDS",
    ),
    "drift_detection_config.py": (
        "HYSTERESIS_CYCLES_TO_RAISE_TIER",
        "HYSTERESIS_CYCLES_TO_LOWER_TIER",
        "DRAWDOWN_FREEZE_WINDOW_CYCLES",
        "MIN_AGREEING_SIGNAL_FAMILIES",
        "BEHAVIORAL_SIGNAL_WINDOW_MONTHS",
        "CAPACITY_SIGNAL_WINDOW_MONTHS",
        "BEHAVIORAL_SIGNAL_DEADBAND_PCT",
    ),
}

IGNORED_NUMERIC_CONFIG_ROOTS = {
    "gamification_config.py": {
        "ROADMAP": "ordered lesson index, not a financial decision threshold",
        "QUIZ_QUESTIONS": "answer-option indices, not a financial decision threshold",
    }
}


def _json_value(value: int | float | Decimal) -> int | float:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"non-finite config value: {value!r}")
        return value
    raise TypeError(f"not a numeric config value: {value!r}")


def _walk_numeric(value: Any, path: str) -> list[tuple[str, int | float]]:
    if isinstance(value, Enum):
        return []
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float, Decimal)):
        return [(path, _json_value(value))]
    if isinstance(value, dict):
        found: list[tuple[str, int | float]] = []
        for key, child in value.items():
            if isinstance(key, tuple):
                key_path = "__".join(str(part.value if isinstance(part, Enum) else part) for part in key)
            else:
                key_path = str(key.value if isinstance(key, Enum) else key)
            found.extend(_walk_numeric(child, f"{path}.{key_path}"))
        return found
    if is_dataclass(value) and not isinstance(value, type):
        found = []
        for item in fields(value):
            child = getattr(value, item.name)
            if item.name in {"questions", "options"} and isinstance(child, tuple):
                for index, option in enumerate(child):
                    label = getattr(option, "id", getattr(option, "value", None))
                    child_path = f"{path}.{item.name}[{label}]" if label is not None else f"{path}.{item.name}[{index}]"
                    found.extend(_walk_numeric(option, child_path))
            else:
                found.extend(_walk_numeric(child, f"{path}.{item.name}"))
        return found
    if isinstance(value, (tuple, list)):
        found = []
        for index, child in enumerate(value):
            found.extend(_walk_numeric(child, f"{path}[{index}]"))
        return found
    return []


def collect_config_values() -> dict[str, int | float]:
    """Return all numeric leaves in the reviewed rule-bearing config roots."""
    inventory: dict[str, int | float] = {}
    for config_file, root_names in TRACKED_CONFIG_ROOTS.items():
        module = _CONFIG_MODULES[config_file]
        for root_name in root_names:
            if not hasattr(module, root_name):
                raise ValueError(f"{config_file} no longer defines tracked root {root_name}")
            root = getattr(module, root_name)
            for constant_name, value in _walk_numeric(root, root_name):
                key = f"{config_file}:{constant_name}"
                if key in inventory:
                    raise ValueError(f"duplicate config evidence path: {key}")
                inventory[key] = value
    return inventory


def _float_equal(left: int | float, right: int | float) -> bool:
    return Decimal(str(left)) == Decimal(str(right))


def load_evidence_registry(path: Path | None = None) -> EvidenceRegistry:
    """Load and validate the registry document against its Pydantic schema."""
    registry_path = path or REGISTRY_PATH
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    return EvidenceRegistry.model_validate(payload)


@lru_cache(maxsize=1)
def _default_registry() -> EvidenceRegistry:
    return load_evidence_registry()


def evidence_entries_by_id() -> dict[str, EvidenceEntry]:
    entries = _default_registry().entries
    return {entry.id: entry for entry in entries}


def evidence_id_by_config_path() -> dict[str, str]:
    return {
        f"{entry.config_file}:{entry.constant_name}": entry.id
        for entry in _default_registry().entries
    }


def evidence_ids_for_capacity(
    inputs: CapacityInputs,
    capacity: CapacityResult,
    rule_table: CapacityRuleTable,
) -> list[str]:
    """Resolve registry ids for the numeric rules used by binding components."""
    by_path = evidence_id_by_config_path()
    ids: list[str] = []
    root = "risk_profile_config.py:CAPACITY_RULE_TABLE_V1"
    ceiling_by_component = {component.name: component for component in capacity.components}
    for component_name in (
        "buffer_months",
        "emi_to_income_ratio",
        "income_stability",
        "insurance_adequacy",
    ):
        component = ceiling_by_component[component_name]
        if not component.applicable or component.ceiling != capacity.ceiling:
            continue
        if component_name == "income_stability":
            stability_key = (
                "regular_income_ceiling"
                if inputs.income_stability.value == "regular"
                else "irregular_income_ceiling"
            )
            path = f"{root}.{stability_key}"
            if path in by_path:
                ids.append(by_path[path])
            continue

        if component_name == "buffer_months":
            value = float(inputs.buffer_coverage_months)
            bands = rule_table.buffer_months_bands
            band_root = "buffer_months_bands"
        elif component_name == "emi_to_income_ratio":
            value = float(inputs.emi_to_income_ratio)
            bands = rule_table.emi_to_income_bands
            band_root = "emi_to_income_bands"
        else:
            required = inputs.monthly_income_paise * 12 * rule_table.required_life_cover_income_multiple
            value = float(Decimal(inputs.total_life_cover_paise) / Decimal(required)) if required else 0.0
            bands = rule_table.insurance_coverage_bands
            band_root = "insurance_coverage_bands"
            multiple_path = f"{root}.required_life_cover_income_multiple"
            if multiple_path in by_path:
                ids.append(by_path[multiple_path])

        matched_index = next(
            (
                index
                for index, band in enumerate(bands)
                if value >= band.min_value and (band.max_value is None or value < band.max_value)
            ),
            None,
        )
        if matched_index is None:
            raise ValueError(f"no {band_root} rule matches {value}")
        for field_name in ("min_value", "max_value", "ceiling"):
            path = f"{root}.{band_root}[{matched_index}].{field_name}"
            if path in by_path:
                ids.append(by_path[path])
    return list(dict.fromkeys(ids))


def registry_issues(registry: EvidenceRegistry | None = None) -> list[str]:
    """Return missing, stale, duplicate, or changed config-entry diagnostics."""
    registry = registry or _default_registry()
    issues: list[str] = []
    expected = collect_config_values()
    actual: dict[str, EvidenceEntry] = {}
    seen_ids: set[str] = set()
    for entry in registry.entries:
        key = f"{entry.config_file}:{entry.constant_name}"
        if entry.id in seen_ids:
            issues.append(f"duplicate registry id: {entry.id}")
        seen_ids.add(entry.id)
        if key in actual:
            issues.append(f"duplicate registry constant path: {key}")
        actual[key] = entry

    for key, value in expected.items():
        entry = actual.get(key)
        if entry is None:
            issues.append(f"missing registry entry: {key}")
        elif not _float_equal(entry.value, value):
            issues.append(
                f"registry value mismatch for {key}: registry={entry.value!r}, config={value!r}"
            )
    for key in actual.keys() - expected.keys():
        issues.append(f"registry entry refers to missing or untracked config constant: {key}")
    return issues


def validate_registry() -> EvidenceRegistry:
    registry = _default_registry()
    issues = registry_issues(registry)
    if issues:
        raise ValueError("evidence registry is out of sync:\n- " + "\n- ".join(issues))
    return registry


def evidence_ids_for_binding(
    inputs: CapacityInputs,
    capacity: CapacityResult,
    rule_table: CapacityRuleTable,
) -> list[str]:
    """Public concise alias for IDs attached to the binding capacity rules."""
    return evidence_ids_for_capacity(inputs, capacity, rule_table)
