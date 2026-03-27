from fastapi.testclient import TestClient

from antibot_image_solver.api.app import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["service"] == "antibot-image-solver"
