"""Failed model initialization must leave the service degraded."""
import importlib
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

api = importlib.import_module("api.app")


@pytest.mark.parametrize("failure", ["missing", "invalid", "explainer"])
def test_failed_model_initialization(tmp_path, monkeypatch, failure):
    db = tmp_path / "demo.db"
    schema = Path(__file__).resolve().parents[2] / "data" / "schema.sql"
    with sqlite3.connect(db) as connection:
        connection.executescript(schema.read_text())
    class Model:
        def predict(self, rows):
            return []

    bundle = {
        "model": Model(), "model_version": "test", "features": ["x"],
        "numeric_features": ["x"], "categorical_features": [], "categories": {},
    }
    if failure == "missing":
        del bundle["model_version"]
    elif failure == "invalid":
        bundle["categories"] = None
    monkeypatch.setattr(api, "load_bundle", lambda path: bundle)
    calls = []
    def broken_explainer(bundle):
        calls.append(bundle)
        raise ValueError("explainer failed")
    monkeypatch.setattr(api, "Explainer", broken_explainer)
    app = api.create_app(db_path=db)
    with TestClient(app) as client:
        assert bool(calls) == (failure == "explainer")
        assert app.state.bundle is None
        assert app.state.explainer is None
        assert app.state.load_error
        assert client.get("/api/health").json()["status"] == "degraded"
        assert client.get("/api/portfolio").status_code == 503
        assert client.post(
            "/api/leads/example/counterfactual", json={"discovery_meeting": True}
        ).status_code == 503
