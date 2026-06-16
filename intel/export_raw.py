# -*- coding: utf-8 -*-
"""raw_records JSON / Excel 导出。"""
import csv
import io
import json
import os
import time

from config import cfg
from intel.db import list_raw_records_paged
from intel.time_util import now_iso

RAW_EXPORT_COLUMNS = [
    ('id', 'id'),
    ('task_id', 'task_id'),
    ('partner_id', 'partner_id'),
    ('source', '数据来源'),
    ('keyword', '关键词'),
    ('title_summary', '标题/摘要'),
    ('published_at', '发布时间'),
    ('created_at', '创建时间'),
    ('updated_at', '更新时间'),
    ('dedup_key', 'dedup_key'),
    ('content_hash', 'content_hash'),
    ('analyze_status', '分析状态'),
    ('intel_id', 'intel_id'),
    ('payload', 'payload'),
]


def _flatten_record(rec):
    out = dict(rec)
    payload = rec.get('payload')
    if payload is not None and not isinstance(payload, str):
        out['payload'] = json.dumps(payload, ensure_ascii=False)
    return out


def build_raw_export_payload(**filters):
    result = list_raw_records_paged(page=1, page_size=100000, include_payload=True, **filters)
    return {
        'schema_version': cfg('intel', 'schema_version', default='1.1'),
        'exported_at': now_iso(),
        'count': len(result['records']),
        'records': result['records'],
    }


def export_raw_json(**filters):
    return build_raw_export_payload(**filters)


def export_raw_csv_bytes(**filters):
    payload = build_raw_export_payload(**filters)
    buf = io.StringIO()
    writer = csv.writer(buf)
    headers = [label for _, label in RAW_EXPORT_COLUMNS]
    writer.writerow(headers)
    for rec in payload['records']:
        flat = _flatten_record(rec)
        writer.writerow([flat.get(key, '') for key, _ in RAW_EXPORT_COLUMNS])
    return buf.getvalue().encode('utf-8-sig')


def export_raw_xlsx_bytes(**filters):
    try:
        from openpyxl import Workbook
    except ImportError:
        return None
    payload = build_raw_export_payload(**filters)
    wb = Workbook()
    ws = wb.active
    ws.title = 'raw'
    headers = [label for _, label in RAW_EXPORT_COLUMNS]
    ws.append(headers)
    for rec in payload['records']:
        flat = _flatten_record(rec)
        ws.append([flat.get(key, '') for key, _ in RAW_EXPORT_COLUMNS])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def write_raw_export_file(fmt, output_dir=None, **filters):
    output_dir = output_dir or cfg('paths', 'output_dir_resolved') or '.'
    os.makedirs(output_dir, exist_ok=True)
    ts = time.strftime('%Y%m%d_%H%M%S')
    task_id = filters.get('task_id')
    suffix = '_%s' % task_id if task_id else ''
    if fmt == 'json':
        path = os.path.join(output_dir, 'raw_export%s_%s.json' % (suffix, ts))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(export_raw_json(**filters), f, ensure_ascii=False, indent=2)
        return path
    if fmt == 'xlsx':
        data = export_raw_xlsx_bytes(**filters)
        if data is None:
            path = os.path.join(output_dir, 'raw_export%s_%s.csv' % (suffix, ts))
            with open(path, 'wb') as f:
                f.write(export_raw_csv_bytes(**filters))
            return path
        path = os.path.join(output_dir, 'raw_export%s_%s.xlsx' % (suffix, ts))
        with open(path, 'wb') as f:
            f.write(data)
        return path
    path = os.path.join(output_dir, 'raw_export%s_%s.csv' % (suffix, ts))
    with open(path, 'wb') as f:
        f.write(export_raw_csv_bytes(**filters))
    return path
