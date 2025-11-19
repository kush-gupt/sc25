"""Tests for FluxOperatorClient helpers."""
from __future__ import annotations

from unittest.mock import MagicMock
import importlib.util
import pathlib

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "src" / "hpc_mcp_server" / "clients" / "flux_operator_client.py"
spec = importlib.util.spec_from_file_location("flux_operator_client", MODULE_PATH)
foc = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(foc)


def test_delete_minicluster_passes_delete_options(monkeypatch) -> None:
    """Ensure delete uses keyword body compatible with kubernetes>=28."""

    mock_api = MagicMock()
    monkeypatch.setattr(foc.FluxOperatorClient, "_configure_client", lambda self: None)
    monkeypatch.setattr(foc.client, "CustomObjectsApi", lambda: mock_api)

    operator = foc.FluxOperatorClient(namespace="flux-operator", default_minicluster="demo")
    operator.delete_minicluster(name="custom", namespace="flux-operator")

    args, kwargs = mock_api.delete_namespaced_custom_object.call_args
    assert args == (foc.GROUP, foc.VERSION, "flux-operator", foc.PLURAL, "custom")
    assert "body" in kwargs
    assert isinstance(kwargs["body"], foc.client.V1DeleteOptions)
    assert kwargs["body"].propagation_policy == "Foreground"

