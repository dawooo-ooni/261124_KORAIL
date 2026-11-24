from app.extensions import db
from app.models import Menu

from .conftest import get_csrf

NEW_MENU = {
    "name": "테스트국밥", "emoji": "🍲", "category": "한식", "price": "9000",
    "fullness": "4", "time_min": "15", "description": "테스트용 메뉴",
    "has_soup": "y", "is_active": "y",
    "tastes": ["담백"], "ingredients": ["돼지", "밥"], "weathers": ["추움"], "situations": ["혼밥"],
}


def count_menus(app):
    with app.app_context():
        return db.session.execute(db.select(db.func.count(Menu.id))).scalar_one()


def test_admin_requires_login(client):
    r = client.get("/admin/menus")
    assert r.status_code == 302 and "/admin/login" in r.headers["Location"]


def test_post_without_csrf_is_400(client):
    r = client.post("/admin/login", data={"password": "test-admin"})
    assert r.status_code == 400


def test_wrong_password(client):
    token = get_csrf(client, "/admin/login")
    r = client.post("/admin/login", data={"password": "nope", "csrf_token": token})
    assert r.status_code == 200 and "비밀번호가 맞지 않아요" in r.get_data(as_text=True)
    assert client.get("/admin/menus").status_code == 302


def test_menu_list(admin_client):
    r = admin_client.get("/admin/menus?cat=중식")
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "짜장면" in html and "김치찌개" not in html


def test_duplicate_name_rejected(admin_client, app):
    token = get_csrf(admin_client, "/admin/menus/new")
    data = dict(NEW_MENU, name="김치찌개", csrf_token=token)
    r = admin_client.post("/admin/menus/new", data=data)
    assert r.status_code == 200 and "이미 같은 이름의 메뉴가 있어요" in r.get_data(as_text=True)
    assert count_menus(app) == 56


def test_price_range_validated(admin_client, app):
    token = get_csrf(admin_client, "/admin/menus/new")
    r = admin_client.post("/admin/menus/new", data=dict(NEW_MENU, price="500", csrf_token=token))
    assert "1,000~100,000원" in r.get_data(as_text=True)
    assert count_menus(app) == 56


def test_add_toggle_affects_recommendations(admin_client, app):
    token = get_csrf(admin_client, "/admin/menus/new")
    r = admin_client.post("/admin/menus/new", data=dict(NEW_MENU, csrf_token=token))
    assert r.status_code == 302
    assert count_menus(app) == 57

    names = lambda: [x["menu"]["name"] for x in admin_client.post(
        "/api/recommendations", json={"filters": {}}).get_json()["items"]]
    assert "테스트국밥" in names()

    with app.app_context():
        mid = db.session.execute(db.select(Menu.id).filter_by(name="테스트국밥")).scalar_one()
        m = db.session.get(Menu, mid)
        assert m.tastes == ["담백"] and m.has_soup is True
    token = get_csrf(admin_client, "/admin/menus")
    assert admin_client.post(f"/admin/menus/{mid}/toggle", data={"csrf_token": token}).status_code == 302
    assert "테스트국밥" not in names()


def test_delete_with_history_requires_force(admin_client, app):
    with app.app_context():
        mid = db.session.execute(db.select(Menu.id).filter_by(name="떡볶이")).scalar_one()
    admin_client.post("/api/decisions", json={"menu_id": mid, "filters": {}})
    token = get_csrf(admin_client, "/admin/menus")
    r = admin_client.post(f"/admin/menus/{mid}/delete", data={"csrf_token": token})
    assert r.status_code == 302 and f"/admin/menus/{mid}/edit" in r.headers["Location"]
    assert count_menus(app) == 56
    r = admin_client.post(f"/admin/menus/{mid}/delete", data={"csrf_token": token, "force": "1"})
    assert r.status_code == 302 and count_menus(app) == 55
    assert admin_client.get("/api/decisions").get_json()["items"][0]["menu_name"] == "떡볶이"


def test_seed_twice_keeps_56(app):
    runner = app.test_cli_runner()
    out = runner.invoke(args=["seed"])
    assert "메뉴 0개 추가" in out.output
    runner.invoke(args=["seed"])
    assert count_menus(app) == 56
