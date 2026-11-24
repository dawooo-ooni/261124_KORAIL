"""화면: 메인(/), 결정 이력(/history)."""
from flask import Blueprint, current_app, g, render_template, request

from ..extensions import db
from ..models import Decision
from ..services.stats import get_stats
from ..utils import load_current_user

bp = Blueprint("main", __name__)
bp.before_request(load_current_user)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/history")
def history():
    page = request.args.get("page", 1, type=int) or 1
    per_page = current_app.config["HISTORY_PAGE_SIZE"]
    stmt = (db.select(Decision).where(Decision.user_id == g.user.id)
            .order_by(Decision.decided_at.desc(), Decision.id.desc()))
    pagination = db.paginate(stmt, page=max(page, 1), per_page=per_page, error_out=False)
    stats = get_stats(g.user.id, 30)
    top_max = max((t["count"] for t in stats["top_menus"]), default=1)
    return render_template("history.html", pagination=pagination, stats=stats,
                           top_max=top_max, user=g.user)
