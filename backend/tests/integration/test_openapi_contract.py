"""Contract test verifying exact OpenAPI schema agreement between FastAPI and spec."""

from pathlib import Path

import pytest
import yaml

from app.main import app


@pytest.mark.integration
def test_openapi_contract_matches_specification() -> None:
    """Verify paths, HTTP methods, and status codes match specs/api/openapi.yaml."""
    spec_path = Path(__file__).resolve().parents[3] / "specs" / "api" / "openapi.yaml"
    assert spec_path.exists(), f"OpenAPI spec not found at {spec_path}"

    with open(spec_path, encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    app_schema = app.openapi()

    spec_paths = spec.get("paths", {})
    app_paths = app_schema.get("paths", {})

    # Check each spec path and operation
    for path, path_item in spec_paths.items():
        assert path in app_paths, f"Spec path '{path}' missing in FastAPI app"

        for method, op_spec in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue

            app_op = app_paths[path].get(method.lower())
            assert app_op is not None, f"Method '{method.upper()}' for '{path}' missing in app"

            # Check operationId
            expected_op_id = op_spec.get("operationId")
            if expected_op_id:
                msg = f"OperationId mismatch on {method.upper()} {path}"
                assert app_op.get("operationId") == expected_op_id, msg

            # Check responses
            expected_responses = op_spec.get("responses", {})
            app_responses = app_op.get("responses", {})

            for status_code in expected_responses:
                err = f"Status code '{status_code}' missing on {method.upper()} {path}"
                assert str(status_code) in app_responses, err
