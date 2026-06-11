#!/usr/bin/env python3
"""Automated checks for console-ux-overhaul §7."""
import json
import urllib.request

BASE = "http://127.0.0.1:5000"


def get_json(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def main():
    checks = []
    params = "relevance_min=medium&partner_id=4"
    listing = get_json(f"/api/intel/records?{params}&page_size=1")
    export = get_json(f"/api/intel/export?format=json&{params}")
    export_list = export if isinstance(export, list) else export.get("records", [])
    checks.append(
        {
            "id": "7.2 intel export full count",
            "ok": len(export_list) >= listing.get("total", 0),
            "detail": f"list_total={listing.get('total')} export_len={len(export_list)}",
        }
    )

    raw_list = get_json("/api/raw/records?task_id=3&page_size=1")
    raw_export = get_json("/api/raw/export?format=json&task_id=3")
    raw_export_list = raw_export if isinstance(raw_export, list) else raw_export.get("records", [])
    checks.append(
        {
            "id": "7.3 raw export full count",
            "ok": len(raw_export_list) >= raw_list.get("total", 0),
            "detail": f"raw_total={raw_list.get('total')} export_len={len(raw_export_list)}",
        }
    )

    print(json.dumps(checks, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
