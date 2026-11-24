"""앱 팩토리."""
import logging
import os
import sqlite3
from datetime import datetime
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_wtf.csrf import CSRFError
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.exceptions import HTTPException

from .extensions import csrf, db
from .utils import KST, ApiError, error_response, set_uid_cookie


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(dbapi_conn, _record):
    """SQLite 연결마다 외래 키 제약을 켠다."""
    if isinstance(dbapi_conn, sqlite3.Connection):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()


def create_app(config_object=None) -> Flask:
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)

    from .config import Config
    if config_object is None:
        app.config.from_object(Config)
        app.config.update(Config.from_env())
    else:
        app.config.from_object(config_object)
    app.json.ensure_ascii = False

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:  # 읽기 전용 환경(Vercel)
        pass

    db.init_app(app)
    csrf.init_app(app)

    from .routes.admin import bp as admin_bp
    from .routes.api import bp as api_bp
    from .routes.main import bp as main_bp

    # JSON API 는 CSRF 토큰 대신 SameSite=Lax 쿠키 + JSON Content-Type 강제로 보호한다.
    csrf.exempt(api_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.after_request(set_uid_cookie)

    from .cli import register_cli
    register_cli(app)

    _setup_logging(app)
    _register_error_handlers(app)

    if not app.testing and app.config["SECRET_KEY"] == Config.SECRET_KEY:
        app.logger.warning("SECRET_KEY 가 기본값입니다. .env 에 임의 문자열을 지정하세요.")
    return app


class _KSTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        return datetime.fromtimestamp(record.created, KST).strftime(datefmt or "%Y-%m-%d %H:%M:%S")


def _setup_logging(app: Flask) -> None:
    app.logger.setLevel(logging.INFO)
    if not app.config.get("LOG_TO_FILE"):
        if not app.testing:  # 서버리스: 표준 출력 → 플랫폼 로그에서 확인
            stream = logging.StreamHandler()
            stream.setFormatter(_KSTFormatter("%(asctime)s [%(levelname)s] %(message)s"))
            app.logger.addHandler(stream)
        return
    log_dir = app.config.get("LOG_DIR") or os.path.join(os.path.dirname(app.root_path), "logs")
    os.makedirs(log_dir, exist_ok=True)
    handler = RotatingFileHandler(os.path.join(log_dir, "app.log"), maxBytes=1_000_000,
                                  backupCount=5, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(_KSTFormatter("%(asctime)s [%(levelname)s] %(message)s"))
    app.logger.addHandler(handler)


def _is_api() -> bool:
    return request.path.startswith("/api/")


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(e: ApiError):
        app.logger.warning("API %s %s -> %s %s", request.method, request.path, e.status, e.code)
        return error_response(e.code, e.message, e.status)

    @app.errorhandler(CSRFError)
    def handle_csrf(e: CSRFError):
        app.logger.warning("CSRF 실패 %s %s: %s", request.method, request.path, e.description)
        return render_template("errors/400.html", message="보안 토큰이 없거나 만료됐어요. 페이지를 새로고침한 뒤 다시 시도해 주세요."), 400

    @app.errorhandler(404)
    def handle_404(e):
        if _is_api():
            return error_response("NOT_FOUND", "요청한 API 를 찾을 수 없어요.", 404)
        return render_template("errors/404.html"), 404

    @app.errorhandler(HTTPException)
    def handle_http(e: HTTPException):
        if _is_api():
            app.logger.warning("API %s %s -> %s", request.method, request.path, e.code)
            code = (e.name or "ERROR").upper().replace(" ", "_")
            return error_response(code, e.description or e.name, e.code)
        return e

    @app.errorhandler(500)
    def handle_500(e):
        original = getattr(e, "original_exception", None)
        app.logger.error("서버 오류 %s %s: %r", request.method, request.path, original or e)
        db.session.rollback()
        if _is_api():
            return error_response("SERVER_ERROR", "서버에서 문제가 생겼어요. 잠시 후 다시 시도해 주세요.", 500)
        return render_template("errors/500.html"), 500
