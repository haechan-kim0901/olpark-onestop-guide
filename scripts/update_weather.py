"""올림픽공원 실시간 날씨를 받아 docs/data/weather.json 을 새로 만드는 스크립트.

GitHub Actions 가 15분마다 실행합니다 (.github/workflows/update-weather.yml).
사용 API: 기상청_단기예보 ((구)_동네예보) 조회서비스 (공공데이터포털)
  1. 초단기실황(getUltraSrtNcst): 지금 기온, 1시간 강수량, 습도, 바람, 강수 형태
  2. 초단기예보(getUltraSrtFcst): 앞으로 6시간 기온, 하늘 상태, 강수 형태, 강수량
  3. 체감온도 계산 (겨울: 기상청 바람냉각 공식, 여름: 기상청 여름철 공식)
  4. 팀 확인용 CSV 저장 (엑셀에서 바로 열림)
     - 전처리 전(원본): data/raw/weather/ 에 API 2개 응답을 JSON, CSV 로 그대로
     - 전처리 후(결과): data/processed/weather_now.csv (지금 1줄), weather_hours.csv (6시간 예보)

이미 있는 weather.json 으로 결과 CSV 만 다시 만들려면 (인증키 필요 없음):
  python scripts/update_weather.py --csv-only

인증키는 코드에 쓰지 않고, 환경 변수 DATA_GO_KR_KEY 로만 받습니다
(물품보관함과 같은 Secret. 공공데이터포털 인증키는 계정마다 하나라서 그대로 씁니다).
API 가 실패하면 기존 weather.json 을 그대로 두고 오류로 끝납니다.
"""
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from csv_out import PROCESSED, RAW, write_csv, write_raw_json

API_BASE = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "weather.json"
KST = timezone(timedelta(hours=9))
LAT, LON = 37.5207, 127.1214  # 올림픽공원 (평화의광장 부근, 송파구 방이동)


def latlon_to_grid(lat, lon):
    """위경도를 기상청 격자(nx, ny)로 바꿈 (기상청 제공 Lambert 변환 공식)."""
    RE, GRID, SLAT1, SLAT2, OLON, OLAT, XO, YO = 6371.00877, 5.0, 30.0, 60.0, 126.0, 38.0, 43, 136
    D = math.pi / 180.0
    re = RE / GRID
    slat1, slat2, olon, olat = SLAT1 * D, SLAT2 * D, OLON * D, OLAT * D
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(
        math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5))
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5) ** sn * math.cos(slat1) / sn
    ro = re * sf / math.tan(math.pi * 0.25 + olat * 0.5) ** sn
    ra = re * sf / math.tan(math.pi * 0.25 + lat * D * 0.5) ** sn
    theta = lon * D - olon
    if theta > math.pi:
        theta -= 2 * math.pi
    if theta < -math.pi:
        theta += 2 * math.pi
    theta *= sn
    return int(ra * math.sin(theta) + XO + 0.5), int(ro - ra * math.cos(theta) + YO + 0.5)


NX, NY = latlon_to_grid(LAT, LON)  # (62, 126)


def call(key, op, base):
    q = {"serviceKey": key, "pageNo": 1, "numOfRows": 1000, "dataType": "JSON",
         "base_date": base.strftime("%Y%m%d"), "base_time": base.strftime("%H%M"), "nx": NX, "ny": NY}
    url = f"{API_BASE}/{op}?{urllib.parse.urlencode(q)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        raw = r.read().decode("utf-8")
    try:
        body = json.loads(raw)["response"]
    except (ValueError, KeyError):
        # 인증키 오류 등은 XML 로 옴 (예: SERVICE_KEY_IS_NOT_REGISTERED_ERROR)
        raise RuntimeError(f"{op}: JSON 이 아닌 응답: {raw[:300]}")
    head = body.get("header", {})
    code, msg = head.get("resultCode"), head.get("resultMsg")
    items = ((body.get("body") or {}).get("items") or {}).get("item") or []
    return code, msg, items


