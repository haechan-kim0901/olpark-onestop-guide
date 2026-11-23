# 전처리 전 (원본) 데이터

API 가 돌려준 값을 **고치지 않고 그대로** 저장한 곳입니다. 기획서의 "데이터 출처, 증빙" 용도입니다.
CSV 는 UTF-8 BOM 으로 저장해서 **엑셀에서 더블클릭해도 한글이 깨지지 않습니다.**
같은 내용의 `.json` 은 API 응답 원본(증빙용)입니다. 인증키는 어떤 파일에도 들어 있지 않습니다.

## 자동으로 갱신되는 파일 (GitHub Actions, 15분마다)

| 폴더 | 파일 | 내용 | 출처 |
|---|---|---|---|
| `lockers/` | `locker_info.csv` | 전국 공영 물품보관함 위치, 이름, 운영 시간 | 행정안전부 한국지역정보개발원 공영 물품보관함 현황 실시간 정보 (`locker_info_v2`) |
| `lockers/` | `locker_detail.csv` | 보관함 크기, 요금 설명 | 같은 API (`locker_detail_info_v2`) |
| `lockers/` | `locker_realtime.csv` | 크기별 지금 빈 칸 수 | 같은 API (`locker_realtime_use_v2`) |
| `weather/` | `ultra_srt_ncst.csv` | 올림픽공원 격자(62, 126) 지금 관측값 (기온, 강수, 습도, 바람) | 기상청 단기예보 조회서비스 초단기실황 |
| `weather/` | `ultra_srt_fcst.csv` | 앞으로 6시간 예보 | 기상청 단기예보 조회서비스 초단기예보 |

- 열 이름은 API 영어 이름 그대로입니다. 날씨 CSV 의 `category_ko` 열에 항목 뜻(기온, 습도 등)을 덧붙였습니다.
- 보관함 주요 열: `stlckId` 보관함 번호, `stlckRprsPstnNm` 대표 위치, `lat`/`lot` 위도/경도, `usePsblty소형/중형/대형StlckCnt` 크기별 빈 칸.

## 주차 (`parking/`)

| 파일 | 내용 |
|---|---|
| `schedule_SAMPLE.csv` | **합성 샘플** 공연 일정 (연습용, 진짜 아님) |
| `parking_SAMPLE_first1000.csv` | **합성 샘플** 입차 기록 앞 1,000줄 (전체 8만여 줄은 노트북이 만들어 씀) |

진짜 주차 CSV 는 용량이 커서 GitHub 에 올리지 않습니다 (`.gitignore` 로 `data/raw/*.csv` 제외).
각자 공공데이터포털에서 내려받아 Colab 에 직접 올려 쓰고, 받은 데이터는 아래 표에 적어 주세요.

| 데이터 이름 | 제공 기관 | 링크 | 받은 사람 | 받은 날짜 |
|---|---|---|---|---|
| (예) 차량입출차, 공연 연계 데이터 | 한국체육산업개발 | | | |
