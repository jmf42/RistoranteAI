from __future__ import annotations

from tests.conftest import login


def test_login_and_me(client):
    login(client)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "owner@trattoriamadonnina.it"
    assert payload["user"]["role"] == "owner"
