# -*- coding: utf-8 -*-
"""Worker 进程内 CDP 会话（独立端口 Chrome）。"""
import os
import threading

from auth_utils import ensure_site_page, source_startup_url
from config import BASE_DIR, cfg


class WorkerRuntime:
    """login_gate 兼容的运行时对象；Worker 子进程内挂载到 crawler_web.S。"""

    def __init__(self, run_id, instance_id, source_id, log_fn, instance_cfg=None):
        self.running = True
        self.phase = ''
        self.login_wait = None
        self.lock = threading.Lock()
        self.log = log_fn
        self.xhs_pending_keyword = ''
        self.heimao_sid = ''
        self.worker_run_id = run_id
        self.worker_instance_id = instance_id
        self.worker_source_id = source_id
        self._worker_status = 'running'
        ic = instance_cfg or {}
        self.cdp_port = int(ic.get('cdp_port') or 9222)

    def attach_to_global_s(self):
        """将 Worker 元数据挂到子进程全局 S，供 crawl_heimao/crawl_xhs + login_gate 使用。"""
        from crawler_web import S
        S.worker_run_id = self.worker_run_id
        S.worker_instance_id = self.worker_instance_id
        S.worker_source_id = self.worker_source_id
        S.worker_cdp_port = self.cdp_port
        S._worker_status = self._worker_status


class WorkerSession:
    def __init__(self, instance_cfg, log_fn=None):
        self.instance_cfg = instance_cfg or {}
        self.log_fn = log_fn
        self.cdp_port = int(self.instance_cfg.get('cdp_port') or 9222)
        self.user_data_dir = self.instance_cfg.get('user_data_dir') or ''
        self._ctx = None

    @property
    def ctx(self):
        return self._ctx

    def refresh_ctx(self):
        """与全局 S.ctx 同步；爬取流程中 connect_cdp 可能已重连。"""
        from crawler_web import connect_cdp
        self._ctx = connect_cdp(cdp_port=self.cdp_port)
        return self._ctx

    def _sync_pool_cookies_to_global(self, cookies_file):
        from crawler_web import S
        S.xhs_pool_cookies_file = cookies_file or ''

    def __enter__(self):
        from crawler_web import prepare_worker_browser, connect_cdp, reserve_worker_port

        if not self.user_data_dir:
            self.user_data_dir = os.path.join(BASE_DIR, 'chrome_profiles', self.instance_cfg.get('instance_id') or 'worker')
        reserve_worker_port(self.cdp_port)
        sid = self.instance_cfg.get('source_id') or ''
        if not prepare_worker_browser(
            self.cdp_port,
            self.user_data_dir,
            log_fn=self.log_fn,
            startup_url=source_startup_url(sid) if sid else None,
        ):
            raise RuntimeError('Worker Chrome 未就绪 port=%d' % self.cdp_port)
        self._ctx = connect_cdp(cdp_port=self.cdp_port, reset=True)
        if sid == 'xhs':
            ensure_site_page(self._ctx, 'xhs', log_fn=self.log_fn)
        return self

    def __exit__(self, exc_type, exc, tb):
        from auth_utils import close_extra_pages, get_active_page
        from crawler_web import S
        S.worker_cdp_port = None
        S.xhs_pool_cookies_file = ''
        from crawler_web import close_cdp, release_worker_port

        try:
            close_extra_pages(self._ctx, keep_page=get_active_page(self._ctx) if self._ctx else None)
        except Exception:
            pass
        close_cdp(shutdown_browser=False, force=True)
        release_worker_port(self.cdp_port)
        return False

    def rebind_account(self, account, log_fn=None):
        """换绑账号：优先 Cookie 轮换（不重启 Chrome），失败再切换 profile。"""
        from intel.xhs_credentials import resolve_pool_path

        profile = resolve_pool_path((account or {}).get('user_data_dir') or '')
        cookies_file = resolve_pool_path((account or {}).get('cookies_file') or '')
        aid = (account or {}).get('id') or ''
        self.refresh_ctx()

        if self._ctx is not None and self.instance_cfg.get('_bound_account_id') == aid:
            from auth_utils import xhs_session_ok
            ok, info = xhs_session_ok(self._ctx, log_fn=log_fn, cookies_file=cookies_file)
            if ok:
                if log_fn:
                    log_fn('[xhs-pool] 账号 %s 已绑定 (%s)' % (aid, info.get('login_source') or 'ok'))
                return
            if log_fn:
                log_fn('[xhs-pool] 账号 %s 会话失效，重新绑定…' % aid, 'WARN')

        if self._ctx is not None and cookies_file:
            from auth_utils import switch_xhs_account
            ok, info = switch_xhs_account(self._ctx, cookies_file, log_fn=log_fn)
            if ok:
                self.instance_cfg['cookies_file'] = cookies_file
                self.instance_cfg['_bound_account_id'] = aid
                self._sync_pool_cookies_to_global(cookies_file)
                if log_fn:
                    log_fn('[xhs-pool] 账号 %s 已绑定 (%s)' % (aid, info.get('login_source') or 'cookie_switch'))
                return
            if log_fn:
                log_fn(
                    '[xhs-pool] Cookie 轮换失败 (%s)，尝试切换 profile…'
                    % (info.get('error') or 'unknown'),
                    'WARN',
                )

        from crawler_web import close_cdp, connect_cdp, kill_cdp_browser_on_port, prepare_worker_browser

        close_cdp(shutdown_browser=True, force=True)
        kill_cdp_browser_on_port(self.cdp_port, log_fn=log_fn)
        self.user_data_dir = profile
        self.instance_cfg['user_data_dir'] = profile
        self.instance_cfg['cookies_file'] = cookies_file
        self.instance_cfg['_bound_account_id'] = aid
        self._sync_pool_cookies_to_global(cookies_file)
        if not prepare_worker_browser(
            self.cdp_port,
            self.user_data_dir,
            log_fn=log_fn,
            force_restart=True,
            startup_url=source_startup_url('xhs'),
        ):
            raise RuntimeError('Worker Chrome 重启失败')
        self._ctx = connect_cdp(cdp_port=self.cdp_port, reset=True)
        from auth_utils import xhs_session_ok
        ok, info = xhs_session_ok(self._ctx, log_fn=log_fn, cookies_file=cookies_file)
        if not ok:
            raise RuntimeError('账号 %s 未登录: %s' % (aid, info.get('error') or info))
        self._sync_pool_cookies_to_global(cookies_file)
        if log_fn:
            log_fn('[xhs-pool] 账号 %s 已绑定 (%s)' % (aid, info.get('login_source') or 'ok'))
