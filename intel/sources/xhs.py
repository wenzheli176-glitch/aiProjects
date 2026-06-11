# -*- coding: utf-8 -*-
"""小红书 CrawlAdapter：封装 crawl_xhs + 弹窗详情。"""
from intel.matcher import partner_search_keywords


class XhsCrawlAdapter:
    source_id = 'xhs'
    supports_fetch_detail = True

    def crawl(self, crawl_ctx, task, partner, options=None):
        options = options or {}
        from crawler_web import crawl_xhs, S

        keywords = partner_search_keywords(partner)
        if not keywords:
            return []
        max_pages = int(options.get('max_pages') or task.get('max_pages') or 2)
        fetch_detail = options.get('fetch_detail', task.get('fetch_detail', True))
        log_fn = crawl_ctx.get('log')

        all_results = []
        for kw in keywords[:3]:
            if not S.running and crawl_ctx.get('monitor_active'):
                break
            if log_fn:
                log_fn('[xhs] 关键词: %s' % kw)
            batch = crawl_xhs(kw, max_pages, fetch_detail=fetch_detail, managed_session=True)
            if batch:
                for r in batch:
                    r['_search_keyword'] = kw
                all_results.extend(batch)
        return all_results
