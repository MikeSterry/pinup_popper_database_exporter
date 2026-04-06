# tests/controllers/test_health_controller.py

import pytest
from flask import Flask

from app.controllers.health_controller import health_bp


@pytest.fixture
def app():
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    flask_app.register_blueprint(health_bp)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_health_returns_200(client):
    response = client.get("/health")

    assert response.status_code == 200


def test_health_returns_expected_json(client):
    response = client.get("/health")

    assert response.is_json
    assert response.get_json() == {"status": "ok"}


def test_health_only_allows_get(client):
    response = client.post("/health")

    assert response.status_code == 405