from __future__ import annotations

from tests.conftest import login


def test_login_and_me(client):
    login(client)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "owner@trattoriamadonnina.it"
    assert payload["user"]["role"] == "owner"


def test_logout_clears_session(client):
    login(client)
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 401
