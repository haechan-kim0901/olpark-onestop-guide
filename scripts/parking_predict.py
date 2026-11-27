# -*- coding: utf-8 -*-
"""
올림픽공원 주차 '단기 예측' (현재 라이브 값 + 2025년 이용 패턴)  — v3

원리
  예측(t) = 기준표(t) + 오프셋 + β(h)·(현재잔차 − 오프셋) + 공연 보정(h) + 절편(h)        [predict_params.json 있을 때]
  예측(t) = 기준표(t) + 오프셋 + 현재잔차 × exp(-경과시간 / TAU_H)                       [predict_params.json 없을 때(구버전)]
    · 기준표   : (날짜유형 × 시각)별 중앙값/p10/p90 — 새 표는 입출차 이력 전량을 재구성한 3문권역(남2+동2+북2) 시간별 값(2025)으로 만들었고,
                 시 라벨 값은 그 시 '끝 무렵'(h:00+50분)에 두고 선형보간한다 (baseline_table.csv의 anchor_min 열로 표시, 없으면 구버전 30분)
    · 현재잔차 : (지금 라이브 값) − (지금 기준표 값)
    · β(h)    : 평소와의 차이가 h시간 뒤에도 남는 비율. 연계 데이터 검증값 1h 0.96 · 3h 0.84 · 6h 0.66
                (구버전 τ=2.5h 가정은 67% · 30% · 9%라 너무 빨리 사라져, 단순히 차이를 유지하는 것보다도 나빴음)
    · 오프셋   : 야간(0~5시) 잔차의 중앙값(라이브 로그 필요). 낮 동안에도 사라지지 않는 '상시 차이'로 가정
    · 공연 보정: 공연 시작 3시간 전 ~ 5시간 후 구간에, (관람객수/12000, 모르면 1.0)에 비례해 더함
  3문 구역별 값은 share_table_3gates.csv의 (요일, 시각) 비율로 나눈 '추정값'

한계 (중요)
  · 유지율·공연 계수는 2025년 3문권역 시간별 값(1~7월 + 10·11월 일부, 8·9월 제외)으로 학습·검증한 값입니다.
    2026년 실시간 값은 수준이 다를 수 있습니다(2025년 같은 조건보다 새벽 값이 약 600대 높게 관측됨: 장기 주차 누적 가능성).
    run_logger()/log_live()로 실시간 값을 쌓은 뒤 diagnose_offset()·backtest()로 확인하세요.
  · 공연 보정은 작습니다(공연 시간대 오차 약 3~5% 개선). 관람객 수는 2025년 일부 공연만 알고, 모르면 평균 규모로 가정합니다.
  · 혼잡/만차 기준(1300/1900대)은 근거를 새로 만들지 못해 그대로입니다. 새 기준표(평일 낮 2000대 이상)에서는 과거 패턴만으로도 낮 시간이 '만차'로 나올 수 있습니다.
  · 기준표 척도 = 실시간 입력(GATE3_ALL, 3문권역 합계)·혼잡 기준(1300/1900)과 같은 3문권역입니다. (연계 데이터 API_CPM_009는 7개 문 합계라 이보다 큽니다.)

필요 파일 (data/05_주차장/processed/, 이름은 '번호_데이터명_날짜', 같은 이름이면 가장 최근 날짜를 씀)
  05_주차장예측설정_날짜.json, 05_주차장기준표_날짜.csv, 05_주차장공연일정_날짜.csv, 05_주차장문별비중_날짜.csv
선택 파일: 05_주차장예측계수_날짜.json(학습된 유지율·공연 계수), 공연일정의 audience 열(관람객 수)
실시간 기록: data/05_주차장/raw/parking_live_log.csv (자동 생성, 저장소에는 올라가지 않음)
폴더 지정: 환경변수 PARKING_DATA_DIR (기본은 이 파일이 scripts/ 에 있을 때 저장소의 data/05_주차장/processed/)
끄는 법: 환경변수 PARKING_LEARNED=0 (구버전 지수 감쇠), PARKING_SHOW_EFFECT=0 (옛 공연 곡선 파일 사용 안 함)
사용
  (입력 없이) 이 셀만 실행하면 과거 패턴만으로 예측이 바로 출력됩니다.
  res = get_service_output(get_status); show_service_output(res)   # 실시간 값까지 쓸 때(기존 서비스 출력 + 예측)
  res = predict_from_live(get_status())      # 예측표만
  res = predict(1026)                        # 3문권역 합계 사용 대수만 알 때
  print_prediction(res)
  run_logger(get_status, minutes=120)        # 실시간 값을 10분마다 live_log.csv에 쌓기
"""
import os
import sys
import glob
import json
import math
import subprocess
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

try:
    import holidays
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "holidays"])
    import holidays

# ───────────────────── 1. 설정 ─────────────────────
HORIZON_H = 6          # 앞으로 몇 시간까지 예측할지
STEP_MIN = 10          # 예측 간격(분)
TAU_H = 2.5            # 일시적 잔차가 줄어드는 시간 규모(시간) = 2시간 30분 (학습 계수가 없을 때만 사용)
NIGHT_HOURS = range(0, 6)   # 오프셋 추정에 쓰는 야간 시각
OFFSET_DAYS = 7        # 오프셋 추정에 쓰는 최근 일수
OFFSET_MIN_N = 6       # 오프셋 추정에 필요한 최소 야간 기록 수
BEFORE_H, AFTER_H, DEFAULT_LEN_H = 2, 1.5, 2.5   # 공연 시간 창(시작 전/종료 후/종료시간 없을 때 길이)

