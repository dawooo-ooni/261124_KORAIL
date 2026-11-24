# 점심메뉴 추천기 (Lunch Picker) — Flask 웹앱

HTML 단일 파일 아티팩트 `점심메뉴 추천기`를 Python Flask + SQLite 웹앱으로 옮긴 버전입니다.
화면과 사용 흐름(오늘의 추천 → 조건 설정 → 추천 → 후보 비교 → 최종 결정)은 원본 그대로이고,
메뉴 데이터·추천 로직·조건·후보·결정 기록은 서버(DB)에서 처리합니다.

## 실행 (Windows PowerShell)

```powershell
cd lunch_picker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # SECRET_KEY, ADMIN_PASSWORD 를 꼭 바꾸세요
flask init-db
flask seed
flask run
```

> `python` 명령이 Microsoft Store 안내로 연결되면 `py -m venv .venv` 를 쓰세요.
> PowerShell 실행 정책 때문에 `Activate.ps1` 이 막히면 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 후 다시 실행하세요.

macOS / Linux 는 `python3 -m venv .venv`, `source .venv/bin/activate`, `cp .env.example .env` 로 바꿔 실행합니다.

- 메인: http://127.0.0.1:5000
- 결정 이력·통계: http://127.0.0.1:5000/history
- 관리자: http://127.0.0.1:5000/admin (비밀번호 = `.env` 의 `ADMIN_PASSWORD`)

## CLI

| 명령 | 동작 |
|---|---|
| `flask init-db` | 테이블 생성 (이미 있으면 건너뜀) |
| `flask seed` | `app/seed/menus.json` 적재 (같은 이름은 건너뜀, 추가 개수 출력) |
| `flask reset-db` | 확인 후 DB 삭제·재생성·시드 적재 (개발용, `--yes` 로 확인 생략) |

## 테스트

```powershell
pytest
```

테스트는 메모리 DB(`sqlite:///:memory:`)를 사용합니다.

## 구조

```text
app/
  __init__.py        create_app(), Blueprint·CLI·오류 처리·로깅 등록
  config.py          Config / TestConfig
  models.py          users, menus, menu_attributes, preferences, candidates, decisions, daily_picks
  constants.py       선택지·화면 문구
  services/          recommender(추천·추첨), today(오늘의 추천), candidates(후보), stats(통계), data(공용 조회)
  routes/            main(페이지), api(JSON API), admin(관리자)
  templates/, static/
tests/               pytest
instance/lunch.db    SQLite DB (자동 생성)
logs/app.log         요청 오류·관리자 작업 기록
```

## 참고

- 사용자는 로그인 없이 쿠키 `lp_uid`(UUID, HttpOnly, SameSite=Lax, 1년)로 구분합니다. 브라우저가 다르면 다른 사용자입니다.
- 관리자 폼은 모두 CSRF 토큰으로 보호합니다. JSON API 는 SameSite 쿠키와 JSON 본문 강제로 보호합니다.
- `POST /api/recommendations` 는 명세 외 선택 필드 `focus_id` 를 받아, 화면에 떠 있는 뽑기 결과의 일치도·사유를 조건 변경에 맞춰 다시 계산해 `focus` 로 돌려줍니다.
- 같은 네트워크의 동료가 접속해야 하면 `flask run --host=0.0.0.0` 으로 실행하고 방화벽 허용 여부를 확인하세요.
