# -*- coding: utf-8 -*-
"""SQLite 持久化：合作方、监测任务、原始记录、情报记录、分析作业。"""
import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from config import BASE_DIR, cfg, get_config

_db_lock = threading.Lock()
_conn = None

SCHEMA_VERSION = 5
INTEL_SCHEMA_VERSION = '1.1'

DEFAULT_SCHEDULE = {
    'enabled': False,
    'cron': '',
    'timezone': 'Asia/Shanghai',
    'preset_id': '',
    'skip_if_running': True,
}


def _utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _db_path():
    path = cfg('database', 'path', default='data/intel.db')
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    return path


def get_connection():
    global _conn
    with _db_lock:
        if _conn is None:
            path = _db_path()
            os.makedirs(os.path.dirname(path) or BASE_DIR, exist_ok=True)
            _conn = sqlite3.connect(path, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute('PRAGMA foreign_keys = ON')
            init_schema(_conn)
        return _conn


def init_schema(conn=None):
    conn = conn or get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS partners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            aliases_json TEXT NOT NULL DEFAULT '[]',
            exclude_words_json TEXT NOT NULL DEFAULT '[]',
            monitor_keywords_json TEXT NOT NULL DEFAULT '[]',
            enabled INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS monitor_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'queued',
            sources_json TEXT NOT NULL DEFAULT '[]',
            max_pages INTEGER NOT NULL DEFAULT 2,
            fetch_detail INTEGER NOT NULL DEFAULT 1,
            progress_json TEXT NOT NULL DEFAULT '{}',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT
        );

        CREATE TABLE IF NOT EXISTS monitor_task_partners (
            task_id INTEGER NOT NULL,
            partner_id INTEGER NOT NULL,
            PRIMARY KEY (task_id, partner_id),
            FOREIGN KEY (task_id) REFERENCES monitor_tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (partner_id) REFERENCES partners(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS raw_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            partner_id INTEGER,
            source TEXT NOT NULL,
            keyword TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES monitor_tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (partner_id) REFERENCES partners(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS intel_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            partner_id INTEGER,
            partner_name TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            published_at TEXT NOT NULL DEFAULT '',
            captured_at TEXT NOT NULL,
            relevance TEXT NOT NULL DEFAULT 'medium',
            risk_types_json TEXT NOT NULL DEFAULT '[]',
            subject_hits_json TEXT NOT NULL DEFAULT '[]',
            summary TEXT NOT NULL DEFAULT '',
            export_tier TEXT NOT NULL DEFAULT 'include',
            dedup_key TEXT NOT NULL DEFAULT '',
            is_duplicate INTEGER NOT NULL DEFAULT 0,
            prompt_version TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            schema_version TEXT NOT NULL DEFAULT '1.0',
            extra_json TEXT NOT NULL DEFAULT '{}',
            raw_record_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES monitor_tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (partner_id) REFERENCES partners(id) ON DELETE SET NULL,
            FOREIGN KEY (raw_record_id) REFERENCES raw_records(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS analysis_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            model TEXT NOT NULL DEFAULT '',
            prompt_version TEXT NOT NULL DEFAULT '',
            batch_count INTEGER NOT NULL DEFAULT 0,
            processed_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT NOT NULL DEFAULT '',
            usage_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            finished_at TEXT,
            FOREIGN KEY (task_id) REFERENCES monitor_tasks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS analysis_job_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            batch_index INTEGER NOT NULL DEFAULT 0,
            partner_name TEXT NOT NULL DEFAULT '',
            item_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'ok',
            model TEXT NOT NULL DEFAULT '',
            latency_ms INTEGER NOT NULL DEFAULT 0,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            items_written INTEGER NOT NULL DEFAULT 0,
            attempt INTEGER NOT NULL DEFAULT 1,
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES analysis_jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (task_id) REFERENCES monitor_tasks(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_analysis_logs_job ON analysis_job_logs(job_id);
        CREATE INDEX IF NOT EXISTS idx_analysis_logs_task ON analysis_job_logs(task_id);

        CREATE INDEX IF NOT EXISTS idx_intel_task ON intel_records(task_id);
        CREATE INDEX IF NOT EXISTS idx_intel_partner ON intel_records(partner_id);
        CREATE INDEX IF NOT EXISTS idx_intel_source ON intel_records(source);
        CREATE INDEX IF NOT EXISTS idx_intel_relevance ON intel_records(relevance);
        CREATE INDEX IF NOT EXISTS idx_intel_dedup ON intel_records(dedup_key);
        CREATE INDEX IF NOT EXISTS idx_raw_task ON raw_records(task_id);

        CREATE TABLE IF NOT EXISTS prompt_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            body TEXT NOT NULL,
            is_builtin INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO schema_meta(key, value) VALUES('db_schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    _migrate_schema(conn)
    _seed_prompt_templates(conn)
    conn.commit()


def _seed_prompt_templates(conn):
    row = conn.execute('SELECT COUNT(*) AS c FROM prompt_templates').fetchone()
    if row and row['c'] > 0:
        return
    from intel.analyze import DEFAULT_SYSTEM_PROMPT
    now = _utc_now()
    conn.execute(
        """
        INSERT INTO prompt_templates(id, name, body, is_builtin, is_active, created_at, updated_at)
        VALUES (?, ?, ?, 1, 1, ?, ?)
        """,
        ('default-high-recall', '内置高召回', DEFAULT_SYSTEM_PROMPT, now, now),
    )


def _migrate_schema(conn):
    cols = {r[1] for r in conn.execute('PRAGMA table_info(intel_records)').fetchall()}
    if 'sentiment_score' not in cols:
        conn.execute('ALTER TABLE intel_records ADD COLUMN sentiment_score REAL')
    if 'sentiment_label' not in cols:
        conn.execute(
            "ALTER TABLE intel_records ADD COLUMN sentiment_label TEXT NOT NULL DEFAULT 'neutral'"
        )
    job_cols = {r[1] for r in conn.execute('PRAGMA table_info(analysis_jobs)').fetchall()}
    if 'usage_json' not in job_cols:
        conn.execute(
            "ALTER TABLE analysis_jobs ADD COLUMN usage_json TEXT NOT NULL DEFAULT '{}'"
        )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS analysis_job_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            batch_index INTEGER NOT NULL DEFAULT 0,
            partner_name TEXT NOT NULL DEFAULT '',
            item_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'ok',
            model TEXT NOT NULL DEFAULT '',
            latency_ms INTEGER NOT NULL DEFAULT 0,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            items_written INTEGER NOT NULL DEFAULT 0,
            attempt INTEGER NOT NULL DEFAULT 1,
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES analysis_jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (task_id) REFERENCES monitor_tasks(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_analysis_logs_job ON analysis_job_logs(job_id);
        CREATE INDEX IF NOT EXISTS idx_analysis_logs_task ON analysis_job_logs(task_id);
        """
    )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS prompt_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            body TEXT NOT NULL,
            is_builtin INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    _seed_prompt_templates(conn)
    raw_cols = {r[1] for r in conn.execute('PRAGMA table_info(raw_records)').fetchall()}
    if 'dedup_key' not in raw_cols:
        conn.execute("ALTER TABLE raw_records ADD COLUMN dedup_key TEXT NOT NULL DEFAULT ''")
    if 'content_hash' not in raw_cols:
        conn.execute("ALTER TABLE raw_records ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''")
    if 'updated_at' not in raw_cols:
        conn.execute("ALTER TABLE raw_records ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
    task_cols = {r[1] for r in conn.execute('PRAGMA table_info(monitor_tasks)').fetchall()}
    if 'schedule_json' not in task_cols:
        conn.execute(
            "ALTER TABLE monitor_tasks ADD COLUMN schedule_json TEXT NOT NULL DEFAULT '{}'"
        )
    if 'last_run_id' not in task_cols:
        conn.execute('ALTER TABLE monitor_tasks ADD COLUMN last_run_id INTEGER')
    if 'run_id' not in job_cols:
        conn.execute('ALTER TABLE analysis_jobs ADD COLUMN run_id INTEGER')
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS monitor_task_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            trigger TEXT NOT NULL DEFAULT 'manual',
            analyze_mode TEXT NOT NULL DEFAULT 'incremental',
            status TEXT NOT NULL DEFAULT 'running',
            started_at TEXT NOT NULL,
            finished_at TEXT,
            crawl_duration_ms INTEGER NOT NULL DEFAULT 0,
            analyze_duration_ms INTEGER NOT NULL DEFAULT 0,
            timing_by_source_json TEXT NOT NULL DEFAULT '{}',
            token_usage_json TEXT NOT NULL DEFAULT '{}',
            stats_json TEXT NOT NULL DEFAULT '{}',
            error_message TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (task_id) REFERENCES monitor_tasks(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_task_runs_task ON monitor_task_runs(task_id);
        CREATE INDEX IF NOT EXISTS idx_raw_dedup ON raw_records(task_id, dedup_key);
        """
    )
    _backfill_raw_hashes(conn)
    conn.execute(
        "UPDATE schema_meta SET value=? WHERE key='db_schema_version'",
        (str(SCHEMA_VERSION),),
    )


def _row_partner(row):
    if not row:
        return None
    return {
        'id': row['id'],
        'name': row['name'],
        'aliases': json.loads(row['aliases_json'] or '[]'),
        'exclude_words': json.loads(row['exclude_words_json'] or '[]'),
        'monitor_keywords': json.loads(row['monitor_keywords_json'] or '[]'),
        'enabled': bool(row['enabled']),
        'notes': row['notes'] or '',
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


def list_partners(enabled_only=False):
    conn = get_connection()
    sql = 'SELECT * FROM partners'
    if enabled_only:
        sql += ' WHERE enabled = 1'
    sql += ' ORDER BY id ASC'
    return [_row_partner(r) for r in conn.execute(sql).fetchall()]


def get_partner(partner_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM partners WHERE id = ?', (partner_id,)).fetchone()
    return _row_partner(row)


def create_partner(data):
    now = _utc_now()
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO partners(name, aliases_json, exclude_words_json, monitor_keywords_json,
                             enabled, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data['name'],
            json.dumps(data.get('aliases') or [], ensure_ascii=False),
            json.dumps(data.get('exclude_words') or [], ensure_ascii=False),
            json.dumps(data.get('monitor_keywords') or [], ensure_ascii=False),
            1 if data.get('enabled', True) else 0,
            data.get('notes') or '',
            now,
            now,
        ),
    )
    conn.commit()
    return get_partner(cur.lastrowid)


def update_partner(partner_id, data):
    existing = get_partner(partner_id)
    if not existing:
        return None
    now = _utc_now()
    conn = get_connection()
    conn.execute(
        """
        UPDATE partners SET name=?, aliases_json=?, exclude_words_json=?, monitor_keywords_json=?,
                            enabled=?, notes=?, updated_at=?
        WHERE id=?
        """,
        (
            data.get('name', existing['name']),
            json.dumps(data.get('aliases', existing['aliases']), ensure_ascii=False),
            json.dumps(data.get('exclude_words', existing['exclude_words']), ensure_ascii=False),
            json.dumps(data.get('monitor_keywords', existing['monitor_keywords']), ensure_ascii=False),
            1 if data.get('enabled', existing['enabled']) else 0,
            data.get('notes', existing['notes']),
            now,
            partner_id,
        ),
    )
    conn.commit()
    return get_partner(partner_id)


def delete_partner(partner_id):
    conn = get_connection()
    cur = conn.execute('DELETE FROM partners WHERE id = ?', (partner_id,))
    conn.commit()
    return cur.rowcount > 0


def _backfill_raw_hashes(conn):
    rows = conn.execute(
        """
        SELECT id, source, payload_json, created_at, dedup_key, content_hash, updated_at
        FROM raw_records
        WHERE dedup_key = '' OR content_hash = '' OR updated_at = ''
        """
    ).fetchall()
    for row in rows:
        try:
            payload = json.loads(row['payload_json'] or '{}')
        except Exception:
            payload = {}
        dk = raw_dedup_key(row['source'], payload)
        ch = raw_content_hash(payload)
        upd = row['updated_at'] or row['created_at']
        conn.execute(
            'UPDATE raw_records SET dedup_key=?, content_hash=?, updated_at=? WHERE id=?',
            (dk, ch, upd, row['id']),
        )


def _parse_schedule(raw):
    try:
        data = json.loads(raw or '{}')
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    out = dict(DEFAULT_SCHEDULE)
    out.update(data)
    out['enabled'] = bool(out.get('enabled'))
    out['skip_if_running'] = bool(out.get('skip_if_running', True))
    return out


def _row_task(row, partner_ids=None, sources=None):
    if not row:
        return None
    progress = json.loads(row['progress_json'] or '{}')
    keys = row.keys()
    schedule = _parse_schedule(
        row['schedule_json'] if 'schedule_json' in keys else '{}'
    )
    return {
        'id': row['id'],
        'name': row['name'] or '',
        'status': row['status'],
        'sources': sources if sources is not None else json.loads(row['sources_json'] or '[]'),
        'partner_ids': partner_ids if partner_ids is not None else [],
        'max_pages': row['max_pages'],
        'fetch_detail': bool(row['fetch_detail']),
        'progress': progress,
        'error_message': row['error_message'] or '',
        'schedule': schedule,
        'last_run_id': row['last_run_id'] if 'last_run_id' in keys else None,
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
        'started_at': row['started_at'],
        'finished_at': row['finished_at'],
    }


def _load_task_relations(task_id):
    conn = get_connection()
    partner_ids = [
        r['partner_id']
        for r in conn.execute(
            'SELECT partner_id FROM monitor_task_partners WHERE task_id = ?', (task_id,)
        ).fetchall()
    ]
    return partner_ids


def get_monitor_task(task_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM monitor_tasks WHERE id = ?', (task_id,)).fetchone()
    if not row:
        return None
    return _row_task(row, partner_ids=_load_task_relations(task_id))


def list_monitor_tasks(limit=50):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM monitor_tasks ORDER BY id DESC LIMIT ?', (limit,)
    ).fetchall()
    return [_row_task(r, partner_ids=_load_task_relations(r['id'])) for r in rows]


def create_monitor_task(data):
    now = _utc_now()
    conn = get_connection()
    sources = data.get('sources') or cfg('monitor', 'default_sources', default=['heimao', 'xhs'])
    cur = conn.execute(
        """
        INSERT INTO monitor_tasks(name, status, sources_json, max_pages, fetch_detail,
                                  progress_json, created_at, updated_at)
        VALUES (?, 'queued', ?, ?, ?, '{}', ?, ?)
        """,
        (
            data.get('name') or ('监测任务 %s' % now[:16]),
            json.dumps(sources, ensure_ascii=False),
            int(data.get('max_pages') or cfg('monitor', 'default_max_pages', default=2)),
            1 if data.get('fetch_detail', True) else 0,
            now,
            now,
        ),
    )
    task_id = cur.lastrowid
    partner_ids = data.get('partner_ids') or []
    for pid in partner_ids:
        conn.execute(
            'INSERT INTO monitor_task_partners(task_id, partner_id) VALUES (?, ?)',
            (task_id, pid),
        )
    if 'schedule' in data and isinstance(data.get('schedule'), dict):
        merged = _parse_schedule(json.dumps(data['schedule'], ensure_ascii=False))
        conn.execute(
            'UPDATE monitor_tasks SET schedule_json=? WHERE id=?',
            (json.dumps(merged, ensure_ascii=False), task_id),
        )
    conn.commit()
    return get_monitor_task(task_id)


def _row_task_run(row):
    if not row:
        return None
    keys = row.keys()

    def _json_col(name):
        try:
            return json.loads(row[name] or '{}')
        except Exception:
            return {}

    return {
        'id': row['id'],
        'task_id': row['task_id'],
        'trigger': row['trigger'],
        'analyze_mode': row['analyze_mode'],
        'status': row['status'],
        'started_at': row['started_at'],
        'finished_at': row['finished_at'] if 'finished_at' in keys else None,
        'crawl_duration_ms': row['crawl_duration_ms'],
        'analyze_duration_ms': row['analyze_duration_ms'],
        'timing_by_source': _json_col('timing_by_source_json'),
        'token_usage': _json_col('token_usage_json'),
        'stats': _json_col('stats_json'),
        'error_message': row['error_message'] or '',
    }


def create_task_run(task_id, trigger='manual', analyze_mode='incremental', status='running'):
    conn = get_connection()
    now = _utc_now()
    cur = conn.execute(
        """
        INSERT INTO monitor_task_runs(
            task_id, trigger, analyze_mode, status, started_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (task_id, trigger, analyze_mode, status, now),
    )
    conn.commit()
    return cur.lastrowid


def finish_task_run(run_id, status='done', error_message='', metrics=None):
    conn = get_connection()
    now = _utc_now()
    fields = {
        'status': status,
        'finished_at': now,
        'error_message': error_message or '',
    }
    if metrics:
        payload = metrics.to_finish_payload() if hasattr(metrics, 'to_finish_payload') else metrics
        fields['crawl_duration_ms'] = int(payload.get('crawl_duration_ms') or 0)
        fields['analyze_duration_ms'] = int(payload.get('analyze_duration_ms') or 0)
        fields['timing_by_source_json'] = json.dumps(
            payload.get('timing_by_source_json') or payload.get('timing_by_source') or {},
            ensure_ascii=False,
        )
        fields['token_usage_json'] = json.dumps(
            payload.get('token_usage_json') or payload.get('token_usage') or {},
            ensure_ascii=False,
        )
        fields['stats_json'] = json.dumps(
            payload.get('stats_json') or payload.get('stats') or {},
            ensure_ascii=False,
        )
    sets = ', '.join('%s=?' % k for k in fields)
    conn.execute(
        'UPDATE monitor_task_runs SET %s WHERE id=?' % sets,
        list(fields.values()) + [run_id],
    )
    row = conn.execute('SELECT task_id FROM monitor_task_runs WHERE id=?', (run_id,)).fetchone()
    if row and status in ('done', 'failed', 'skipped_overlap'):
        conn.execute(
            'UPDATE monitor_tasks SET last_run_id=? WHERE id=?',
            (run_id, row['task_id']),
        )
    conn.commit()
    return get_task_run(run_id)


def get_task_run(run_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM monitor_task_runs WHERE id=?', (run_id,)).fetchone()
    return _row_task_run(row)


def list_task_runs(task_id, limit=20, page=1):
    conn = get_connection()
    offset = (max(page, 1) - 1) * limit
    total = conn.execute(
        'SELECT COUNT(*) FROM monitor_task_runs WHERE task_id=?', (task_id,)
    ).fetchone()[0]
    rows = conn.execute(
        """
        SELECT * FROM monitor_task_runs WHERE task_id=?
        ORDER BY id DESC LIMIT ? OFFSET ?
        """,
        (task_id, limit, offset),
    ).fetchall()
    return {
        'total': total,
        'page': page,
        'page_size': limit,
        'runs': [_row_task_run(r) for r in rows],
    }


def list_scheduled_tasks():
    conn = get_connection()
    rows = conn.execute('SELECT * FROM monitor_tasks ORDER BY id ASC').fetchall()
    out = []
    for row in rows:
        task = _row_task(row, partner_ids=_load_task_relations(row['id']))
        sched = task.get('schedule') or {}
        if sched.get('enabled') and sched.get('cron'):
            out.append(task)
    return out


def update_monitor_task(task_id, data):
    task = get_monitor_task(task_id)
    if not task:
        return None, '不存在'
    if task['status'] in ('crawling', 'analyzing'):
        return None, '运行中的任务不可编辑'
    conn = get_connection()
    now = _utc_now()
    sources = data.get('sources', task['sources'])
    conn.execute(
        """
        UPDATE monitor_tasks SET name=?, sources_json=?, max_pages=?, fetch_detail=?,
                                 status='queued', error_message='', updated_at=?,
                                 started_at=NULL, finished_at=NULL, progress_json='{}'
        WHERE id=?
        """,
        (
            data.get('name', task['name']),
            json.dumps(sources, ensure_ascii=False),
            int(data.get('max_pages', task['max_pages'])),
            1 if data.get('fetch_detail', task['fetch_detail']) else 0,
            now,
            task_id,
        ),
    )
    if 'partner_ids' in data:
        conn.execute('DELETE FROM monitor_task_partners WHERE task_id = ?', (task_id,))
        for pid in data.get('partner_ids') or []:
            conn.execute(
                'INSERT INTO monitor_task_partners(task_id, partner_id) VALUES (?, ?)',
                (task_id, pid),
            )
    if 'schedule' in data:
        sched = data.get('schedule')
        if isinstance(sched, dict):
            merged = _parse_schedule(json.dumps(sched, ensure_ascii=False))
            conn.execute(
                'UPDATE monitor_tasks SET schedule_json=? WHERE id=?',
                (json.dumps(merged, ensure_ascii=False), task_id),
            )
    conn.commit()
    return get_monitor_task(task_id), None


def delete_monitor_task(task_id):
    task = get_monitor_task(task_id)
    if not task:
        return False, '不存在'
    if task['status'] in ('crawling', 'analyzing'):
        return False, '运行中的任务不可删除'
    conn = get_connection()
    cur = conn.execute('DELETE FROM monitor_tasks WHERE id = ?', (task_id,))
    conn.commit()
    return cur.rowcount > 0, None


def update_task_status(task_id, status, **extra):
    conn = get_connection()
    row = conn.execute('SELECT * FROM monitor_tasks WHERE id = ?', (task_id,)).fetchone()
    if not row:
        return None
    now = _utc_now()
    progress = json.loads(row['progress_json'] or '{}')
    progress.update(extra.get('progress') or {})
    fields = {
        'status': status,
        'updated_at': now,
        'progress_json': json.dumps(progress, ensure_ascii=False),
    }
    if extra.get('error_message') is not None:
        fields['error_message'] = extra['error_message']
    if status == 'crawling' and not row['started_at']:
        fields['started_at'] = now
    if status in ('done', 'failed'):
        fields['finished_at'] = now
    sets = ', '.join('%s=?' % k for k in fields)
    conn.execute(
        'UPDATE monitor_tasks SET %s WHERE id=?' % sets,
        list(fields.values()) + [task_id],
    )
    conn.commit()
    return get_monitor_task(task_id)


def raw_content_hash(rec):
    canonical = json.dumps(rec or {}, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.md5(canonical.encode('utf-8')).hexdigest()


def raw_dedup_key(source, rec):
    url = (rec.get('link') or rec.get('url') or '').strip()
    if url:
        return '%s:%s' % (source, hashlib.md5(url.encode('utf-8')).hexdigest()[:16])
    title = (rec.get('title') or '').strip()
    body = (rec.get('content') or rec.get('body') or '').strip()
    text = title + body
    if text:
        return '%s:%s' % (source, hashlib.md5(text.encode('utf-8')).hexdigest()[:16])
    return ''


def _raw_dedup_key(source, rec):
    return raw_dedup_key(source, rec)


def _raw_index_by_dedup(task_id):
    conn = get_connection()
    rows = conn.execute(
        'SELECT id, dedup_key, content_hash FROM raw_records WHERE task_id=? AND dedup_key != ""',
        (task_id,),
    ).fetchall()
    return {r['dedup_key']: {'id': r['id'], 'hash': r['content_hash']} for r in rows}


def delete_intel_by_dedup_key(task_id, dedup_key):
    if not dedup_key:
        return 0
    conn = get_connection()
    cur = conn.execute(
        'DELETE FROM intel_records WHERE task_id=? AND dedup_key=? AND is_duplicate=0',
        (task_id, dedup_key),
    )
    conn.commit()
    return cur.rowcount


def get_raw_analysis_state(task_id):
    """返回 raw_id -> {has_intel, analyzed_at, dedup_key}。"""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT r.id AS raw_id, r.updated_at, r.created_at, r.dedup_key,
               i.created_at AS analyzed_at
        FROM raw_records r
        LEFT JOIN intel_records i ON i.raw_record_id = r.id AND i.is_duplicate = 0
        WHERE r.task_id = ?
        """,
        (task_id,),
    ).fetchall()
    out = {}
    for row in rows:
        rid = row['raw_id']
        analyzed_at = row['analyzed_at']
        if rid not in out or (analyzed_at and (
            not out[rid].get('analyzed_at') or analyzed_at > out[rid]['analyzed_at']
        )):
            out[rid] = {
                'has_intel': bool(analyzed_at),
                'analyzed_at': analyzed_at or '',
                'dedup_key': row['dedup_key'] or '',
                'updated_at': row['updated_at'] or row['created_at'] or '',
            }
    return out


def _existing_raw_dedup_keys(task_id):
    return set(_raw_index_by_dedup(task_id).keys())


def _intel_dedup_exists(task_id, dedup_key):
    if not dedup_key:
        return False
    conn = get_connection()
    row = conn.execute(
        'SELECT id FROM intel_records WHERE task_id=? AND dedup_key=? AND is_duplicate=0 LIMIT 1',
        (task_id, dedup_key),
    ).fetchone()
    return row is not None


def insert_raw_records(task_id, partner_id, source, keyword, records, run_metrics=None):
    if not records:
        return {'ids': [], 'inserted': 0, 'updated': 0, 'unchanged': 0, 'skipped': 0}
    conn = get_connection()
    now = _utc_now()
    index = _raw_index_by_dedup(task_id)
    ids = []
    inserted = 0
    updated = 0
    unchanged = 0
    for rec in records:
        key = raw_dedup_key(source, rec)
        ch = raw_content_hash(rec)
        payload_str = json.dumps(rec, ensure_ascii=False)
        if key and key in index:
            existing = index[key]
            if existing['hash'] == ch:
                unchanged += 1
                if run_metrics:
                    run_metrics.record_raw_unchanged(1)
                continue
            conn.execute(
                """
                UPDATE raw_records
                SET payload_json=?, content_hash=?, updated_at=?, partner_id=?, keyword=?
                WHERE id=?
                """,
                (payload_str, ch, now, partner_id, keyword, existing['id']),
            )
            index[key]['hash'] = ch
            ids.append(existing['id'])
            updated += 1
            if run_metrics:
                run_metrics.record_raw_update(source, 1)
            continue
        cur = conn.execute(
            """
            INSERT INTO raw_records(
                task_id, partner_id, source, keyword, payload_json,
                dedup_key, content_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, partner_id, source, keyword, payload_str, key, ch, now, now),
        )
        rid = cur.lastrowid
        ids.append(rid)
        if key:
            index[key] = {'id': rid, 'hash': ch}
        inserted += 1
        if run_metrics:
            run_metrics.record_raw_insert(source, 1)
    conn.commit()
    return {
        'ids': ids,
        'inserted': inserted,
        'updated': updated,
        'unchanged': unchanged,
        'skipped': unchanged,
    }


def _shanghai_today_start_utc():
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo('Asia/Shanghai')
    except Exception:
        tz = timezone.utc
    now_local = datetime.now(tz)
    start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _raw_title_summary(payload):
    if not isinstance(payload, dict):
        return ''
    title = (payload.get('title') or '').strip()
    if title:
        return title
    body = (payload.get('body') or payload.get('text') or payload.get('content') or '').strip()
    return body[:80] if body else ''


def _row_raw_list(row):
    payload = json.loads(row['payload_json'] or '{}')
    intel_id = row['intel_id'] if row['intel_id'] else None
    return {
        'id': row['id'],
        'task_id': row['task_id'],
        'partner_id': row['partner_id'],
        'source': row['source'],
        'keyword': row['keyword'],
        'title_summary': _raw_title_summary(payload),
        'created_at': row['created_at'],
        'updated_at': (row['updated_at'] if 'updated_at' in row.keys() else None) or row['created_at'],
        'intel_id': intel_id,
        'analyze_status': 'analyzed' if intel_id else 'pending',
    }


def _row_raw_detail(row):
    if not row:
        return None
    payload = json.loads(row['payload_json'] or '{}')
    intel_id = row['intel_id'] if row['intel_id'] else None
    return {
        'id': row['id'],
        'task_id': row['task_id'],
        'partner_id': row['partner_id'],
        'source': row['source'],
        'keyword': row['keyword'],
        'title_summary': _raw_title_summary(payload),
        'payload': payload,
        'dedup_key': row['dedup_key'] if 'dedup_key' in row.keys() else '',
        'content_hash': row['content_hash'] if 'content_hash' in row.keys() else '',
        'created_at': row['created_at'],
        'updated_at': (row['updated_at'] if 'updated_at' in row.keys() else None) or row['created_at'],
        'intel_id': intel_id,
        'analyze_status': 'analyzed' if intel_id else 'pending',
    }


def list_raw_records_paged(
    task_id=None,
    partner_id=None,
    source=None,
    since=None,
    page=1,
    page_size=50,
    include_payload=False,
):
    conn = get_connection()
    where = ['1=1']
    params = []
    if task_id:
        where.append('r.task_id = ?')
        params.append(task_id)
    if partner_id:
        where.append('r.partner_id = ?')
        params.append(partner_id)
    if source:
        where.append('r.source = ?')
        params.append(source)
    if since:
        where.append('r.created_at >= ?')
        params.append(since)
    sql_base = """
        FROM raw_records r
        LEFT JOIN intel_records i ON i.raw_record_id = r.id AND i.is_duplicate = 0
        WHERE """ + ' AND '.join(where)
    total = conn.execute('SELECT COUNT(*)' + sql_base, params).fetchone()[0]
    rows = conn.execute(
        """
        SELECT r.*, i.id AS intel_id
        """ + sql_base + """
        ORDER BY r.id DESC LIMIT ? OFFSET ?
        """,
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    row_fn = _row_raw_detail if include_payload else _row_raw_list
    return {
        'total': total,
        'page': page,
        'page_size': page_size,
        'records': [row_fn(r) for r in rows],
    }


def get_raw_record_detail(raw_id):
    conn = get_connection()
    row = conn.execute(
        """
        SELECT r.*, i.id AS intel_id
        FROM raw_records r
        LEFT JOIN intel_records i ON i.raw_record_id = r.id AND i.is_duplicate = 0
        WHERE r.id = ?
        """,
        (raw_id,),
    ).fetchone()
    return _row_raw_detail(row)


def list_raw_records(task_id, source=None):
    conn = get_connection()
    sql = 'SELECT * FROM raw_records WHERE task_id = ?'
    params = [task_id]
    if source:
        sql += ' AND source = ?'
        params.append(source)
    sql += ' ORDER BY id ASC'
    rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        out.append({
            'id': r['id'],
            'task_id': r['task_id'],
            'partner_id': r['partner_id'],
            'source': r['source'],
            'keyword': r['keyword'],
            'payload': json.loads(r['payload_json'] or '{}'),
            'dedup_key': r['dedup_key'] if 'dedup_key' in r.keys() else '',
            'content_hash': r['content_hash'] if 'content_hash' in r.keys() else '',
            'created_at': r['created_at'],
            'updated_at': (r['updated_at'] if 'updated_at' in r.keys() else None) or r['created_at'],
        })
    return out


def insert_intel_record(data):
    conn = get_connection()
    now = _utc_now()
    dedup_key = data.get('dedup_key') or ''
    if dedup_key and _intel_dedup_exists(data['task_id'], dedup_key):
        return None
    cur = conn.execute(
        """
        INSERT INTO intel_records(
            task_id, partner_id, partner_name, source, url, title, body, published_at,
            captured_at, relevance, risk_types_json, subject_hits_json, summary,
            export_tier, dedup_key, is_duplicate, prompt_version, model, schema_version,
            extra_json, raw_record_id, sentiment_score, sentiment_label, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            data['task_id'],
            data.get('partner_id'),
            data.get('partner_name') or '',
            data['source'],
            data.get('url') or '',
            data.get('title') or '',
            data.get('body') or '',
            data.get('published_at') or '',
            data.get('captured_at') or now,
            data.get('relevance') or 'medium',
            json.dumps(data.get('risk_types') or [], ensure_ascii=False),
            json.dumps(data.get('subject_hits') or [], ensure_ascii=False),
            data.get('summary') or '',
            data.get('export_tier') or 'include',
            dedup_key,
            0,
            data.get('prompt_version') or '',
            data.get('model') or '',
            data.get('schema_version') or INTEL_SCHEMA_VERSION,
            json.dumps(data.get('extra') or {}, ensure_ascii=False),
            data.get('raw_record_id'),
            data.get('sentiment_score'),
            data.get('sentiment_label') or 'neutral',
            now,
        ),
    )
    conn.commit()
    return get_intel_record(cur.lastrowid)


def get_intel_record(record_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM intel_records WHERE id = ?', (record_id,)).fetchone()
    return _row_intel(row)


def _row_intel(row):
    if not row:
        return None
    return {
        'id': row['id'],
        'task_id': row['task_id'],
        'partner_id': row['partner_id'],
        'partner_name': row['partner_name'],
        'source': row['source'],
        'url': row['url'],
        'title': row['title'],
        'body': row['body'],
        'published_at': row['published_at'],
        'captured_at': row['captured_at'],
        'relevance': row['relevance'],
        'risk_types': json.loads(row['risk_types_json'] or '[]'),
        'subject_hits': json.loads(row['subject_hits_json'] or '[]'),
        'summary': row['summary'],
        'export_tier': row['export_tier'],
        'dedup_key': row['dedup_key'],
        'is_duplicate': bool(row['is_duplicate']),
        'sentiment_score': row['sentiment_score'] if 'sentiment_score' in row.keys() else None,
        'sentiment_label': row['sentiment_label'] if 'sentiment_label' in row.keys() else 'neutral',
        'prompt_version': row['prompt_version'],
        'model': row['model'],
        'schema_version': row['schema_version'],
        'extra': json.loads(row['extra_json'] or '{}'),
        'raw_record_id': row['raw_record_id'],
        'created_at': row['created_at'],
        'analyzed_at': row['created_at'],
    }


_RELEVANCE_ORDER = {'noise': 0, 'low': 1, 'medium': 2, 'high': 3}


def list_intel_records(
    task_id=None,
    partner_id=None,
    source=None,
    relevance_min=None,
    since=None,
    risk_type=None,
    export_tier=None,
    include_duplicates=False,
    page=1,
    page_size=50,
):
    conn = get_connection()
    where = ['1=1']
    params = []
    if task_id:
        where.append('task_id = ?')
        params.append(task_id)
    if partner_id:
        where.append('partner_id = ?')
        params.append(partner_id)
    if source:
        where.append('source = ?')
        params.append(source)
    if since:
        where.append('captured_at >= ?')
        params.append(since)
    if export_tier:
        where.append('export_tier = ?')
        params.append(export_tier)
    if not include_duplicates:
        where.append('is_duplicate = 0')
    if relevance_min:
        min_ord = _RELEVANCE_ORDER.get(relevance_min, 0)
        allowed = [k for k, v in _RELEVANCE_ORDER.items() if v >= min_ord]
        if allowed:
            where.append('relevance IN (%s)' % ','.join('?' * len(allowed)))
            params.extend(allowed)
    if risk_type:
        where.append("risk_types_json LIKE ?")
        params.append('%%"%s"%%' % risk_type.replace('"', ''))

    sql_base = ' FROM intel_records WHERE ' + ' AND '.join(where)
    total = conn.execute('SELECT COUNT(*)' + sql_base, params).fetchone()[0]

    rows = conn.execute(
        'SELECT *' + sql_base + ' ORDER BY id DESC LIMIT ? OFFSET ?',
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    records = [_row_intel(r) for r in rows]
    return {'total': total, 'page': page, 'page_size': page_size, 'records': records}


def _row_analysis_job(row):
    if not row:
        return None
    usage = {}
    try:
        raw_usage = row['usage_json'] if 'usage_json' in row.keys() else '{}'
        usage = json.loads(raw_usage or '{}')
    except Exception:
        usage = {}
    return {
        'id': row['id'],
        'task_id': row['task_id'],
        'status': row['status'],
        'model': row['model'] or '',
        'prompt_version': row['prompt_version'] or '',
        'batch_count': row['batch_count'],
        'processed_count': row['processed_count'],
        'error_message': row['error_message'] or '',
        'usage': usage,
        'run_id': row['run_id'] if 'run_id' in row.keys() else None,
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
        'finished_at': row['finished_at'],
    }


def get_analysis_job(job_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM analysis_jobs WHERE id = ?', (job_id,)).fetchone()
    return _row_analysis_job(row)


def list_analysis_jobs(task_id=None, limit=10):
    conn = get_connection()
    if task_id:
        rows = conn.execute(
            'SELECT * FROM analysis_jobs WHERE task_id = ? ORDER BY id DESC LIMIT ?',
            (task_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM analysis_jobs ORDER BY id DESC LIMIT ?',
            (limit,),
        ).fetchall()
    return [_row_analysis_job(r) for r in rows]


def insert_analysis_log(data):
    conn = get_connection()
    now = _utc_now()
    cur = conn.execute(
        """
        INSERT INTO analysis_job_logs(
            job_id, task_id, batch_index, partner_name, item_count, status, model,
            latency_ms, prompt_tokens, completion_tokens, total_tokens,
            items_written, attempt, error_message, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            data['job_id'],
            data['task_id'],
            int(data.get('batch_index') or 0),
            data.get('partner_name') or '',
            int(data.get('item_count') or 0),
            data.get('status') or 'ok',
            data.get('model') or '',
            int(data.get('latency_ms') or 0),
            int(data.get('prompt_tokens') or 0),
            int(data.get('completion_tokens') or 0),
            int(data.get('total_tokens') or 0),
            int(data.get('items_written') or 0),
            int(data.get('attempt') or 1),
            data.get('error_message') or '',
            now,
        ),
    )
    conn.commit()
    return cur.lastrowid


def list_analysis_logs(task_id=None, job_id=None, limit=100):
    conn = get_connection()
    where = ['1=1']
    params = []
    if task_id:
        where.append('task_id = ?')
        params.append(task_id)
    if job_id:
        where.append('job_id = ?')
        params.append(job_id)
    sql = (
        'SELECT * FROM analysis_job_logs WHERE '
        + ' AND '.join(where)
        + ' ORDER BY id DESC LIMIT ?'
    )
    rows = conn.execute(sql, params + [limit]).fetchall()
    out = []
    for r in rows:
        out.append({
            'id': r['id'],
            'job_id': r['job_id'],
            'task_id': r['task_id'],
            'batch_index': r['batch_index'],
            'partner_name': r['partner_name'],
            'item_count': r['item_count'],
            'status': r['status'],
            'model': r['model'],
            'latency_ms': r['latency_ms'],
            'prompt_tokens': r['prompt_tokens'],
            'completion_tokens': r['completion_tokens'],
            'total_tokens': r['total_tokens'],
            'items_written': r['items_written'],
            'attempt': r['attempt'],
            'error_message': r['error_message'],
            'created_at': r['created_at'],
        })
    return out


def update_analysis_job_usage(job_id, delta):
    job = get_analysis_job(job_id)
    if not job:
        return
    usage = dict(job.get('usage') or {})
    for key in (
        'prompt_tokens', 'completion_tokens', 'total_tokens',
        'api_calls', 'mock_batches', 'failed_batches', 'elapsed_ms', 'items_written',
    ):
        usage[key] = int(usage.get(key) or 0) + int(delta.get(key) or 0)
    update_analysis_job(job_id, usage_json=json.dumps(usage, ensure_ascii=False))


def create_analysis_job(task_id, model, prompt_version, run_id=None):
    conn = get_connection()
    now = _utc_now()
    cur = conn.execute(
        """
        INSERT INTO analysis_jobs(task_id, status, model, prompt_version, run_id, created_at, updated_at)
        VALUES (?, 'running', ?, ?, ?, ?, ?)
        """,
        (task_id, model, prompt_version, run_id, now, now),
    )
    conn.commit()
    return cur.lastrowid


def update_analysis_job(job_id, **fields):
    conn = get_connection()
    now = _utc_now()
    fields['updated_at'] = now
    if fields.get('status') in ('done', 'failed'):
        fields['finished_at'] = now
    sets = ', '.join('%s=?' % k for k in fields)
    conn.execute(
        'UPDATE analysis_jobs SET %s WHERE id=?' % sets,
        list(fields.values()) + [job_id],
    )
    conn.commit()


def count_intel_by_partner(task_id):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT partner_id, partner_name, source, relevance, COUNT(*) AS cnt
        FROM intel_records
        WHERE task_id=? AND is_duplicate=0
        GROUP BY partner_id, partner_name, source, relevance
        """,
        (task_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_dashboard_summary():
    conn = get_connection()
    intel_total = conn.execute(
        'SELECT COUNT(*) FROM intel_records WHERE is_duplicate = 0',
    ).fetchone()[0]
    intel_medium_plus = conn.execute(
        """
        SELECT COUNT(*) FROM intel_records
        WHERE is_duplicate = 0 AND relevance IN ('medium', 'high')
        """,
    ).fetchone()[0]
    today_start = _shanghai_today_start_utc()
    intel_today = conn.execute(
        """
        SELECT COUNT(*) FROM intel_records
        WHERE is_duplicate = 0 AND created_at >= ?
        """,
        (today_start,),
    ).fetchone()[0]
    by_source = {}
    for row in conn.execute(
        """
        SELECT source, COUNT(*) AS cnt FROM intel_records
        WHERE is_duplicate = 0 GROUP BY source
        """,
    ).fetchall():
        by_source[row['source']] = row['cnt']
    by_relevance = {}
    for row in conn.execute(
        """
        SELECT relevance, COUNT(*) AS cnt FROM intel_records
        WHERE is_duplicate = 0 GROUP BY relevance
        """,
    ).fetchall():
        by_relevance[row['relevance']] = row['cnt']
    tasks_running = conn.execute(
        """
        SELECT COUNT(*) FROM monitor_tasks
        WHERE status IN ('crawling', 'analyzing')
        """,
    ).fetchone()[0]
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
    tasks_failed_recent = conn.execute(
        """
        SELECT COUNT(*) FROM monitor_tasks
        WHERE status = 'failed' AND updated_at >= ?
        """,
        (week_ago,),
    ).fetchone()[0]
    run_rows = conn.execute(
        """
        SELECT * FROM monitor_task_runs
        ORDER BY id DESC LIMIT 5
        """,
    ).fetchall()
    return {
        'intel_total': intel_total,
        'intel_medium_plus': intel_medium_plus,
        'intel_today': intel_today,
        'by_source': by_source,
        'by_relevance': by_relevance,
        'tasks_running': tasks_running,
        'tasks_failed_recent': tasks_failed_recent,
        'recent_runs': [_row_task_run(r) for r in run_rows],
    }


def count_raw_records(task_id):
    conn = get_connection()
    return conn.execute(
        'SELECT COUNT(*) FROM raw_records WHERE task_id = ?',
        (task_id,),
    ).fetchone()[0]


def count_intel_records_for_task(task_id, unique_only=True):
    conn = get_connection()
    sql = 'SELECT COUNT(*) FROM intel_records WHERE task_id = ?'
    params = [task_id]
    if unique_only:
        sql += ' AND is_duplicate = 0'
    return conn.execute(sql, params).fetchone()[0]


def clear_intel_for_task(task_id):
    conn = get_connection()
    conn.execute('DELETE FROM analysis_job_logs WHERE task_id = ?', (task_id,))
    conn.execute('DELETE FROM intel_records WHERE task_id = ?', (task_id,))
    conn.execute('DELETE FROM analysis_jobs WHERE task_id = ?', (task_id,))
    conn.commit()


def _row_prompt(row):
    if not row:
        return None
    return {
        'id': row['id'],
        'name': row['name'],
        'body': row['body'],
        'is_builtin': bool(row['is_builtin']),
        'is_active': bool(row['is_active']),
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


def list_prompt_templates():
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM prompt_templates ORDER BY is_active DESC, updated_at DESC'
    ).fetchall()
    return [_row_prompt(r) for r in rows]


def get_prompt_template(prompt_id=None, active_only=False):
    conn = get_connection()
    if active_only:
        row = conn.execute(
            'SELECT * FROM prompt_templates WHERE is_active = 1 LIMIT 1'
        ).fetchone()
        return _row_prompt(row)
    row = conn.execute(
        'SELECT * FROM prompt_templates WHERE id = ?', (prompt_id,)
    ).fetchone()
    return _row_prompt(row)


def create_prompt_template(prompt_id, name, body, is_builtin=False):
    conn = get_connection()
    now = _utc_now()
    pid = (prompt_id or '').strip()
    if not pid:
        raise ValueError('id required')
    conn.execute(
        """
        INSERT INTO prompt_templates(id, name, body, is_builtin, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, 0, ?, ?)
        """,
        (pid, name or pid, body or '', 1 if is_builtin else 0, now, now),
    )
    conn.commit()
    return get_prompt_template(pid)


def update_prompt_template(prompt_id, name=None, body=None):
    conn = get_connection()
    row = get_prompt_template(prompt_id)
    if not row:
        return None
    fields = {'updated_at': _utc_now()}
    if name is not None:
        fields['name'] = name
    if body is not None:
        fields['body'] = body
    sets = ', '.join('%s=?' % k for k in fields)
    conn.execute(
        'UPDATE prompt_templates SET %s WHERE id=?' % sets,
        list(fields.values()) + [prompt_id],
    )
    conn.commit()
    return get_prompt_template(prompt_id)


def activate_prompt_template(prompt_id):
    conn = get_connection()
    if not get_prompt_template(prompt_id):
        return None
    conn.execute('UPDATE prompt_templates SET is_active = 0')
    conn.execute(
        'UPDATE prompt_templates SET is_active = 1, updated_at = ? WHERE id = ?',
        (_utc_now(), prompt_id),
    )
    conn.commit()
    return get_prompt_template(prompt_id)


def delete_prompt_template(prompt_id):
    conn = get_connection()
    row = get_prompt_template(prompt_id)
    if not row:
        return False
    if row.get('is_builtin'):
        raise ValueError('builtin prompt cannot be deleted')
    if row.get('is_active'):
        raise ValueError('active prompt cannot be deleted')
    conn.execute('DELETE FROM prompt_templates WHERE id = ?', (prompt_id,))
    conn.commit()
    return True