KST = ZoneInfo("Asia/Seoul")
FMT = "%Y-%m-%d %H:%M:%S"

# ───────────────────── 2. 데이터 파일 읽기 ─────────────────────
# 저장소 규칙(data/README.md)대로 파일 이름이 '번호_데이터명_날짜.확장자' 입니다. 날짜가 달라져도 같은 데이터명이면
# 가장 최근 날짜 파일을 자동으로 씁니다. 파일은 data/05_주차장/processed/ 에 있습니다.
_FILES = {                      # 데이터명(파일 이름 앞부분) : 확장자
    "config":   ("05_주차장예측설정", "json"),
    "baseline": ("05_주차장기준표", "csv"),
    "shows":    ("05_주차장공연일정", "csv"),
    "share":    ("05_주차장문별비중", "csv"),
    "params":   ("05_주차장예측계수", "json"),
}


def _repo_dirs():
    """데이터 파일이 있을 만한 폴더 후보 (앞에 있을수록 우선)."""
    rel = os.path.join("data", "05_주차장", "processed")
    out = []
    if os.environ.get("PARKING_DATA_DIR"):
        out.append(os.environ["PARKING_DATA_DIR"])
    try:                                                   # 이 파일이 scripts/ 안에 있으면 저장소 루트를 찾는다
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out.append(os.path.join(root, rel))
    except NameError:                                      # 노트북 셀에서 실행하면 __file__ 이 없음
        pass
    cwd = os.getcwd()
    out += [os.path.join(cwd, rel), os.path.join(os.path.dirname(cwd), rel), cwd,
            os.path.join("/content", "olpark-onestop-guide", rel)]
    return out


def _find(key, dirs):
    """key 에 해당하는 가장 최근 날짜 파일의 경로. 없으면 None."""
    name, ext = _FILES[key]
    for d in dirs:
        hits = sorted(glob.glob(os.path.join(d, f"{name}_*.{ext}")))
        if hits:
            return hits[-1]
    return None


def _locate():
    dirs = _repo_dirs()
    paths = {k: _find(k, dirs) for k in _FILES}
    if not all(paths[k] for k in ("config", "baseline", "shows", "share")):
        try:                                               # Colab 이면 드라이브를 연결해 한 번 더 찾는다
            from google.colab import drive
            drive.mount("/content/drive")
            dirs = dirs + ["/content/drive/MyDrive"]
            paths = {k: _find(k, dirs) for k in _FILES}
        except ImportError:
            pass
    missing = [_FILES[k][0] + "_날짜." + _FILES[k][1] for k in ("config", "baseline", "shows", "share") if not paths[k]]
    if missing:
        raise FileNotFoundError(
            f"데이터 파일을 찾지 못했습니다: {missing}. data/05_주차장/processed/ 에 두거나 "
            f"환경변수 PARKING_DATA_DIR 에 폴더 경로를 지정하세요. (찾아 본 폴더: {dirs})")
    return paths


PATHS = _locate()
DATA_DIR = os.path.dirname(PATHS["config"])
# 실시간 기록(live_log)은 '받은 그대로의 값'이라 raw/ 에 쌓는다 (.gitignore 가 raw/*.csv 를 막아 저장소에는 올라가지 않음)
LOG_PATH = os.environ.get("PARKING_LIVE_LOG", os.path.join(os.path.dirname(DATA_DIR), "raw", "parking_live_log.csv"))

cfg = json.load(open(PATHS["config"], encoding="utf-8"))
THR = (cfg["thresholds"]["혼잡_시작"], cfg["thresholds"]["만차_시작"])      # 3문권역 합계 기준
CAP = cfg["ref_max_observed"]["3문권역"]                                  # 관측 최대(예측 상한)
OFFICIAL_CAP = 2200    # 공식 안내 용량: 3개 문 권역 '합계'로만 공개 (문별 공식 용량은 없음 → 문별 값은 점유율을 계산하지 않는다)
GATES = ["동2문", "남2문", "북2문"]
GATE_SHARE = cfg.get("gate_mean_share", {"동2문": 1 / 3, "남2문": 1 / 3, "북2문": 1 / 3})
NOTICE = cfg["notice"]
# 2025-11은 2~6일 5일치뿐이라 설정 파일 값에 11월을 더해 '신뢰도 낮음'으로 취급
LOW_CONF_MONTHS = {int(m) for m in cfg["low_confidence_months"]} | {11}

tbl = pd.read_csv(PATHS["baseline"], encoding="utf-8-sig").set_index(["cat", "hour"]).sort_index()   # med, p10, p90, n
ev = pd.read_csv(PATHS["shows"], encoding="utf-8-sig", parse_dates=["date"])
_sh = pd.read_csv(PATHS["share"], encoding="utf-8-sig")
_sh = _sh.rename(columns={_sh.columns[0]: "dow", _sh.columns[1]: "hour"}).set_index(["dow", "hour"])
SHARE = _sh[GATES]
# 기준표 값이 놓이는 시각: 'anchor_min' 열(분, 시 라벨 기준)이 있으면 그것, 없으면 30(= 그 시의 평균, 구버전 표)
ANCHOR_MIN = int(tbl["anchor_min"].iloc[0]) if "anchor_min" in tbl.columns else 30

