"""SQLAlchemy 모델 (작업 지시서 5장)."""
from .constants import CATEGORIES
from .extensions import db
from .utils import now

_cat_list = ",".join(f"'{c}'" for c in CATEGORIES)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False)
    nickname = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=now)

    def to_dict(self):
        return {"nickname": self.nickname, "created_at": self.created_at.isoformat(timespec="seconds")}


class Menu(db.Model):
    __tablename__ = "menus"
    __table_args__ = (
        db.CheckConstraint(f"category IN ({_cat_list})", name="ck_menu_category"),
        db.CheckConstraint("price > 0", name="ck_menu_price"),
        db.CheckConstraint("fullness BETWEEN 1 AND 5", name="ck_menu_fullness"),
        db.CheckConstraint("time_min > 0", name="ck_menu_time"),
        db.Index("ix_menus_category_active", "category", "is_active"),
    )
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)
    emoji = db.Column(db.String(16), nullable=False)
    category = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    has_soup = db.Column(db.Boolean, nullable=False, default=False)
    fullness = db.Column(db.Integer, nullable=False)
    time_min = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(80), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)

    attributes = db.relationship(
        "MenuAttribute", back_populates="menu", order_by="MenuAttribute.id",
        cascade="all, delete-orphan", passive_deletes=True,
    )

    def _attr(self, kind):
        return [a.value for a in self.attributes if a.attr_type == kind]

    @property
    def tastes(self):
        return self._attr("taste")

    @property
    def ingredients(self):
        return self._attr("ingredient")

    @property
    def weathers(self):
        return self._attr("weather")

    @property
    def situations(self):
        return self._attr("situation")

    def set_attributes(self, tastes=(), ingredients=(), weathers=(), situations=()):
        """맛·재료·날씨·상황 태그를 통째로 교체한다 (입력 순서 유지)."""
        self.attributes = []
        for kind, values in (("taste", tastes), ("ingredient", ingredients),
                             ("weather", weathers), ("situation", situations)):
            seen = set()
            for v in values:
                if v not in seen:
                    seen.add(v)
                    self.attributes.append(MenuAttribute(attr_type=kind, value=v))

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "emoji": self.emoji, "category": self.category,
            "price": self.price, "has_soup": self.has_soup, "fullness": self.fullness,
            "time_min": self.time_min, "description": self.description, "is_active": self.is_active,
            "tastes": self.tastes, "ingredients": self.ingredients,
            "weathers": self.weathers, "situations": self.situations,
        }


class MenuAttribute(db.Model):
    __tablename__ = "menu_attributes"
    __table_args__ = (
        db.UniqueConstraint("menu_id", "attr_type", "value", name="uq_menu_attr"),
        db.CheckConstraint("attr_type IN ('taste','ingredient','weather','situation')", name="ck_attr_type"),
        db.Index("ix_menu_attr_type_value", "attr_type", "value"),
    )
    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey("menus.id", ondelete="CASCADE"), nullable=False)
    attr_type = db.Column(db.String(12), nullable=False)
    value = db.Column(db.String(20), nullable=False)
    menu = db.relationship("Menu", back_populates="attributes")


class Preference(db.Model):
    __tablename__ = "preferences"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    filters_json = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)


class Candidate(db.Model):
    __tablename__ = "candidates"
    __table_args__ = (db.UniqueConstraint("user_id", "menu_id", name="uq_candidate"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    menu_id = db.Column(db.Integer, db.ForeignKey("menus.id", ondelete="CASCADE"), nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=now)
    menu = db.relationship("Menu")


class Decision(db.Model):
    __tablename__ = "decisions"
    __table_args__ = (db.Index("ix_decisions_user_time", "user_id", "decided_at"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    menu_id = db.Column(db.Integer, db.ForeignKey("menus.id", ondelete="SET NULL"))
    menu_name = db.Column(db.String(30), nullable=False)
    price_at_decision = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    filters_json = db.Column(db.Text, nullable=False)
    decided_at = db.Column(db.DateTime, nullable=False, default=now, index=True)
    menu = db.relationship("Menu")

    def to_dict(self):
        m = self.menu
        return {
            "id": self.id,
            "menu_id": self.menu_id,
            "menu_name": self.menu_name,
            "emoji": m.emoji if m else "🍽️",
            "category": m.category if m else None,
            "price": self.price_at_decision,
            "reason": self.reason,
            "decided_at": self.decided_at.isoformat(timespec="seconds"),
        }


class DailyPick(db.Model):
    __tablename__ = "daily_picks"
    pick_date = db.Column(db.Date, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey("menus.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    menu = db.relationship("Menu")
