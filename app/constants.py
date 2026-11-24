"""선택지 정의: 카테고리·맛·재료·날씨·상황·예산 (원본 아티팩트와 동일한 값과 문구)."""

CATEGORIES = ["한식", "중식", "일식", "양식", "분식", "아시안"]
CATEGORY_LABEL = {
    "한식": "🍚 한식", "중식": "🥟 중식", "일식": "🍣 일식",
    "양식": "🍝 양식", "분식": "🍢 분식", "아시안": "🍜 아시안",
}

TASTES = ["매운맛", "담백", "기름진", "가벼움", "든든"]
TASTE_LABEL = {
    "매운맛": "매운맛", "담백": "담백한 맛", "기름진": "기름진 맛",
    "가벼움": "가벼운 식사", "든든": "든든한 식사",
}
TASTE_CHIP = {**TASTE_LABEL, "매운맛": "🌶️ 매운맛"}

# 필터의 '좋아하는 재료' (고기 = 돼지·소·닭 중 하나)
LIKES = ["고기", "해산물", "면", "밥", "채소"]
LIKE_CHIP = {"고기": "🥩 고기", "해산물": "🦐 해산물", "면": "🍜 면", "밥": "🍚 밥", "채소": "🥬 채소"}
MEAT = {"돼지", "소", "닭"}

# 메뉴에 붙일 수 있는 재료 태그 (원본 데이터의 '빵' 포함)
INGREDIENTS = ["돼지", "소", "닭", "해산물", "면", "밥", "채소", "빵"]

AVOIDS = ["해산물", "돼지", "소", "닭", "매운맛", "면"]
AVOID_LABEL = {
    "해산물": "해산물", "돼지": "돼지고기", "소": "소고기",
    "닭": "닭고기", "매운맛": "매운 음식", "면": "면 요리",
}

SOUPS = {"any": "상관없음", "yes": "국물 있게", "no": "국물 없이"}

WEATHERS = ["맑음", "비", "추움", "더움", "흐림"]
WEATHER_CHIP = {"맑음": "☀️ 맑음", "비": "🌧️ 비", "추움": "🥶 추움", "더움": "🥵 더움", "흐림": "☁️ 흐림"}
WEATHER_REASON = {"맑음": "맑은 날", "비": "비 오는 날", "추움": "추운 날", "더움": "더운 날", "흐림": "흐린 날"}

SITUATIONS = ["혼밥", "동료", "회식", "빨리", "해장"]
SIT_CHIP = {
    "혼밥": "🙋 혼밥", "동료": "👥 동료와 함께", "회식": "🥂 회식·접대",
    "빨리": "⏱️ 빨리 먹어야 함", "해장": "🫠 해장 필요",
}
SIT_REASON = {
    "혼밥": "혼밥하기 좋음", "동료": "동료와 함께 먹기 좋음", "회식": "회식·접대에 어울림",
    "빨리": "빨리 먹을 수 있음", "해장": "해장에 좋음",
}

BUDGETS = {
    "all": {"label": "상관없음", "reason": None},
    "b1": {"label": "8천 원 이하", "reason": "8천 원 이하 예산"},
    "b2": {"label": "8천~1만2천 원", "reason": "1만2천 원 이하 예산"},
    "b3": {"label": "1만2천~1만5천 원", "reason": "1만5천 원 미만 예산"},
    "b4": {"label": "1만5천 원 이상", "reason": "넉넉한 예산"},
}


def budget_ok(key: str, price: int) -> bool:
    if key == "b1":
        return price <= 8000
    if key == "b2":
        return 8000 < price <= 12000
    if key == "b3":
        return 12000 < price < 15000
    if key == "b4":
        return price >= 15000
    return True


ATTR_TYPES = ("taste", "ingredient", "weather", "situation")
# 관리자 폼 체크박스 허용값
ATTR_CHOICES = {
    "taste": TASTES,
    "ingredient": INGREDIENTS,
    "weather": WEATHERS,
    "situation": SITUATIONS,
}


def meta_groups() -> list[dict]:
    """프론트엔드 조건 패널용 선택지 (원본 GROUPS 와 동일한 순서·문구)."""
    return [
        {"key": "cat", "title": "음식 종류", "type": "multi", "all": True,
         "opts": [[c, CATEGORY_LABEL[c]] for c in CATEGORIES]},
        {"key": "taste", "title": "맛 취향", "type": "multi",
         "opts": [[t, TASTE_CHIP[t]] for t in TASTES]},
        {"key": "like", "title": "좋아하는 재료", "type": "multi",
         "opts": [[l, LIKE_CHIP[l]] for l in LIKES]},
        {"key": "avoid", "title": "피하고 싶은 것", "type": "multi", "cls": "avoid",
         "opts": [[a, "🚫 " + AVOID_LABEL[a]] for a in AVOIDS]},
        {"key": "soup", "title": "국물", "type": "single",
         "opts": [[k, v] for k, v in SOUPS.items()]},
        {"key": "budget", "title": "예산 (1인)", "type": "single",
         "opts": [[k, v["label"]] for k, v in BUDGETS.items()]},
        {"key": "weather", "title": "오늘 날씨", "type": "single", "toggle": True,
         "opts": [[w, WEATHER_CHIP[w]] for w in WEATHERS]},
        {"key": "sit", "title": "식사 상황", "type": "multi",
         "opts": [[s, SIT_CHIP[s]] for s in SITUATIONS]},
    ]
