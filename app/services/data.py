"""서비스 공용 DB 조회 헬퍼."""
import json

from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Decision, Menu, Preference
from ..utils import now
from .recommender import MenuView, default_filters, validate_filters, FilterError

RECENT_LIMIT = 5


def active_menus() -> list[MenuView]:
    stmt = (db.select(Menu).where(Menu.is_active.is_(True)).order_by(Menu.id)
            .options(selectinload(Menu.attributes)))
    return [MenuView.from_model(m) for m in db.session.execute(stmt).scalars()]


def get_menu(menu_id: int) -> Menu | None:
    return db.session.get(Menu, menu_id)


def recent_names(user_id: int, limit: int = RECENT_LIMIT) -> list[str]:
    """가장 최근 결정부터 메뉴명 목록 (원본의 최근 5개 기록과 같은 역할)."""
    stmt = (db.select(Decision.menu_name).where(Decision.user_id == user_id)
            .order_by(Decision.decided_at.desc(), Decision.id.desc()).limit(limit))
    return list(db.session.execute(stmt).scalars())


def load_preferences(user_id: int) -> dict:
    pref = db.session.get(Preference, user_id)
    if not pref:
        return default_filters()
    try:
        return validate_filters(json.loads(pref.filters_json))
    except (ValueError, FilterError):
        return default_filters()


def save_preferences(user_id: int, filters: dict) -> dict:
    pref = db.session.get(Preference, user_id)
    payload = json.dumps(filters, ensure_ascii=False)
    if pref:
        pref.filters_json = payload
        pref.updated_at = now()
    else:
        db.session.add(Preference(user_id=user_id, filters_json=payload, updated_at=now()))
    db.session.commit()
    return filters
