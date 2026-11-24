"""공용 확장 객체 (앱 팩토리에서 init_app 으로 연결)."""
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()
