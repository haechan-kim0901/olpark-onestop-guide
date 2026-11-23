"""물품보관함 실시간 빈 칸을 받아 docs/data/lockers.json 을 새로 만드는 스크립트.

GitHub Actions 가 15분마다 실행합니다 (.github/workflows/update-lockers.yml).
하는 일은 notebooks/02_lockers_api.ipynb 와 같습니다.
  1. 공영 물품보관함 API 3개(위치, 요금, 실시간 빈 칸) 받기
  2. 올림픽공원 중심 1.5km 안 보관함만 고르기
  3. 보관함 번호(stlckId)로 세 표 합치기
  4. 화면용 형식(lockers.json)으로 바꾸기

인증키는 코드에 쓰지 않고, 환경 변수 DATA_GO_KR_KEY 로만 받습니다
(GitHub 저장소 Settings > Secrets 에 등록한 값).
API 가 실패하면 기존 lockers.json 을 그대로 두고 오류로 끝납니다.
"""
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_BASE = "https://apis.data.go.kr/B551982/psl_v2"
STDG_CD = "1100000000"  # 서울특별시. 지역 코드 없이 K3(데이터 없음)이면 이 값으로 다시 시도
OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "lockers.json"
KST = timezone(timedelta(hours=9))

CENTER_LAT, CENTER_LON = 37.5207, 127.1214  # 올림픽공원 중심 (평화의광장 부근)
RADIUS_M = 1500
VENUES = {
    "dome": (37.5196, 127.1273),   # KSPO DOME
    "hall": (37.5180, 127.1250),   # 올림픽홀
    "arena": (37.5186, 127.1300),  # 핸드볼경기장
    "lawn": (37.5213, 127.1196),   # 88잔디마당
}
NEAR_M = 600

# 데모 지도는 개략도라서, 공원 옆 역은 지도 위 역 표시 옆에 고정하고 먼 역은 방향에 맞춰 가장자리에
KNOWN = {
    "올림픽공원": (318, 160, "Olympic Park Stn"),
    "몽촌토성": (58, 124, "Mongchontoseong Stn"),
    "한성백제": (126, 270, "Hanseong Baekje Stn"),
    "강동구청": (None, None, "Gangdong-gu Office Stn"),
    "송파나루": (None, None, "Songpanaru Stn"),
    "방이": (None, None, "Bangi Stn"),
}


def call_once(key, path, extra):
    items, page = [], 1
    while True:
        q = {"serviceKey": key, "type": "JSON", "pageNo": page, "numOfRows": 1000, **extra}
        url = f"{API_BASE}/{path}?{urllib.parse.urlencode(q)}"
        with urllib.request.urlopen(url, timeout=30) as r:
            raw = r.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except ValueError:
            raise RuntimeError(f"{path}: JSON 이 아닌 응답: {raw[:200]}")
        head = body.get("header", {})
        code = head.get("resultCode")
        if code != "K0":
            return code, head.get("resultMsg"), items
        got = body.get("body", {}).get("item") or []
        got = got if isinstance(got, list) else [got]
        items += got
        total = int(body.get("body", {}).get("totalCount") or len(items))
        if len(items) >= total or not got:
            return code, "", items
        page += 1


def call(key, path):
    for extra in ({}, {"stdgCd": STDG_CD}):
        code, msg, items = call_once(key, path, extra)
        print(f"  {path} {extra or '(지역 코드 없음)'} -> {code} {msg} {len(items)}개")
        if code == "K0" and items:
            return items
        if code not in ("K0", "K3"):
            raise RuntimeError(f"{path}: 결과 코드 {code} {msg}")
    return []


