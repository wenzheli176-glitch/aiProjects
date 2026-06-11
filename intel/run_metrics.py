# -*- coding: utf-8 -*-
"""单次 monitor_task_run 的耗时与 token 汇总。"""


def _empty_source_bucket():
    return {
        'crawl_ms': 0,
        'analyze_ms': 0,
        'raw_new': 0,
        'raw_updated': 0,
        'intel_written': 0,
        'prompt_tokens': 0,
        'completion_tokens': 0,
        'total_tokens': 0,
    }


class RunMetrics:
    def __init__(self):
        self.stats = {
            'raw_new': 0,
            'raw_updated': 0,
            'raw_unchanged': 0,
            'intel_written': 0,
            'intel_replaced': 0,
            'intel_skipped': 0,
        }
        self.timing_by_source = {}
        self.token_by_source = {}
        self.crawl_duration_ms = 0
        self.analyze_duration_ms = 0

    def _src(self, source):
        source = source or 'unknown'
        if source not in self.timing_by_source:
            self.timing_by_source[source] = _empty_source_bucket()
        if source not in self.token_by_source:
            self.token_by_source[source] = {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
            }
        return source

    def record_raw_insert(self, source, count=1):
        source = self._src(source)
        self.stats['raw_new'] += count
        self.timing_by_source[source]['raw_new'] += count

    def record_raw_update(self, source, count=1):
        source = self._src(source)
        self.stats['raw_updated'] += count
        self.timing_by_source[source]['raw_updated'] += count

    def record_raw_unchanged(self, count=1):
        self.stats['raw_unchanged'] += count

    def add_crawl_ms(self, source, ms):
        source = self._src(source)
        self.timing_by_source[source]['crawl_ms'] += int(ms)
        self.crawl_duration_ms += int(ms)

    def record_intel_written(self, source, replaced=False):
        source = self._src(source)
        self.stats['intel_written'] += 1
        if replaced:
            self.stats['intel_replaced'] += 1
        self.timing_by_source[source]['intel_written'] += 1

    def record_intel_skipped(self, count=1):
        self.stats['intel_skipped'] += int(count)

    def accumulate_batch(self, batch, meta, analyze_ms):
        if not batch:
            return
        analyze_ms = int(analyze_ms)
        self.analyze_duration_ms += analyze_ms
        by_src = {}
        for cand in batch:
            s = cand.get('source') or 'unknown'
            by_src[s] = by_src.get(s, 0) + 1
        total_items = len(batch)
        pt = int(meta.get('prompt_tokens') or 0)
        ct = int(meta.get('completion_tokens') or 0)
        tt = int(meta.get('total_tokens') or 0)
        if tt <= 0:
            tt = pt + ct
        for source, cnt in by_src.items():
            share = cnt / total_items
            source = self._src(source)
            ams = int(analyze_ms * share)
            self.timing_by_source[source]['analyze_ms'] += ams
            ppt = int(pt * share)
            cct = int(ct * share)
            ttt = int(tt * share)
            self.token_by_source[source]['prompt_tokens'] += ppt
            self.token_by_source[source]['completion_tokens'] += cct
            self.token_by_source[source]['total_tokens'] += ttt

    def to_finish_payload(self):
        total_pt = sum(v['prompt_tokens'] for v in self.token_by_source.values())
        total_ct = sum(v['completion_tokens'] for v in self.token_by_source.values())
        total_tt = sum(v['total_tokens'] for v in self.token_by_source.values())
        return {
            'crawl_duration_ms': self.crawl_duration_ms,
            'analyze_duration_ms': self.analyze_duration_ms,
            'timing_by_source_json': self.timing_by_source,
            'token_usage_json': {
                'total': {
                    'prompt_tokens': total_pt,
                    'completion_tokens': total_ct,
                    'total_tokens': total_tt,
                },
                'by_source': self.token_by_source,
            },
            'stats_json': self.stats,
        }
