# -*- coding: utf-8 -*-
"""合作方风险情报 REST API（Flask Blueprint）。"""
import threading

from flask import Blueprint, jsonify, request, send_file

from admin_auth import require_admin
from config import cfg, get_config, load_config, save_config
from source_profiles import (
    NORMALIZE_PROFILE_KEYS,
    SOURCE_PROFILE_KEYS,
    SOURCES_NOTICE,
    extract_normalize_profile,
    extract_profile,
    filter_normalize_patch,
    filter_profile_patch,
    validate_crawl_mode_patch,
)
from intel.db import (
    count_intel_records_for_task,
    count_raw_records,
    create_monitor_task,
    create_partner,
    delete_monitor_task,
    delete_partner,
    get_dashboard_summary,
    get_intel_record,
    get_monitor_task,
    get_partner,
    get_raw_record_detail,
    get_task_run,
    list_analysis_jobs,
    list_analysis_logs,
    list_intel_records,
    list_monitor_tasks,
    list_partners,
    list_partners_priority,
    list_raw_records_paged,
    list_run_logs,
    list_task_runs,
    update_monitor_task,
    update_partner,
    update_partner_priority,
)
from intel.export_intel import write_export_file
from intel.export_raw import write_raw_export_file
from intel.registry import registry, register_default_sources
from intel.runner import reanalyze_monitor_task, run_monitor_task

intel_bp = Blueprint('intel', __name__, url_prefix='/api')

_registered = False


def _enrich_task(task):
    from intel.run_state import is_monitor_busy
    from intel.scheduler import get_next_run_at

    t = dict(task)
    t['raw_count'] = count_raw_records(task['id'])
    t['intel_count'] = count_intel_records_for_task(task['id'])
    busy = is_monitor_busy()
    t['can_reanalyze'] = t['raw_count'] > 0 and not busy
    t['can_run'] = not busy and task['status'] not in ('crawling', 'analyzing')
    if not t['can_run']:
        if task['status'] in ('crawling', 'analyzing'):
            t['run_block_reason'] = '任务正在运行中'
        elif busy:
            t['run_block_reason'] = '系统中有未结束的监测 Run 或手工爬取进行中'
        else:
            t['run_block_reason'] = '暂不可执行'
    else:
        t['run_block_reason'] = ''
    t['next_run_at'] = get_next_run_at(task['id'])
    last_run = None
    if task.get('last_run_id'):
        last_run = get_task_run(task['last_run_id'])
    t['last_run'] = last_run
    return t


def _ensure_registry():
    global _registered
    if not _registered:
        register_default_sources()
        _registered = True


@intel_bp.before_app_request
def _init_intel():
    _ensure_registry()
    try:
        from intel.prompts import migrate_legacy_system_prompt
        migrate_legacy_system_prompt()
    except Exception:
        pass


@intel_bp.route('/partners', methods=['GET'])
def api_partners_list():
    enabled_only = request.args.get('enabled_only') == '1'
    return jsonify({'ok': True, 'partners': list_partners(enabled_only=enabled_only)})


@intel_bp.route('/partners/<int:partner_id>', methods=['GET'])
def api_partners_get(partner_id):
    p = get_partner(partner_id)
    if not p:
        return jsonify({'ok': False, 'msg': '不存在'}), 404
    return jsonify({'ok': True, 'partner': p})


@intel_bp.route('/partners', methods=['POST'])
@require_admin
def api_partners_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'ok': False, 'msg': 'name 必填'})
    p = create_partner(data)
    return jsonify({'ok': True, 'partner': p})


@intel_bp.route('/partners/<int:partner_id>', methods=['PUT'])
@require_admin
def api_partners_update(partner_id):
    data = request.get_json() or {}
    p = update_partner(partner_id, data)
    if not p:
        return jsonify({'ok': False, 'msg': '不存在'}), 404
    return jsonify({'ok': True, 'partner': p})


@intel_bp.route('/partners/<int:partner_id>', methods=['DELETE'])
@require_admin
def api_partners_delete(partner_id):
    ok = delete_partner(partner_id)
    return jsonify({'ok': ok})


