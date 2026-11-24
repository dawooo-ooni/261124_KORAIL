"""관리자 폼 (Flask-WTF, CSRF 보호)."""
from flask_wtf import FlaskForm
from wtforms import (BooleanField, IntegerField, PasswordField, SelectField,
                     SelectMultipleField, StringField)
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, ValidationError
from wtforms.widgets import CheckboxInput, ListWidget

from .constants import ATTR_CHOICES, CATEGORIES
from .extensions import db
from .models import Menu


class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


def _choices(values):
    return list(values)


class LoginForm(FlaskForm):
    password = PasswordField("관리자 비밀번호", validators=[DataRequired("비밀번호를 입력해 주세요.")])


class MenuForm(FlaskForm):
    name = StringField("메뉴명", validators=[DataRequired("메뉴명을 입력해 주세요."),
                                          Length(max=30, message="30자까지 입력할 수 있어요.")])
    emoji = StringField("이모지", validators=[DataRequired("이모지를 입력해 주세요."),
                                           Length(max=16, message="이모지는 짧게 입력해 주세요.")])
    category = SelectField("카테고리", choices=_choices(CATEGORIES))
    price = IntegerField("가격(원)", validators=[
        InputRequired("가격을 입력해 주세요."),
        NumberRange(1000, 100000, "가격은 1,000~100,000원 사이여야 해요.")])
    fullness = IntegerField("포만감(1~5)", default=3, validators=[
        InputRequired("포만감을 입력해 주세요."), NumberRange(1, 5, "포만감은 1~5 사이여야 해요.")])
    time_min = IntegerField("소요 시간(분)", default=15, validators=[
        InputRequired("소요 시간을 입력해 주세요."), NumberRange(1, 120, "소요 시간은 1~120분 사이여야 해요.")])
    description = StringField("한 줄 설명", validators=[
        DataRequired("설명을 입력해 주세요."), Length(max=80, message="80자까지 입력할 수 있어요.")])
    has_soup = BooleanField("국물 있음")
    is_active = BooleanField("추천 대상으로 사용", default=True)
    tastes = MultiCheckboxField("맛", choices=_choices(ATTR_CHOICES["taste"]))
    ingredients = MultiCheckboxField("재료", choices=_choices(ATTR_CHOICES["ingredient"]))
    weathers = MultiCheckboxField("어울리는 날씨", choices=_choices(ATTR_CHOICES["weather"]))
    situations = MultiCheckboxField("어울리는 상황", choices=_choices(ATTR_CHOICES["situation"]))

    def __init__(self, *args, menu_id: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._menu_id = menu_id

    def validate_name(self, field):
        field.data = (field.data or "").strip()
        stmt = db.select(Menu.id).where(Menu.name == field.data)
        if self._menu_id is not None:
            stmt = stmt.where(Menu.id != self._menu_id)
        if db.session.execute(stmt).first():
            raise ValidationError("이미 같은 이름의 메뉴가 있어요.")

    def validate_description(self, field):
        field.data = (field.data or "").strip()
