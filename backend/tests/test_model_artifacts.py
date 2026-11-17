import json

import pytest

from app.services.model_artifacts import load_versioned_model, runtime_versions


def test_model_loader_rejects_runtime_version_mismatch_before_deserialization(tmp_path):
    model_path = tmp_path / "model.pkl"
    model_path.write_bytes(b"not a serialized model")
    versions = runtime_versions()
    versions["scikit_learn"] = "0.0.0"
    model_path.with_suffix(".json").write_text(
        json.dumps({"versions": versions}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="scikit_learn"):
        load_versioned_model(model_path)