@intel_bp.route('/partners/priority', methods=['GET'])
def api_partners_priority_list():
    return jsonify({'ok': True, 'partners': list_partners_priority()})


@intel_bp.route('/partners/<int:partner_id>/priority', methods=['PATCH'])
def api_partners_priority_patch(partner_id):
    data = request.get_json() or {}
    tier = data.get('tier') or data.get('priority_tier')
    if not tier:
        return jsonify({'ok': False, 'msg': 'tier 必填'})
    p = update_partner_priority(
        partner_id,
        tier,
        source=data.get('source') or 'business',
        reason=data.get('reason') or '',
    )
    if not p:
        return jsonify({'ok': False, 'msg': '不存在'}), 404
    return jsonify({'ok': True, 'partner': p})


@intel_bp.route('/partners/bulk-priority', methods=['POST'])
def api_partners_bulk_priority():
    data = request.get_json() or {}
    items = data.get('items') or data.get('partners') or []
    if not items:
        return jsonify({'ok': False, 'msg': 'items 必填'})
    ok_list = []
    fail_list = []
    for it in items:
        pid = it.get('partner_id') or it.get('id')
        tier = it.get('tier') or it.get('priority_tier')
        if not pid or not tier:
            fail_list.append({'item': it, 'msg': 'partner_id/tier 必填'})
            continue
        p = update_partner_priority(
            int(pid), tier,
            source=it.get('source') or 'business',
            reason=it.get('reason') or data.get('reason') or '',
        )
        if p:
            ok_list.append(p)
        else:
            fail_list.append({'partner_id': pid, 'msg': '不存在'})
    return jsonify({'ok': True, 'updated': ok_list, 'failed': fail_list})


@intel_bp.route('/sources', methods=['GET'])
def api_sources_list():
    _ensure_registry()
    detail = request.args.get('detail') == '1'
    if detail:
        return jsonify({
            'ok': True,
            'sources': registry.list_sources_detail(),
            'notice': SOURCES_NOTICE,
        })
    items = registry.list_sources()
    slim = [{
        'source_id': s['source_id'],
        'label': s['label'],
        'supports_fetch_detail': s.get('supports_fetch_detail', True),
    } for s in items]
    return jsonify({'ok': True, 'sources': slim})


def _reject_if_running():
    from crawler_web import S
    if S.running:
        return jsonify({'ok': False, 'msg': '任务进行中，请先停止再保存配置'})
    return None


@intel_bp.route('/sources/<source_id>', methods=['PATCH'])
@require_admin
def api_sources_patch(source_id):
    _ensure_registry()
    if not registry.is_registered(source_id):
        return jsonify({'ok': False, 'msg': '未注册的数据源: %s' % source_id}), 404
    blocked = _reject_if_running()
    if blocked:
        return blocked
    data = request.get_json() or {}
    patch = {}
    if 'enabled' in data:
        patch['enabled'] = bool(data['enabled'])
    if 'label' in data:
        patch['label'] = str(data['label'] or source_id).strip() or source_id
    if 'crawl_mode' in data:
        ok, msg = validate_crawl_mode_patch(source_id, data['crawl_mode'])
        if not ok:
            return jsonify({'ok': False, 'msg': msg}), 400
        patch['crawl_mode'] = data['crawl_mode']
    if not patch:
        return jsonify({'ok': False, 'msg': '无有效字段'})
    save_config({'sources': {source_id: patch}})
    load_config(force=True)
    item = next((s for s in registry.list_sources_detail() if s['source_id'] == source_id), None)
    return jsonify({'ok': True, 'source': item})


@intel_bp.route('/sources/<source_id>/profile', methods=['GET'])
def api_sources_profile_get(source_id):
    _ensure_registry()
    if not registry.is_registered(source_id):
        return jsonify({'ok': False, 'msg': '未注册的数据源'}), 404
    node = get_config().get(source_id) or {}
    return jsonify({
        'ok': True,
        'source_id': source_id,
        'profile': extract_profile(source_id, node),
        'profile_normalize': extract_normalize_profile(source_id, node),
        'profile_keys': SOURCE_PROFILE_KEYS.get(source_id, []),
        'profile_keys_crawl': SOURCE_PROFILE_KEYS.get(source_id, []),
        'profile_keys_normalize': NORMALIZE_PROFILE_KEYS.get(source_id, []),
    })