def call_latest(key, op, now, lag_min, minute):
    """발표 시각이 지난 가장 최근 자료를 받음. 아직 없으면(03 NO_DATA) 한 시간 전 자료로."""
    t = now - timedelta(minutes=lag_min)
    base = t.replace(minute=minute, second=0, microsecond=0)
    if base > t:
        base -= timedelta(hours=1)
    for _ in range(3):
        code, msg, items = call(key, op, base)
        print(f"  {op} {base:%Y-%m-%d %H:%M} -> {code} {msg} {len(items)}개")
        if code == "00" and items:
            return base, items
        if code not in ("00", "03"):
            raise RuntimeError(f"{op}: 결과 코드 {code} {msg}")
        base -= timedelta(hours=1)
    return None, []


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def rain_mm(v):
    """초단기예보 RN1 은 '강수없음', '1mm 미만', '1.0mm', '30.0~50.0mm', '50.0mm 이상' 같은 글자."""
    s = str(v or "").strip()
    if not s or s in ("강수없음", "0"):
        return 0.0
    if "미만" in s:
        return 0.5
    s = s.replace("mm", "").replace("이상", "").strip()
    if "~" in s:
        s = s.split("~")[0]
    return num(s) or 0.0


def feels_like(t, rh, wind_ms, month):
    """기상청 체감온도. 10월~4월은 바람냉각(기온 10도 이하, 풍속 1.3m/s 이상), 5월~9월은 여름철 공식."""
    if t is None:
        return None
    if 5 <= month <= 9:
        if rh is None:
            return t
        tw = (t * math.atan(0.151977 * (rh + 8.313659) ** 0.5) + math.atan(t + rh) - math.atan(rh - 1.67633)
              + 0.00391838 * rh ** 1.5 * math.atan(0.023101 * rh) - 4.686035)
        return -0.2442 + 0.55399 * tw + 0.45535 * t - 0.0022 * tw ** 2 + 0.00278 * tw * t + 3.0
    if wind_ms is None or t > 10 or wind_ms < 1.3:
        return t
    v = (wind_ms * 3.6) ** 0.16
    return 13.12 + 0.6215 * t - 11.37 * v + 0.3965 * t * v


def r1(v):
    return None if v is None else round(v, 1)


def build(ncst_base, ncst, fcst_base, fcst):
    obs = {i["category"]: i.get("obsrValue") for i in ncst}
    t, rh, ws = num(obs.get("T1H")), num(obs.get("REH")), num(obs.get("WSD"))
    if t is None:
        raise RuntimeError("초단기실황에 기온(T1H)이 없습니다.")

    by_time = {}
    for i in fcst:
        k = f"{i['fcstDate']}{i['fcstTime']}"
        by_time.setdefault(k, {})[i["category"]] = i.get("fcstValue")
    hours = []
    for k in sorted(by_time)[:6]:
        f = by_time[k]
        ft = num(f.get("T1H"))
        hours.append({
            "time": f"{k[8:10]}:{k[10:12]}",
            "temp": r1(ft),
            "feels": r1(feels_like(ft, num(f.get("REH")), num(f.get("WSD")), int(k[4:6]))),
            "sky": int(num(f.get("SKY")) or 1),   # 1 맑음, 3 구름많음, 4 흐림
            "pty": int(num(f.get("PTY")) or 0),   # 0 없음, 1 비, 2 비/눈, 3 눈, 5 빗방울, 6 빗방울눈날림, 7 눈날림
            "rain_mm": rain_mm(f.get("RN1")),
        })

    return {
        "_설명": "scripts/update_weather.py 가 기상청 초단기실황, 초단기예보를 받아 자동 생성 (GitHub Actions 15분마다). "
                 "fetched_at 은 초단기실황 관측 시각(KST).",
        "sample": False,
        "source": "기상청_단기예보 ((구)_동네예보) 조회서비스 초단기실황, 초단기예보 (공공데이터포털)",
        "grid": {"nx": NX, "ny": NY, "name": "서울 송파구 방이동 (올림픽공원)"},
        "fetched_at": ncst_base.strftime("%Y-%m-%d %H:%M"),
        "forecast_base": fcst_base.strftime("%Y-%m-%d %H:%M") if fcst_base else "",
        "now": {
            "temp": r1(t),
            "feels": r1(feels_like(t, rh, ws, ncst_base.month)),
            "humidity": rh,
            "wind_ms": ws,
            "rain_1h_mm": num(obs.get("RN1")) or 0.0,
            "pty": int(num(obs.get("PTY")) or 0),
            # 실황에는 하늘 상태가 없어 가장 가까운 예보 시각의 값을 씀
            "sky": hours[0]["sky"] if hours else 1,
        },
        "hours": hours,
    }


