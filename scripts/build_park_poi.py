"""park_poi.csv의 지정 행을 지도용 JSON으로 복사한다.

실행: python scripts/build_park_poi.py
CSV와 JSON 모두 원래 14개 컬럼명과 값을 유지한다.
헤더를 1행으로 세어 2~34행 전체와 35행 이후의 지정 시설만 사용한다.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "06_공원볼거리" / "processed" / "park_poi.csv"
OUT = ROOT / "docs" / "data" / "park_poi.json"
COLUMNS = [
    "poi_id", "type", "name_ko", "name_en", "name_zh", "name_ja",
    "lat", "lon", "season", "photo_url", "desc_ko", "desc_en", "desc_zh", "desc_ja",
]
FACILITIES = {"facility_restroom", "facility_vending_machine", "facility_smoking_area"}


def build():
    with SRC.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != COLUMNS:
            raise ValueError("park_poi.csv의 원래 14개 컬럼명과 순서를 확인하세요.")
        rows = list(reader)
    if len(rows) < 33:
        raise ValueError("park_poi.csv에 2~34행이 모두 있어야 합니다.")
    selected = rows[:33] + [row for row in rows[33:] if row["type"] in FACILITIES]
    ids = set()
    for row in selected:
        if set(row) != set(COLUMNS) or any(value is None for value in row.values()):
            raise ValueError("CSV의 행별 컬럼 수를 확인하세요.")
        if not row["poi_id"] or row["poi_id"] in ids:
            raise ValueError("poi_id가 비어 있거나 중복되었습니다.")
        ids.add(row["poi_id"])
        # 빈 좌표는 그대로 보존하며 임의의 위치로 보충하지 않는다.
        if row["lat"] or row["lon"]:
            lat, lon = float(row["lat"]), float(row["lon"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError(f"좌표 범위를 확인하세요: {row['poi_id']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    located = sum(bool(row["lat"] and row["lon"]) for row in selected)
    print(f"park_poi.csv → docs/data/park_poi.json: {len(selected)}건, 좌표 {located}건")


if __name__ == "__main__":
    build()