@intel_bp.route('/sources/<source_id>/profile', methods=['PATCH'])
@require_admin
def api_sources_profile_patch(source_id):
    _ensure_registry()
    if not registry.is_registered(source_id):
        return jsonify({'ok': False, 'msg': '未注册的数据源'}), 404
    blocked = _reject_if_running()
    if blocked:
        return blocked
    data = request.get_json() or {}
    raw = data.get('profile') if isinstance(data.get('profile'), dict) else data
    crawl_patch = filter_profile_patch(source_id, raw or {})
    norm_patch = filter_normalize_patch(source_id, raw or {})
    if isinstance(data.get('normalize'), dict):
        norm_patch = filter_normalize_patch(source_id, data['normalize']) or norm_patch
    if not crawl_patch and not norm_patch:
        return jsonify({'ok': False, 'msg': '无有效 profile 字段'})
    node = get_config().get(source_id) or {}
    if isinstance(crawl_patch.get('early_stop'), dict):
        prev_es = node.get('early_stop') if isinstance(node.get('early_stop'), dict) else {}
        merged_es = dict(prev_es)
        merged_es.update(crawl_patch['early_stop'])
        crawl_patch['early_stop'] = merged_es
    if isinstance(crawl_patch.get('investigation_detail'), dict):
        prev_inv = node.get('investigation_detail') if isinstance(node.get('investigation_detail'), dict) else {}
        merged_inv = dict(prev_inv)
        merged_inv.update(crawl_patch['investigation_detail'])
        crawl_patch['investigation_detail'] = merged_inv
    merge = dict(crawl_patch)
    if norm_patch:
        node = get_config().get(source_id) or {}
        prev = node.get('normalize') if isinstance(node.get('normalize'), dict) else {}
        merged_norm = dict(prev)
        merged_norm.update(norm_patch)
        merge['normalize'] = merged_norm
    save_config({source_id: merge})
    load_config(force=True)
    node = get_config().get(source_id) or {}
    return jsonify({
        'ok': True,
        'profile': extract_profile(source_id, node),
        'profile_normalize': extract_normalize_profile(source_id, node),
    })


@intel_bp.route('/monitor/defaults', methods=['GET'])
def api_monitor_defaults_get():
    m = cfg('monitor') or {}
    return jsonify({
        'ok': True,
        'defaults': {
            'default_sources': m.get('default_sources') or [],
            'default_max_pages': m.get('default_max_pages', 2),
            'task_timeout_sec': m.get('task_timeout_sec', 7200),
            'analysis_timeout_sec': m.get('analysis_timeout_sec', 3600),
        },
    })


@intel_bp.route('/monitor/defaults', methods=['PATCH'])
@require_admin
def api_monitor_defaults_patch():
    blocked = _reject_if_running()
    if blocked:
        return blocked
    data = request.get_json() or {}
    patch = {}
    if 'default_sources' in data and isinstance(data['default_sources'], list):
        patch['default_sources'] = data['default_sources']
    if 'default_max_pages' in data:
        patch['default_max_pages'] = int(data['default_max_pages'] or 2)
    if 'task_timeout_sec' in data:
        patch['task_timeout_sec'] = int(data['task_timeout_sec'] or 7200)
    if 'analysis_timeout_sec' in data:
        patch['analysis_timeout_sec'] = int(data['analysis_timeout_sec'] or 3600)
    if not patch:
        return jsonify({'ok': False, 'msg': '无有效字段'})
    save_config({'monitor': patch})
    load_config(force=True)
    return jsonify({'ok': True, 'defaults': cfg('monitor') or {}})


@intel_bp.route('/monitor/tasks', methods=['GET'])
def api_monitor_tasks_list():
    tasks = [_enrich_task(t) for t in list_monitor_tasks()]
    return jsonify({'ok': True, 'tasks': tasks})


