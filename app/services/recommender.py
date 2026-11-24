"""추천 엔진: 필터 검증, 제외 조건, 점수 계산, 추천 사유, 가중치 랜덤 추첨 (작업 지시서 6장).

원본 아티팩트의 JS 로직(hardViolations / evaluate / reasonText / compute / pickRandom)과
같은 규칙을 따른다. DB 에 의존하지 않는 순수 함수로 두고, 데이터 적재는 services.data 에서 한다.
"""
from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, field

from ..constants import (
    AVOID_LABEL, AVOIDS, BUDGETS, CATEGORIES, LIKES, MEAT, SIT_REASON, SITUATIONS,
    SOUPS, TASTE_LABEL, TASTES, WEATHER_REASON, WEATHERS, budget_ok,
)

# ---------------------------------------------------------------- 필터

DEFAULT_FILTERS = {
    "cat": [], "taste": [], "like": [], "avoid": [],
    "soup": "any", "budget": "all", "weather": "", "sit": [],
}
_MULTI = {"cat": CATEGORIES, "taste": TASTES, "like": LIKES, "avoid": AVOIDS, "sit": SITUATIONS}
_SINGLE = {"soup": list(SOUPS), "budget": list(BUDGETS), "weather": [""] + WEATHERS}


class FilterError(ValueError):
    """허용값이 아닌 필터 (→ 400 INVALID_FILTER)."""


def default_filters() -> dict:
    return copy.deepcopy(DEFAULT_FILTERS)


def validate_filters(raw) -> dict:
    """요청 필터를 검증·정규화한다. 빠진 키는 기본값, 알 수 없는 키는 무시."""
    if raw is None:
        return default_filters()
    if not isinstance(raw, dict):
        raise FilterError("filters 는 객체여야 해요.")
    f = default_filters()
    for key, allowed in _MULTI.items():
        val = raw.get(key)
        if val is None:
            continue
        if not isinstance(val, list):
            raise FilterError(f"'{key}' 값은 배열이어야 해요.")
        out = []
        for v in val:
            if not isinstance(v, str) or v not in allowed:
                raise FilterError(f"'{key}' 에 허용되지 않은 값이 있어요: {v!r}")
            if v not in out:
                out.append(v)
        f[key] = out
    for key, allowed in _SINGLE.items():
        val = raw.get(key)
        if val is None:
            continue
        if not isinstance(val, str) or val not in allowed:
            raise FilterError(f"'{key}' 에 허용되지 않은 값이 있어요: {val!r}")
        f[key] = val
    return f


# ---------------------------------------------------------------- 메뉴 스냅샷

@dataclass(frozen=True)
class MenuView:
    id: int
    name: str
    emoji: str
    category: str
    price: int
    tastes: tuple
    ingredients: tuple
    has_soup: bool
    weathers: tuple
    situations: tuple
    fullness: int
    time_min: int
    description: str

    @classmethod
    def from_model(cls, m) -> "MenuView":
        return cls(
            id=m.id, name=m.name, emoji=m.emoji, category=m.category, price=m.price,
            tastes=tuple(m.tastes), ingredients=tuple(m.ingredients), has_soup=bool(m.has_soup),
            weathers=tuple(m.weathers), situations=tuple(m.situations),
            fullness=m.fullness, time_min=m.time_min, description=m.description,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "emoji": self.emoji, "category": self.category,
            "price": self.price, "tastes": list(self.tastes), "ingredients": list(self.ingredients),
            "has_soup": self.has_soup, "weathers": list(self.weathers),
            "situations": list(self.situations), "fullness": self.fullness,
            "time_min": self.time_min, "description": self.description,
        }


@dataclass
class Evaluation:
    score: int
    pct: int | None
    parts: list = field(default_factory=list)
    recent: bool = False


@dataclass
class Scored:
    menu: MenuView
    ev: Evaluation
    rank: int
    reason: str


@dataclass
class RecResult:
    items: list
    relaxed: bool
    total: int


@dataclass
class DrawResult:
    pick: Scored
    roll: list
    relaxed: bool


# ---------------------------------------------------------------- 점수 계산

def has_like(m: MenuView, like: str) -> bool:
    if like == "고기":
        return any(x in MEAT for x in m.ingredients)
    return like in m.ingredients


def hard_violations(m: MenuView, f: dict) -> list[str]:
    v = []
    if f["cat"] and m.category not in f["cat"]:
        v.append("cat")
    if not budget_ok(f["budget"], m.price):
        v.append("budget")
    if any((a in m.tastes) if a == "매운맛" else (a in m.ingredients) for a in f["avoid"]):
        v.append("avoid")
    return v


def _js_round(x: float) -> int:
    """JS Math.round 와 같은 반올림."""
    return math.floor(x + 0.5)


