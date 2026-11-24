"""결정 이력 통계: 많이 먹은 메뉴 TOP 5, 카테고리 비율, 평균 점심 지출."""
from collections import Counter
from datetime import timedelta

from ..extensions import db
from ..models import Decision
from ..utils import now


def get_stats(user_id: int, days: int = 30) -> dict:
    since = now() - timedelta(days=days)
    rows = list(db.session.execute(
        db.select(Decision).where(Decision.user_id == user_id, Decision.decided_at >= since)
        .order_by(Decision.decided_at.desc())
    ).scalars())

    counts = Counter(r.menu_name for r in rows)
    emoji = {}
    for r in rows:
        emoji.setdefault(r.menu_name, r.menu.emoji if r.menu else "🍽️")
    top = [{"name": n, "emoji": emoji[n], "count": c} for n, c in counts.most_common(5)]

    cats = Counter((r.menu.category if r.menu else "기타") for r in rows)
    total = len(rows)
    ratio = {c: {"count": n, "pct": round(n / total * 100)} for c, n in cats.most_common()}

    avg = round(sum(r.price_at_decision for r in rows) / total) if total else None
    return {"days": days, "total": total, "top_menus": top,
            "category_ratio": ratio, "avg_spend": avg}