@intel_bp.route('/monitor/tasks', methods=['POST'])
@require_admin
def api_monitor_tasks_create():
    data = request.get_json() or {}
    if not data.get('partner_ids'):
        return jsonify({'ok': False, 'msg': 'partner_ids 必填'})
    task = create_monitor_task(data)
    try:
        from intel.scheduler import reload_task_job
        reload_task_job(task['id'])
    except Exception:
        pass
    return jsonify({'ok': True, 'task': _enrich_task(task)})


@intel_bp.route('/monitor/tasks/<int:task_id>', methods=['GET'])
def api_monitor_tasks_get(task_id):
    task = get_monitor_task(task_id)
    if not task:
        return jsonify({'ok': False, 'msg': '不存在'}), 404
    return jsonify({'ok': True, 'task': _enrich_task(task)})


@intel_bp.route('/monitor/tasks/<int:task_id>', methods=['PUT'])
@require_admin
def api_monitor_tasks_update(task_id):
    from crawler_web import S

    if S.running:
        return jsonify({'ok': False, 'msg': '已有任务进行中，请稍后再编辑'})
    data = request.get_json() or {}
    if data.get('partner_ids') is not None and not data.get('partner_ids'):
        return jsonify({'ok': False, 'msg': 'partner_ids 不能为空'})
    task, err = update_monitor_task(task_id, data)
    if not task:
        return jsonify({'ok': False, 'msg': err or '更新失败'}), 404
    try:
        from intel.scheduler import reload_task_job
        reload_task_job(task_id)
    except Exception:
        pass
    return jsonify({'ok': True, 'task': _enrich_task(task)})


@intel_bp.route('/monitor/tasks/<int:task_id>', methods=['DELETE'])
@require_admin
def api_monitor_tasks_delete(task_id):
    from crawler_web import S

    if S.running:
        return jsonify({'ok': False, 'msg': '已有任务进行中，请稍后再删除'})
    ok, err = delete_monitor_task(task_id)
    if not ok:
        return jsonify({'ok': False, 'msg': err or '删除失败'}), 404
    return jsonify({'ok': True})


@intel_bp.route('/monitor/tasks/<int:task_id>/runs', methods=['GET'])
def api_monitor_task_runs(task_id):
    task = get_monitor_task(task_id)
    if not task:
        return jsonify({'ok': False, 'msg': '不存在'}), 404
    page = int(request.args.get('page', 1))
    limit = min(int(request.args.get('limit', 20)), 100)
    result = list_task_runs(task_id, limit=limit, page=page)
    return jsonify({'ok': True, **result})


@intel_bp.route('/monitor/runs/<int:run_id>', methods=['GET'])
def api_monitor_run_get(run_id):
    run = get_task_run(run_id)
    if not run:
        return jsonify({'ok': False, 'msg': '不存在'}), 404
    logs = list_run_logs(run_id, limit=int(request.args.get('log_limit', 500)))
    return jsonify({'ok': True, 'run': run, 'logs': logs})


@intel_bp.route('/monitor/run', methods=['POST'])
def api_monitor_run():
    from crawler_web import log
    from intel.run_state import is_monitor_busy

    if is_monitor_busy():
        return jsonify({'ok': False, 'msg': '已有任务进行中'})
    data = request.get_json() or {}
    task_id = data.get('task_id')
    if not task_id:
        return jsonify({'ok': False, 'msg': 'task_id 必填'})
    task = get_monitor_task(task_id)
    if not task:
        return jsonify({'ok': False, 'msg': '任务不存在'}), 404
    analyze_mode = data.get('analyze_mode') or 'incremental'
    if analyze_mode not in ('incremental', 'full_replace'):
        analyze_mode = 'incremental'
    business_spec = data.get('business_spec')
    if business_spec is not None and not isinstance(business_spec, dict):
        business_spec = None

    def _run():
        try:
            run_monitor_task(
                task_id,
                log_fn=log,
                trigger='manual',
                analyze_mode=analyze_mode,
                business_spec=business_spec,
            )
        except Exception as e:
            from intel.error_util import format_exception
            from intel.db import update_task_status

            msg = format_exception(e)
            log('[monitor] 任务 #%s 启动失败: %s' % (task_id, msg), 'ERROR')
            try:
                update_task_status(task_id, 'failed', error_message=msg)
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'ok': True, 'task_id': task_id, 'analyze_mode': analyze_mode})


