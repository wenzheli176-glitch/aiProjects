# -*- coding: utf-8 -*-
"""应用时区（默认 Asia/Shanghai）与时间戳读写。"""
from datetime import datetime, timezone

from config import cfg

DEFAULT_TZ = 'Asia/Shanghai'


def app_timezone_name():
    return (
        cfg('app', 'timezone', default=None)
        or cfg('monitor', 'scheduler_timezone', default=None)
        or DEFAULT_TZ
    )


def app_tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(app_timezone_name())
    except Exception:
        return timezone.utc


def now_iso():
    """当前时刻，应用时区 wall clock，格式 YYYY-MM-DDTHH:MM:SS。"""
    return datetime.now(app_tz()).strftime('%Y-%m-%dT%H:%M:%S')


def app_today_start_iso():
    """今日 00:00:00（应用时区）。"""
    now = datetime.now(app_tz())
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.strftime('%Y-%m-%dT%H:%M:%S')


def anchor_date(iso_text):
    """将时间戳转为应用时区日历日期（相对时间解析锚点）。"""
    if not iso_text:
        return datetime.now(app_tz()).date()
    text = str(iso_text).strip()
    if not text:
        return datetime.now(app_tz()).date()
    if len(text) >= 10 and text[4] == '-' and text[10:11] not in ('T', ' '):
        try:
            return datetime.strptime(text[:10], '%Y-%m-%d').date()
        except ValueError:
            pass
    try:
        if text.endswith('Z'):
            dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
        elif len(text) >= 25 and text[19] in '+-':
            dt = datetime.fromisoformat(text)
        elif 'T' in text:
            dt = datetime.fromisoformat(text[:19]).replace(tzinfo=app_tz())
        else:
            dt = datetime.fromisoformat(text[:19]).replace(tzinfo=app_tz())
        return dt.astimezone(app_tz()).date()
    except ValueError:
        return datetime.now(app_tz()).date()
