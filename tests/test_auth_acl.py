def test_login_page_open(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert "Войти" in r.text or "login" in r.text.lower()


def test_login_success_redirect(client):
    r = client.post(
        "/login",
        data={"username": "admin", "password": "test-admin-pass-123", "next": "/phones"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert "/phones" in r.headers.get("location", "")


def test_login_fail(client):
    r = client.post(
        "/login",
        data={"username": "admin", "password": "wrong-password", "next": "/"},
        follow_redirects=False,
    )
    assert r.status_code == 401


def test_unauthenticated_redirect(client):
    # новый client без cookie — но session fixture shared... use cookie clear
    client.cookies.clear()
    r = client.get("/phones", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert "/login" in r.headers.get("location", "")


def test_operator_forbidden_settings(client, operator_session):
    r = client.get("/settings/global", follow_redirects=False)
    assert r.status_code == 403


def test_operator_can_phones(client, operator_session):
    r = client.get("/phones/")
    assert r.status_code == 200


def test_admin_can_users(client, admin_session):
    r = client.get("/users/")
    assert r.status_code == 200


def test_logout(client, admin_session):
    r = client.get("/logout", follow_redirects=False)
    assert r.status_code in (302, 303)
    client.cookies.clear()
    r2 = client.get("/phones", follow_redirects=False)
    assert r2.status_code in (302, 303)
