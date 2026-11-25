# 04. 물품보관함

- **담당**: 김해찬
- **출처**: 행정안전부 한국지역정보개발원 공영 물품보관함 현황 실시간 정보 (`locker_info_v2`, `locker_detail_info_v2`, `locker_realtime_use_v2`)
- **갱신**: 자동, GitHub Actions 15분마다 (`scripts/update_lockers.py`)
- **샘플 여부**: 진짜 데이터

| 폴더 | 들어가는 것 |
|---|---|
| `raw/` | 전처리 전, 받은 그대로 |
| `processed/` | 전처리 후, 화면이나 기획서에 쓰는 표 |

| 파일 | 내용 |
|---|---|
| `raw/locker_info.csv` | 전국 보관함 위치, 이름, 운영 시간 |
| `raw/locker_detail.csv` | 보관함 크기, 요금 설명 |
| `raw/locker_realtime.csv` | 크기별 지금 빈 칸 수 |
| `processed/lockers_olympicpark.csv` | 올림픽공원 중심 1.5km 안, 실시간 값이 있는 보관함만 한 줄씩 (이름, 거리, 가까운 공연장, 빈 칸, 요금) |

- 같은 이름의 `.json` 은 API 응답 원본(증빙용)입니다. 인증키는 어떤 파일에도 없습니다.
- 하는 일: 1.5km 안만 고르기, 보관함 번호로 3개 표 합치기, 실시간 값 없는 곳 빼기. 자세히는 `notebooks/02_lockers_api.ipynb`
- 웹 화면은 `docs/data/lockers.json` 을 읽습니다.
- 자동 갱신 파일이라 **이름을 바꾸거나 옮기지 마세요.**
