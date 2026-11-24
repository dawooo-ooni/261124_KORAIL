"""관리자: 로그인, 메뉴 목록·추가·수정·사용 전환·삭제."""
import hmac
from functools import wraps

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request,
                   session, url_for)
from sqlalchemy.orm import selectinload

from ..constants import CATEGORIES
from ..extensions import db
from ..forms import LoginForm, MenuForm
from ..models import Decision, Menu

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _actor() -> str:
    return f"admin@{request.remote_addr}"


def _log(action: str, menu: Menu, detail: str = "") -> None:
    current_app.logger.info("ADMIN %s | %s | menu id=%s name=%s %s",
                            _actor(), action, menu.id, menu.name, detail)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def _safe_next(target: str | None) -> str:
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("admin.menus")


def _get_menu_or_404(menu_id: int) -> Menu:
    menu = db.session.get(Menu, menu_id)
    if not menu:
        abort(404)
    return menu


def _decision_count(menu_id: int) -> int:
    return db.session.execute(
        db.select(db.func.count(Decision.id)).where(Decision.menu_id == menu_id)).scalar_one()


@bp.get("/")
def home():
    return redirect(url_for("admin.menus"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("is_admin"):
        return redirect(_safe_next(request.args.get("next")))
    form = LoginForm()
    if form.validate_on_submit():
        expected = str(current_app.config.get("ADMIN_PASSWORD") or "")
        if expected and hmac.compare_digest(form.password.data.encode(), expected.encode()):
            session.clear()
            session["is_admin"] = True
            current_app.logger.info("ADMIN %s | 로그인", _actor())
            return redirect(_safe_next(request.args.get("next")))
        current_app.logger.warning("ADMIN %s | 로그인 실패", _actor())
        flash("비밀번호가 맞지 않아요.", "error")
    return render_template("admin/login.html", form=form)


@bp.post("/logout")
def logout():
    session.pop("is_admin", None)
    flash("로그아웃했어요.", "info")
    return redirect(url_for("admin.login"))


@bp.get("/menus")
@login_required
def menus():
    q = (request.args.get("q") or "").strip()
    cat = request.args.get("cat") or ""
    status = request.args.get("status") or ""
    stmt = db.select(Menu).options(selectinload(Menu.attributes)).order_by(Menu.category, Menu.id)
    if q:
        stmt = stmt.where(Menu.name.contains(q) | Menu.description.contains(q))
    if cat in CATEGORIES:
        stmt = stmt.where(Menu.category == cat)
    if status == "active":
        stmt = stmt.where(Menu.is_active.is_(True))
    elif status == "inactive":
        stmt = stmt.where(Menu.is_active.is_(False))
    rows = list(db.session.execute(stmt).scalars())
    counts = dict(db.session.execute(
        db.select(Decision.menu_id, db.func.count(Decision.id)).group_by(Decision.menu_id)).all())
    total = db.session.execute(db.select(db.func.count(Menu.id))).scalar_one()
    active = db.session.execute(
        db.select(db.func.count(Menu.id)).where(Menu.is_active.is_(True))).scalar_one()
    return render_template("admin/menus.html", menus=rows, counts=counts, q=q, cat=cat,
                           status=status, categories=CATEGORIES, total=total, active=active)


def _apply(form: MenuForm, menu: Menu) -> None:
    menu.name = form.name.data.strip()
    menu.emoji = form.emoji.data.strip()
    menu.category = form.category.data
    menu.price = form.price.data
    menu.fullness = form.fullness.data
    menu.time_min = form.time_min.data
    menu.description = form.description.data.strip()
    menu.has_soup = bool(form.has_soup.data)
    menu.is_active = bool(form.is_active.data)
    menu.set_attributes(form.tastes.data or [], form.ingredients.data or [],
                        form.weathers.data or [], form.situations.data or [])


@bp.route("/menus/new", methods=["GET", "POST"])
@login_required
def menu_new():
    form = MenuForm()
    if form.validate_on_submit():
        menu = Menu()
        _apply(form, menu)
        db.session.add(menu)
        db.session.commit()
        _log("메뉴 추가", menu, f"price={menu.price} active={menu.is_active}")
        flash(f"‘{menu.name}’ 메뉴를 추가했어요.", "success")
        return redirect(url_for("admin.menus"))
    return render_template("admin/menu_form.html", form=form, menu=None, decision_count=0)


@bp.route("/menus/<int:menu_id>/edit", methods=["GET", "POST"])
@login_required
def menu_edit(menu_id):
    menu = _get_menu_or_404(menu_id)
    form = MenuForm(obj=menu, menu_id=menu.id)
    if request.method == "GET":
        form.tastes.data = menu.tastes
        form.ingredients.data = menu.ingredients
        form.weathers.data = menu.weathers
        form.situations.data = menu.situations
    if form.validate_on_submit():
        before = menu.to_dict()
        _apply(form, menu)
        db.session.commit()
        after = menu.to_dict()
        changes = ", ".join(f"{k}: {before[k]!r}→{after[k]!r}"
                            for k in after if k != "id" and before[k] != after[k])
        _log("메뉴 수정", menu, changes or "(변경 없음)")
        flash(f"‘{menu.name}’ 메뉴를 수정했어요.", "success")
        return redirect(url_for("admin.menus"))
    return render_template("admin/menu_form.html", form=form, menu=menu,
                           decision_count=_decision_count(menu.id))


@bp.post("/menus/<int:menu_id>/toggle")
@login_required
def menu_toggle(menu_id):
    menu = _get_menu_or_404(menu_id)
    menu.is_active = not menu.is_active
    db.session.commit()
    state = "사용" if menu.is_active else "중지"
    _log(f"메뉴 {state}", menu)
    flash(f"‘{menu.name}’ 메뉴를 {state} 상태로 바꿨어요.", "success")
    return redirect(request.referrer or url_for("admin.menus"))


@bp.post("/menus/<int:menu_id>/delete")
@login_required
def menu_delete(menu_id):
    menu = _get_menu_or_404(menu_id)
    count = _decision_count(menu.id)
    if count and request.form.get("force") != "1":
        flash(f"‘{menu.name}’에는 결정 이력이 {count}건 있어요. 삭제보다 ‘중지’를 권장해요. "
              "그래도 삭제하려면 아래 ‘위험 구역’에서 확인 후 삭제하세요.", "warning")
        return redirect(url_for("admin.menu_edit", menu_id=menu.id))
    name = menu.name
    _log("메뉴 삭제", menu, f"decisions={count}")
    db.session.delete(menu)
    db.session.commit()
    flash(f"‘{name}’ 메뉴를 삭제했어요. (결정 이력의 메뉴명은 그대로 남아요)", "success")
    return redirect(url_for("admin.menus"))
