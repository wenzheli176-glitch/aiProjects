# -*- coding: utf-8 -*-
"""列表 LLM 初筛。"""
import json
import time

from config import cfg
from intel.analyze import _parse_llm_json, _resolve_api_key, _truncate
from intel.db import update_raw_triage


LIST_TRIAGE_PROMPT = """你是舆情列表初筛助手。对每条列表摘要判断是否与任意合作方相关及是否值得深入勘察。
策略：高召回——存疑标 medium，仅明确无关标 noise。

合作方名单（名称/别名）：{partner_names}

输入 JSON 数组，每项含 id、source、title、body。输出 JSON 数组，每项：
{{"id":<同输入>, "triage_relevance":"high|medium|low|noise", "triage_risk_hint":"none|elevated|severe", "needs_investigation": true/false, "summary":"一句话"}}

needs_investigation 规则：triage_relevance 为 high 或 medium 且 triage_risk_hint 为 elevated 或 severe 时为 true；主体明确无关则为 false。
只输出 JSON 数组。"""


def _list_triage_cfg():
    ac = cfg('analysis') or {}
    lt = ac.get('list_triage') or {}
    return {
        'enabled': bool(lt.get('enabled', True)),
        'model': lt.get('model') or ac.get('model') or 'MiniMax-M3',
        'batch_size': int(lt.get('batch_size') or 20),
        'max_body_chars': int(lt.get('max_body_chars') or 400),
        'threshold': lt.get('investigation_threshold') or {},
    }


def _partner_names(partners):
    names = []
    for p in partners:
        names.append(p.get('name') or '')
        names.extend(p.get('aliases') or [])
    return ', '.join(n for n in names if n)


def _mock_triage_item(item):
    title = (item.get('title') or '') + (item.get('body') or '')
    rel = 'medium' if title.strip() else 'noise'
    return {
        'id': item.get('id'),
        'triage_relevance': rel,
        'triage_risk_hint': 'elevated' if rel == 'medium' else 'none',
        'needs_investigation': rel in ('high', 'medium'),
        'summary': (item.get('title') or '')[:80],
    }


def run_list_triage(task_id, raw_rows, partners, log_fn=None, run_metrics=None):
    lt_cfg = _list_triage_cfg()
    if not lt_cfg['enabled'] or not raw_rows:
        return {'processed': 0, 'stats': {}}

    ac = cfg('analysis') or {}
    api_key = _resolve_api_key(ac)
    batch_size = lt_cfg['batch_size']
    max_body = lt_cfg['max_body_chars']
    stats = {'triage_high': 0, 'triage_medium': 0, 'triage_noise': 0, 'needs_investigation_count': 0}
    processed = 0
    t0 = time.monotonic()

    pending = [r for r in raw_rows if not (r.get('list_triage') or {}).get('triage_relevance')]
    for i in range(0, len(pending), batch_size):
        batch_rows = pending[i:i + batch_size]
        items = []
        for row in batch_rows:
            payload = row.get('payload') or {}
            body = payload.get('content') or payload.get('text') or payload.get('body') or ''
            items.append({
                'id': row['id'],
                'source': row.get('source') or '',
                'title': payload.get('title') or row.get('keyword') or '',
                'body': _truncate(body, max_body),
            })

        if not api_key and ac.get('mock_without_key'):
            results = [_mock_triage_item(it) for it in items]
        else:
            results = _call_triage_llm(items, partners, ac, lt_cfg, log_fn)

        for res in results:
            rid = res.get('id')
            if not rid:
                continue
            triage = {
                'triage_relevance': res.get('triage_relevance') or 'medium',
                'triage_risk_hint': res.get('triage_risk_hint') or 'none',
                'needs_investigation': bool(res.get('needs_investigation')),
                'summary': res.get('summary') or '',
            }
            update_raw_triage(rid, triage)
            processed += 1
            rel = triage['triage_relevance']
            if rel == 'high':
                stats['triage_high'] += 1
            elif rel == 'medium':
                stats['triage_medium'] += 1
            elif rel == 'noise':
                stats['triage_noise'] += 1
            if triage['needs_investigation']:
                stats['needs_investigation_count'] += 1

    if run_metrics:
        elapsed = int((time.monotonic() - t0) * 1000)
        run_metrics.add_triage_ms(elapsed)
        run_metrics.merge_stats(stats)
    return {'processed': processed, 'stats': stats}


def _call_triage_llm(items, partners, ac, lt_cfg, log_fn=None):
    import urllib.error
    import urllib.request

    prompt = LIST_TRIAGE_PROMPT.format(partner_names=_partner_names(partners))
    user_content = json.dumps(items, ensure_ascii=False)
    body = {
        'model': lt_cfg['model'],
        'messages': [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': user_content},
        ],
        'temperature': 0.2,
    }
    api_key = _resolve_api_key(ac)
    endpoint = ac.get('endpoint') or ''
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % api_key,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=int(ac.get('timeout_sec') or 120)) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        content = data['choices'][0]['message']['content']
        parsed = _parse_llm_json(content)
        if isinstance(parsed, list):
            return parsed
    except Exception as e:
        if log_fn:
            log_fn('[triage] LLM 失败: %s' % str(e)[:80], 'WARN')
    return [_mock_triage_item(it) for it in items]
