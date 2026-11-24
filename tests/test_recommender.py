import random
from datetime import date

import pytest

from app.services.data import active_menus
from app.services.recommender import (FilterError, default_filters, draw, evaluate, recommend,
                                      validate_filters)
from app.services.today import pick_index


@pytest.fixture
def menus(app):
    with app.app_context():
        return active_menus()


def F(**kw):
    f = default_filters()
    f.update(kw)
    return f


def by_name(menus, name):
    return next(m for m in menus if m.name == name)


def test_no_filters_returns_all_active_with_null_pct(menus):
    res = recommend(menus, F(), [])
    assert res.total == 56 and len(res.items) == 56 and not res.relaxed
    assert all(x.ev.pct is None for x in res.items)
    assert res.items[0].reason == "특별한 조건이 없어 누구나 무난하게 즐기기 좋은 메뉴로 골랐어요."


def test_budget_b1_excludes_over_8000(menus):
    res = recommend(menus, F(budget="b1"), [])
    assert res.items and all(x.menu.price <= 8000 for x in res.items)
    assert all("8천 원 이하 예산" in x.reason for x in res.items)


def test_avoid_seafood(menus):
    res = recommend(menus, F(avoid=["해산물"]), [])
    assert res.items and all("해산물" not in x.menu.ingredients for x in res.items)


def test_avoid_spicy_uses_taste_tag(menus):
    res = recommend(menus, F(avoid=["매운맛"]), [])
    assert res.items and all("매운맛" not in x.menu.tastes for x in res.items)


def test_like_meat_adds_score(menus):
    res = recommend(menus, F(like=["고기"]), [])
    for x in res.items:
        meat = any(i in ("돼지", "소", "닭") for i in x.menu.ingredients)
        assert x.ev.score == (2 if meat else 0)
        assert x.ev.pct == (100 if meat else 0)
    assert res.items[0].ev.score == 2  # 점수 내림차순


def test_rain_and_soup_reason(menus):
    ev = evaluate(by_name(menus, "김치찌개"), F(weather="비", soup="yes"), [])
    res = recommend(menus, F(weather="비", soup="yes"), [])
    top = res.items[0]
    assert "비 오는 날" in top.reason and "국물 선호" in top.reason
    assert top.reason.endswith("조건에 맞아 추천했어요.")
    assert ev.score == 4 and ev.pct == 100


def test_relaxed_when_nothing_matches(menus):
    res = recommend(menus, F(cat=["일식"], budget="b1"), [])
    assert res.relaxed is True
    assert len(res.items) == 3
    assert res.total == 0


def test_recent_decision_penalty(menus):
    recent = ["김치찌개", "된장찌개", "제육볶음", "비빔밥"]
    f = F()
    assert evaluate(by_name(menus, "김치찌개"), f, recent).score == -4
    assert evaluate(by_name(menus, "된장찌개"), f, recent).score == -2
    assert evaluate(by_name(menus, "제육볶음"), f, recent).score == -2
    ev = evaluate(by_name(menus, "비빔밥"), f, recent)
    assert ev.score == 0 and ev.recent is True
    assert evaluate(by_name(menus, "순댓국"), f, recent).recent is False


def test_draw_never_returns_excluded(menus):
    f = F(cat=["한식"])
    target = by_name(menus, "김치찌개").id
    rng = random.Random(1)
    for _ in range(200):
        res = draw(menus, f, [], exclude_id=target, rng=rng)
        assert res.pick.menu.id != target
        assert 2 <= len(res.roll) <= 20


def test_draw_excludes_last_decision(menus):
    rng = random.Random(2)
    for _ in range(100):
        res = draw(menus, F(cat=["한식"]), ["된장찌개"], rng=rng)
        assert res.pick.menu.name != "된장찌개"


def test_draw_single_candidate_returns_it(menus):
    f = F(cat=["양식"], budget="b1")  # 샌드위치(8,000원)만 해당
    only = recommend(menus, f, []).items
    assert len(only) == 1
    res = draw(menus, f, [], exclude_id=only[0].menu.id, rng=random.Random(3))
    assert res.pick.menu.id == only[0].menu.id


def test_today_pick_index_deterministic():
    d = date(2026, 11, 24)
    assert pick_index(d, 56) == pick_index(d, 56)
    assert 0 <= pick_index(d, 56) < 56


@pytest.mark.parametrize("raw", [
    {"cat": ["피자"]}, {"budget": "b9"}, {"soup": "maybe"}, {"weather": "눈"},
    {"taste": "매운맛"}, {"sit": [1]}, "not-a-dict",
])
def test_invalid_filters_rejected(raw):
    with pytest.raises(FilterError):
        validate_filters(raw)


def test_validate_filters_fills_defaults():
    f = validate_filters({"cat": ["한식", "한식"], "unknown": 1})
    assert f["cat"] == ["한식"] and f["soup"] == "any" and f["budget"] == "all"
