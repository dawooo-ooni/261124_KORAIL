"""오늘의 추천: 날짜별로 서버에 고정해 모든 사용자에게 같은 메뉴를 보여 준다."""
import hashlib
from datetime import date

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import DailyPick, Menu
from ..utils import today as kst_today


def pick_index(day: date, count: int) -> int:
    digest = hashlib.sha256(day.isoformat().encode("utf-8")).hexdigest()
    return int(digest, 16) % count


def get_today_menu(day: date | None = None) -> tuple[Menu | None, date]:
    day = day or kst_today()
    pick = db.session.get(DailyPick, day)
    if pick and pick.menu:
        # 오늘 저장된 메뉴는 중간에 사용 중지돼도 오늘은 그대로 둔다 (다음 날부터 새 계산).
        return pick.menu, day

    ids = list(db.session.execute(
        db.select(Menu.id).where(Menu.is_active.is_(True)).order_by(Menu.id)
    ).scalars())
    if not ids:
        return None, day
    menu_id = ids[pick_index(day, len(ids))]
    try:
        db.session.add(DailyPick(pick_date=day, menu_id=menu_id))
        db.session.commit()
    except IntegrityError:  # 동시에 다른 요청이 먼저 저장한 경우
        db.session.rollback()
        pick = db.session.get(DailyPick, day)
        return (pick.menu if pick else db.session.get(Menu, menu_id)), day
    return db.session.get(Menu, menu_id), day
