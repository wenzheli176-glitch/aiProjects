# -*- coding: utf-8 -*-
"""黑猫 NormalizeAdapter。"""
from auth_utils import extract_complaint_id
from intel.normalize_utils import apply_text_cleanup, normalize_options
from reports import structure_heimao_record


class HeimaoNormalizeAdapter:
    source_id = 'heimao'

    def normalize(self, raw):
        opts = normalize_options('heimao')
        structured = structure_heimao_record(raw)
        link = structured.get('link') or raw.get('link') or ''
        body_parts = [structured.get('content') or '']
        if opts.get('include_problem_in_body', True):
            body_parts.append(structured.get('problem') or '')
        if opts.get('include_merchant_in_body', True):
            body_parts.append(structured.get('merchant') or '')
        if opts.get('include_reply_in_body', True):
            body_parts.append(structured.get('reply') or '')
        body = apply_text_cleanup('\n'.join(p for p in body_parts if p).strip(), opts)
        title = structured.get('title') or raw.get('title') or ''
        if not title.strip() and body:
            title = body[:80]
        return {
            'source': 'heimao',
            'external_id': structured.get('complaint_id') or extract_complaint_id(link),
            'url': link,
            'published_at': structured.get('time') or '',
            'title': title,
            'body': body,
            'author': structured.get('author') or '',
            'extra': {
                'merchant': structured.get('merchant'),
                'problem': structured.get('problem'),
                'amount': structured.get('amount'),
                'status': structured.get('status'),
                'demand': structured.get('demand'),
                'date_parse_quality': structured.get('date_parse_quality') or '',
            },
            'raw_payload': raw,
        }