# 학습된 유지율·공연 계수 (없거나 PARKING_LEARNED=0 이면 구버전 지수 감쇠)
PARAMS = None
if os.environ.get("PARKING_LEARNED", "1") != "0" and PATHS["params"]:
    try:
        PARAMS = json.load(open(PATHS["params"], encoding="utf-8"))
        for _k in ("horizon_h", "beta", "gamma_pre", "gamma_post", "intercept", "flag", "aud_unit",
                   "show_pre_h", "show_post_h"):
            assert _k in PARAMS, _k
    except Exception as _err:
        print("예측 계수 파일을 읽지 못해 지수 감쇠를 씁니다:", _err)
        PARAMS = None
LEARNED_ON = PARAMS is not None

# 공연 효과(선택): show_effect.py가 만든 show_effect.csv + baseline_noshow_table.csv가 있으면 자동으로 사용
tbl_ns, EFFECT = None, {}
# 끄려면 환경변수 PARKING_SHOW_EFFECT=0 (또는 코드 위에서 os.environ["PARKING_SHOW_EFFECT"]="0")
for _d in (DATA_DIR, os.getcwd(), "/content") if os.environ.get("PARKING_SHOW_EFFECT", "1") != "0" else ():
    _fe, _fb = os.path.join(_d, "show_effect.csv"), os.path.join(_d, "baseline_noshow_table.csv")
    if os.path.exists(_fe) and os.path.exists(_fb):
        try:
            _e = pd.read_csv(_fe)
            tbl_ns = pd.read_csv(_fb).set_index(["cat", "hour"]).sort_index()
            for _g, _x in _e.groupby("group"):
                _x = _x.sort_values("rel_min")
                EFFECT[_g] = (_x["rel_min"].to_numpy(float), _x["effect"].to_numpy(float))
        except Exception as _err:                       # 파일이 깨졌으면 효과 없이 계속
            print("공연 효과 파일을 읽지 못해 사용하지 않습니다:", _err)
            tbl_ns, EFFECT = None, {}
        break
SHOW_EFFECT_ON = bool(EFFECT) and tbl_ns is not None

kr = holidays.KR(years=range(2025, 2028))
MYEONGJEOL = {pd.Timestamp(x) for x in [          # 설·추석 연휴 (대체공휴일 제외)
    "2025-01-27", "2025-01-28", "2025-01-29", "2025-01-30",
    "2025-10-05", "2025-10-06", "2025-10-07",
    "2026-02-16", "2026-02-17", "2026-02-18",
    "2026-09-24", "2026-09-25", "2026-09-26",
    "2027-02-06", "2027-02-07", "2027-02-08",
    "2027-09-14", "2027-09-15", "2027-09-16",
]}


