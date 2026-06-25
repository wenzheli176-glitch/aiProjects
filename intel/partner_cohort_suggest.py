# -*- coding: utf-8 -*-
"""合作方 industry_cohort 推荐：已有 cohort 优先 + LLM + 可选联网搜索。"""
import json
import urllib.error
import urllib.parse
import urllib.request

from config import cfg, load_config

from intel.analyze import _parse_llm_json, _resolve_api_key

COHORT_SUGGEST_PROMPT = """你是行业分类助手。根据品牌/企业名称推断其所属行业 cohort（开放标签，用于舆情监测关键词合并）。

已有 cohort 列表（必须优先 verbatim 选用，不要同义改写）：
{existing_cohorts}

规则：
1. 若品牌行业与已有 cohort 接近，必须输出已有列表中的原文字符串。
2. 仅当确实无合适已有 cohort 时，才提出新的开放标签（简短，如「新能源汽车」「消费电子」）。
3. 输出 JSON 对象：{{"candidates": ["cohort1", "cohort2"], "reason": "一句话说明"}}

只输出 JSON，不要 markdown。"""


def _suggest_cfg():
    load_config(force=True)
    ac = cfg('analysis') or {}
    sc = ac.get('partner_cohort_suggest') or {}
    return {
        'enabled': bool(sc.get('enabled', True)),
        'model': (sc.get('model') or ac.get('model') or 'MiniMax-M3').strip(),
        'max_candidates': max(1, min(int(sc.get('max_candidates') or 5), 10)),
        'web_search_enabled': bool(sc.get('web_search_enabled', True)),
        'web_search_max_results': max(0, min(int(sc.get('web_search_max_results') or 3), 5)),
        'mock_without_key': bool(sc.get('mock_without_key', ac.get('mock_without_key', False))),
        'timeout_sec': int(sc.get('timeout_sec') or ac.get('timeout_sec') or 60),
        'endpoint': ac.get('endpoint') or '',
    }


