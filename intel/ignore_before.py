# -*- coding: utf-8 -*-
"""任务 ignore_before：列表入库 / 详情勘察 / 分析阶段跳过过旧内容。"""


def should_skip_ignore_before(published_at, ignore_before):
    cutoff = (ignore_before or '').strip()
    if not cutoff:
        return False
    pub = (published_at or '').strip()
    if not pub:
        return False
    pub_day = pub[:10]
    cutoff_day = cutoff[:10]
    if len(pub_day) < 10 or len(cutoff_day) < 10:
        return False
    return pub_day < cutoff_day


def resolve_ignore_before(task=None, business_spec=None):
    bs = dict((task or {}).get('business_spec') or {})
    if business_spec:
        bs.update(business_spec)
    val = (bs.get('ignore_before') or '').strip()
    return val or None


def raw_record_published_at(source, record):
    """从列表/详情 raw dict 解析 YYYY-MM-DD（与入库展示口径一致）。"""
    from intel.db import _raw_published_at

    if not isinstance(record, dict):
        return ''
    return _raw_published_at(source, record) or ''


def filter_raw_records_by_ignore_before(records, source, ignore_before, run_metrics=None):
    """列表爬取入库前过滤。返回 (kept_records, skipped_count)。"""
    if not ignore_before or not records:
        return list(records or []), 0
    kept = []
    skipped = 0
    for rec in records:
        pub = raw_record_published_at(source, rec)
        if should_skip_ignore_before(pub, ignore_before):
            skipped += 1
            if run_metrics:
                run_metrics.record_raw_skipped_ignore_before(1)
            continue
        kept.append(rec)
    return kept, skipped


def raw_insert_log_parts(ins, ignore_before=None):
    """insert_raw_records 结果 → 日志片段。"""
    ins = ins or {}
    parts = []
    skip_n = int(ins.get('skipped_ignore_before') or 0)
    if skip_n and ignore_before:
        parts.append('忽略早于 %s 跳过 %d' % (ignore_before, skip_n))
    if ins.get('inserted'):
        parts.append('新增 %d' % ins['inserted'])
    if ins.get('updated'):
        parts.append('更新 %d' % ins['updated'])
    if ins.get('unchanged'):
        parts.append('未变 %d' % ins['unchanged'])
    return parts
