"""앱 설정. 운영 값은 .env(환경변수)에서 읽는다."""
import os


class Config:
    SECRET_KEY = "dev-only-secret-change-me"
    ADMIN_PASSWORD = "change-me"
    # 상대 경로 sqlite URI 는 Flask-SQLAlchemy 가 instance/ 폴더 기준으로 해석한다.
    SQLALCHEMY_DATABASE_URI = "sqlite:///lunch.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TIMEZONE = "Asia/Seoul"
    LOG_TO_FILE = True
    LOG_DIR = None  # None 이면 프로젝트 루트의 logs/
    JSON_AS_ASCII = False
    HISTORY_PAGE_SIZE = 10

    @staticmethod
    def from_env() -> dict:
        """환경변수(.env)에 값이 있으면 기본값을 덮어쓴다."""
        overrides = {}
        mapping = {
            "SECRET_KEY": "SECRET_KEY",
            "ADMIN_PASSWORD": "ADMIN_PASSWORD",
            "DATABASE_URL": "SQLALCHEMY_DATABASE_URI",
        }
        for env_key, cfg_key in mapping.items():
            value = (os.environ.get(env_key) or "").strip()  # 대시보드/CLI 입력 시 붙는 줄바꿈 제거
            if value:
                overrides[cfg_key] = value

        uri = overrides.get("SQLALCHEMY_DATABASE_URI", "")
        if uri.startswith(("postgres://", "postgresql://")):
            # Supabase Postgres: psycopg3 드라이버 사용, 서버리스에서는 연결을 풀링하지 않는다
            # (Supabase 커넥션 풀러가 풀링을 담당). 트랜잭션 풀러 호환을 위해 prepared statement 끔.
            from sqlalchemy.pool import NullPool
            overrides["SQLALCHEMY_DATABASE_URI"] = "postgresql+psycopg://" + uri.split("://", 1)[1]
            overrides["SQLALCHEMY_ENGINE_OPTIONS"] = {
                "poolclass": NullPool,
                "connect_args": {"prepare_threshold": None},
            }

        if os.environ.get("VERCEL"):
            # Vercel: 파일 시스템이 읽기 전용이므로 파일 로그 대신 표준 출력, HTTPS 쿠키
            overrides["LOG_TO_FILE"] = False
            overrides["SESSION_COOKIE_SECURE"] = True
            overrides["UID_COOKIE_SECURE"] = True
        return overrides


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    ADMIN_PASSWORD = "test-admin"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LOG_TO_FILE = False
    # CSRF 는 테스트에서도 켜 둔다 (토큰 없는 POST → 400 검증용).
    WTF_CSRF_ENABLED = True
