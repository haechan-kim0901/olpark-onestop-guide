# 올팍 공연일 다국어 원스톱 가이드

한국체육산업개발(주) 공공데이터 활용 경진대회 출품작입니다. (마감 2026-12-01 18:00)

올림픽공원 공연 관객이 **공지, 주차 혼잡, 대기 안전(체감온도), 현장 지도**를 한 화면에서 한국어와 영어로 확인하는 모바일 웹 서비스의 MVP 데모입니다.

- 데모 링크: `https://<계정이름>.github.io/olpark-onestop-guide/` (GitHub Pages 설정 후 생김, 아래 4번)
- 팀: 조소영, 김해찬, 정한솔, 한성우, 차승우

## 폴더 구조

```
olpark-onestop-guide/
├─ docs/                      ← 웹 데모 (GitHub Pages 가 이 폴더를 그대로 보여 줌)
│  ├─ index.html              ← 화면 전체가 들어 있는 파일 하나 (HTML, CSS, JS)
│  └─ data/
│     └─ parking_entry.json   ← 노트북이 만든 주차 입차 평균 (지금은 샘플 값)
├─ notebooks/
│  └─ 01_preprocess_parking.ipynb  ← Colab 전처리 노트북
├─ data/
│  ├─ raw/                    ← 원본 CSV (GitHub 에 안 올림, 출처만 기록)
│  └─ processed/              ← 팀원과 나눌 작은 중간 결과
└─ README.md
```

## 데이터가 화면까지 가는 길

```
공공데이터포털 CSV  →  Colab 노트북 (정리, 병합, 평균)  →  parking_entry.json  →  docs/data/ 에 업로드  →  웹 화면 그래프
```

`docs/index.html` 맨 위 `샘플 데이터` 부분에 화면별 값이 모여 있습니다. 하나씩 실제 데이터로 바꿔 가면 됩니다.

| 화면 | 지금 | 바꿀 방법 |
|---|---|---|
| 주차 혼잡 그래프 (`HOURS`, `ENTRY_SHOW`, `ENTRY_NORM`) | **JSON 연결 완료** (값은 샘플) | 노트북을 진짜 CSV로 실행 → JSON 교체 |
| 공연 목록 (`SHOWS`), 공지 (`NOTICES`) | 샘플 | 공연 일정 데이터로 채우거나 팀이 직접 입력 |
| 실시간 주차 (`LOTS`) | 샘플 | 실시간 주차 API 를 `fetch` 로 호출 |
| 체감온도 (`FEELS`) | 샘플 | 기상청 단기예보 API 또는 노트북 |
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
5. **원본 CSV 는 올리지 않기**: 용량 제한(파일당 100MB)과 개인정보 우려. 출처만 `data/raw/README.md` 에 기록
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