# ───────────────────── 3. 기준표 조회 ─────────────────────
def _naive(ts):
    """어떤 시각이든 'KST 현지 시각, tz 없음' Timestamp로 통일 (tz 혼용 오류 방지)."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(KST).tz_localize(None)
    return ts


def day_cat(d):
    """날짜 유형: 평일 / 휴일(주말·공휴일) / 명절"""
    d = pd.Timestamp(d).normalize()
    if d in MYEONGJEOL:
        return "명절"
    if d.weekday() >= 5 or d.date() in kr:
        return "휴일"
    return "평일"


def lv(v):
    return "원활" if v < THR[0] else ("혼잡" if v < THR[1] else "만차")


@lru_cache(maxsize=None)
def _vals(cat, hr, ns=False):
    """(med, p10, p90). 없으면 명절→휴일, 그래도 없으면 같은 유형의 가까운 시각. ns=True면 '공연 없는 날' 기준표."""
    tbl_ = tbl_ns if ns else tbl
    chain = [cat] + (["휴일"] if cat == "명절" else [])
    for c in chain:
        if (c, hr) in tbl_.index:
            r = tbl_.loc[(c, hr)]
            return float(r["med"]), float(r["p10"]), float(r["p90"])
    types = set(tbl_.index.get_level_values(0))
    for c in chain:
        if c in types:
            sub = tbl_.loc[c]
            r = sub.loc[sub.index[abs(sub.index - hr).argmin()]]
            return float(r["med"]), float(r["p10"]), float(r["p90"])
    raise KeyError(f"기준표에 {cat}/{hr}시 및 대체 유형 데이터가 없습니다")


_COL = {"med": 0, "p10": 1, "p90": 2}


def _hour_val(t, col, ns=False):
    return _vals(day_cat(pd.Timestamp(t.date())), t.hour, ns)[_COL[col]]


def base_at(ts, col="med", ns=False):
    """ts 시각의 기준값. 시 라벨 h의 값을 (h:00 + ANCHOR_MIN분)에 두고 선형보간한다.
    (구버전 표: 30분 = 그 시의 평균 / 새 표: 60분 = 연계 데이터의 시 라벨은 그 시 끝 무렵 값)
    자정을 넘으면 라벨이 속한 날의 유형(평일/휴일)의 기준표를 쓴다."""
    ts = _naive(ts)
    a = (ts - pd.Timedelta(minutes=ANCHOR_MIN)).replace(minute=0, second=0, microsecond=0, nanosecond=0)
    b = a + pd.Timedelta(hours=1)
    frac = (ts - (a + pd.Timedelta(minutes=ANCHOR_MIN))) / pd.Timedelta(hours=1)
    va, vb = _hour_val(a, col, ns), _hour_val(b, col, ns)
    return va + (vb - va) * frac


def share_at(ts):
    ts = _naive(ts)
    key = (ts.dayofweek, ts.hour)
    s = SHARE.loc[key] if key in SHARE.index else pd.Series(GATE_SHARE)
    s = s[GATES].astype(float)
    return (s / s.sum()).to_dict()


# ───────────────────── 4. 공연 ─────────────────────
def show_effect_at(ts):
    """ts 시각에 공연들이 더하는 추가 대수(공연 시작 기준 곡선의 합). 효과 파일이 없으면 0."""
    if not SHOW_EFFECT_ON:
        return 0.0
    ts = _naive(ts)
    tot = 0.0
    for d in (ts.normalize(), ts.normalize() - pd.Timedelta(days=1)):     # 어제 밤 공연의 자정 이후 구간 포함
        for s in shows_on(d):
            grp = s.get("grp")
            st = _hm(d, s.get("start"))
            if grp not in EFFECT or st is None:
                continue
            rel_x, eff_y = EFFECT[grp]
            rel = (ts - st) / pd.Timedelta(minutes=1)
            if rel_x[0] <= rel <= rel_x[-1]:
                tot += float(np.interp(rel, rel_x, eff_y))
    return tot


def base_ex(ts, col="med"):
    """공연 효과까지 반영한 기준값. 효과 파일이 없으면 기존 base_at과 같다."""
    if not SHOW_EFFECT_ON:
        return base_at(ts, col)
    try:
        return max(base_at(ts, col, ns=True) + show_effect_at(ts), 0.0)
    except KeyError:
        return base_at(ts, col)



@lru_cache(maxsize=None)
def _shows_on(date_str):
    d = pd.Timestamp(date_str)
    sh = ev[(ev["date"] == d) & ev["grp"].isin(["대형", "중형", "야외"])]
    cols = ["title", "venue", "grp", "start_time"] + (["end_time"] if "end_time" in ev.columns else []) \
        + (["audience"] if "audience" in ev.columns else [])
    out = []
    for r in sh[cols].drop_duplicates().itertuples(index=False):
        item = {"title": r.title, "venue": r.venue, "grp": r.grp,
                "start": "" if pd.isna(r.start_time) else str(r.start_time)}
        if "end_time" in cols and not pd.isna(r.end_time):
            item["end"] = str(r.end_time)
        if "audience" in cols and not pd.isna(r.audience):
            item["aud"] = float(r.audience)
        out.append(item)
    return tuple(tuple(x.items()) for x in out)


def shows_on(date):
    return [dict(x) for x in _shows_on(pd.Timestamp(date).strftime("%Y-%m-%d"))]


def _hm(date, hhmm):
    try:
        h, m = map(int, str(hhmm).split(":")[:2])
        return pd.Timestamp(date.year, date.month, date.day, h, m)
    except (ValueError, TypeError):
        return None


def show_phase_at(s, ts):
    """공연 s 기준 ts의 단계: 'before' / 'during' / 'after' / None(시간 창 밖)"""
    ts = _naive(ts)
    st = _hm(ts, s.get("start"))
    if st is None:
        return None
    en = _hm(ts, s.get("end")) or st + pd.Timedelta(hours=DEFAULT_LEN_H)
    if en <= st:
        en += pd.Timedelta(days=1)
    if ts < st - pd.Timedelta(hours=BEFORE_H) or ts > en + pd.Timedelta(hours=AFTER_H):
        return None
    return "before" if ts < st else ("during" if ts <= en else "after")


_PHASE_MSG = {"before": "공연 시작 전후로 붐빌 수 있습니다",
              "during": "공연이 진행 중입니다",
              "after": "공연 종료 직후 퇴장 차량으로 일시적으로 붐빌 수 있습니다"}


def _coef(key, h, mode="real"):
    """학습 계수를 h시간(0~6, 그 이상은 6시간 값 유지)에서 선형보간. mode: 'real'(관람객 수 아는 경우) / 'flag'(모르는 경우)"""
    src = PARAMS if mode == "real" else PARAMS["flag"]
    xs = PARAMS["horizon_h"]
    return float(np.interp(min(max(h, 0.0), xs[-1]), xs, src[key]))


def show_terms(ts):
    """ts 시각에 영향을 주는 공연의 규모 합 (공연 시작 PRE시간 전~POST시간 후).
    반환: (pre_real, post_real, pre_flag, post_flag, 관람객수를 다 아는지)
      real = 관람객수/aud_unit (모르는 공연은 1.0), flag = 공연마다 1.0"""
    if not LEARNED_ON:
        return 0.0, 0.0, 0.0, 0.0, True
    ts = _naive(ts)
    pre_r = post_r = pre_f = post_f = 0.0
    known = True
    for d in (ts.normalize(), ts.normalize() - pd.Timedelta(days=1)):     # 어제 밤 공연의 자정 이후 구간 포함
        for s_ in shows_on(d):
            st = _hm(d, s_.get("start"))
            if st is None:
                continue
            rel = (ts - st) / pd.Timedelta(hours=1)
            pre = -PARAMS["show_pre_h"] <= rel < 0
            post = 0 <= rel <= PARAMS["show_post_h"]
            if not (pre or post):
                continue
            a = s_.get("aud")
            if a is None:
                known = False
                a_r = 1.0
            else:
                a_r = a / PARAMS["aud_unit"]
            if pre:
                pre_r += a_r
                pre_f += 1.0
            else:
                post_r += a_r
                post_f += 1.0
    return pre_r, post_r, pre_f, post_f, known


def show_flags(ts):
    ts = _naive(ts)
    out = []
    for s in shows_on(ts.normalize()):
        p = show_phase_at(s, ts)
        if p:
            out.append({"title": s["title"], "phase": p})
    return out


# ───────────────────── 5. 라이브 로그 · 오프셋 ─────────────────────
def log_live(used, now=None, path=None):
    """라이브 3문권역 합계를 CSV에 한 줄 추가 (실시간 API를 부를 때마다 호출 권장, 10분 간격이면 이상적)."""
    path = path or LOG_PATH
    now = _naive(now if now is not None else datetime.now(KST))
    row = pd.DataFrame({"ts": [now.strftime(FMT)], "used": [int(used)]})
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        row.to_csv(path, mode="a", header=not os.path.exists(path), index=False)
    except OSError as e:                       # 드라이브 쓰기 실패 등: 예측은 계속
        print("라이브 로그 기록 실패:", e)


def run_logger(get_status_fn, minutes=60, interval_min=10, path=None):
    """Colab 등에서 실시간 값을 interval_min분마다 minutes분 동안 live_log.csv에 쌓는다 (셀을 계속 실행해 두어야 함).
    get_status_fn(): 기존 get_status와 같은 형식(dict, zones에 GATE3_ALL)을 돌려주는 함수. 실패하면 그 회차는 건너뜀."""
    import time as _t
    end = datetime.now(KST).timestamp() + minutes * 60
    n = 0
    while datetime.now(KST).timestamp() < end:
        try:
            live = get_status_fn()
            zones = live.get("zones") if isinstance(live, dict) else None
            tot = next((z for z in (zones or []) if z.get("zone_id") == "GATE3_ALL"), None)
            if live.get("status") == "정상" and tot is not None and _num(tot.get("used")) is not None:
                log_live(tot["used"], path=path)
                n += 1
        except Exception as err:
            print("로그 회차 실패:", err)
        _t.sleep(interval_min * 60)
    print(f"기록 {n}건 → {path or LOG_PATH}")


def _read_log(path=None):
    path = path or LOG_PATH
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    df = df.dropna(subset=["ts", "used"]).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    return df if len(df) else None


def _with_resid(df):
    df = df.copy()
    df["base"] = df["ts"].map(base_ex)
    df["resid"] = df["used"] - df["base"]
    return df


def estimate_offset(now, path=None):
    """최근 OFFSET_DAYS일 야간(NIGHT_HOURS) 잔차의 중앙값. 기록이 부족하면 (0.0, 'none')."""
    df = _read_log(path)
    if df is None:
        return 0.0, "none"
    now = _naive(now)
    df = df[(df["ts"] > now - pd.Timedelta(days=OFFSET_DAYS)) & (df["ts"] <= now)]
    df = df[df["ts"].dt.hour.isin(list(NIGHT_HOURS))]
    if len(df) < OFFSET_MIN_N:
        return 0.0, "none"
    return float(_with_resid(df)["resid"].median()), "log"


def diagnose_offset(path=None):
    """라이브 로그의 시각별 잔차(라이브 − 기준표). 새벽 시간대 잔차가 크고 일정하면 '상시 오프셋'이 있다는 뜻."""
    df = _read_log(path)
    if df is None:
        raise ValueError("라이브 로그가 없습니다. log_live()로 먼저 기록을 쌓으세요.")
    df = _with_resid(df)
    g = df.groupby(df["ts"].dt.hour)["resid"].agg(n="size", mean="mean", median="median").round(0)
    print(g.to_string())
    return g


# ───────────────────── 6. 예측 ─────────────────────
def _num(x):
    """숫자로 바꿀 수 없거나 NaN/음수면 None."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v >= 0 else None


