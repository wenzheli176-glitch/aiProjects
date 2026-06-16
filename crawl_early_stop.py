# -*- coding: utf-8 -*-
"""分页见底早停：按源配置，供 crawler_web 调用。"""

HEIMAO_EARLY_STOP_DEFAULT = {
    'enabled': True,
    'min_pages': 1,
    'empty_pages_threshold': 1,
    'protect_first_page': True,
    'empty_page_retry': 1,
}

XHS_EARLY_STOP_DEFAULT = {
    'enabled': True,
    'min_pages': 1,
    'protect_first_page': True,
    'end_texts': ['- THE END -', 'THE END'],
    'end_selectors': [],
    'saturation_rounds': 2,
}


def early_stop_cfg(site, site_config=None):
    if site_config is None:
        from config import get_config
        site_config = get_config().get(site) or {}
    defaults = HEIMAO_EARLY_STOP_DEFAULT if site == 'heimao' else XHS_EARLY_STOP_DEFAULT
    raw = site_config.get('early_stop') if isinstance(site_config.get('early_stop'), dict) else {}
    out = dict(defaults)
    out.update(raw)
    out['enabled'] = bool(out.get('enabled', defaults.get('enabled', True)))
    if site == 'heimao':
        out['min_pages'] = max(1, int(out.get('min_pages', 1) or 1))
        out['empty_pages_threshold'] = max(1, int(out.get('empty_pages_threshold', 1) or 1))
        out['protect_first_page'] = bool(out.get('protect_first_page', True))
        out['empty_page_retry'] = max(0, int(out.get('empty_page_retry', 1) or 0))
    else:
        out['min_pages'] = max(1, int(out.get('min_pages', 1) or 1))
        out['protect_first_page'] = bool(out.get('protect_first_page', True))
        texts = out.get('end_texts')
        out['end_texts'] = list(texts) if isinstance(texts, list) and texts else list(defaults['end_texts'])
        sels = out.get('end_selectors')
        out['end_selectors'] = list(sels) if isinstance(sels, list) else []
        out['saturation_rounds'] = max(1, int(out.get('saturation_rounds', 2) or 2))
    return out


def format_early_stop_log(source, reason, stopped_at, max_pages):
    return 'early_stop: %s · reason=%s · stopped_at=%d/%d' % (source, reason, stopped_at, max_pages)


def heimao_should_stop_after_page(es, p, max_pages, new_count, consecutive_empty, page_too_short=False):
    """返回 (stop, reason, new_consecutive_empty)。"""
    if not es.get('enabled') or page_too_short:
        return False, None, consecutive_empty
    if new_count > 0:
        return False, None, 0
    min_pages = int(es.get('min_pages', 1))
    if p == 1 and es.get('protect_first_page'):
        return True, 'empty_page', consecutive_empty
    consecutive_empty += 1
    threshold = int(es.get('empty_pages_threshold', 1))
    if consecutive_empty >= threshold and p >= min_pages:
        return True, 'empty_page', consecutive_empty
    return False, None, consecutive_empty


def xhs_body_has_end_marker(body_text, cfg):
    text = body_text or ''
    for marker in cfg.get('end_texts') or []:
        if marker and marker in text:
            return True
    return False


def xhs_has_end_marker(page, cfg):
    for marker in cfg.get('end_texts') or []:
        if not marker:
            continue
        try:
            loc = page.get_by_text(marker, exact=False).first
            if loc.is_visible():
                return True
        except Exception:
            pass
    for sel in cfg.get('end_selectors') or []:
        if not sel:
            continue
        try:
            loc = page.locator(sel).first
            if loc.is_visible():
                return True
        except Exception:
            pass
    try:
        body = page.inner_text('body')[:12000]
    except Exception:
        body = ''
    return xhs_body_has_end_marker(body, cfg)


def xhs_should_stop_end_marker(es, p, max_pages, page, note_item_count):
    if not es.get('enabled'):
        return False, None
    if p < int(es.get('min_pages', 1)):
        return False, None
    if es.get('protect_first_page') and p == 1 and note_item_count == 0:
        return False, None
    if xhs_has_end_marker(page, es):
        return True, 'end_marker'
    return False, None


def xhs_update_saturation(es, state, p, max_pages, new_count, item_count):
    """更新 state['saturation_rounds']，返回 (stop, reason)。"""
    if not es.get('enabled'):
        return False, None
    if p < int(es.get('min_pages', 1)):
        state['saturation_rounds'] = 0
        return False, None
    if es.get('protect_first_page') and p == 1 and item_count == 0:
        state['saturation_rounds'] = 0
        return False, None
    prev_items = state.get('prev_item_count', 0)
    saturated = new_count == 0 and item_count <= prev_items
    if saturated:
        state['saturation_rounds'] = state.get('saturation_rounds', 0) + 1
    else:
        state['saturation_rounds'] = 0
    state['prev_item_count'] = item_count
    need = int(es.get('saturation_rounds', 2))
    if state.get('saturation_rounds', 0) >= need:
        return True, 'scroll_saturated'
    return False, None
