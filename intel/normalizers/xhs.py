# -*- coding: utf-8 -*-
"""小红书 NormalizeAdapter。"""
from intel.normalize_utils import apply_text_cleanup, normalize_options
from reports import structure_xhs_record


class XhsNormalizeAdapter:
    source_id = 'xhs'

    def normalize(self, raw):
        opts = normalize_options('xhs')
        structured = structure_xhs_record(raw)
        link = structured.get('link') or raw.get('link') or ''
        body = apply_text_cleanup(structured.get('content') or raw.get('content') or '', opts)
        title = structured.get('title') or raw.get('title') or ''
        if not title.strip() and opts.get('fallback_title_from_body', True) and body:
            title = body[:80]
        extra = {}
        if opts.get('include_likes_in_extra', True):
            extra['likes'] = structured.get('likes')
        extra.update({
            'collects': structured.get('collects'),
            'comments': structured.get('comments'),
            'tags': structured.get('tags'),
            'date_parse_quality': structured.get('date_parse_quality') or '',
        })
        return {
            'source': 'xhs',
            'external_id': structured.get('note_id') or '',
            'url': link,
            'published_at': structured.get('time') or '',
            'title': title,
            'body': body,
            'author': structured.get('author') or raw.get('author') or '',
            'extra': extra,
            'raw_payload': raw,
        }
