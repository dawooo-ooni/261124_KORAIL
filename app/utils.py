"""익명 사용자 쿠키, 공통 오류 응답, 검증 헬퍼."""
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import g, jsonify, request

KST = ZoneInfo("Asia/Seoul")
UID_COOKIE = "lp_uid"
UID_MAX_AGE = 365 * 24 * 3600


def now() -> datetime:
    """서울 기준 현재 시각 (DB 저장용 naive datetime)."""
    return datetime.now(KST).replace(tzinfo=None)


def today():
    return now().date()


class ApiError(Exception):
    """API 에서 공통 JSON 오류 형식으로 응답할 예외."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def error_response(code: str, message: str, status: int):
    return jsonify(error={"code": code, "message": message}), status


def json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("INVALID_JSON", "요청 본문은 JSON 객체여야 해요.", 400)
    return data


def require_int(value, name: str, lo: int | None = None, hi: int | None = None) -> int:
    if isinstance(value, bool):
        value = None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ApiError("INVALID_PARAM", f"{name} 값이 올바르지 않아요.", 400)
    if (lo is not None and n < lo) or (hi is not None and n > hi):
        raise ApiError("INVALID_PARAM", f"{name} 값은 {lo}~{hi} 사이여야 해요.", 400)
    return n


def query_int(name: str, default: int, lo: int, hi: int) -> int:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    return require_int(raw, name, lo, hi)


def load_current_user():
    """before_request: 쿠키 lp_uid 로 익명 사용자를 찾거나 새로 만든다."""
    from .extensions import db
    from .models import User

    user = None
    raw = request.cookies.get(UID_COOKIE)
    if raw:
        try:
            uid = str(uuid.UUID(raw))
        except ValueError:
            uid = None
        if uid:
            user = db.session.execute(db.select(User).filter_by(uuid=uid)).scalar_one_or_none()

    ts = now()
    if user is None:
        user = User(uuid=str(uuid.uuid4()), created_at=ts, last_seen_at=ts)
        db.session.add(user)
        db.session.commit()
        g.new_uid = user.uuid
    elif ts - user.last_seen_at > timedelta(minutes=5):
        user.last_seen_at = ts
        db.session.commit()
    g.user = user


def set_uid_cookie(response):
    """after_request: 새로 발급한 사용자 UUID 를 쿠키로 내려 준다."""
    from flask import current_app

    uid = g.get("new_uid")
    if uid:
        response.set_cookie(UID_COOKIE, uid, max_age=UID_MAX_AGE, httponly=True, samesite="Lax",
                            secure=bool(current_app.config.get("UID_COOKIE_SECURE")))
    return response
