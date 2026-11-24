"""후보 담기/빼기/비교 (사용자당 최대 3개)."""
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Candidate, Menu
from ..utils import ApiError, now
from .data import load_preferences, recent_names
from .recommender import MenuView, score_menu

MAX_CANDIDATES = 3


def _rows(user_id: int) -> list[Candidate]:
    stmt = (db.select(Candidate).where(Candidate.user_id == user_id)
            .order_by(Candidate.added_at, Candidate.id))
    return list(db.session.execute(stmt).scalars())


def add_candidate(user_id: int, menu_id: int) -> None:
    menu = db.session.get(Menu, menu_id)
    if not menu or not menu.is_active:
        raise ApiError("MENU_NOT_FOUND", "메뉴를 찾을 수 없어요.", 404)
    rows = _rows(user_id)
    if any(r.menu_id == menu_id for r in rows):
        raise ApiError("ALREADY_ADDED", "이미 후보에 있어요.", 409)
    if len(rows) >= MAX_CANDIDATES:
        raise ApiError("CANDIDATE_LIMIT", "후보는 최대 3개까지 담을 수 있어요.", 409)
    try:
        db.session.add(Candidate(user_id=user_id, menu_id=menu_id, added_at=now()))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError("ALREADY_ADDED", "이미 후보에 있어요.", 409)


def remove_candidate(user_id: int, menu_id: int) -> None:
    db.session.execute(db.delete(Candidate).where(
        Candidate.user_id == user_id, Candidate.menu_id == menu_id))
    db.session.commit()


def clear_candidates(user_id: int) -> None:
    db.session.execute(db.delete(Candidate).where(Candidate.user_id == user_id))


def _best_ids(items, key, prefer_max: bool) -> list[int]:
    if len(items) < 2:
        return []
    vals = [key(x) for x in items]
    target = max(vals) if prefer_max else min(vals)
    return [x.menu.id for x, v in zip(items, vals) if v == target]


def compare(user_id: int) -> dict:
    """후보 비교 데이터. 조건 일치도는 저장된 조건(preferences) 기준."""
    f = load_preferences(user_id)
    names = recent_names(user_id)
    items = [score_menu(MenuView.from_model(r.menu), f, names)
             for r in _rows(user_id) if r.menu and r.menu.is_active]
    has_pct = bool(items) and items[0].ev.pct is not None
    best = {
        "price": _best_ids(items, lambda x: x.menu.price, False),
        "fullness": _best_ids(items, lambda x: x.menu.fullness, True),
        "time": _best_ids(items, lambda x: x.menu.time_min, False),
        "match": _best_ids(items, lambda x: x.ev.pct, True) if has_pct else [],
    }
    return {
        "items": [{"menu": x.menu.to_dict(), "match_pct": x.ev.pct, "reason": x.reason,
                   "recent": x.ev.recent} for x in items],
        "best": best,
        "max": MAX_CANDIDATES,
    }