def _clip(v):
    return float(min(max(v, 0.0), CAP))


def predict(live_used, now=None, horizon_h=HORIZON_H, step_min=STEP_MIN, tau_h=TAU_H, log_path=None):
    """현재 3문권역 합계 사용 대수(live_used)로 앞으로 horizon_h시간을 예측한다.
    live_used=None이면 과거 패턴만 쓴다(mode='baseline_only')."""
    now = _naive(now if now is not None else datetime.now(KST))
    live_used = _num(live_used)
    base_now, p10_now, p90_now = base_ex(now), base_ex(now, "p10"), base_ex(now, "p90")

    if live_used is None:
        mode, resid, offset, src = "baseline_only", 0.0, 0.0, "none"
    else:
        mode = "anchored"
        resid = float(live_used) - base_now
        offset, src = estimate_offset(now, log_path)
    transient = resid - offset

    points = []
    for k in range(int(round(horizon_h * 60 / step_min)) + 1):
        t = now + pd.Timedelta(minutes=k * step_min)
        h = k * step_min / 60
        show_adj = 0.0
        if LEARNED_ON:
            pre_r, post_r, pre_f, post_f, known = show_terms(t)
            cmode = "real" if known else "flag"
            sp, so = (pre_r, post_r) if known else (pre_f, post_f)
            if live_used is None:      # 현재 값이 없으면 공연 정보를 대신 알려 주는 항이 없으므로 긴 시간대(6h) 계수를 쓴다
                show_adj = _coef("gamma_pre", 99, cmode) * sp + _coef("gamma_post", 99, cmode) * so
                adj = show_adj
            else:
                show_adj = _coef("gamma_pre", h, cmode) * sp + _coef("gamma_post", h, cmode) * so
                adj = (offset + transient * _coef("beta", h, cmode) + show_adj + _coef("intercept", h, cmode))
        else:
            adj = offset + transient * math.exp(-h / tau_h)
        e, lo, hi = (_clip(base_ex(t, c) + adj) for c in ("med", "p10", "p90"))
        sh = share_at(t)
        points.append({
            "time": t.strftime(FMT), "hours_ahead": round(h, 2),
            "expected": int(round(e)), "low": int(round(lo)), "high": int(round(hi)),
            "level": lv(e), "level_if_busy": lv(hi),
            "pct_of_official_cap": round(100 * e / OFFICIAL_CAP),
            "pct_range": [round(100 * lo / OFFICIAL_CAP), round(100 * hi / OFFICIAL_CAP)],
            "gates_estimate": {g: int(round(e * sh[g])) for g in GATES},
            "show_effect": int(round(show_adj if LEARNED_ON else show_effect_at(t))),
            "shows": show_flags(t),
        })

    cur_level = lv(live_used) if live_used is not None else lv(base_now)
    peak = max(points, key=lambda p: p["expected"])
    change = next((p for p in points if p["level"] != cur_level), None)

    caution = []
    if mode != "baseline_only" and not (p10_now <= live_used <= p90_now):
        caution.append(f"현재 값이 평소 범위({int(p10_now)}~{int(p90_now)}대)를 벗어나 있어 예측 불확실성이 큽니다"
                       + ("" if src == "log" else " (야간 기록이 쌓이면 상시 차이를 보정합니다)."))
    if live_used is not None and live_used > OFFICIAL_CAP:
        caution.append(f"현재 값이 공식 안내 용량({OFFICIAL_CAP:,}대)을 넘습니다. 입출차 집계 오차(출차 미기록 등)일 수 있어 해석에 주의하세요.")
    for s in shows_on(now.normalize()):
        p = show_phase_at(s, now)
        if p:
            caution.append(f"{_PHASE_MSG[p]}: {s['title']}({s['start']})")

    span_dates = sorted({pd.Timestamp(p_["time"]).normalize() for p_ in points})
    shows_list = [dict(date=d.strftime("%Y-%m-%d"), **x) for d in span_dates for x in shows_on(d)]

    return {
        "as_of": now.strftime(FMT), "mode": mode, "notice": NOTICE, "shows": shows_list,
        "live": None if live_used is None else {
            "used": int(live_used), "level": cur_level,
            "pct_of_official_cap": round(100 * live_used / OFFICIAL_CAP),
            "baseline_now": int(round(base_now)), "residual": int(round(resid)),
            "offset": int(round(offset)), "offset_source": src, "transient": int(round(transient)),
        },
        "params": {"decay": "learned" if LEARNED_ON else f"exp(tau={tau_h}h)", "tau_h": tau_h, "horizon_h": horizon_h,
                   "step_min": step_min, "show_effect": SHOW_EFFECT_ON or LEARNED_ON, "anchor_min": ANCHOR_MIN},
        "summary": {
            "peak": {"time": peak["time"], "expected": peak["expected"], "level": peak["level"]},
            "next_level_change": None if change is None else {
                "time": change["time"], "from": cur_level, "to": change["level"]},
        },
        "points": points, "caution": caution,
    }