def evaluate(m: MenuView, f: dict, recent_names: list[str]) -> Evaluation:
    wt = wm = 0
    parts: list[str] = []
    if f["weather"]:
        wt += 2
        if f["weather"] in m.weathers:
            wm += 2
            parts.append(WEATHER_REASON[f["weather"]])
    for t in f["taste"]:
        wt += 3
        if t in m.tastes:
            wm += 3
            parts.append(TASTE_LABEL[t] + " 선호")
    for like in f["like"]:
        wt += 2
        if has_like(m, like):
            wm += 2
            parts.append(like + " 좋아함")
    if f["soup"] != "any":
        wt += 2
        if (f["soup"] == "yes") == m.has_soup:
            wm += 2
            parts.append("국물 선호" if f["soup"] == "yes" else "국물 없는 메뉴 선호")
    for s in f["sit"]:
        wt += 2
        if s in m.situations:
            wm += 2
            parts.append(SIT_REASON[s])
    if f["budget"] != "all" and budget_ok(f["budget"], m.price):
        parts.append(BUDGETS[f["budget"]]["reason"])
    if f["avoid"] and "avoid" not in hard_violations(m, f):
        parts.append("·".join(AVOID_LABEL[a] for a in f["avoid"]) + " 제외")

    try:
        ri = recent_names.index(m.name)
    except ValueError:
        ri = -1
    penalty = 4 if ri == 0 else (2 if 0 < ri < 3 else 0)
    pct = _js_round(wm / wt * 100) if wt else None
    return Evaluation(score=wm - penalty, pct=pct, parts=parts, recent=ri >= 0)


def reason_text(f: dict, parts: list[str]) -> str:
    if parts:
        return " + ".join(parts) + " 조건에 맞아 추천했어요."
    any_soft = f["weather"] or f["taste"] or f["like"] or f["sit"] or f["soup"] != "any"
    if any_soft:
        return "조건에 완전히 맞진 않지만 가장 가까운 메뉴예요."
    return "특별한 조건이 없어 누구나 무난하게 즐기기 좋은 메뉴로 골랐어요."


def score_menu(m: MenuView, f: dict, recent_names: list[str], violations: int = 0) -> Scored:
    ev = evaluate(m, f, recent_names)
    return Scored(menu=m, ev=ev, rank=ev.score - violations * 5, reason=reason_text(f, ev.parts))


# ---------------------------------------------------------------- 추천 / 추첨

def recommend(menus: list[MenuView], f: dict, recent_names: list[str], rng=None) -> RecResult:
    """menus 는 사용 중인 메뉴만 넘긴다. 점수 내림차순, 같은 점수는 무작위."""
    rng = rng or random
    pool = [m for m in menus if not hard_violations(m, f)]
    relaxed = False
    if not pool and menus:
        relaxed = True
        pool = list(menus)
    scored = [
        score_menu(m, f, recent_names, len(hard_violations(m, f)) if relaxed else 0)
        for m in pool
    ]
    rng.shuffle(scored)
    scored.sort(key=lambda x: -x.rank)  # 안정 정렬 → 동점은 섞인 순서 유지
    if relaxed:
        return RecResult(items=scored[:3], relaxed=True, total=0)
    return RecResult(items=scored, relaxed=False, total=len(pool))


def draw(menus: list[MenuView], f: dict, recent_names: list[str],
         exclude_id: int | None = None, rng=None) -> DrawResult | None:
    """가중치 랜덤 추첨. 직전 결과(exclude_id)와 가장 최근 결정 메뉴는 제외 (제외 후 0개면 제외 안 함)."""
    rng = rng or random
    res = recommend(menus, f, recent_names, rng)
    pool = list(res.items)
    if not pool:
        return None
    ex: set[int] = set()
    if exclude_id is not None:
        ex.add(exclude_id)
    if recent_names:
        last = next((m.id for m in menus if m.name == recent_names[0]), None)
        if last is not None:
            ex.add(last)
    filtered = [x for x in pool if x.menu.id not in ex]
    if filtered:
        pool = filtered
    lo = min(x.rank for x in pool)
    weights = [(x.rank - lo + 1) ** 2 for x in pool]
    pick = rng.choices(pool, weights=weights, k=1)[0]
    src = pool if len(pool) <= 20 else rng.sample(pool, 20)
    roll = [{"name": x.menu.name, "emoji": x.menu.emoji} for x in src]
    return DrawResult(pick=pick, roll=roll, relaxed=res.relaxed)


def scored_to_dict(x: Scored) -> dict:
    return {
        "menu": x.menu.to_dict(),
        "score": x.ev.score,
        "match_pct": x.ev.pct,
        "reason": x.reason,
        "recent": x.ev.recent,
    }