@intel_bp.route('/monitor/reanalyze', methods=['POST'])
def api_monitor_reanalyze():
    from crawler_web import S, log

    if S.running:
        return jsonify({'ok': False, 'msg': '已有任务进行中'})
    data = request.get_json() or {}
    task_id = data.get('task_id')
    if not task_id:
        return jsonify({'ok': False, 'msg': 'task_id 必填'})
    task = get_monitor_task(task_id)
    if not task:
        return jsonify({'ok': False, 'msg': '任务不存在'}), 404
    if count_raw_records(task_id) <= 0:
        return jsonify({'ok': False, 'msg': '无原始数据，请先执行完整监测'})
    analyze_mode = data.get('analyze_mode')
    if analyze_mode not in ('incremental', 'full_replace'):
        replace = data.get('replace', True)
        analyze_mode = 'full_replace' if replace else 'incremental'

    def _run():
        try:
            reanalyze_monitor_task(
                task_id,
                log_fn=log,
                analyze_mode=analyze_mode,
                trigger='manual',
            )
        except Exception as e:
            log('重跑 AI 分析异常: %s' % str(e)[:120], 'ERROR')

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'ok': True, 'task_id': task_id, 'analyze_mode': analyze_mode})


@intel_bp.route('/dashboard/summary', methods=['GET'])
def api_dashboard_summary():
    return jsonify({'ok': True, **get_dashboard_summary()})


def _parse_float_query(args, key):
    raw = args.get(key)
    if raw is None or raw == '':
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _intel_records_filters(args):
    from intel.db import _normalize_sentiment_label_filter
    sentiment_label = _normalize_sentiment_label_filter(args.get('sentiment_label'))
    sentiment_score_min = _parse_float_query(args, 'sentiment_score_min')
    sentiment_score_max = _parse_float_query(args, 'sentiment_score_max')
    filters = {
        'task_id': args.get('task_id', type=int),
        'partner_id': args.get('partner_id', type=int),
        'source': args.get('source') or None,
        'relevance_min': args.get('relevance_min') or None,
        'since': args.get('since') or None,
        'risk_type': args.get('risk_type') or None,
        'export_tier': args.get('export_tier') or None,
        'sentiment_label': sentiment_label,
        'sentiment_score_min': sentiment_score_min,
        'sentiment_score_max': sentiment_score_max,
    }
    return {k: v for k, v in filters.items() if v is not None}


@intel_bp.route('/intel/records', methods=['GET'])
def api_intel_records():
    args = request.args
    page = int(args.get('page', 1))
    page_size = min(int(args.get('page_size', 50)), 500)
    filters = _intel_records_filters(args)
    result = list_intel_records(
        page=page,
        page_size=page_size,
        **filters,
    )
    return jsonify({'ok': True, 'applied_filters': filters, **result})


@intel_bp.route('/intel/records/<int:record_id>', methods=['GET'])
def api_intel_record_get(record_id):
    record = get_intel_record(record_id)
    if not record:
        return jsonify({'ok': False, 'msg': '不存在'}), 404
    return jsonify({'ok': True, 'record': record})


def _raw_list_filters():
    args = request.args
    filters = {}
    task_id = args.get('task_id', type=int)
    if task_id:
        filters['task_id'] = task_id
    partner_id = args.get('partner_id', type=int)
    if partner_id:
        filters['partner_id'] = partner_id
    source = args.get('source')
    if source:
        filters['source'] = source
    since = args.get('since')
    if since:
        filters['since'] = since
    return filters


@intel_bp.route('/raw/records', methods=['GET'])
def api_raw_records():
    args = request.args
    page = int(args.get('page', 1))
    page_size = min(int(args.get('page_size', 50)), 500)
    result = list_raw_records_paged(
        page=page,
        page_size=page_size,
        **_raw_list_filters(),
    )
    return jsonify({'ok': True, **result})


