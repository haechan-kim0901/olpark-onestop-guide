# 08. 인구 밀집도

- **담당**: 정한솔
- **출처**: 서울 열린데이터광장 '서울시 실시간 인구데이터' (citydata_ppltn), 장소 `올림픽공원`
- **갱신**: 15분마다 자동 (GitHub Actions, `scripts/update_crowd.py`)
- **샘플 여부**: 인증키(SEOUL_API_KEY)를 등록하기 전까지는 샘플. 화면에 '예시' 표시

| 폴더 | 들어가는 것 |
|---|---|
| `raw/` | 서울시 API 응답 그대로 (`citydata_ppltn.json`, `.csv`) |
| `processed/` | `crowd_now.csv` 지금 혼잡도 1줄, `crowd_forecast.csv` 앞으로 12시간 예측 |

## 실제 값으로 바꾸는 법 (한 번만)

1. [서울 열린데이터광장](https://data.seoul.go.kr) 로그인 → 인증키 신청 (일반 인증키)
2. GitHub 저장소 Settings → Secrets and variables → Actions → New repository secret
3. 이름 `SEOUL_API_KEY`, 값에 인증키 붙여넣기 → 저장
4. Actions 탭 → '인구 밀집도 자동 갱신' → Run workflow

> 혼잡도 단계는 서울시 기준 그대로 씁니다: 여유, 보통, 약간 붐빔, 붐빔.
> 이 폴더 파일은 자동으로 만들어지니 이름을 바꾸거나 옮기지 마세요.
