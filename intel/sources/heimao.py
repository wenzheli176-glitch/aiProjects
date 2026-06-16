# -*- coding: utf-8 -*-

"""黑猫 CrawlAdapter：封装 crawl_heimao。"""

from intel.matcher import partner_search_keywords





class HeimaoCrawlAdapter:

    source_id = 'heimao'

    supports_fetch_detail = True



    def crawl(self, crawl_ctx, task, partner, options=None):

        options = options or {}

        from crawler_web import crawl_heimao, S



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

                log_fn('[heimao] 关键词: %s' % kw)

            batch = crawl_heimao(
                kw, max_pages, fetch_detail=fetch_detail, managed_session=True,
                timeout_check=crawl_ctx.get('timeout_check'),
            )

            if batch:

                for r in batch:

                    r['_search_keyword'] = kw

                all_results.extend(batch)

        return all_results



    def crawl_list_batch(self, crawl_ctx, task, keyword_batch, options=None):

        options = dict(options or {})

        options['fetch_detail'] = False

        from crawler_web import crawl_heimao, S



        max_pages = int(options.get('max_pages') or task.get('max_pages') or 2)

        log_fn = crawl_ctx.get('log')

        all_results = []

        for kw in keyword_batch.get('keywords') or []:

            if not S.running and crawl_ctx.get('monitor_active'):

                break

            if log_fn:

                log_fn('[heimao] 批次 %s 关键词: %s' % (

                    keyword_batch.get('cohort') or '', kw,

                ))

            batch = crawl_heimao(
                kw, max_pages, fetch_detail=False, managed_session=True,
                timeout_check=crawl_ctx.get('timeout_check'),
            )

            if batch:

                for r in batch:

                    r['_search_keyword'] = kw

                    r['_cohort'] = keyword_batch.get('cohort') or ''

                all_results.extend(batch)

        return all_results



    def crawl_investigation(self, crawl_ctx, task, urls, options=None):

        from crawler_web import fetch_heimao_details_by_urls

        return fetch_heimao_details_by_urls(urls, managed_session=True, log_fn=crawl_ctx.get('log'))


