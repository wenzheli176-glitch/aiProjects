# -*- coding: utf-8 -*-
"""云模型高召回分析管道。"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import cfg, load_config
from intel.recency import apply_recency_relevance, clamp_confidence
from intel.db import (
    delete_intel_by_dedup_key,
    insert_analysis_log,
    insert_intel_record,
    update_analysis_job,
    update_analysis_job_usage,
    INTEL_SCHEMA_VERSION,
)


DEFAULT_SYSTEM_PROMPT = """你是商业合作伙伴风险情报分析师。对每条来自舆情平台的内容判断是否与指定合作方相关及风险类型。
策略：宁可错杀不可放过——主体存疑标 medium，仅明确无关标 noise。

合作方：{partner_name}
别名：{aliases}

输入为 JSON 数组，每项含 id、source、title、body、published_at（YYYY-MM-DD 或空）、captured_at（采集时间）。请输出 JSON 数组，每项：
{{"id": <同输入id>, "relevance": "high|medium|low|noise", "confidence": 0.0到1.0的小数, "risk_types": ["投诉维权","产品质量","服务","舆情扩散","监管","其他"...], "summary": "一句话摘要", "subject_hits": ["命中的别名"], "sentiment": "positive|neutral|negative", "sentiment_score": -1.0到1.0的小数}}

confidence 规则（自报，综合主体命中、信息完整度、时效）：
- 0.8~1.0：主体明确、信息完整、published_at 可判断且与风险时效匹配
- 0.5~0.8：主体较清晰或信息较完整
- 0.0~0.5：主体模糊、信息缺失、或 published_at 为空/难以判断时效

sentiment 规则：
- negative：负面、投诉、风险、批评（分数倾向 -0.3 到 -1.0）
- neutral：中性信息、客观报道（-0.3 到 0.3）
- positive：正面、 praise、推荐（0.3 到 1.0）
sentiment_score 与 sentiment 一致，数值越负越负面。

relevance 规则（结合 published_at 与 captured_at 判断时效）：
- high：明确针对该合作方的负面/风险信号，且时效上仍具参考价值
- medium：可能相关或主体不确定（默认倾向）
- low：弱相关、或发布时间较早风险信号减弱
- noise：仅当明确与排查对象无关

