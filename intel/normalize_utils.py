# -*- coding: utf-8 -*-
"""归一化文本清洗辅助。"""
from config import cfg


def normalize_options(source_id):
    return cfg(source_id, 'normalize') or {}


def apply_text_cleanup(text, opts=None):
    text = text or ''
    opts = opts or {}
    if opts.get('strip_whitespace', True):
        text = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
    max_chars = int(opts.get('body_max_chars') or 0)
    if max_chars > 0 and len(text) > max_chars:
        text = text[:max_chars]
    return text
