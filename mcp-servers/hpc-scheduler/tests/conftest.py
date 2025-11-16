"""Shared pytest configuration and fixtures for all tests."""

import os
import pytest


@pytest.fixture(autouse=True)
def setup_mock_backend():
    """
    Automatically enable mock backends for all tests.
    This fixture runs before each test and resets the cluster registry.
    """
    # Enable mock backend
    os.environ["USE_MOCK_BACKENDS"] = "true"

    # Reset the cluster registry to ensure fresh adapters
    from src.cluster_registry import reset_registry
    reset_registry()

    yield

    # Cleanup after test
    reset_registry()