def predict_from_live(live, now=None, log=True, **kw):
    """get_status() 결과(dict)로 예측. GATE3_ALL이 없거나 상태가 '정상'이 아니면 과거 패턴만 사용."""
    zones = live.get("zones") if isinstance(live, dict) else None
    total = next((z for z in (zones or []) if z.get("zone_id") == "GATE3_ALL"), None)
    if isinstance(live, dict) and live.get("status") == "정상" and total is not None and _num(total.get("used")) is not None:
        if log:
            log_live(total["used"], now)
        return predict(total["used"], now, **kw)
    res = predict(None, now, **kw)
    res["caution"].insert(0, "실시간 데이터를 받지 못했습니다(갱신 지연).")
    return res


_PH_KO = {"before": "공연 전", "during": "공연 중", "after": "종료 후"}


def _show_line(x):
    t = f"{x['start']}" if x.get("start") else "시간 미정"
    return f"{x['date'][5:]} {t} {x['title']} ({x['venue']})"


def _row_flag(shows):
    def short(t, n=16):
        return t if len(t) <= n else t[:n] + "…"
    return ", ".join(f"{_PH_KO[x['phase']]}:{short(x['title'])}" for x in shows)


def print_prediction(res):
    lv_ = res["live"]
    print(f"\n■ 예측 기준 {res['as_of']} · 모드 {res['mode']}")
    if lv_:
        print(f"  현재 {lv_['used']}대({lv_['level']}, 공식 용량 {OFFICIAL_CAP:,}대의 {lv_['pct_of_official_cap']}%) | 평소 {lv_['baseline_now']} | 잔차 {lv_['residual']:+d} "
              f"(오프셋 {lv_['offset']:+d} [{lv_['offset_source']}], 일시 {lv_['transient']:+d})")
    s = res["summary"]
    print(f"  피크 {s['peak']['time'][11:16]} {s['peak']['expected']}대({s['peak']['level']})", end="")
    c = s["next_level_change"]
    print(f" | 등급 변화 {c['time'][11:16]} {c['from']}→{c['to']}" if c else " | 예측 구간 내 등급 변화 없음")
    if res.get("shows"):
        print("  공연:")
        for x in res["shows"]:
            print("   -", _show_line(x))
    else:
        print("  공연: 해당 시간대 없음")
    for c_ in res["caution"]:
        print("  ※", c_)
    print("  시각          예상(점유율)   등급   동2/남2/북2(추정)  공연")
    for p in res["points"]:
        g = p["gates_estimate"]
        print(f"  {p['time'][5:16]} {p['expected']:>5}대({p['pct_of_official_cap']:>3}%)  {p['level']}"
              f"   {g['동2문']}/{g['남2문']}/{g['북2문']}   {_row_flag(p['shows'])}")