@intel_bp.route('/raw/records/<int:raw_id>', methods=['GET'])
def api_raw_record_get(raw_id):
    record = get_raw_record_detail(raw_id)
    if not record:
        return jsonify({'ok': False, 'msg': '不存在'}), 404
    return jsonify({'ok': True, 'record': record})


@intel_bp.route('/raw/export', methods=['GET'])
def api_raw_export():
    fmt = request.args.get('format', 'json')
    path = write_raw_export_file(fmt, **_raw_list_filters())
    return send_file(path, as_attachment=True)


@intel_bp.route('/analysis/config', methods=['GET'])
def api_analysis_config_get():
    from config import get_config
    from intel.analyze import analysis_status

    c = get_config()
    ac = dict(c.get('analysis') or {})
    if ac.get('api_key'):
        ac['api_key'] = '***已配置***'
    from intel.prompts import get_active_prompt_body, get_active_prompt_id, list_prompts
    active = get_active_prompt_id()
    status = analysis_status()
    return jsonify({
        'ok': True,
        'analysis': ac,
        'status': status,
        'active_prompt_id': active,
        'active_prompt_body': get_active_prompt_body(),
        'prompts': [{'id': p['id'], 'name': p['name'], 'is_active': p['is_active'], 'is_builtin': p['is_builtin']} for p in list_prompts()],
    })


@intel_bp.route('/analysis/config', methods=['POST'])
@require_admin
def api_analysis_config_post():
    from crawler_web import S
    from config import get_config, save_config, load_config

    if S.running:
        return jsonify({'ok': False, 'msg': '任务进行中，请先停止再保存配置'})
    data = request.get_json() or {}
    incoming = data.get('analysis') if isinstance(data.get('analysis'), dict) else data
    if not isinstance(incoming, dict):
        return jsonify({'ok': False, 'msg': '无效配置'})

    current = get_config().get('analysis') or {}
    merged = dict(current)
    for key, val in incoming.items():
        if key in ('api_key',) and val in ('', '***已配置***'):
            continue
        if key == 'system_prompt':
            continue
        merged[key] = val

    save_config({'analysis': merged})
    load_config(force=True)
    from intel.analyze import analysis_status
    ac_out = dict(get_config().get('analysis') or {})
    if ac_out.get('api_key'):
        ac_out['api_key'] = '***已配置***'
    from intel.prompts import get_active_prompt_body, get_active_prompt_id, list_prompts
    return jsonify({
        'ok': True,
        'analysis': ac_out,
        'status': analysis_status(),
        'active_prompt_id': get_active_prompt_id(),
        'active_prompt_body': get_active_prompt_body(),
        'prompts': list_prompts(),
    })


@intel_bp.route('/analysis/jobs', methods=['GET'])
def api_analysis_jobs_list():
    task_id = request.args.get('task_id', type=int)
    limit = min(int(request.args.get('limit', 5)), 20)
    jobs = list_analysis_jobs(task_id=task_id, limit=limit)
    return jsonify({'ok': True, 'jobs': jobs})


@intel_bp.route('/analysis/logs', methods=['GET'])
def api_analysis_logs_list():
    task_id = request.args.get('task_id', type=int)
    job_id = request.args.get('job_id', type=int)
    limit = min(int(request.args.get('limit', 100)), 500)
    logs = list_analysis_logs(task_id=task_id, job_id=job_id, limit=limit)
    jobs = list_analysis_jobs(task_id=task_id, limit=1) if task_id else list_analysis_jobs(limit=1)
    latest_job = jobs[0] if jobs else None
    return jsonify({
        'ok': True,
        'logs': logs,
        'latest_job': latest_job,
    })


@intel_bp.route('/analysis/prompts', methods=['GET'])
def api_analysis_prompts_list():
    from intel.prompts import list_prompts
    return jsonify({'ok': True, 'prompts': list_prompts()})


