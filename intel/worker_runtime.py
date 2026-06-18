# -*- coding: utf-8 -*-
"""Worker 进程内 CDP 会话（独立端口 Chrome）。"""
import os
import threading

from config import BASE_DIR, cfg


class WorkerRuntime:
    """login_gate 兼容的运行时对象；Worker 子进程内挂载到 crawler_web.S。"""

    def __init__(self, run_id, instance_id, source_id, log_fn):
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

    def attach_to_global_s(self):
        """将 Worker 元数据挂到子进程全局 S，供 crawl_heimao/crawl_xhs + login_gate 使用。"""
        from crawler_web import S
        S.worker_run_id = self.worker_run_id
        S.worker_instance_id = self.worker_instance_id
        S.worker_source_id = self.worker_source_id
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

    def __enter__(self):
        from crawler_web import prepare_worker_browser, connect_cdp, reserve_worker_port

        if not self.user_data_dir:
            self.user_data_dir = os.path.join(BASE_DIR, 'chrome_profiles', self.instance_cfg.get('instance_id') or 'worker')
        reserve_worker_port(self.cdp_port)
        if not prepare_worker_browser(self.cdp_port, self.user_data_dir, log_fn=self.log_fn):
            raise RuntimeError('Worker Chrome 未就绪 port=%d' % self.cdp_port)
        self._ctx = connect_cdp(cdp_port=self.cdp_port, reset=True)
        return self

    def __exit__(self, exc_type, exc, tb):
        from crawler_web import close_cdp, release_worker_port

        close_cdp(shutdown_browser=False, force=True)
        release_worker_port(self.cdp_port)
        return False
