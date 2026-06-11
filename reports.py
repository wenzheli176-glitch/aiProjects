# -*- coding: utf-8 -*-
"""黑猫投诉结构化与报表生成。"""
import html
import re
from collections import Counter
from datetime import datetime

from auth_utils import extract_complaint_id

HEIMAO_COLUMNS = [
    ('序号', '_index'),
    ('投诉编号', 'complaint_id'),
    ('投诉标题', 'title'),
    ('投诉对象', 'merchant'),
    ('投诉问题', 'problem'),
    ('涉诉金额', 'amount'),
    ('投诉要求', 'demand'),
    ('投诉状态', 'status'),
    ('发布时间', 'time'),
    ('用户标识', 'author'),
    ('投诉内容', 'content'),
    ('商家回复', 'reply'),
    ('链接', 'link'),
    ('来源', 'source'),
    ('页码', 'page'),
]


def structure_heimao_record(raw, index=None):
    """按黑猫详情页字段结构化为中文键名记录。"""
    link = raw.get('link', '') or ''
    content = (raw.get('content') or '').strip()
    title = (raw.get('title') or '').strip()
    if not title and content:
        title = content[:100]
    time_raw = (raw.get('time') or '').strip()
    publish_date = ''
    m = re.search(r'(\d{4}-\d{2}-\d{2})', time_raw)
    if m:
        publish_date = m.group(1)
    structured = {
        '_index': index,
        'complaint_id': extract_complaint_id(link),
        'title': title,
        'merchant': (raw.get('merchant') or '').strip(),
        'problem': (raw.get('problem') or '').strip(),
        'amount': (raw.get('amount') or '').strip(),
        'demand': (raw.get('demand') or '').strip(),
        'status': (raw.get('status') or '').strip(),
        'time': publish_date or time_raw,
        'time_raw': time_raw,
        'author': (raw.get('author') or '').strip(),
        'content': content,
        'reply': (raw.get('reply') or '').strip(),
        'comments': (raw.get('comments') or '').strip(),
        'link': link,
        'source': raw.get('source', '黑猫投诉'),
        'page': raw.get('page', ''),
    }
    structured['labels'] = {
        '投诉编号': structured['complaint_id'],
        '投诉标题': structured['title'],
        '投诉对象': structured['merchant'],
        '投诉问题': structured['problem'],
        '涉诉金额': structured['amount'],
        '投诉要求': structured['demand'],
        '投诉状态': structured['status'],
        '发布时间': structured['time'],
        '用户标识': structured['author'],
        '投诉内容': structured['content'],
        '商家回复': structured['reply'],
        '链接': structured['link'],
    }
    return structured


def structure_heimao_list(records):
    return [structure_heimao_record(r, i + 1) for i, r in enumerate(records)]


def _extract_xhs_note_id(link):
    link = link or ''
    m = re.search(r'/explore/([a-fA-F0-9]+)', link)
    if m:
        return m.group(1)
    m = re.search(r'noteId=([a-fA-F0-9]+)', link)
    if m:
        return m.group(1)
    return ''


def structure_xhs_record(raw, index=None):
    """小红书记录结构化，供 NormalizeAdapter 与报表使用。"""
    link = raw.get('link', '') or ''
    content = (raw.get('content') or '').strip()
    title = (raw.get('title') or '').strip()
    if not title and content:
        title = content[:100]
    structured = {
        '_index': index,
        'note_id': _extract_xhs_note_id(link),
        'title': title,
        'content': content,
        'author': (raw.get('author') or '').strip(),
        'time': (raw.get('time') or '').strip(),
        'likes': (raw.get('likes') or '').strip(),
        'collects': (raw.get('collects') or '').strip(),
        'comments': (raw.get('comments') or '').strip(),
        'tags': (raw.get('tags') or '').strip(),
        'link': link,
        'source': raw.get('source', '小红书'),
        'page': raw.get('page', ''),
    }
    return structured


def structure_xhs_list(records):
    return [structure_xhs_record(r, i + 1) for i, r in enumerate(records)]


def _summarize(records):
    status_cnt = Counter((r.get('status') or '未知') for r in records)
    merchant_cnt = Counter((r.get('merchant') or '未知') for r in records)
    problem_cnt = Counter((r.get('problem') or '未知') for r in records)
    with_reply = sum(1 for r in records if (r.get('reply') or '').strip())
    return {
        'total': len(records),
        'with_reply': with_reply,
        'status': status_cnt.most_common(10),
        'merchants': merchant_cnt.most_common(10),
        'problems': problem_cnt.most_common(10),
    }


def build_heimao_report_html(records, title='黑猫投诉舆情报表'):
    structured = structure_heimao_list(records)
    summary = _summarize(structured)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def rows_html(items):
        if not items:
            return '<tr><td colspan="2">无数据</td></tr>'
        return ''.join(
            '<tr><td>%s</td><td>%d</td></tr>' % (html.escape(str(k)), v)
            for k, v in items
        )

    detail_rows = []
    for r in structured:
        cells = []
        for label, key in HEIMAO_COLUMNS:
            val = r.get(key, '')
            if key == 'content' or key == 'reply':
                val = (val or '')[:500]
            if key == 'link' and val:
                cells.append('<td><a href="%s" target="_blank">链接</a></td>' % html.escape(val))
            else:
                cells.append('<td>%s</td>' % html.escape(str(val or '')))
        detail_rows.append('<tr>' + ''.join(cells) + '</tr>')

    thead = ''.join('<th>%s</th>' % html.escape(l) for l, _ in HEIMAO_COLUMNS)

    return '''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>%s</title>
<style>
body{font-family:"Segoe UI",sans-serif;margin:24px;background:#f8fafc;color:#0f172a}
h1{font-size:22px} h2{font-size:16px;margin-top:28px;color:#334155}
.meta{color:#64748b;font-size:13px}
.cards{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;min-width:140px}
.card b{font-size:22px;color:#ea580c}
table{border-collapse:collapse;width:100%%;font-size:12px;background:#fff;margin-top:8px}
th,td{border:1px solid #e2e8f0;padding:8px;text-align:left;vertical-align:top}
th{background:#f1f5f9;position:sticky;top:0}
tr:nth-child(even){background:#fafafa}
a{color:#2563eb}
</style></head><body>
<h1>%s</h1>
<p class="meta">生成时间：%s | 共 %d 条 | 含商家回复 %d 条</p>
<div class="cards">
<div class="card">总量<br><b>%d</b></div>
<div class="card">有回复<br><b>%d</b></div>
</div>
<h2>状态分布</h2>
<table><tr><th>状态</th><th>数量</th></tr>%s</table>
<h2>投诉对象 TOP10</h2>
<table><tr><th>商家</th><th>数量</th></tr>%s</table>
<h2>问题类型 TOP10</h2>
<table><tr><th>问题</th><th>数量</th></tr>%s</table>
<h2>明细列表</h2>
<div style="overflow:auto;max-height:70vh">
<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>
</div>
</body></html>''' % (
        html.escape(title), html.escape(title), now,
        summary['total'], summary['with_reply'],
        summary['total'], summary['with_reply'],
        rows_html(summary['status']),
        rows_html(summary['merchants']),
        rows_html(summary['problems']),
        thead, ''.join(detail_rows),
    )


def build_heimao_report_csv_rows(records):
    structured = structure_heimao_list(records)
    header = [label for label, _ in HEIMAO_COLUMNS]
    rows = [header]
    for r in structured:
        rows.append([str(r.get(key, '') or '') for _, key in HEIMAO_COLUMNS])
    return structured, rows
