# 올팍 공연일 다국어 원스톱 가이드

한국체육산업개발(주) 공공데이터 활용 경진대회 출품작입니다. (마감 2026-12-01 18:00)

올림픽공원 공연 관객이 **공지, 주차 혼잡, 대기 안전(체감온도), 물품보관함 빈 칸, 현장 지도**를 한 화면에서 한국어와 영어로 확인하는 모바일 웹 서비스의 MVP 데모입니다.

- 데모 링크: `https://<계정이름>.github.io/olpark-onestop-guide/` (GitHub Pages 설정 후 생김, 아래 4번)
- 팀: 조소영, 김해찬, 정한솔, 한성우, 차승우
- **GitHub 처음이면 먼저 읽기**: [GitHub 사용 가이드 (PDF)](guide/GitHub_사용가이드.pdf)

## 폴더 구조

```
olpark-onestop-guide/
├─ docs/                      ← 웹 데모 (GitHub Pages 가 이 폴더를 그대로 보여 줌)
│  ├─ index.html              ← 화면 전체가 들어 있는 파일 하나 (HTML, CSS, JS)
│  └─ data/
│     ├─ parking_entry.json   ← 노트북이 만든 주차 입차 평균 (지금은 샘플 값)
│     ├─ lockers.json         ← 물품보관함 크기별 빈 칸 수 (15분마다 자동 갱신)
│     └─ weather.json         ← 올림픽공원 실시간 날씨 (15분마다 자동 갱신)
├─ notebooks/
│  ├─ 01_preprocess_parking.ipynb  ← 주차 전처리 노트북 (Colab)
│  ├─ 02_lockers_api.ipynb         ← 물품보관함 처리 과정 보기 (실행 결과 저장돼 있음)
│  └─ 03_weather_api.ipynb         ← 날씨 처리 과정 보기 (실행 결과 저장돼 있음)
├─ data/                      ← 팀 확인용 CSV (엑셀에서 바로 열림, 한글 안 깨짐)
│  ├─ 01_공연정보/  02_공중화장실/  03_날씨/  04_물품보관함/
│  ├─ 05_주차장/  06_공원볼거리/  07_주변관광정보/
│  │     (각 폴더 안: raw/ 전처리 전, processed/ 전처리 후, README.md 담당과 출처)
│  └─ README.md               ← 폴더 사용 약속 (파일 이름, _SAMPLE 등)
└─ README.md
```

> 웹 화면은 계속 `docs/data/*.json` 을 읽습니다. `data/` 의 CSV 는 사람이 확인하고 기획서 근거로 쓰는 용도입니다.
> 폴더 사용 약속은 [`data/README.md`](data/README.md), 데이터별 파일 목록은 각 폴더의 `README.md` 에 있습니다.

## 데이터가 화면까지 가는 길

```
공공데이터포털 CSV  →  Colab 노트북 (정리, 병합, 평균)  →  parking_entry.json  →  docs/data/ 에 업로드  →  웹 화면 그래프
```

`docs/index.html` 맨 위 `샘플 데이터` 부분에 화면별 값이 모여 있습니다. 하나씩 실제 데이터로 바꿔 가면 됩니다.

| 화면 | 지금 | 바꿀 방법 |
|---|---|---|
| 주차 혼잡 그래프 (`HOURS`, `ENTRY_SHOW`, `ENTRY_NORM`) | **JSON 연결 완료** (값은 샘플) | 노트북을 진짜 CSV로 실행 → JSON 교체 |
| 공연 목록 (`SHOWS`) | **CSV 자동 변환** (값은 샘플 12건) | `data/01_공연정보/processed/` 에 CSV 를 올리면 Actions 가 `docs/data/shows.json` 으로 바꿈. 첫 화면에서 스크롤 목록, 검색, 공연장 필터 |
| 공지 (`NOTICES`) | 샘플 | 팀이 직접 입력 |
| 실시간 주차 (`LOTS`) | 샘플 | 실시간 주차 API 를 `fetch` 로 호출 |
| 물품보관함 (`LOCKERS`) | **JSON 연결 완료** (값은 샘플) | `docs/data/lockers.json` 의 `empty`(빈 칸), `total`(전체 칸) 숫자만 고치면 화면이 바뀜. 실시간 API 가 생기면 같은 형식으로 변환 |
| 실시간 날씨 (`WEATHER`) | **자동 갱신** (기상청 API) | GitHub Actions 가 15분마다 `docs/data/weather.json` 생성. 아래 '실시간 날씨' 참고 |
| 체감온도 시간대 그래프 (`FEELS`) | 샘플 (2025 재생 모드) | 발표용 시연 값 그대로 사용 |
| 지도 (`PLACES`) | 고정 좌표 | 그대로 사용 |

