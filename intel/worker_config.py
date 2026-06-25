# -*- coding: utf-8 -*-
"""Worker 实例配置读取。"""
import os

from config import BASE_DIR, cfg


def workers_enabled():
    w = cfg('monitor', 'workers') or {}
    return bool(w.get('enabled', False))


def run_state_cfg():
    rs = cfg('monitor', 'run_state') or {}
    return {
        'claim_timeout_sec': int(rs.get('claim_timeout_sec') or 600),
        'heartbeat_interval_sec': int(rs.get('heartbeat_interval_sec') or 30),
    }


def _resolve_path(path):
    if not path:
        return ''
    if os.path.isabs(path):
        return path
    return os.path.join(BASE_DIR, path)


def _default_instances():
    chrome = cfg('chrome') or {}
    auth = cfg('auth') or {}
    return {
        'heimao': {
            'instances': [{
                'instance_id': 'heimao-0',
                'cdp_port': int(chrome.get('cdp_port') or 9222),
                'user_data_dir': chrome.get('profile_dir') or 'chrome_heimao_profile',
                'cookies_file': (auth.get('heimao') or {}).get('cookies_file') or 'credentials/heimao_cookies.json',
            }],
        },
        'xhs': {
            'max_instances': 1,
            'instances': [{
                'instance_id': 'xhs-0',
                'cdp_port': int(chrome.get('cdp_port') or 9222) + 8,
                'user_data_dir': 'chrome_profiles/xhs_0',
                'cookies_file': (auth.get('xhs') or {}).get('cookies_file') or 'credentials/xhs_cookies.json',
            }],
        },
    }


def worker_block(source_id):
    w = cfg('monitor', 'workers') or {}
    block = w.get(source_id)
    if not isinstance(block, dict) or not block.get('instances'):
        defaults = _default_instances()
        block = defaults.get(source_id) or {}
    return block


def list_instances(source_id=None):
    w = cfg('monitor', 'workers') or {}
    max_total = int(w.get('max_workers_total') or 4)
    out = []
    source_ids = [source_id] if source_id else ['heimao', 'xhs']
    for sid in source_ids:
        block = worker_block(sid)
        max_inst = int(block.get('max_instances') or len(block.get('instances') or []) or 1)
        for inst in (block.get('instances') or [])[:max_inst]:
            if not isinstance(inst, dict):
                continue
            item = dict(inst)
            item['source_id'] = sid
            item['instance_id'] = item.get('instance_id') or '%s-0' % sid
            item['cdp_port'] = int(item.get('cdp_port') or 9222)
            item['user_data_dir'] = _resolve_path(item.get('user_data_dir') or '')
            item['cookies_file'] = _resolve_path(item.get('cookies_file') or '')
            out.append(item)
            if len(out) >= max_total:
                return out
    return out


def instances_for_sources(source_ids):
    wanted = set(source_ids or [])
    return [i for i in list_instances() if i.get('source_id') in wanted]


def validate_worker_instances(instances):
    """校验 Worker 实例：同一 cookies_file 不可被多实例共用（尤其小红书）。"""
    errors = []
    file_owners = {}
    for inst in instances or []:
        cf = (inst.get('cookies_file') or '').strip()
        if not cf:
            continue
        iid = inst.get('instance_id') or '?'
        sid = inst.get('source_id') or '?'
        if cf in file_owners:
            prev = file_owners[cf]
            errors.append(
                'cookies_file 重复: %s 被 %s(%s) 与 %s(%s) 共用'
                % (cf, prev['instance_id'], prev['source_id'], iid, sid)
            )
        else:
            file_owners[cf] = {'instance_id': iid, 'source_id': sid}
    xhs_insts = [i for i in (instances or []) if i.get('source_id') == 'xhs']
    if len(xhs_insts) > 1:
        xhs_files = {(i.get('cookies_file') or '').strip() for i in xhs_insts}
        if len(xhs_files) < len(xhs_insts):
            errors.append(
                '小红书多 Worker 不得共用同一 cookies_file；请为每个 instance 配置独立账号 Cookie'
            )
    return errors
