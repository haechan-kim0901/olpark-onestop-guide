"""CSV, 원본 JSON 저장 도우미 (update_lockers.py, update_weather.py 가 같이 씀).

- CSV 는 UTF-8 BOM(utf-8-sig) 으로 저장해서 엑셀에서 더블클릭해도 한글이 안 깨집니다.
- 원본 JSON 에는 API 가 돌려준 item 목록과 요청 조건만 담고, 인증키(serviceKey)는 절대 넣지 않습니다.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def write_csv(path, rows, columns=None):
    """rows(딕셔너리 목록)를 CSV 로 저장. columns 가 없으면 처음 나온 순서대로 모든 열을 씀."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is None:
        columns = []
        for r in rows:
            for k in r:
                if k not in columns:
                    columns.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in columns})
    return path


def write_raw_json(path, api, params, items, fetched_at):
    """API 원본(item 목록)을 JSON 으로 저장. params 에서 serviceKey 는 지움."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = {k: v for k, v in (params or {}).items() if k.lower() != "servicekey"}
    body = {"api": api, "params": safe, "fetched_at": fetched_at, "count": len(items), "items": items}
    path.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path