def list_distinct_cohorts(exclude_partner_id=None):
    from intel.db import get_connection

    conn = get_connection()
    if exclude_partner_id:
        rows = conn.execute(
            """
            SELECT industry_cohort AS cohort, COUNT(*) AS cnt
            FROM partners
            WHERE industry_cohort IS NOT NULL AND TRIM(industry_cohort) != ''
              AND id != ?
            GROUP BY industry_cohort
            ORDER BY cnt DESC, industry_cohort ASC
            """,
            (exclude_partner_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT industry_cohort AS cohort, COUNT(*) AS cnt
            FROM partners
            WHERE industry_cohort IS NOT NULL AND TRIM(industry_cohort) != ''
            GROUP BY industry_cohort
            ORDER BY cnt DESC, industry_cohort ASC
            """
        ).fetchall()
    out = []
    counts = {}
    for row in rows:
        c = (row['cohort'] or '').strip()
        if not c:
            continue
        counts[c] = int(row['cnt'])
        out.append(c)
    return out, counts


def normalize_to_existing(label, existing_cohorts):
    """将 LLM 输出映射到已有 cohort（包含关系优先）。"""
    label = (label or '').strip()
    if not label:
        return '', False
    if label in existing_cohorts:
        return label, True
    label_lower = label.lower()
    for ex in existing_cohorts:
        if ex.lower() == label_lower:
            return ex, True
    best = None
    best_len = 0
    for ex in existing_cohorts:
        ex_l = ex.lower()
        if ex_l in label_lower or label_lower in ex_l:
            if len(ex) > best_len:
                best = ex
                best_len = len(ex)
    if best:
        return best, True
    return label, False


def fetch_web_search_context(name, aliases=None, max_results=3):
    """DuckDuckGo Instant Answer API（无 key）；失败返回空字符串。"""
    if not name:
        return ''
    alias_part = ' '.join((aliases or [])[:2])
    query = '%s %s 行业 所属' % (name, alias_part)
    url = 'https://api.duckduckgo.com/?q=%s&format=json&no_html=1&skip_disambig=1' % (
        urllib.parse.quote(query),
    )
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception:
        return ''
    parts = []
    abstract = (data.get('AbstractText') or '').strip()
    if abstract:
        parts.append(abstract)
    for item in (data.get('RelatedTopics') or []):
        if len(parts) >= max_results:
            break
        if isinstance(item, dict):
            text = (item.get('Text') or '').strip()
            if text:
                parts.append(text)
        elif isinstance(item, list):
            for sub in item:
                if isinstance(sub, dict) and sub.get('Text'):
                    parts.append(sub['Text'].strip())
                    if len(parts) >= max_results:
                        break
    return '\n'.join(parts[:max_results])


def _mock_llm_candidates(name, existing_cohorts):
    """无 API key 时的启发式 mock。"""
    name = name or ''
    automotive_kw = ('汽车', '车', '蔚来', '小鹏', '理想', '比亚迪', '特斯拉', '奔驰', '宝马', '别克')
    if any(k in name for k in automotive_kw):
        if existing_cohorts:
            for ex in existing_cohorts:
                if '汽车' in ex or '新能源' in ex or '车' in ex:
                    return [ex, '新能源汽车'], 'mock：汽车品牌'
        return ['新能源汽车', '汽车'], 'mock：汽车品牌'
    if existing_cohorts:
        return [existing_cohorts[0]], 'mock：默认已有 cohort'
    return ['综合行业'], 'mock：默认'


def _call_cohort_llm(name, aliases, existing_cohorts, web_context, scfg):
    ac = cfg('analysis') or {}
    api_key = _resolve_api_key(ac)
    if not api_key and scfg.get('mock_without_key'):
        cands, reason = _mock_llm_candidates(name, existing_cohorts)
        return cands, reason, True

    if not api_key:
        return [], '未配置 API Key', False

    alias_s = ', '.join(aliases or [])
    user_parts = ['品牌/企业名称：%s' % name]
    if alias_s:
        user_parts.append('别名：%s' % alias_s)
    if web_context:
        user_parts.append('联网检索摘要：\n' + web_context)
    user_content = '\n'.join(user_parts)

    existing_block = '\n'.join('- %s' % c for c in existing_cohorts) if existing_cohorts else '（暂无，可新建）'
    system = COHORT_SUGGEST_PROMPT.format(existing_cohorts=existing_block)

    body = {
        'model': scfg['model'],
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user_content},
        ],
        'temperature': 0.2,
    }
    extra = ac.get('extra_body')
    if isinstance(extra, dict) and extra:
        body.update(extra)

    req = urllib.request.Request(
        scfg['endpoint'],
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % api_key,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=scfg['timeout_sec']) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        content = data['choices'][0]['message']['content']
        parsed = _parse_llm_json(content)
        if isinstance(parsed, dict):
            cands = parsed.get('candidates') or []
            reason = parsed.get('reason') or ''
        elif isinstance(parsed, list):
            cands = parsed
            reason = ''
        else:
            cands, reason = [], ''
        clean = []
        for c in cands:
            if isinstance(c, str) and c.strip():
                clean.append(c.strip())
        return clean, reason, False
    except (urllib.error.HTTPError, urllib.error.URLError, KeyError, json.JSONDecodeError, RuntimeError) as e:
        return [], str(e)[:200], False


def _build_candidate_items(raw_labels, existing_cohorts, cohort_counts, max_candidates):
    """排序：existing 优先，再 llm 归一化到 existing，再 is_new。"""
    seen = set()
    items = []

    def add_item(cohort, source, confidence=0.8, is_new=False):
        cohort = (cohort or '').strip()
        if not cohort or cohort in seen:
            return
        seen.add(cohort)
        normalized, matched = normalize_to_existing(cohort, existing_cohorts)
        if matched:
            cohort = normalized
            source = 'existing'
            is_new = False
        cnt = cohort_counts.get(cohort, 0)
        items.append({
            'cohort': cohort,
            'source': source,
            'partner_count': cnt,
            'confidence': confidence,
            'is_new': bool(is_new and cohort not in existing_cohorts),
        })

    for ex in existing_cohorts:
        if ex in raw_labels or any(ex in r or r in ex for r in raw_labels):
            add_item(ex, 'existing', confidence=0.95, is_new=False)

    for label in raw_labels:
        normalized, matched = normalize_to_existing(label, existing_cohorts)
        add_item(
            normalized,
            'existing' if matched else 'llm',
            confidence=0.85 if matched else 0.7,
            is_new=not matched,
        )

    def sort_key(it):
        is_existing = 0 if it['source'] == 'existing' and not it.get('is_new') else 1
        return (is_existing, -it.get('partner_count', 0), -it.get('confidence', 0))

    items.sort(key=sort_key)
    return items[:max_candidates]


def suggest_cohort_candidates(name, aliases=None, exclude_partner_id=None):
    name = (name or '').strip()
    if not name:
        raise ValueError('name 必填')

    scfg = _suggest_cfg()
    if not scfg['enabled']:
        return {
            'ok': False,
            'msg': 'cohort 推荐已关闭',
            'candidates': [],
            'existing_cohorts': [],
        }

    aliases = [a.strip() for a in (aliases or []) if a and str(a).strip()]
    existing_cohorts, cohort_counts = list_distinct_cohorts(exclude_partner_id=exclude_partner_id)

    web_context = ''
    if scfg['web_search_enabled']:
        web_context = fetch_web_search_context(
            name, aliases, max_results=scfg['web_search_max_results'],
        )

    raw_labels, reason, mock = _call_cohort_llm(
        name, aliases, existing_cohorts, web_context, scfg,
    )

    candidates = _build_candidate_items(
        raw_labels, existing_cohorts, cohort_counts, scfg['max_candidates'],
    )

    return {
        'ok': True,
        'candidates': candidates,
        'existing_cohorts': existing_cohorts,
        'reason': reason,
        'mock': mock,
        'web_search_used': bool(web_context),
    }