@intel_bp.route('/analysis/prompts/<prompt_id>', methods=['GET'])
def api_analysis_prompts_get(prompt_id):
    from intel.prompts import load_prompt
    row = load_prompt(prompt_id)
    if not row:
        return jsonify({'ok': False, 'msg': '不存在'}), 404
    return jsonify({'ok': True, 'prompt': row})


@intel_bp.route('/analysis/prompts', methods=['POST'])
@require_admin
def api_analysis_prompts_create():
    from intel.prompts import save_prompt
    data = request.get_json() or {}
    pid = (data.get('id') or '').strip()
    name = (data.get('name') or pid).strip()
    body = data.get('body') or ''
    if not pid or not body:
        return jsonify({'ok': False, 'msg': 'id 与 body 必填'})
    try:
        row = save_prompt(pid, name, body)
        return jsonify({'ok': True, 'prompt': row})
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)})


@intel_bp.route('/analysis/prompts/<prompt_id>', methods=['PUT'])
@require_admin
def api_analysis_prompts_update(prompt_id):
    from intel.prompts import save_prompt
    data = request.get_json() or {}
    row = save_prompt(
        prompt_id,
        data.get('name'),
        data.get('body') if 'body' in data else None,
    )
    if not row:
        return jsonify({'ok': False, 'msg': '不存在'}), 404
    return jsonify({'ok': True, 'prompt': row})


@intel_bp.route('/analysis/prompts/<prompt_id>/activate', methods=['POST'])
@require_admin
def api_analysis_prompts_activate(prompt_id):
    from intel.prompts import activate_prompt
    row = activate_prompt(prompt_id)
    if not row:
        return jsonify({'ok': False, 'msg': '不存在'}), 404
    return jsonify({'ok': True, 'prompt': row})


@intel_bp.route('/analysis/prompts/<prompt_id>', methods=['DELETE'])
@require_admin
def api_analysis_prompts_delete(prompt_id):
    from intel.prompts import remove_prompt
    try:
        ok = remove_prompt(prompt_id)
        return jsonify({'ok': ok})
    except ValueError as e:
        return jsonify({'ok': False, 'msg': str(e)})


@intel_bp.route('/intel/export', methods=['GET'])
def api_intel_export():
    fmt = request.args.get('format', 'json')
    task_id = request.args.get('task_id', type=int)
    filters = _intel_records_filters(request.args)
    filters.pop('task_id', None)
    path = write_export_file(fmt, task_id=task_id, **filters)
    return send_file(path, as_attachment=True)


def register_intel_routes(app):
    _ensure_registry()
    app.register_blueprint(intel_bp)
    try:
        from intel.scheduler import init_scheduler
        init_scheduler()
    except Exception:
        pass


@intel_bp.route('/cookie-instances', methods=['GET'])
def api_cookie_instances_list():
    from intel.cookie_instances import list_cookie_instances
    data = list_cookie_instances()
    return jsonify({'ok': True, **data})


@intel_bp.route('/cookie-instances/<source_id>/<instance_id>/upload', methods=['POST'])
@require_admin
def api_cookie_instance_upload(source_id, instance_id):
    from intel.cookie_instances import save_instance_cookies
    if source_id not in ('heimao', 'xhs'):
        return jsonify({'ok': False, 'msg': '无效数据源'}), 400
    body = request.get_json() or {}
    cookies = body.get('cookies') or body.get('content') or ''
    if not cookies:
        return jsonify({'ok': False, 'msg': 'cookies 必填'}), 400
    try:
        result = save_instance_cookies(source_id, instance_id, cookies)
        return jsonify({'ok': True, **result})
    except ValueError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 400
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)[:200]}), 500


@intel_bp.route('/cookie-instances/<source_id>/<instance_id>/diagnose', methods=['POST'])
@require_admin
def api_cookie_instance_diagnose(source_id, instance_id):
    from intel.cookie_instances import diagnose_instance
    if source_id not in ('heimao', 'xhs'):
        return jsonify({'ok': False, 'msg': '无效数据源'}), 400
    try:
        result = diagnose_instance(source_id, instance_id)
        return jsonify({'ok': True, 'result': result})
    except ValueError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 400
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)[:200]}), 500
