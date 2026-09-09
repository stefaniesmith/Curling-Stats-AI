from fastapi.testclient import TestClient


def test_healthcheck(api_client: TestClient) -> None:
    client = api_client

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
