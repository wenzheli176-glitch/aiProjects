#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM 用量汇总与初筛日志。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intel.db import (
    aggregate_llm_usage,
    get_connection,
    insert_llm_usage_log,
    list_analysis_logs,
    reset_db_connection,
)
from intel.time_util import now_iso


def test_llm_usage_aggregate():
    reset_db_connection()
    conn = get_connection()
    cols = {r[1] for r in conn.execute('PRAGMA table_info(llm_usage_logs)').fetchall()}
    assert cols, 'llm_usage_logs table missing'

    task_id = conn.execute('SELECT id FROM monitor_tasks ORDER BY id LIMIT 1').fetchone()
    task_id = task_id['id'] if task_id else None
    ts = now_iso()

    insert_llm_usage_log({
        'task_id': task_id,
        'phase': 'list_triage',
        'batch_index': 1,
        'item_count': 5,
        'status': 'ok',
        'model': 'test-model',
        'prompt_tokens': 100,
        'completion_tokens': 20,
        'total_tokens': 120,
        'created_at': ts,
    })
    insert_llm_usage_log({
        'task_id': task_id,
        'phase': 'analysis',
        'job_id': 1,
        'batch_index': 1,
        'item_count': 3,
        'status': 'ok',
        'model': 'test-model',
        'prompt_tokens': 200,
        'completion_tokens': 50,
        'total_tokens': 250,
        'created_at': ts,
    })

    usage = aggregate_llm_usage(days=7, task_id=task_id)
    assert usage['period']['total']['total_tokens'] >= 370
    assert usage['period']['by_phase']['list_triage']['total_tokens'] >= 120
    assert usage['period']['by_phase']['analysis']['total_tokens'] >= 250
    assert usage['today']['total_tokens'] >= 370
    assert usage['daily'], 'expected daily rows'
    assert usage['by_task'], 'expected by_task rows'

    logs = list_analysis_logs(task_id=task_id, limit=5)
    assert any(l.get('phase') == 'list_triage' for l in logs)
    print('OK test_llm_usage_aggregate')


if __name__ == '__main__':
    test_llm_usage_aggregate()
    print('All llm usage tests passed.')