# ───────────────────── 7. 백테스트 (라이브 로그가 쌓인 뒤) ─────────────────────
def backtest(path=None, horizons_h=(1, 2, 3), taus=(1, 2, 3, 6, 12, 1e9), tol_min=10):
    """로그의 각 시점에서 h시간 뒤를 예측해 실제 기록과 비교한다.
    '기준표만', 'tau=…'(잔차만 감쇠), '오프셋+tau=…'(야간 상시 오프셋 보정 + 나머지 감쇠)의 MAE를 비교한다.
    taus의 1e9는 '잔차가 영구 지속'. predict()와 같은 방식은 '오프셋+tau=…'이다."""
    df = _read_log(path)
    if df is None or len(df) < 20:
        raise ValueError("라이브 로그가 부족합니다(최소 20건, 10분 간격이면 며칠치 권장).")
    df = _with_resid(df)
    rows = []
    for h in horizons_h:
        target = df[["ts", "used"]].rename(columns={"ts": "ts_t", "used": "y"}).sort_values("ts_t")
        q = df.assign(ts_t=df["ts"] + pd.Timedelta(hours=h)).sort_values("ts_t")
        m = pd.merge_asof(q, target, on="ts_t", tolerance=pd.Timedelta(minutes=tol_min), direction="nearest")
        m = m.dropna(subset=["y"])
        if m.empty:
            continue
        base_t = m["ts_t"].map(base_at)
        preds = {"기준표만": base_t.clip(0, CAP)}
        night = df[df["ts"].dt.hour.isin(list(NIGHT_HOURS))]
        off_cache = {}
        def _off(ts):                      # 그날 아침 6시 이전에 알 수 있던 오프셋(미래 정보 미사용)
            cut = ts.normalize() + pd.Timedelta(hours=6) if ts.hour >= 6 else ts.normalize()
            if cut not in off_cache:
                w = night[(night["ts"] > cut - pd.Timedelta(days=OFFSET_DAYS)) & (night["ts"] <= cut)]
                off_cache[cut] = float(w["resid"].median()) if len(w) >= OFFSET_MIN_N else 0.0
            return off_cache[cut]
        off_q = m["ts"].map(_off)
        if LEARNED_ON:
            b_ = _coef("beta", h, "flag")
            preds["학습 유지율"] = (base_t + m["resid"] * b_).clip(0, CAP)
            preds["오프셋+학습 유지율"] = (base_t + off_q + (m["resid"] - off_q) * b_).clip(0, CAP)
        for tau in taus:
            preds[f"tau={tau:g}h"] = (base_t + m["resid"] * math.exp(-h / tau)).clip(0, CAP)
            preds[f"오프셋+tau={tau:g}h"] = (base_t + off_q + (m["resid"] - off_q) * math.exp(-h / tau)).clip(0, CAP)
        for name, p in preds.items():
            err = p - m["y"]
            rows.append({"horizon_h": h, "method": name, "n": len(m),
                         "MAE": round(float(err.abs().mean()), 1), "bias": round(float(err.mean()), 1)})
    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("비교할 수 있는 시점 쌍이 없습니다(로그 간격이 너무 성기거나 짧습니다).")
    print(out.pivot(index="method", columns="horizon_h", values="MAE").to_string())
    best = out.loc[out.groupby("horizon_h")["MAE"].idxmin()][["horizon_h", "method", "MAE"]]
    print("\n시간대별 최적 방법:\n" + best.to_string(index=False))
    return out


# ───────────────────── 7-2. 서비스 출력 (기존 형식 + 예측) ─────────────────────
def compare_now(used, now=None):
    """현재 값을 같은 날짜 유형·같은 시(時)의 평소 범위(p10~p90)와 비교 (기존 서비스 출력과 같은 형식)."""
    now = _naive(now if now is not None else datetime.now(KST))
    med, p10, p90 = (int(round(x)) for x in _vals(day_cat(pd.Timestamp(now.date())), now.hour))
    used = int(round(float(used)))
    level = lv(used)
    if used > p90:
        label = "평소 범위보다 많음" + ("(아직 원활 수준)" if level == "원활" else "")
    elif used < p10:
        label = "평소 범위보다 적음"
    else:
        label = "평소 수준"
    return {"now": used, "pct": round(100 * used / OFFICIAL_CAP), "usual": med, "usual_pct": round(100 * med / OFFICIAL_CAP),
            "diff": used - med,
            "ratio": round(used / med, 1) if med else None,
            "range": [p10, p90], "level": level, "label": label}


