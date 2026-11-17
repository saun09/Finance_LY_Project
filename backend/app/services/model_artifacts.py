"""Version-checked loading for persisted scikit-learn model artifacts."""

from __future__ import annotations

import json
import platform
import warnings
from pathlib import Path
from typing import Any

import joblib
import numpy
import sklearn


def runtime_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scikit_learn": sklearn.__version__,
        "joblib": joblib.__version__,
    }


def _versions_compatible(name: str, recorded: str | None, current: str) -> bool:
    """numpy/scikit-learn/joblib must match exactly (they define the pickle
    format and are pinned in requirements.txt). Python only needs the same
    major.minor: patch releases don't change pickling, and hosts such as
    Render pick their own patch version."""
    if recorded is None:
        return False
    if name == "python":
        return recorded.split(".")[:2] == current.split(".")[:2]
    return recorded == current


def load_versioned_model(
    model_path: Path,
    *,
    sidecar_path: Path | None = None,
) -> Any:
    """Load a joblib estimator only when its required runtime versions match."""
    model_path = Path(model_path)
    sidecar_path = Path(sidecar_path or model_path.with_suffix(".json"))
    if not model_path.is_file():
        raise FileNotFoundError(f"model artifact not found: {model_path}")
    if not sidecar_path.is_file():
        raise FileNotFoundError(f"model version sidecar not found: {sidecar_path}")

    metadata = json.loads(sidecar_path.read_text(encoding="utf-8"))
    recorded_versions = metadata.get("versions")
    if not isinstance(recorded_versions, dict):
        raise ValueError(f"model sidecar has no versions mapping: {sidecar_path}")
    current_versions = runtime_versions()
    mismatches = {
        name: (recorded_versions.get(name), current)
        for name, current in current_versions.items()
        if not _versions_compatible(name, recorded_versions.get(name), current)
    }
    if mismatches:
        detail = ", ".join(
            f"{name}: artifact={recorded!r}, runtime={current!r}"
            for name, (recorded, current) in mismatches.items()
        )
        raise RuntimeError(f"incompatible model runtime versions for {model_path}: {detail}")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = joblib.load(model_path)
    version_warnings = [
        str(item.message)
        for item in caught
        if "trying to unpickle estimator" in str(item.message).lower()
        or "inconsistentversionwarning" in type(item.message).__name__.lower()
    ]
    if version_warnings:
        raise RuntimeError(
            f"model loader emitted scikit-learn compatibility warnings for {model_path}: "
            + " | ".join(version_warnings)
        )
    for item in caught:
        warnings.warn(item.message, item.category, stacklevel=2)
    return model
