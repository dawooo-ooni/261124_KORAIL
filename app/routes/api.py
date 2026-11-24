"""JSON API (작업 지시서 7장)."""
import json

from flask import Blueprint, g, jsonify, request

from ..constants import meta_groups
from ..extensions import db
from ..models import Decision
from ..services import candidates as cand_svc
from ..services.data import (active_menus, get_menu, load_preferences, recent_names,
                             save_preferences)
from ..services.recommender import (FilterError, MenuView, draw, recommend, score_menu,
                                    scored_to_dict, validate_filters)
from ..services.stats import get_stats
from ..services.today import get_today_menu
from ..utils import ApiError, json_body, load_current_user, now, query_int, require_int

bp = Blueprint("api", __name__, url_prefix="/api")
bp.before_request(load_current_user)


def _filters(raw) -> dict:
    try:
        return validate_filters(raw)
    except FilterError as e:
        raise ApiError("INVALID_FILTER", f"조건 값이 올바르지 않아요. {e}", 400)


def _optional_int(value, name):
    if value is None or value == "":
        return None
    return require_int(value, name, 1)


@bp.get("/meta")
def meta():
    return jsonify(groups=meta_groups(), max_candidates=cand_svc.MAX_CANDIDATES)


@bp.get("/today")
def today():
    menu, day = get_today_menu()
    return jsonify(menu=menu.to_dict() if menu else None, date=day.isoformat())


@bp.post("/recommendations")
def recommendations():
    body = json_body()
    f = _filters(body.get("filters"))
    menus = active_menus()
    names = recent_names(g.user.id)
    res = recommend(menus, f, names)
    out = {
        "items": [scored_to_dict(x) for x in res.items],
        "total": res.total,
        "relaxed": res.relaxed,
    }
    # (확장) 화면에 떠 있는 메뉴의 일치도·사유를 조건 변경에 맞춰 다시 계산
    focus_id = _optional_int(body.get("focus_id"), "focus_id")
    if focus_id is not None:
        m = get_menu(focus_id)
        if m and m.is_active:
            out["focus"] = scored_to_dict(score_menu(MenuView.from_model(m), f, names))
    return jsonify(out)


@bp.post("/draw")
def draw_menu():
    body = json_body()
    f = _filters(body.get("filters"))
    exclude_id = _optional_int(body.get("exclude_id"), "exclude_id")
    res = draw(active_menus(), f, recent_names(g.user.id), exclude_id)
    if res is None:
        raise ApiError("NO_MENU", "추천할 수 있는 메뉴가 없어요. 관리자 화면에서 메뉴를 확인해 주세요.", 404)
    d = scored_to_dict(res.pick)
    return jsonify(menu=d["menu"], reason=d["reason"], match_pct=d["match_pct"],
                   recent=d["recent"], roll=res.roll, relaxed=res.relaxed)


@bp.get("/preferences")
def get_preferences():
    return jsonify(filters=load_preferences(g.user.id))


@bp.put("/preferences")
def put_preferences():
    body = json_body()
    f = _filters(body.get("filters"))
    return jsonify(filters=save_preferences(g.user.id, f))


@bp.get("/candidates")
def list_candidates():
    return jsonify(cand_svc.compare(g.user.id))


@bp.post("/candidates")
def add_candidate():
    body = json_body()
    menu_id = require_int(body.get("menu_id"), "menu_id", 1)
    cand_svc.add_candidate(g.user.id, menu_id)
    return jsonify(cand_svc.compare(g.user.id)), 201


@bp.delete("/candidates/<int:menu_id>")
def remove_candidate(menu_id):
    cand_svc.remove_candidate(g.user.id, menu_id)
    return jsonify(cand_svc.compare(g.user.id))


@bp.post("/decisions")
def create_decision():
    body = json_body()
    menu_id = require_int(body.get("menu_id"), "menu_id", 1)
    f = _filters(body.get("filters"))
    menu = get_menu(menu_id)
    if not menu or not menu.is_active:
        raise ApiError("MENU_NOT_FOUND", "메뉴를 찾을 수 없어요.", 404)
    scored = score_menu(MenuView.from_model(menu), f, recent_names(g.user.id))
    dec = Decision(
        user_id=g.user.id, menu_id=menu.id, menu_name=menu.name,
        price_at_decision=menu.price, reason=scored.reason,
        filters_json=json.dumps(f, ensure_ascii=False), decided_at=now(),
    )
    db.session.add(dec)
    cand_svc.clear_candidates(g.user.id)
    db.session.commit()
    return jsonify(decision={
        "id": dec.id,
        "menu": menu.to_dict(),
        "reason": dec.reason,
        "price": dec.price_at_decision,
        "decided_at": dec.decided_at.isoformat(timespec="seconds"),
    }), 201


@bp.get("/decisions")
def list_decisions():
    limit = query_int("limit", 5, 1, 50)
    page = query_int("page", 1, 1, 100000)
    base = db.select(Decision).where(Decision.user_id == g.user.id)
    total = db.session.execute(
        db.select(db.func.count()).select_from(base.subquery())).scalar_one()
    rows = db.session.execute(
        base.order_by(Decision.decided_at.desc(), Decision.id.desc())
        .limit(limit).offset((page - 1) * limit)).scalars()
    return jsonify(items=[r.to_dict() for r in rows], total=total, page=page, limit=limit)


@bp.get("/stats")
def stats():
    days = query_int("days", 30, 1, 365)
    return jsonify(get_stats(g.user.id, days))


@bp.get("/me")
def get_me():
    return jsonify(user=g.user.to_dict())


@bp.put("/me")
def put_me():
    body = json_body()
    nick = body.get("nickname")
    if nick is not None and not isinstance(nick, str):
        raise ApiError("INVALID_PARAM", "닉네임은 문자열이어야 해요.", 400)
    nick = (nick or "").strip()
    if len(nick) > 20:
        raise ApiError("INVALID_PARAM", "닉네임은 20자까지 쓸 수 있어요.", 400)
    g.user.nickname = nick or None
    db.session.commit()
    return jsonify(user=g.user.to_dict())