SKY_KO = {1: "맑음", 3: "구름많음", 4: "흐림"}
PTY_KO = {0: "없음", 1: "비", 2: "비/눈", 3: "눈", 5: "빗방울", 6: "빗방울눈날림", 7: "눈날림"}
CAT_KO = {"T1H": "기온(도)", "RN1": "1시간 강수량(mm)", "REH": "습도(%)", "WSD": "풍속(m/s)", "VEC": "풍향(도)",
          "UUU": "동서바람성분(m/s)", "VVV": "남북바람성분(m/s)", "PTY": "강수형태(코드)", "SKY": "하늘상태(코드)",
          "LGT": "낙뢰(kA)"}


def save_processed_csv(out):
    now = out.get("now", {})
    write_csv(PROCESSED / "weather_now.csv", [{
        "관측시각": out.get("fetched_at", ""), "기온_도": now.get("temp"), "체감온도_도": now.get("feels"),
        "습도_퍼센트": now.get("humidity"), "풍속_ms": now.get("wind_ms"), "1시간강수량_mm": now.get("rain_1h_mm"),
        "강수형태": PTY_KO.get(now.get("pty"), now.get("pty")), "하늘상태": SKY_KO.get(now.get("sky"), now.get("sky")),
        "격자": f"nx={out.get('grid', {}).get('nx')}, ny={out.get('grid', {}).get('ny')}", "출처": out.get("source", ""),
    }])
    write_csv(PROCESSED / "weather_hours.csv", [{
        "예보발표시각": out.get("forecast_base", ""), "예보시각": h.get("time"), "기온_도": h.get("temp"),
        "체감온도_도": h.get("feels"), "하늘상태": SKY_KO.get(h.get("sky"), h.get("sky")),
        "강수형태": PTY_KO.get(h.get("pty"), h.get("pty")), "강수량_mm": h.get("rain_mm"),
    } for h in out.get("hours", [])])
    print("결과 CSV 저장: data/processed/weather_now.csv, weather_hours.csv")


def save_raw(name, op, base, items):
    for i in items:  # 원본 열은 그대로 두고, 읽기 쉽게 항목 이름만 한 열 덧붙임
        i.setdefault("category_ko", CAT_KO.get(i.get("category"), ""))
    params = {"dataType": "JSON", "numOfRows": 1000, "nx": NX, "ny": NY,
              "base_date": base.strftime("%Y%m%d"), "base_time": base.strftime("%H%M")}
    # 받은 시각 대신 발표 시각을 적어서, 자료가 같으면 파일도 그대로 (쓸데없는 커밋 방지)
    write_raw_json(RAW / "weather" / f"{name}.json", op, params, items, base.strftime("%Y-%m-%d %H:%M"))
    write_csv(RAW / "weather" / f"{name}.csv", items)
    print(f"원본 저장: data/raw/weather/{name}.json, .csv ({len(items)}행)")


def main():
    if "--csv-only" in sys.argv:
        save_processed_csv(json.loads(OUT.read_text(encoding="utf-8")))
        return
    key = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", "").strip())
    if not key:
        sys.exit("DATA_GO_KR_KEY 가 없습니다. 저장소 Settings > Secrets and variables > Actions 에 등록하세요.")
    now = datetime.now(KST).replace(tzinfo=None)
    print(f"격자 nx={NX}, ny={NY}, 지금 {now:%Y-%m-%d %H:%M} (KST)")
    # 초단기실황: 매시 정시 자료, 매시 40분 이후 제공 / 초단기예보: 매시 30분 자료, 매시 45분 이후 제공
    ncst_base, ncst = call_latest(key, "getUltraSrtNcst", now, 40, 0)
    if not ncst:
        sys.exit("초단기실황이 비어 있어 기존 파일을 그대로 둡니다.")
    try:
        fcst_base, fcst = call_latest(key, "getUltraSrtFcst", now, 45, 30)
    except RuntimeError as e:
        print(f"  초단기예보 실패, 지금 날씨만 저장: {e}")
        fcst_base, fcst = None, []
    out = build(ncst_base, ncst, fcst_base, fcst)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"저장: {out['fetched_at']} 기준 {out['now']['temp']}도, 체감 {out['now']['feels']}도, 예보 {len(out['hours'])}시간")

    # 팀 확인용: 전처리 전(기상청 원본) / 전처리 후(화면에 쓰는 값)
    save_raw("ultra_srt_ncst", "getUltraSrtNcst (초단기실황)", ncst_base, ncst)
    if fcst:
        save_raw("ultra_srt_fcst", "getUltraSrtFcst (초단기예보)", fcst_base, fcst)
    save_processed_csv(out)


if __name__ == "__main__":
    main()
