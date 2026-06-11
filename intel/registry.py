# -*- coding: utf-8 -*-
"""数据源插件注册表。"""
from config import cfg


class SourceRegistry:
    def __init__(self):
        self._crawlers = {}
        self._normalizers = {}

    def register_crawler(self, source_id, crawler_cls):
        self._crawlers[source_id] = crawler_cls

    def register_normalizer(self, source_id, normalizer_cls):
        self._normalizers[source_id] = normalizer_cls

    def get_crawler(self, source_id):
        cls = self._crawlers.get(source_id)
        if not cls:
            raise KeyError('未注册 CrawlAdapter: %s' % source_id)
        return cls()

    def get_normalizer(self, source_id):
        cls = self._normalizers.get(source_id)
        if not cls:
            raise KeyError('未注册 NormalizeAdapter: %s' % source_id)
        return cls()

    def list_sources(self):
        return [
            s for s in self.list_sources_detail()
            if s.get('enabled') and s.get('registered')
        ]

    def list_sources_detail(self):
        from source_profiles import SOURCE_PROFILE_KEYS

        out = []
        sources_cfg = cfg('sources') or {}
        seen = set()
        for source_id in sorted(set(list(sources_cfg.keys()) + list(self._crawlers.keys()))):
            meta = sources_cfg.get(source_id) if isinstance(sources_cfg.get(source_id), dict) else {}
            registered = source_id in self._crawlers
            seen.add(source_id)
            crawler_cls = self._crawlers.get(source_id)
            out.append({
                'source_id': source_id,
                'label': (meta or {}).get('label') or source_id,
                'enabled': bool((meta or {}).get('enabled', False)),
                'registered': registered,
                'supports_fetch_detail': getattr(crawler_cls, 'supports_fetch_detail', True) if crawler_cls else False,
                'profile_keys': SOURCE_PROFILE_KEYS.get(source_id, []),
            })
        return out

    def is_registered(self, source_id):
        return source_id in self._crawlers


registry = SourceRegistry()


def register_default_sources():
    from intel.sources.heimao import HeimaoCrawlAdapter
    from intel.sources.xhs import XhsCrawlAdapter
    from intel.normalizers.heimao import HeimaoNormalizeAdapter
    from intel.normalizers.xhs import XhsNormalizeAdapter

    registry.register_crawler('heimao', HeimaoCrawlAdapter)
    registry.register_crawler('xhs', XhsCrawlAdapter)
    registry.register_normalizer('heimao', HeimaoNormalizeAdapter)
    registry.register_normalizer('xhs', XhsNormalizeAdapter)