def dist_m(a_lat, a_lon, b_lat, b_lon):
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def cnt(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def hhmm(v):
    v = str(v or "")
    return f"{v[:2]}:{v[2:4]}" if len(v) >= 4 else ""


def edge_xy(lat, lon):
    dx = (lon - CENTER_LON) * 88000
    dy = (CENTER_LAT - lat) * 111000
    if dx == 0 and dy == 0:
        return 180, 150
    t = min((164 / abs(dx)) if dx else 1e9, (134 / abs(dy)) if dy else 1e9)
    return round(180 + dx * t), round(150 + dy * t)


def place_of(name, lat, lon):
    line = re.match(r"^(\d)호선", name)
    suffix = f" (Line {line.group(1)})" if line else ""
    for k, (x, y, en) in KNOWN.items():
        if k in name:
            if x is None:
                x, y = edge_xy(lat, lon)
            return x, y, en + suffix
    x, y = edge_xy(lat, lon)
    return x, y, name


def build(info, detail, realtime):
    rt_by_id = {str(r.get("stlckId")): r for r in realtime}
    dt_by_id = {str(r.get("stlckId")): r for r in detail}

    nearby = []
    for r in info:
        lat, lon = num(r.get("lat")), num(r.get("lot"))
        if lat is None or lon is None:
            continue
        d = dist_m(CENTER_LAT, CENTER_LON, lat, lon)
        if d <= RADIUS_M:
            nearby.append((round(d), r, lat, lon))
    nearby.sort(key=lambda x: x[0])

    lockers, latest = [], ""
    for d, r, lat, lon in nearby:
        sid = str(r.get("stlckId"))
        rt = rt_by_id.get(sid)
        if not rt:
            continue  # 실시간 값이 없으면 '만석' 으로 오해할 수 있어 뺌
        sizes = {}
        for key, field in (("S", "usePsbltySmlszStlckCnt"), ("M", "usePsbltyMdmszStlckCnt"), ("L", "usePsbltyLrgszStlckCnt")):
            e = cnt(rt.get(field))
            if e is not None:
                sizes[key] = {"total": None, "empty": e}
        if not sizes:
            continue
        latest = max(latest, str(rt.get("totDt") or ""))
        name = str(r.get("stlckRprsPstnNm") or sid)
        x, y, name_en = place_of(name, lat, lon)
        spot = str(r.get("stlckDtlPstnNm") or "")
        open_, close = hhmm(r.get("wkdyOperBgngTm")), hhmm(r.get("wkdyOperEndTm"))
        lockers.append({
            "id": sid, "x": x, "y": y, "lat": lat, "lon": lon, "dist_m": d,
            "near": [v for v, (vl, vo) in VENUES.items() if dist_m(lat, lon, vl, vo) <= NEAR_M],
            "op": True,
            "hours": f"{open_}~{close}" if open_ else "",
            "name": {"ko": name, "en": name_en},
            "spot": {"ko": spot, "en": spot},
            "fee": str(dt_by_id.get(sid, {}).get("utztnCrgExpln") or ""),
            "sizes": sizes,
        })

    seen = {}
    for k in lockers:  # 같은 역 보관함은 지도에서 겹치지 않게 옆으로
        n = seen.get((k["x"], k["y"]), 0)
        seen[(k["x"], k["y"])] = n + 1
        if n:
            k["x"] = max(14, k["x"] - 22 * n)

    if len(latest) >= 12:
        stamp = datetime.strptime(latest[:12], "%Y%m%d%H%M")
    else:
        stamp = datetime.now(KST).replace(tzinfo=None)
    return {
        "_설명": "scripts/update_lockers.py 가 공영 물품보관함 실시간 API 를 받아 자동 생성 (GitHub Actions 15분마다). total 은 API 에 없어 비움.",
        "sample": False,
        "source": "행정안전부 한국지역정보개발원_(전국 통합데이터) 공영 물품보관함 현황 실시간 정보 (공공데이터포털)",
        "fetched_at": stamp.strftime("%Y-%m-%d %H:%M"),
        "updated": stamp.strftime("%H:%M"),
        "lockers": lockers,
    }


def main():
    key = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", "").strip())
    if not key:
        sys.exit("DATA_GO_KR_KEY 가 없습니다. 저장소 Settings > Secrets and variables > Actions 에 등록하세요.")
    info = call(key, "locker_info_v2")
    detail = call(key, "locker_detail_info_v2")
    realtime = call(key, "locker_realtime_use_v2")
    if not info or not realtime:
        sys.exit("위치 또는 실시간 데이터가 비어 있어 기존 파일을 그대로 둡니다.")
    out = build(info, detail, realtime)
    if not out["lockers"]:
        sys.exit("올림픽공원 주변 보관함이 0곳이라 기존 파일을 그대로 둡니다.")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"보관함 {len(out['lockers'])}곳 저장, 기준 시각 {out['fetched_at']}")


if __name__ == "__main__":
    main()
