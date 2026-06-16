# -*- coding: utf-8 -*-
"""异常格式化（完整栈写入 run / task error_message）。"""
import traceback

MAX_ERROR_CHARS = 8192


def format_exception(exc, *, limit=MAX_ERROR_CHARS):
    """返回含类型、消息与完整 traceback 的文本。"""
    if exc is None:
        return ''
    text = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    text = text.strip()
    if not text:
        text = '%s: %s' % (type(exc).__name__, exc)
    if limit and len(text) > limit:
        text = text[: limit - 24] + '\n…(truncated %d chars)' % (len(text) - limit + 24)
    return text
