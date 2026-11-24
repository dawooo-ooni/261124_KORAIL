import os
import re
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from app.cli import seed_menus  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        seed_menus()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


_TOKEN_RE = re.compile(r'name="csrf_token"[^>]*value="([^"]+)"')


def get_csrf(client, url):
    html = client.get(url).get_data(as_text=True)
    m = _TOKEN_RE.search(html)
    assert m, f"CSRF 토큰을 찾지 못함: {url}"
    return m.group(1)


@pytest.fixture
def admin_client(client):
    token = get_csrf(client, "/admin/login")
    res = client.post("/admin/login", data={"password": TestConfig.ADMIN_PASSWORD, "csrf_token": token})
    assert res.status_code == 302
    return client
