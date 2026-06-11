# -*- coding: utf-8 -*-
"""Prompt 模板库（SQLite）。"""
from config import cfg, load_config, save_config
from intel.analyze import DEFAULT_SYSTEM_PROMPT
from intel.db import (
    activate_prompt_template,
    create_prompt_template,
    delete_prompt_template,
    get_prompt_template,
    list_prompt_templates,
    update_prompt_template,
)


def get_active_prompt_id():
    active = get_prompt_template(active_only=True)
    if active:
        return active['id']
    return cfg('analysis', 'active_prompt_id') or 'default-high-recall'


def get_active_prompt_body():
    active = get_prompt_template(active_only=True)
    if active and active.get('body'):
        return active['body']
    ac = cfg('analysis') or {}
    legacy = (ac.get('system_prompt') or '').strip()
    if legacy:
        return legacy
    return DEFAULT_SYSTEM_PROMPT


def migrate_legacy_system_prompt():
    ac = cfg('analysis') or {}
    legacy = (ac.get('system_prompt') or '').strip()
    if not legacy:
        return
    existing = get_prompt_template('legacy-config')
    if existing:
        return
    create_prompt_template('legacy-config', '自 config 迁移', legacy, is_builtin=False)
    activate_prompt_template('legacy-config')
    merged = dict(ac)
    merged.pop('system_prompt', None)
    save_config({'analysis': merged})
    load_config(force=True)


def list_prompts():
    return list_prompt_templates()


def load_prompt(prompt_id):
    return get_prompt_template(prompt_id)


def save_prompt(prompt_id, name=None, body=None):
    row = get_prompt_template(prompt_id)
    if row:
        return update_prompt_template(
            prompt_id,
            name=name if name is not None else row['name'],
            body=body if body is not None else row['body'],
        )
    return create_prompt_template(prompt_id, name or prompt_id, body or '')


def activate_prompt(prompt_id):
    row = activate_prompt_template(prompt_id)
    if row:
        save_config({'analysis': {'active_prompt_id': prompt_id}})
        load_config(force=True)
    return row


def remove_prompt(prompt_id):
    return delete_prompt_template(prompt_id)
