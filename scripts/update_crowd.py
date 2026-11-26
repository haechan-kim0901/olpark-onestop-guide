"""올림픽공원 주변 인구 밀집도를 받아 docs/data/crowd.json 을 새로 만드는 스크립트.

GitHub Actions 가 15분마다 실행합니다 (.github/workflows/update-crowd.yml).
사용 API: 서울 열린데이터광장 '서울시 실시간 인구데이터' (citydata_ppltn, 서울 주요 장소 115곳)
  - 지금 혼잡도 단계(여유, 보통, 약간 붐빔, 붐빔), 안내 문구, 추정 인구 범위
  - 앞으로 12시간 혼잡도 예측
  - 서울시 자료는 5분 단위로 바뀝니다.
팀 확인용 CSV 저장
  - 전처리 전(원본): data/08_인구밀집도/raw/citydata_ppltn.json, .csv
  - 전처리 후(결과): data/08_인구밀집도/processed/crowd_now.csv (지금 1줄), crowd_forecast.csv (예측)

인증키는 코드에 쓰지 않고, 환경 변수 SEOUL_API_KEY 로만 받습니다
(서울 열린데이터광장 인증키. 공공데이터포털 키와 다릅니다).
키가 아직 없으면 아무것도 바꾸지 않고 정상 종료합니다 (화면은 샘플 값 그대로).
API 가 실패하면 기존 crowd.json 을 그대로 두고 오류로 끝납니다.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from csv_out import CROWD_DIR, write_csv, write_raw_json

RAW = CROWD_DIR / "raw"
PROCESSED = CROWD_DIR / "processed"
OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "crowd.json"
KST = timezone(timedelta(hours=9))
AREA = os.environ.get("SEOUL_AREA", "올림픽공원")  # 서울시 주요 장소 이름 그대로
LEVELS = ["여유", "보통", "약간 붐빔", "붐빔"]


def find_area(obj):
    """응답 안에서 AREA_CONGEST_LVL 이 들어 있는 장소 정보를 찾음 (응답 모양이 조금 달라도 동작)."""
    if isinstance(obj, dict):
        if "AREA_CONGEST_LVL" in obj:
            return obj
        for v in obj.values():
            r = find_area(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_area(v)
            if r:
                return r
    return None


def num(v):
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def main():
    key = urllib.parse.unquote(os.environ.get("SEOUL_API_KEY", "").strip())
    if not key:
        print("SEOUL_API_KEY 가 없어 건너뜁니다. 서울 열린데이터광장 인증키를 Settings > Secrets and variables > Actions 에 등록하면 실제 값으로 바뀝니다.")
        return 0
    url = f"http://openapi.seoul.go.kr:8088/{urllib.parse.quote(key)}/json/citydata_ppltn/1/5/{urllib.parse.quote(AREA)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    a = find_area(data)
    if not a:
        sys.exit(f"응답에 혼잡도 정보가 없어 기존 파일을 그대로 둡니다: {str(data)[:300]}")

    fetched = a.get("PPLTN_TIME") or datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    fcst = []
    for f in a.get("FCST_PPLTN") or []:
        t = str(f.get("FCST_TIME", ""))
        fcst.append({"time": t[-5:], "level": f.get("FCST_CONGEST_LVL", ""),
                     "min": num(f.get("FCST_PPLTN_MIN")), "max": num(f.get("FCST_PPLTN_MAX"))})
    lvl = a.get("AREA_CONGEST_LVL", "")
    out = {
        "_설명": "scripts/update_crowd.py 가 서울시 실시간 인구데이터(citydata_ppltn)를 받아 자동 생성 (GitHub Actions 15분마다). fetched_at 은 서울시 자료 기준 시각(KST).",
        "sample": False,
        "area": a.get("AREA_NM", AREA),
        "fetched_at": fetched,
        "level": lvl,
        "level_idx": LEVELS.index(lvl) if lvl in LEVELS else None,
        "message": a.get("AREA_CONGEST_MSG", ""),
        "min": num(a.get("AREA_PPLTN_MIN")),
        "max": num(a.get("AREA_PPLTN_MAX")),
        "forecast": fcst[:12],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # 팀 확인용: 원본(인증키 없이)과 정리 결과
    raw_item = {k: v for k, v in a.items() if k != "FCST_PPLTN"}
    write_raw_json(RAW / "citydata_ppltn.json", "citydata_ppltn", {"AREA_NM": AREA}, [a], fetched)
    write_csv(RAW / "citydata_ppltn.csv", [raw_item])
    write_csv(PROCESSED / "crowd_now.csv",
              [{"기준시각": fetched, "장소": out["area"], "혼잡도": lvl, "최소인구": out["min"], "최대인구": out["max"], "안내": out["message"]}])
    write_csv(PROCESSED / "crowd_forecast.csv",
              [{"예측시각": f["time"], "혼잡도": f["level"], "최소인구": f["min"], "최대인구": f["max"]} for f in out["forecast"]])
    print(f"{out['area']} {fetched} 혼잡도 {lvl} ({out['min']}~{out['max']}명), 예측 {len(out['forecast'])}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