## 1. Colab 에서 노트북 여는 법

1. 저장소에서 `notebooks/01_preprocess_parking.ipynb` 를 클릭
2. 주소창의 `github.com` 을 `githubtocolab.com` 으로 바꿔서 Enter (Colab 에서 바로 열림)
   - 또는 [colab.research.google.com](https://colab.research.google.com) → **파일 → 노트 열기 → GitHub** 탭 → 저장소 주소 붙여넣기
3. **Drive에 사본 저장** 을 눌러 내 사본에서 작업
4. 처음엔 `USE_SAMPLE = True` 그대로 위에서부터 `Shift + Enter` 로 끝까지 실행해 보기
5. 진짜 CSV가 준비되면 `USE_SAMPLE = False`, 파일 이름과 컬럼 이름만 0단계 셀에서 고치고 다시 실행
6. 마지막 셀에서 내려받은 `parking_entry.json` 을 GitHub `docs/data/` 에 업로드 (Add file → Upload files)

> 수정한 노트북을 저장소에 다시 넣을 때: Colab **파일 → GitHub에 사본 저장** → 이 저장소, `main` 브랜치 선택.

## 2. 팀원 5명이 같이 작업하는 법

처음이면 **GitHub 웹사이트에서만** 작업해도 충분합니다. (프로그램 설치 불필요)

1. **초대 받기**: 저장소 주인이 Settings → Collaborators → Add people 로 팀원 GitHub 아이디를 초대 → 메일에서 수락
2. **역할 나누기**: 같은 파일을 동시에 고치면 충돌이 나니 파일 단위로 맡기
   | 담당 | 파일 |
   |---|---|
   | 데이터 전처리 | `notebooks/` , `docs/data/*.json` |
   | 웹 화면 | `docs/index.html` |
   | 기획서, 발표 | 노션 (저장소 밖) |
3. **파일 고치기**: 파일 열기 → 연필 아이콘(Edit) → 수정 → **Commit changes** → 무엇을 바꿨는지 한 줄로 적기 (예: `주차 그래프 제목 수정`)
4. **새 파일 올리기**: 폴더에서 **Add file → Upload files**
5. **원본 CSV 는 올리지 않기**: 용량 제한(파일당 100MB)과 개인정보 우려. 출처만 `data/05_주차장/README.md` 에 기록
6. 큰 변경은 **Issues** 탭에 할 일로 적고 담당자를 지정하면 누가 뭘 하는지 한눈에 보입니다

## 3. 내 PC 에서 화면 미리 보기

`docs/index.html` 을 더블클릭하면 열리지만, 이때는 브라우저 보안 때문에 JSON 을 못 읽어 **샘플 값**이 보입니다.
JSON 까지 반영된 화면은 아래 4번 GitHub Pages 링크에서 확인하세요.
(파이썬이 있으면 `docs` 폴더에서 `python -m http.server` 실행 후 http://localhost:8000 접속해도 됩니다)

## 4. GitHub Pages 로 데모 링크 만들기 (무료, 공개 저장소 필요)

1. 저장소 **Settings → Pages**
2. Build and deployment 의 Source: **Deploy from a branch**
3. Branch: **main**, 폴더: **/docs** → **Save**
4. 1~2분 뒤 같은 화면 위쪽에 `https://<계정이름>.github.io/olpark-onestop-guide/` 링크가 뜸
5. 이 링크를 기획서의 **서비스 확인 방법** 칸에 적기

## 사용 데이터

| 데이터 | 기관 | 쓰는 곳 |
|---|---|---|
| 차량 입출차, 공연 연계 데이터 | 한국체육산업개발 | 주차 혼잡 그래프 |
| 올림픽공원 실시간 주차 현황 | 한국체육산업개발 | 실시간 주차 위젯 |
| 단기예보 (체감온도) | 기상청 | 대기 안전 등급 |

## 일정

| 날짜 | 할 일 |
|---|---|
| ~11/26 | 데이터 수집, 노트북 전처리, 기획서 초안 |
| 11/27~29 | 웹 데모 실제 데이터 연결, GitHub Pages 배포 |
| 11/30 | 최종 점검 |
| 12/1 18:00 | data@ksponco.or.kr 메일 제출 (신청서, 기획서, 개인정보 동의서) |

## 물품보관함 현황 화면 (대시보드 → 물품보관함 카드)

- **보이는 곳**: 대시보드 맨 아래 `물품보관함` 카드 → 누르면 보관함 화면. 지도 탭에도 `보관함` 필터가 생김
- **무엇을 보여 주나**: 보관함마다 소형, 중형, 대형 빈 칸 수와 상태(여유 / 얼마 안 남음 / 만석). 내 공연장 근처에서 빈 칸이 있는 보관함을 맨 위에 추천
- **상태 기준**: 빈 칸 0 = 만석. 전체 칸 수를 알면 15% 미만, 모르면 3칸 이하 = 얼마 안 남음. 그 외 = 여유
- **지금 값**: `docs/data/lockers.json` 은 샘플(`"sample": true`). 아래 방법으로 실제 값으로 바꾸면 화면의 '예시' 표시와 출처 문구가 자동으로 바뀜

### 실제 데이터로 바꾸는 법 (인증키는 Colab 에서만)

사용 API: **행정안전부 한국지역정보개발원_(전국 통합데이터) 공영 물품보관함 현황 실시간 정보** (공공데이터포털, REST)

| 기능 | 주소 |
|---|---|
| 위치, 이름, 운영 시간 | `https://apis.data.go.kr/B551982/psl_v2/locker_info_v2` |
| 크기, 요금 설명 | `https://apis.data.go.kr/B551982/psl_v2/locker_detail_info_v2` |
| 크기별 지금 빈 칸 수 | `https://apis.data.go.kr/B551982/psl_v2/locker_realtime_use_v2` |

요청 값: `serviceKey`(인증키), `type=JSON`, `pageNo`, `numOfRows`(1000 이하), 필요하면 `stdgCd`(지역 코드, 서울 1100000000). 정상이면 결과 코드 `K0`, `K3 NODATA_ERROR` 는 키는 정상인데 데이터가 없다는 뜻 (노트북이 지역 코드를 넣어 자동 재시도).

**처리 과정 보기:** `notebooks/02_lockers_api.ipynb` 를 GitHub 에서 클릭하면 실행 결과(표, 숫자)가 저장된 채로 보입니다. 실행하지 않아도 됩니다.
가져오기, 정리(1.5km 고르기, 세 표 합치기, 화면 형식), 안정성(오류 대비, 점검표), 결과 형태 순서이고, 마지막에 자동 갱신 스크립트와 결과가 같은지 확인합니다.

직접 돌려 보려면 [Colab 에서 바로 열기](https://colab.research.google.com/github/haechan-kim0901/olpark-onestop-guide/blob/main/notebooks/02_lockers_api.ipynb) → **런타임 → 모두 실행** ("Google 이 만들지 않은 노트북" 경고는 무시하고 실행).
- 기본 `MODE = "saved"`: Actions 가 올려 둔 최근 원본으로 실행, **인증키 필요 없음**
- `MODE = "live"`: 지금 API 를 부름. 인증키는 환경 변수 `DATA_GO_KR_KEY` 에서 읽고, 없으면 입력 칸이 뜸 (화면, 파일 어디에도 남지 않음)
- 화면 값은 Actions 가 15분마다 자동으로 바꾸므로, 파일을 직접 올릴 필요는 없습니다

> **인증키를 `index.html`, GitHub, 노션, 단톡방에 넣지 마세요.** GitHub Pages 는 소스가 공개라서 키가 그대로 노출됩니다. 그래서 화면은 키 없이 JSON 만 읽습니다. 발표 직전에 노트북을 한 번 더 돌리면 최신 값이 됩니다.

- 이 API 는 전체 칸 수를 주지 않아 화면은 빈 칸 수만 보여 줌
- 2026-11-23 실제 실행 결과: 올림픽공원 1.5km 안 7곳 (올림픽공원역 5호선, 9호선, 몽촌토성, 한성백제, 강동구청, 송파나루, 방이). 공원 밖 먼 역은 지도 가장자리에 방향만 맞춰 표시
- 공원 안 임시 보관함(KSPO DOME 앞, 88잔디마당)은 샘플에만 있는 가상 예시

### 자동 갱신 (GitHub Actions, 15분마다)

`.github/workflows/update-lockers.yml` 이 15분마다 `scripts/update_lockers.py` 를 실행해 `docs/data/lockers.json` 을 새로 만들고 main 에 커밋합니다. 노트북 02 와 같은 전처리를 합니다 (노트북 3단계에서 두 결과가 같은지 확인). 데모 화면은 5분마다 이 파일을 다시 읽고, 카드에 "마지막 갱신" 시각을 보여 줍니다. 1시간 넘게 갱신이 없으면 빨간 글씨로 알려 줍니다.

**처음 한 번만: 인증키 등록**
1. 저장소 **Settings → Secrets and variables → Actions → New repository secret**
2. Name: `DATA_GO_KR_KEY`, Secret: 공공데이터포털 **일반 인증키(Decoding)** 붙여 넣기 → **Add secret**
3. **Actions** 탭 → 왼쪽 `물품보관함 자동 갱신` → **Run workflow** 로 바로 한 번 실행해 보기 (초록 체크면 성공)

참고
- GitHub 사정으로 실행이 몇 분 늦거나 가끔 건너뛸 수 있습니다
- 저장소에 60일 동안 활동이 없으면 GitHub 가 예약 실행을 멈춥니다 (Actions 탭에서 다시 켜기)
- 15분마다 "보관함 빈 칸 자동 갱신" 커밋이 쌓이는 것은 정상입니다
- 멈추고 싶으면 Actions 탭 → 이 워크플로 → `...` → **Disable workflow**

## 실시간 날씨 (대시보드, 대기 안전 화면)

- **보이는 곳**: 대시보드 '지금 할 일' 아래 `지금 올림픽공원 날씨` 카드, 대기 안전 탭 맨 위의 자세한 카드
- **무엇을 보여 주나**: 지금 기온, 하늘 상태(맑음, 구름 많음, 흐림, 비, 눈), 체감온도, 습도, 바람, 1시간 강수량, 앞으로 6시간 예보, 마지막 관측 시각
- **야외 공연 팁**: 6시간 안에 비나 눈 예보가 있으면 우비, 우산 안내 / 체감 영하면 핫팩, 외투 / 밤에 8도 이하면 겉옷 / 31도 이상이면 물, 그늘 / 바람 9m/s 이상이면 짐 조심
- **공연 정보와의 관계**: 공연 시간표는 2025년 재생 모드 그대로이고, 날씨 카드만 오늘 실제 값입니다

사용 API: **기상청_단기예보 ((구)_동네예보) 조회서비스** (공공데이터포털, REST)

| 기능 | 주소 | 발표 |
|---|---|---|
| 초단기실황 (지금 관측값) | `https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst` | 매시 정시 자료, 40분쯤 제공 |
| 초단기예보 (6시간 예보) | `https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst` | 매시 30분 자료, 45분쯤 제공 |

- 위치: 올림픽공원(위도 37.5207, 경도 127.1214) → 기상청 격자 **nx 62, ny 126** (송파구 방이동). 스크립트가 직접 계산
- 체감온도: 10월~4월은 기상청 바람냉각 공식, 5월~9월은 기상청 여름철 공식으로 계산
- `.github/workflows/update-weather.yml` 이 15분마다 `scripts/update_weather.py` 실행 → `docs/data/weather.json` 저장 → 바뀌었으면 main 에 커밋. 기상청 자료가 한 시간에 한 번 바뀌어 커밋도 보통 한 시간에 하나
- 인증키는 보관함과 같은 `DATA_GO_KR_KEY` Secret 을 그대로 씁니다 (공공데이터포털 인증키는 계정마다 하나)
- 화면은 5분마다 파일을 다시 읽고, 관측 시각이 2시간 넘게 지나면 빨간 글씨로 알려 줌. 파일이 아직 없으면 '예시' 표시와 함께 샘플 값
- **처리 과정 보기**: `notebooks/03_weather_api.ipynb` ([Colab 에서 열기](https://colab.research.google.com/github/haechan-kim0901/olpark-onestop-guide/blob/main/notebooks/03_weather_api.ipynb)). 격자 변환, 발표 시각 고르기, 세로 표를 시각별 표로, 강수량 글자를 숫자로, 체감온도, 안정성 점검을 단계별로 보여 줌. 실행 결과가 저장돼 있어 GitHub 에서 바로 읽을 수 있고, 기본 `saved` 모드는 인증키 없이 돌아감

**처음 한 번 실행해 보기**: **Actions** 탭 → 왼쪽 `날씨 자동 갱신` → **Run workflow**. 초록 체크면 성공. 빨간 X 면 로그의 `날씨 데이터 받기` 단계를 열어 보세요. `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` 는 기상청 API 활용 승인이 막 났을 때 키가 퍼지기까지(보통 1시간 안팎) 기다리면 해결됩니다.