只输出 JSON 数组，不要 markdown。"""

def _analysis_cfg():
    load_config(force=True)
    return cfg('analysis') or {}


def _resolve_api_key(ac):
    key = (ac.get('api_key') or '').strip()
    if key:
        return key
    env_name = ac.get('api_key_env') or 'MINIMAX_API_KEY'
    return os.environ.get(env_name, '').strip()


def get_system_prompt(partner):
    from intel.prompts import get_active_prompt_body
    tpl = get_active_prompt_body()
    aliases = ', '.join((partner.get('aliases') or []) + [partner.get('name') or ''])
    return tpl.format(
        partner_name=partner.get('name') or '',
        aliases=aliases or partner.get('name') or '',
    )


def analysis_status():
    ac = _analysis_cfg()
    api_key = _resolve_api_key(ac)
    return {
        'endpoint': ac.get('endpoint') or '',
        'model': ac.get('model') or '',
        'prompt_version': ac.get('prompt_version') or '',
        'api_key_env': ac.get('api_key_env') or 'MINIMAX_API_KEY',
        'has_api_key': bool(api_key),
        'mock_without_key': bool(ac.get('mock_without_key', False)),
        'mock_mode': not api_key and bool(ac.get('mock_without_key', False)),
        'batch_size': int(ac.get('batch_size') or 15),
        'max_body_chars': int(ac.get('max_body_chars') or 2000),
        'max_retries': int(ac.get('max_retries') or 2),
        'temperature': float(ac.get('temperature', 0.2)),
        'timeout_sec': int(ac.get('timeout_sec') or 120),
    }


def _truncate(text, max_chars):
    text = (text or '').strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + '…'


def _normalize_sentiment(r):
    label = (r.get('sentiment') or 'neutral').strip().lower()
    if label not in ('positive', 'neutral', 'negative'):
        label = 'neutral'
    score = r.get('sentiment_score')
    try:
        score = float(score)
        score = max(-1.0, min(1.0, score))
    except (TypeError, ValueError):
        score = {'negative': -0.6, 'neutral': 0.0, 'positive': 0.6}.get(label, 0.0)
    return label, score


def _parse_llm_json(content):
    content = (content or '').strip()
    if content.startswith('```'):
        content = re.sub(r'^```(?:json)?\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r'\[[\s\S]*\]', content)
        if m:
            return json.loads(m.group(0))
        raise


def _extract_usage(data):
    usage = (data or {}).get('usage') or {}
    prompt = int(usage.get('prompt_tokens') or 0)
    completion = int(usage.get('completion_tokens') or 0)
    total = int(usage.get('total_tokens') or 0)
    if not total and (prompt or completion):
        total = prompt + completion
    return {
        'prompt_tokens': prompt,
        'completion_tokens': completion,
        'total_tokens': total,
    }


def _ai_log(log_fn, msg, level='INFO'):
    if log_fn:
        log_fn('[AI] ' + msg, level)


def _mock_analyze(batch, ac):
    default_rel = ac.get('mock_default_relevance') or 'medium'
    out = []
    for item in batch:
        body = (item.get('body') or item.get('title') or '').strip()
        rel = default_rel if body else 'low'
        neg_words = ('投诉', '维权', '避雷', '问题', '失败', '差', '坑')
        pos_words = ('推荐', '喜提', '满意', '好评', '赞')
        sentiment = 'neutral'
        score = 0.0
        if any(w in body for w in neg_words):
            sentiment, score = 'negative', -0.5
        elif any(w in body for w in pos_words):
            sentiment, score = 'positive', 0.5
        out.append({
            'id': item['id'],
            'relevance': rel,
            'confidence': 0.55 if body else 0.35,
            'risk_types': ['其他'] if body else [],
            'summary': (body or item.get('title') or '')[:120],
            'subject_hits': [],
            'sentiment': sentiment,
            'sentiment_score': score,
        })
    return out


def _call_llm(batch, partner):
    ac = _analysis_cfg()
    api_key = _resolve_api_key(ac)
    model = ac.get('model') or 'gpt-4o-mini'
    endpoint = ac.get('endpoint') or ''

    if not api_key and ac.get('mock_without_key', False):
        t0 = time.time()
        results = _mock_analyze(batch, ac)
        return results, {
            'mock': True,
            'model': model,
            'endpoint': endpoint,
            'latency_ms': int((time.time() - t0) * 1000),
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
        }

    max_body = int(ac.get('max_body_chars') or 2000)
    temperature = float(ac.get('temperature', 0.2))
    timeout_sec = int(ac.get('timeout_sec') or 120)

    payload_items = []
    for item in batch:
        payload_items.append({
            'id': item['id'],
            'source': item.get('source'),
            'title': item.get('title') or '',
            'body': _truncate(item.get('body') or '', max_body),
            'published_at': item.get('published_at') or '',
            'captured_at': item.get('captured_at') or '',
        })

    system_prompt = get_system_prompt(partner)
    user_content = json.dumps(payload_items, ensure_ascii=False)

    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content},
        ],
        'temperature': temperature,
    }
    extra = ac.get('extra_body')
    if isinstance(extra, dict) and extra:
        body.update(extra)

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % api_key,
        },
        method='POST',
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode('utf-8')
            data = json.loads(raw)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')[:300]
        raise RuntimeError('HTTP %s: %s' % (e.code, err_body)) from e
    latency_ms = int((time.time() - t0) * 1000)
    usage = _extract_usage(data)
    content = data['choices'][0]['message']['content']
    results = _parse_llm_json(content)
    return results, {
        'mock': False,
        'model': model,
        'endpoint': endpoint,
        'latency_ms': latency_ms,
        **usage,
    }


def _log_batch_summary(log_fn, bi, batch_total, partner, batch, meta, batch_written, attempt):
    mode = 'Mock' if meta.get('mock') else 'API'
    _ai_log(
        log_fn,
        '批次 %d/%d · %s · %d条 · %s · %s · %dms · tokens in=%d out=%d total=%d · 写入 %d%s' % (
            bi + 1,
            batch_total,
            partner.get('name') or '-',
            len(batch),
            meta.get('model') or '-',
            mode,
            int(meta.get('latency_ms') or 0),
            int(meta.get('prompt_tokens') or 0),
            int(meta.get('completion_tokens') or 0),
            int(meta.get('total_tokens') or 0),
            batch_written,
            (' · 重试%d' % attempt if attempt > 1 else ''),
        ),
    )


def analyze_candidates(task_id, job_id, candidates, partner, log_fn=None, run_metrics=None):
    ac = _analysis_cfg()
    batch_size = int(ac.get('batch_size') or 15)
    parallel_batches = max(1, int(ac.get('parallel_batches') or 1))
    max_retries = int(ac.get('max_retries') or 2)
    retry_delay = float(ac.get('retry_delay_sec') or 1.5)
    model = ac.get('model') or ''
    from intel.prompts import get_active_prompt_id
    prompt_version = get_active_prompt_id() or ac.get('prompt_version') or 'default-high-recall'
    endpoint = ac.get('endpoint') or ''
    written = 0
    written_lock = threading.Lock()
    metrics_lock = threading.Lock()
    batches = [candidates[i:i + batch_size] for i in range(0, len(candidates), batch_size)]
    job_start = time.time()
    mock_mode = not _resolve_api_key(ac) and ac.get('mock_without_key', False)

    if mock_mode:
        _ai_log(log_fn, '未配置 API Key，使用 Mock 打标', 'WARN')
    else:
        _ai_log(
            log_fn,
            '开始分析 · 作业 #%d · 合作方=%s · 候选 %d 条 · %d 批 · 并行=%d · 模型=%s · endpoint=%s' % (
                job_id,
                partner.get('name') or '-',
                len(candidates),
                len(batches),
                parallel_batches,
                model or '-',
                endpoint[:60] + ('…' if len(endpoint) > 60 else ''),
            ),
        )

    def _process_batch(bi, batch):
        nonlocal written
        results = None
        meta = {}
        err = None
        attempt_used = 0
        batch_start = time.time()
        for attempt in range(max_retries + 1):
            attempt_used = attempt + 1
            try:
                results, meta = _call_llm(batch, partner)
                break
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError, RuntimeError) as e:
                err = str(e)
                _ai_log(
                    log_fn,
                    '批次 %d/%d 失败(尝试 %d/%d): %s' % (
                        bi + 1, len(batches), attempt_used, max_retries + 1, err[:120],
                    ),
                    'WARN',
                )
                if attempt < max_retries:
                    time.sleep(retry_delay * attempt_used)

        if results is None:
            insert_analysis_log({
                'job_id': job_id,
                'task_id': task_id,
                'batch_index': bi + 1,
                'partner_name': partner.get('name') or '',
                'item_count': len(batch),
                'status': 'failed',
                'model': model,
                'latency_ms': int((time.time() - batch_start) * 1000),
                'attempt': attempt_used,
                'error_message': (err or 'unknown')[:500],
            })
            update_analysis_job_usage(job_id, {
                'failed_batches': 1,
                'elapsed_ms': int((time.time() - batch_start) * 1000),
            })
            _ai_log(log_fn, '批次 %d 最终失败，跳过该批 %d 条' % (bi + 1, len(batch)), 'ERROR')
            return 0

        result_map = {r.get('id'): r for r in results if isinstance(r, dict)}
        batch_written = 0
        for cand in batch:
            r = result_map.get(cand['id'], {})
            rel_llm = r.get('relevance') or 'medium'
            confidence = clamp_confidence(r.get('confidence'), default=0.5)
            rel, relevance_llm = apply_recency_relevance(
                rel_llm,
                confidence,
                cand.get('published_at') or '',
                cand.get('captured_at') or '',
            )
            sentiment_label, sentiment_score = _normalize_sentiment(r)
            tier = cand.get('export_tier') or 'include'
            if rel == 'noise' and tier != 'exclude':
                tier = 'exclude'
            elif rel in ('high', 'medium') and tier == 'review':
                tier = 'include'
            extra = dict(cand.get('extra') or {})
            extra['relevance_llm'] = relevance_llm
            if cand.get('replace_intel') and cand.get('dedup_key'):
                delete_intel_by_dedup_key(task_id, cand.get('dedup_key'))
            saved = insert_intel_record({
                'task_id': task_id,
                'partner_id': cand.get('partner_id'),
                'partner_name': cand.get('partner_name') or partner.get('name'),
                'source': cand.get('source'),
                'url': cand.get('url'),
                'title': cand.get('title'),
                'body': cand.get('body'),
                'published_at': cand.get('published_at'),
                'captured_at': cand.get('captured_at') or '',
                'relevance': rel,
                'confidence': confidence,
                'risk_types': r.get('risk_types') or [],
                'subject_hits': r.get('subject_hits') or cand.get('subject_hits') or [],
                'summary': r.get('summary') or '',
                'export_tier': tier,
                'dedup_key': cand.get('dedup_key'),
                'prompt_version': prompt_version,
                'model': model,
                'schema_version': INTEL_SCHEMA_VERSION,
                'extra': extra,
                'raw_record_id': cand.get('raw_record_id'),
                'sentiment_label': sentiment_label,
                'sentiment_score': sentiment_score,
            })
            if saved:
                batch_written += 1
                with written_lock:
                    written += 1
                if run_metrics:
                    with metrics_lock:
                        run_metrics.record_intel_written(
                            cand.get('source'), replaced=bool(cand.get('replace_intel')),
                        )

        status = 'mock' if meta.get('mock') else 'ok'
        batch_elapsed_ms = int((time.time() - batch_start) * 1000)
        if run_metrics:
            with metrics_lock:
                run_metrics.accumulate_batch(batch, meta, batch_elapsed_ms)
        insert_analysis_log({
            'job_id': job_id,
            'task_id': task_id,
            'batch_index': bi + 1,
            'partner_name': partner.get('name') or '',
            'item_count': len(batch),
            'status': status,
            'model': meta.get('model') or model,
            'latency_ms': int(meta.get('latency_ms') or 0),
            'prompt_tokens': int(meta.get('prompt_tokens') or 0),
            'completion_tokens': int(meta.get('completion_tokens') or 0),
            'total_tokens': int(meta.get('total_tokens') or 0),
            'items_written': batch_written,
            'attempt': attempt_used,
        })
        update_analysis_job_usage(job_id, {
            'api_calls': 0 if meta.get('mock') else 1,
            'mock_batches': 1 if meta.get('mock') else 0,
            'prompt_tokens': int(meta.get('prompt_tokens') or 0),
            'completion_tokens': int(meta.get('completion_tokens') or 0),
            'total_tokens': int(meta.get('total_tokens') or 0),
            'items_written': batch_written,
            'elapsed_ms': batch_elapsed_ms,
        })
        with written_lock:
            current_written = written
        update_analysis_job(
            job_id,
            processed_count=current_written,
            batch_count=len(batches),
        )
        _log_batch_summary(log_fn, bi, len(batches), partner, batch, meta, batch_written, attempt_used)
        return batch_written

    workers = min(parallel_batches, len(batches)) if batches else 1
    if threading.current_thread() is not threading.main_thread():
        workers = 1
    if workers <= 1 or len(batches) <= 1:
        for bi, batch in enumerate(batches):
            _process_batch(bi, batch)
    else:
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_process_batch, bi, batch) for bi, batch in enumerate(batches)]
                for fut in as_completed(futures):
                    fut.result()
        except RuntimeError as e:
            msg = str(e).lower()
            if 'cannot schedule new futures' in msg or 'interpreter shutdown' in msg:
                _ai_log(
                    log_fn,
                    '并行分析线程池不可用（%s），改为顺序执行' % str(e)[:80],
                    'WARN',
                )
                for bi, batch in enumerate(batches):
                    _process_batch(bi, batch)
            else:
                raise

    elapsed = time.time() - job_start
    from intel.db import get_analysis_job
    usage = (get_analysis_job(job_id) or {}).get('usage') or {}
    update_analysis_job(job_id, status='done', processed_count=written, batch_count=len(batches))
    _ai_log(
        log_fn,
        '作业 #%d 完成 · API %d 次 · Mock %d 批 · 失败 %d 批 · tokens in=%d out=%d total=%d · 情报 %d 条 · 耗时 %.1fs' % (
            job_id,
            int(usage.get('api_calls') or 0),
            int(usage.get('mock_batches') or 0),
            int(usage.get('failed_batches') or 0),
            int(usage.get('prompt_tokens') or 0),
            int(usage.get('completion_tokens') or 0),
            int(usage.get('total_tokens') or 0),
            written,
            elapsed,
        ),
    )
    return written