def get_service_output(get_status_fn=None, now=None, total_zone_id="GATE3_ALL", out_path=None, horizon_h=HORIZON_H):
    """기존 서비스 출력(updated_at, day_type, compare, caution, realtime) + 'forecast'(단기 예측).
    get_status_fn: 노트북의 get_status 함수. None이면 전역의 get_status를 찾는다."""
    now = _naive(now if now is not None else datetime.now(KST))
    fn = get_status_fn or globals().get("get_status")
    live = None
    if callable(fn):
        try:
            live = fn()
        except Exception as e:                                   # API 일시 실패 대비
            print("get_status 실패:", e)
    if not isinstance(live, dict):
        live = {"status": "갱신 지연", "updated_at": now.strftime(FMT), "notice": NOTICE, "zones": []}
    zones = live.get("zones") or []
    for z in zones:
        if "total" in z:
            z["ref_max"] = z.pop("total")

    cat = day_cat(pd.Timestamp(now.date()))
    out = {"updated_at": now.strftime(FMT), "data_updated_at": live.get("updated_at"),
           "notice": NOTICE, "day_type": cat, "realtime": live,
           "compare": None, "caution": [], "forecast": None}

    total = next((z for z in zones if z.get("zone_id") == total_zone_id), None)
    ok = live.get("status") == "정상" and total is not None and _num(total.get("used")) is not None
    if ok:
        out["compare"] = compare_now(total["used"], now)
    pred = predict(total["used"] if ok else None, now, horizon_h=horizon_h)
    if ok:
        log_live(total["used"], now)
    out["forecast"] = {k: pred[k] for k in ("mode", "live", "params", "summary", "shows", "points")}

    if cat == "평일" and 8 <= now.hour <= 18:
        out["caution"].append("평일 낮 수치에는 상시 이용 차량이 포함될 수 있어 방문객 체감 혼잡보다 높게 나올 수 있습니다.")
    out["caution"].extend(pred["caution"])
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    return out


def show_service_output(res):
    """기존 노트북과 같은 모양으로 출력 + 예측 요약."""
    print(json.dumps({k: res[k] for k in ("updated_at", "data_updated_at", "day_type", "compare", "caution")},
                     ensure_ascii=False, indent=2))
    print(res["realtime"].get("status"),
          [(z.get("zone_id"), z.get("used"), z.get("level", "-")) for z in res["realtime"].get("zones", [])])
    fc = res["forecast"]
    print("\n[예측]", "실시간 기준" if fc["mode"] == "anchored" else "과거 패턴만")
    pk, ch = fc["summary"]["peak"], fc["summary"]["next_level_change"]
    print(f"  피크 {pk['time'][11:16]} {pk['expected']}대({pk['level']})",
          f"| 등급 변화 {ch['time'][11:16]} {ch['from']}→{ch['to']}" if ch else "| 등급 변화 없음")
    cmp_ = res.get("compare")
    if cmp_:
        print(f"  현재 {cmp_['now']}대 = 공식 용량({OFFICIAL_CAP:,}대)의 {cmp_['pct']}% | 평소 {cmp_['usual']}대({cmp_['usual_pct']}%)")
    if fc.get("shows"):
        print("  공연:")
        for x in fc["shows"]:
            print("   -", _show_line(x))
    else:
        print("  공연: 해당 시간대 없음")
    print("  (10분 간격 전체는 res['forecast']['points'] 참고, 아래는 30분 간격 요약)")
    step = max(1, 30 // fc["params"]["step_min"])
    for p in fc["points"][::step]:
        print(f"  {p['time'][11:16]}  예상 {p['expected']:>5}대 ({p['pct_of_official_cap']}%)  {p['level']}  {_row_flag(p['shows'])}")


# ───────────────────── 8. 실행 ─────────────────────
# 노트북에서 이 셀을 실행하면(get_status가 이미 정의돼 있을 때) 바로 결과를 출력한다.
# 다른 파일에서 import 했을 때는 아무것도 실행하지 않는다.
def run_notebook(get_status_fn=None, out_path=None):
    res = get_service_output(get_status_fn, out_path=out_path)
    show_service_output(res)
    return res


if __name__ == "__main__":
    used = os.environ.get("PARKING_LIVE_USED")
    if used:
        print_prediction(predict(float(used)))
    elif callable(globals().get("get_status")):
        res = run_notebook(globals()["get_status"])
    else:
        # 입력이 전혀 없어도 동작: 과거 패턴(기준표)만으로 지금부터 6시간을 예측한다.
        print("※ get_status가 없어 실시간 값 없이 '과거 패턴'만으로 예측합니다.")
        print("  실시간 값까지 쓰려면 get_status 셀을 실행한 뒤 run_notebook(get_status) 를 호출하세요.")
        res = predict(None)
        print_prediction(res)
