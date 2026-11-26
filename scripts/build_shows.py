"""공연정보 CSV → 웹 데모용 docs/data/shows.json 만들기.

쓰는 법
  python scripts/build_shows.py
  (GitHub 에서 data/01_공연정보/processed/ 에 CSV 를 올리면 Actions 가 자동으로 실행합니다.)

- data/01_공연정보/processed/ 안의 CSV 중 이름순으로 가장 마지막 파일 하나를 읽습니다.
  진짜 파일(_SAMPLE 이 없는 것)이 있으면 그걸 먼저 씁니다.
- 꼭 있어야 하는 열: 공연명, 공연장, 공연일, 시작시각
- 없어도 되는 열: 공연ID, 공연명_영문, 종료시각, 장르, 장르_영문
- 종료시각이 빈 칸이면 그대로 빈 칸으로 둡니다. 웹 화면이 '시작 + 2시간 30분 (예상)' 으로 보여 줍니다.
  도착 권장 시각(시작 3시간 전)도 웹 화면이 계산합니다 (docs/index.html 의 ARRIVE_BEFORE, END_AFTER).
- 공연장은 팀 표준이름(KSPO DOME, 올림픽홀, 핸드볼경기장, 88잔디마당)만 받습니다.
"""
import csv
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "data" / "01_공연정보" / "processed"
OUT = ROOT / "docs" / "data" / "shows.json"

VENUES = {"KSPO DOME": "dome", "올림픽홀": "hall", "핸드볼경기장": "arena", "88잔디마당": "lawn"}
GENRE_EN = {"콘서트": "Concert", "페스티벌": "Festival", "팬미팅": "Fan meeting", "뮤지컬": "Musical",
            "클래식": "Classical", "스포츠": "Sports", "기타": "Other"}


def pick_csv():
    files = sorted(SRC_DIR.glob("*.csv"))
    real = [f for f in files if "_SAMPLE" not in f.name]
    return (real or files or [None])[-1]


def hhmm(v):
    """'18:00', '1800', '18시', '2025-08-09 18:00' → '18:00'. 못 읽으면 빈 문자열."""
    m = re.search(r"(\d{1,2})\s*[:시]?\s*(\d{2})?", str(v or "").split(" ")[-1])
    if not m:
        return ""
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    return f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else ""


def ymd(v):
    """'2025-08-09', '2025.08.09', '20250809', '2025/8/9' → '2025-08-09'."""
    d = re.sub(r"\D", " ", str(v or "")).split()
    if len(d) == 1 and len(d[0]) >= 8:
        d = [d[0][:4], d[0][4:6], d[0][6:8]]
    if len(d) < 3:
        return ""
    return f"{int(d[0]):04d}-{int(d[1]):02d}-{int(d[2]):02d}"


def main():
    src = pick_csv()
    if src is None:
        print("공연정보 CSV 가 없습니다:", SRC_DIR)
        return 1
    shows, skipped = [], []
    with src.open(encoding="utf-8-sig", newline="") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
            venue = VENUES.get(r.get("공연장", ""))
            date, start = ymd(r.get("공연일")), hhmm(r.get("시작시각"))
            if not (r.get("공연명") and venue and date and start):
                skipped.append(f"{i}행 ({r.get('공연명') or '이름 없음'}, 공연장 '{r.get('공연장', '')}')")
                continue
            genre = r.get("장르", "")
            shows.append({
                "id": r.get("공연ID") or f"r{i}",
                "venue": venue,
                "title": {"ko": r["공연명"], "en": r.get("공연명_영문") or r["공연명"]},
                "genre": {"ko": genre, "en": r.get("장르_영문") or GENRE_EN.get(genre, genre)},
                "date": date, "start": start,
                "end": hhmm(r.get("종료시각")),
            })
    shows.sort(key=lambda s: (s["date"], s["start"]))
    now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    body = {"sample": "_SAMPLE" in src.name, "source_file": src.name, "updated": now, "count": len(shows), "shows": shows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{src.name} → {OUT.relative_to(ROOT)} : 공연 {len(shows)}개")
    if skipped:
        print("건너뛴 줄 (공연명, 공연장 표준이름, 공연일, 시작시각을 확인하세요):")
        for s in skipped:
            print("  -", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
