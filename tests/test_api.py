from app.extensions import db
from app.models import Decision, Menu


def menu_id(app, name):
    with app.app_context():
        return db.session.execute(db.select(Menu.id).filter_by(name=name)).scalar_one()


def test_cookie_issued_and_users_isolated(app):
    a, b = app.test_client(), app.test_client()
    r = a.get("/api/preferences")
    assert r.status_code == 200
    assert "lp_uid=" in r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in r.headers["Set-Cookie"]
    a.put("/api/preferences", json={"filters": {"cat": ["중식"]}})
    assert a.get("/api/preferences").get_json()["filters"]["cat"] == ["중식"]
    assert b.get("/api/preferences").get_json()["filters"]["cat"] == []


def test_meta_and_today(client):
    meta = client.get("/api/meta").get_json()
    assert [g["key"] for g in meta["groups"]] == ["cat", "taste", "like", "avoid", "soup", "budget", "weather", "sit"]
    t1 = client.get("/api/today").get_json()
    t2 = client.get("/api/today").get_json()
    assert t1["menu"]["id"] == t2["menu"]["id"]
    assert t1["date"] == t2["date"]


def test_today_same_for_all_users(app):
    a = app.test_client().get("/api/today").get_json()
    b = app.test_client().get("/api/today").get_json()
    assert a["menu"]["id"] == b["menu"]["id"]


def test_recommendations(client):
    res = client.post("/api/recommendations", json={"filters": {"budget": "b1"}}).get_json()
    assert res["total"] == len(res["items"]) and not res["relaxed"]
    assert all(x["menu"]["price"] <= 8000 for x in res["items"])
    assert {"menu", "score", "match_pct", "reason", "recent"} <= set(res["items"][0])


def test_invalid_filter_returns_400(client):
    r = client.post("/api/recommendations", json={"filters": {"cat": ["피자"]}})
    assert r.status_code == 400
    assert r.get_json()["error"]["code"] == "INVALID_FILTER"
    r = client.put("/api/preferences", json={"filters": {"budget": "rich"}})
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "INVALID_FILTER"


def test_non_json_body_rejected(client):
    r = client.post("/api/recommendations", data="filters=1")
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "INVALID_JSON"


def test_draw(client, app):
    ex = menu_id(app, "김치찌개")
    for _ in range(20):
        r = client.post("/api/draw", json={"filters": {"cat": ["한식"]}, "exclude_id": ex}).get_json()
        assert r["menu"]["id"] != ex and r["menu"]["category"] == "한식"
        assert r["roll"] and r["reason"]


def test_candidate_limit_and_duplicate(client, app):
    ids = [menu_id(app, n) for n in ("김치찌개", "된장찌개", "제육볶음", "비빔밥")]
    for i in ids[:3]:
        assert client.post("/api/candidates", json={"menu_id": i}).status_code == 201
    r = client.post("/api/candidates", json={"menu_id": ids[3]})
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "CANDIDATE_LIMIT"
    r = client.post("/api/candidates", json={"menu_id": ids[0]})
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "ALREADY_ADDED"
    data = client.delete(f"/api/candidates/{ids[0]}").get_json()
    assert [x["menu"]["id"] for x in data["items"]] == ids[1:3]


def test_candidate_compare_best(client, app):
    a, b = menu_id(app, "김밥"), menu_id(app, "갈비탕")
    client.post("/api/candidates", json={"menu_id": a})
    data = client.post("/api/candidates", json={"menu_id": b}).get_json()
    assert data["best"]["price"] == [a]
    assert data["best"]["fullness"] == [b]
    assert data["best"]["match"] == []  # 저장된 조건 없음 → 일치도 없음


def test_decision_saves_and_clears_candidates(client, app):
    mid = menu_id(app, "짬뽕")
    client.post("/api/candidates", json={"menu_id": mid})
    r = client.post("/api/decisions", json={"menu_id": mid, "filters": {"weather": "비"}})
    assert r.status_code == 201
    dec = r.get_json()["decision"]
    assert dec["menu"]["name"] == "짬뽕" and "비 오는 날" in dec["reason"]
    with app.app_context():
        assert db.session.execute(db.select(db.func.count(Decision.id))).scalar_one() == 1
    assert client.get("/api/candidates").get_json()["items"] == []
    hist = client.get("/api/decisions?limit=5").get_json()
    assert hist["total"] == 1 and hist["items"][0]["menu_name"] == "짬뽕"


def test_history_keeps_name_after_menu_deleted(client, app):
    mid = menu_id(app, "울면")
    client.post("/api/decisions", json={"menu_id": mid, "filters": {}})
    with app.app_context():
        db.session.delete(db.session.get(Menu, mid))
        db.session.commit()
    item = client.get("/api/decisions").get_json()["items"][0]
    assert item["menu_name"] == "울면" and item["menu_id"] is None


def test_recent_decision_penalty_via_api(client, app):
    mid = menu_id(app, "김밥")
    client.post("/api/decisions", json={"menu_id": mid, "filters": {}})
    items = client.post("/api/recommendations", json={"filters": {}}).get_json()["items"]
    kimbap = next(x for x in items if x["menu"]["id"] == mid)
    assert kimbap["score"] == -4 and kimbap["recent"] is True
    assert items[-1]["menu"]["id"] == mid


def test_stats(client, app):
    for n in ("김밥", "김밥", "짜장면"):
        client.post("/api/decisions", json={"menu_id": menu_id(app, n), "filters": {}})
    s = client.get("/api/stats?days=30").get_json()
    assert s["total"] == 3
    assert s["top_menus"][0] == {"name": "김밥", "emoji": "🍙", "count": 2}
    assert s["category_ratio"]["분식"]["count"] == 2
    assert s["avg_spend"] == round((4500 * 2 + 7500) / 3)


def test_nickname(client):
    assert client.put("/api/me", json={"nickname": "점심요정"}).get_json()["user"]["nickname"] == "점심요정"
    r = client.put("/api/me", json={"nickname": "가" * 21})
    assert r.status_code == 400


def test_api_404_is_json(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.get_json()["error"]["code"] == "NOT_FOUND"


def test_pages_render(client):
    assert client.get("/").status_code == 200
    assert client.get("/history").status_code == 200
    assert client.get("/no-such-page").status_code == 404
