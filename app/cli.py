"""flask init-db / seed / reset-db 명령."""
import json
import os

import click
from flask import Flask, current_app

from .extensions import db
from .models import Menu


def seed_path() -> str:
    return os.path.join(current_app.root_path, "seed", "menus.json")


def seed_menus() -> int:
    """menus.json 을 적재한다. 같은 이름 메뉴는 건너뛰고 추가한 개수를 돌려준다."""
    with open(seed_path(), encoding="utf-8") as fp:
        rows = json.load(fp)
    existing = set(db.session.execute(db.select(Menu.name)).scalars())
    added = 0
    for r in rows:
        if r["name"] in existing:
            continue
        m = Menu(
            name=r["name"], emoji=r["emoji"], category=r["category"], price=r["price"],
            has_soup=bool(r["has_soup"]), fullness=r["fullness"], time_min=r["time_min"],
            description=r["description"], is_active=True,
        )
        m.set_attributes(r.get("tastes", []), r.get("ingredients", []),
                         r.get("weathers", []), r.get("situations", []))
        db.session.add(m)
        existing.add(r["name"])
        added += 1
    db.session.commit()
    return added


def enable_rls() -> None:
    """Postgres(Supabase)에서는 모든 테이블에 RLS 를 켠다.
    정책이 없으므로 Supabase 공개 API(anon/authenticated)로는 접근할 수 없고,
    앱은 DB 소유자 계정으로 접속하므로 영향이 없다."""
    if db.engine.dialect.name != "postgresql":
        return
    with db.engine.begin() as conn:
        for table in db.metadata.sorted_tables:
            conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY')


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        """테이블 생성 (이미 있으면 건너뜀)."""
        db.create_all()
        enable_rls()
        click.echo("DB 테이블 준비 완료.")

    @app.cli.command("seed")
    def seed():
        """seed/menus.json 적재."""
        db.create_all()
        added = seed_menus()
        total = db.session.execute(db.select(db.func.count(Menu.id))).scalar_one()
        click.echo(f"메뉴 {added}개 추가 (전체 {total}개).")

    @app.cli.command("reset-db")
    @click.option("--yes", is_flag=True, help="확인 질문 없이 실행")
    def reset_db(yes):
        """DB 삭제·재생성·시드 적재 (개발용)."""
        if not yes and not click.confirm("모든 데이터(결정 이력 포함)를 지우고 다시 만들까요?"):
            click.echo("취소했어요.")
            return
        db.drop_all()
        db.create_all()
        enable_rls()
        added = seed_menus()
        click.echo(f"DB 를 다시 만들고 메뉴 {added}개를 적재했어요.")
