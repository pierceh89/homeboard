# Homeboard

FastAPI 기반 홈 대시보드입니다.  
실시간 버스 도착 정보와 단기 날씨 예보를 한 화면(`/home`)에 보여줍니다.

## 주요 기능

- 날씨 정보 조회: 기온, 강수확률, 습도, 풍속, 하늘 상태
- 시간대별 차트: 기온/강수확률/바람 탭 전환
- 버스 도착 정보 조회: 정류장별 노선 도착 예정 정보
- 공기질 정보 조회: 미세먼지, 초미세먼지 등
- 네이버 캘린더 일정 조회 API: CalDAV 기반 당일 일정 JSON 반환
- 접근 키(`ACCESS_KEY`) 기반 `/home` 페이지 보호

## 기술 스택

- Backend: FastAPI, Uvicorn, Jinja2, httpx
- Frontend: Tailwind CSS (CLI)
- Runtime: Python 3.12.8 (`apps/api/runtime.txt`)
- Python dependency management: uv

## 프로젝트 구조

```text
.
├── apps/
│   └── api/
│       ├── app/
│       │   ├── main.py          # FastAPI 앱 진입점, 템플릿 렌더링
│       │   ├── api.py           # 버스 도착 정보 조회/정규화
│       │   ├── weather.py       # 날씨 예보 조회/정규화
│       │   ├── air.py           # 공기질 정보 조회/정규화
│       │   ├── api_shared.py    # API 공유 유틸리티
│       │   └── settings.py      # 설정 관리
│       ├── static/
│       │   ├── templates/home.html
│       │   ├── src/input.css
│       │   └── css/tailwind.css
│       ├── pyproject.toml
│       ├── uv.lock
│       ├── Procfile
│       ├── app.json
│       ├── runtime.txt
│       ├── run.sh
│       └── settings.yaml
├── package.json
└── tailwind.config.js
```

## 사전 준비

1. Python 3.12+
2. Node.js + npm
3. 공공데이터 API 키
   - 버스 도착정보 API (경기도 버스도착정보)
   - 기상청 단기예보 API
   - 공기질 API

## 설치 방법

1. 저장소를 클론합니다:

   ```bash
   git clone https://github.com/pierceh89/homeboard.git
   cd homeboard
   ```

2. uv를 설치합니다:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Python 의존성을 설치합니다:

   ```bash
   cd apps/api
   uv sync --frozen
   ```

4. Node.js 의존성을 설치합니다:

   ```bash
   npm install
   ```

5. Tailwind CSS를 빌드합니다:
   ```bash
   npm run tw:build
   ```

## 환경 변수 설정

`.env` 파일을 생성하고 다음 변수를 설정합니다:

```env
PUBLIC_API_KEY=your_public_data_api_key
ACCESS_KEY=your_private_access_key  # 선택사항, 설정하지 않으면 접근 제한 없음
```

## 실행 방법

1. 개발 서버를 실행합니다:

   ```bash
   cd apps/api
   uv run --frozen uvicorn app.main:app --reload
   ```

2. 브라우저에서 `http://localhost:8000/home`에 접속합니다.

## 배포

### Heroku

1. Heroku CLI를 설치합니다.

2. Heroku 앱을 생성합니다:

   ```bash
   heroku create your-app-name
   ```

3. 환경 변수를 설정합니다:

   ```bash
   heroku config:set PUBLIC_API_KEY=your_api_key
   heroku config:set ACCESS_KEY=your_access_key  # 선택사항
   ```

4. 배포합니다:

   ```bash
   heroku container:login

   heroku container:push web --app homeboard --context-path apps/api # 도커 빌드 및 푸시

   # heroku container:push가 먹히지 않는 경우 직접 빌드 및 푸시
   docker buildx build --platform linux/amd64 -t registry.heroku.com/homeboard/web apps/api
   docker push registry.heroku.com/homeboard/web

   heroku container:release web --app homeboard
   ```

## API 엔드포인트

- `GET /home`: 홈 대시보드 페이지
- `GET /api/calendar/naver/today`: 네이버 캘린더 당일 일정 API

## 환경변수

- `PUBLIC_API_KEY`: 버스/날씨 공공 API 호출 키
- `ACCESS_KEY`: `/home` 접근 시 쿼리 파라미터로 전달할 키
- `NAVER_CALDAV_URL`: 네이버 CalDAV 서버 URL (기본값: `https://caldav.calendar.naver.com`)
- `NAVER_CALDAV_USERNAME`: 네이버 캘린더 CalDAV 계정
- `NAVER_CALDAV_PASSWORD`: 네이버 캘린더 CalDAV 비밀번호/앱 비밀번호
- `NAVER_CALDAV_CALENDAR_NAME`: 조회할 캘린더 이름 (선택)

## YAML 설정

날씨 좌표와 버스 정류장 목록은 `apps/api/settings.yaml`에서 관리합니다.

1. `apps/api/settings.yaml` 에서 원하는 지역/정류장 값으로 수정

`apps/api/settings.yaml` 예시:

```yaml
weather:
  region: "용인시 수지구 동천동"
  nx: 62
  ny: 122

bus_arrival:
  busstops:
    - id: "228003400"
      name: "벽산.동천디이스트정문"
      filter: ["17", "17-1"]
      no: "56421"
    - id: "228002981"
      name: "벽산아파트"
      filter: ["14"]
      no: "56079

air:
  station: "수지"
```

## 커스터마이징 포인트

- 버스 정류장/노선 필터: `apps/api/settings.yaml`의 `bus_arrival.busstops` 수정
- 날씨 지역 좌표: `apps/api/settings.yaml`의 `weather(nx, ny, region)` 수정
- 미세먼지 측정소: `apps/api/settings.yaml`의 `air.station` 수정
- UI 수정: `apps/api/static/templates/home.html`
- 스타일 수정: `apps/api/static/src/input.css` 변경 후 `npm run tw:build`
