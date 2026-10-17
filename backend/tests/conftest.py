import os

os.environ["VIDEO_PROVIDER"] = "mock"
os.environ["REASONING_PROVIDER"] = "none"

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_PROVIDER", "mock")
    monkeypatch.setenv("REASONING_PROVIDER", "none")
    monkeypatch.setenv("SHERLOCKED_DB", str(tmp_path / "sherlocked.db"))
    with TestClient(create_app()) as test_client:
        yield test_client
