# -*- coding: utf-8 -*-
"""IntelRecord JSON / Excel 导出。"""
import csv
import io
import json
import os
import time

from config import cfg
from intel.db import INTEL_SCHEMA_VERSION, list_intel_records

INTEL_EXPORT_COLUMNS = [
    ('id', 'id'),
    ('task_id', 'task_id'),
    ('partner_id', 'partner_id'),
    ('partner_name', '合作方'),
    ('source', '数据来源'),
    ('url', '链接'),
    ('title', '标题'),
    ('body', '正文'),
    ('published_at', '发布时间'),
    ('captured_at', '采集时间'),
    ('analyzed_at', '生成时间'),
    ('relevance', '相关度'),
    ('sentiment_label', '情感倾向'),
    ('sentiment_score', '情感分数'),
    ('risk_types', '风险类型'),
    ('subject_hits', '命中别名'),
    ('summary', '摘要'),
    ('export_tier', '导出分桶'),
    ('prompt_version', 'prompt版本'),
    ('model', '模型'),
    ('schema_version', 'schema版本'),
]


def _flatten_record(rec):
    out = dict(rec)
    out['risk_types'] = ', '.join(rec.get('risk_types') or [])
    out['subject_hits'] = ', '.join(rec.get('subject_hits') or [])
    return out


def build_intel_export_payload(task_id=None, **filters):
    result = list_intel_records(task_id=task_id, page=1, page_size=100000, **filters)
    return {
        'schema_version': cfg('intel', 'schema_version', default=INTEL_SCHEMA_VERSION),
        'exported_at': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'task_id': task_id,
        'count': len(result['records']),
        'records': result['records'],
    }


def export_intel_json(task_id=None, **filters):
    return build_intel_export_payload(task_id=task_id, **filters)


def export_intel_csv_bytes(task_id=None, **filters):
    payload = build_intel_export_payload(task_id=task_id, **filters)
    buf = io.StringIO()
    writer = csv.writer(buf)
    headers = [label for _, label in INTEL_EXPORT_COLUMNS]
    writer.writerow(headers)
    for rec in payload['records']:
        flat = _flatten_record(rec)
        writer.writerow([flat.get(key, '') for key, _ in INTEL_EXPORT_COLUMNS])
    return buf.getvalue().encode('utf-8-sig')


def export_intel_xlsx_bytes(task_id=None, **filters):
    try:
        from openpyxl import Workbook
    except ImportError:
        return None
    payload = build_intel_export_payload(task_id=task_id, **filters)
    wb = Workbook()
    ws = wb.active
    ws.title = 'intel'
    headers = [label for _, label in INTEL_EXPORT_COLUMNS]
    ws.append(headers)
    for rec in payload['records']:
        flat = _flatten_record(rec)
        ws.append([flat.get(key, '') for key, _ in INTEL_EXPORT_COLUMNS])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def write_export_file(fmt, task_id=None, output_dir=None, **filters):
    output_dir = output_dir or cfg('paths', 'output_dir_resolved') or '.'
    os.makedirs(output_dir, exist_ok=True)
    ts = time.strftime('%Y%m%d_%H%M%S')
    suffix = '_%s' % task_id if task_id else ''
    if fmt == 'json':
        path = os.path.join(output_dir, 'intel_export%s_%s.json' % (suffix, ts))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(export_intel_json(task_id=task_id, **filters), f, ensure_ascii=False, indent=2)
        return path
    if fmt == 'xlsx':
        data = export_intel_xlsx_bytes(task_id=task_id, **filters)
        if data is None:
            path = os.path.join(output_dir, 'intel_export%s_%s.csv' % (suffix, ts))
            with open(path, 'wb') as f:
                f.write(export_intel_csv_bytes(task_id=task_id, **filters))
            return path
        path = os.path.join(output_dir, 'intel_export%s_%s.xlsx' % (suffix, ts))
        with open(path, 'wb') as f:
            f.write(data)
        return path
    path = os.path.join(output_dir, 'intel_export%s_%s.csv' % (suffix, ts))
    with open(path, 'wb') as f:
        f.write(export_intel_csv_bytes(task_id=task_id, **filters))
    return path
