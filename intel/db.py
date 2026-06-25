# -*- coding: utf-8 -*-
"""SQLite 持久化：合作方、监测任务、原始记录、情报记录、分析作业。"""
import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from config import BASE_DIR, cfg, get_config
from intel.time_util import app_today_start_iso, app_tz, now_iso

_db_lock = threading.RLock()
_local = threading.local()
_conn = None  # 兼容旧测试代码

SCHEMA_VERSION = 11
INTEL_SCHEMA_VERSION = '1.1'

DEFAULT_SCHEDULE = {
    'enabled': False,
    'cron': '',
    'timezone': 'Asia/Shanghai',
    'preset_id': '',
    'skip_if_running': True,
}


def _utc_now():
    """兼容旧名：写入应用时区（北京时间）时间戳。"""
    return now_iso()


def _db_path():
    path = cfg('database', 'path', default='data/intel.db')
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    return path


def reset_db_connection():
    """关闭当前线程的数据库连接（测试或热重载时使用）。"""
    global _conn
    conn = getattr(_local, 'conn', None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    _local.conn = None
    _conn = None


def get_connection():
    global _conn
    conn = getattr(_local, 'conn', None)
    if conn is None:
        path = _db_path()
        os.makedirs(os.path.dirname(path) or BASE_DIR, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        try:
            conn.execute('PRAGMA journal_mode = WAL')
        except Exception:
            pass
        _local.conn = conn
        _conn = conn
        init_schema(conn)
    return conn


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
    if 'confidence' not in cols:
        conn.execute('ALTER TABLE intel_records ADD COLUMN confidence REAL')
        try:
            from intel.analyze import DEFAULT_SYSTEM_PROMPT
            conn.execute(
                """
                UPDATE prompt_templates SET body=?, updated_at=?
                WHERE id='default-high-recall' AND is_builtin=1
                """,
                (DEFAULT_SYSTEM_PROMPT, _utc_now()),
            )
        except Exception:
            pass
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
    partner_cols = {r[1] for r in conn.execute('PRAGMA table_info(partners)').fetchall()}
    if 'industry_cohort' not in partner_cols:
        conn.execute("ALTER TABLE partners ADD COLUMN industry_cohort TEXT NOT NULL DEFAULT ''")
    if 'priority_tier' not in partner_cols:
        conn.execute("ALTER TABLE partners ADD COLUMN priority_tier TEXT NOT NULL DEFAULT 'P1'")
    if 'priority_source' not in partner_cols:
        conn.execute(
            "ALTER TABLE partners ADD COLUMN priority_source TEXT NOT NULL DEFAULT 'auto'"
        )
    if 'priority_updated_at' not in partner_cols:
        conn.execute("ALTER TABLE partners ADD COLUMN priority_updated_at TEXT NOT NULL DEFAULT ''")
    if 'priority_reason' not in partner_cols:
        conn.execute("ALTER TABLE partners ADD COLUMN priority_reason TEXT NOT NULL DEFAULT ''")
    if 'source_timeouts_json' not in partner_cols:
        conn.execute(
            "ALTER TABLE partners ADD COLUMN source_timeouts_json TEXT NOT NULL DEFAULT '{}'"
        )
    kw_run_cols = {r[1] for r in conn.execute('PRAGMA table_info(monitor_keyword_runs)').fetchall()}
    if kw_run_cols and 'timeout_sec' not in kw_run_cols:
        conn.execute(
            "ALTER TABLE monitor_keyword_runs ADD COLUMN timeout_sec INTEGER NOT NULL DEFAULT 0"
        )
    raw_cols2 = {r[1] for r in conn.execute('PRAGMA table_info(raw_records)').fetchall()}
    if 'crawl_phase' not in raw_cols2:
        conn.execute("ALTER TABLE raw_records ADD COLUMN crawl_phase TEXT NOT NULL DEFAULT 'legacy'")
    if 'list_triage_json' not in raw_cols2:
        conn.execute(
            "ALTER TABLE raw_records ADD COLUMN list_triage_json TEXT NOT NULL DEFAULT '{}'"
        )
    task_cols2 = {r[1] for r in conn.execute('PRAGMA table_info(monitor_tasks)').fetchall()}
    if 'crawl_mode' not in task_cols2:
        # 保留列：legacy 单源 heimao 且无 Worker 时作 fallback；混合源/xhs 改读 config.sources.*.crawl_mode
        conn.execute(
            "ALTER TABLE monitor_tasks ADD COLUMN crawl_mode TEXT NOT NULL DEFAULT 'legacy'"
        )
    if 'business_spec_json' not in task_cols2:
        conn.execute(
            "ALTER TABLE monitor_tasks ADD COLUMN business_spec_json TEXT NOT NULL DEFAULT '{}'"
        )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS investigation_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            raw_id INTEGER NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            priority_score REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES monitor_tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (raw_id) REFERENCES raw_records(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_investigation_task ON investigation_queue(task_id, status);
        """
    )
    run_cols = {r[1] for r in conn.execute('PRAGMA table_info(monitor_task_runs)').fetchall()}
    if 'stop_requested' not in run_cols:
        conn.execute(
            "ALTER TABLE monitor_task_runs ADD COLUMN stop_requested INTEGER NOT NULL DEFAULT 0"
        )
    if 'pause_requested' not in run_cols:
        conn.execute(
            "ALTER TABLE monitor_task_runs ADD COLUMN pause_requested INTEGER NOT NULL DEFAULT 0"
        )
    if 'worker_state_json' not in run_cols:
        conn.execute(
            "ALTER TABLE monitor_task_runs ADD COLUMN worker_state_json TEXT NOT NULL DEFAULT '{}'"
        )
    if 'source_halt_json' not in run_cols:
        conn.execute(
            "ALTER TABLE monitor_task_runs ADD COLUMN source_halt_json TEXT NOT NULL DEFAULT '{}'"
        )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS crawl_work_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            source_id TEXT NOT NULL,
            phase TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            priority_score REAL NOT NULL DEFAULT 0,
            worker_instance_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            claimed_at TEXT,
            heartbeat_at TEXT,
            skip_reason TEXT NOT NULL DEFAULT '',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES monitor_task_runs(id) ON DELETE CASCADE,
            FOREIGN KEY (task_id) REFERENCES monitor_tasks(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_cwq_run_status ON crawl_work_queue(run_id, status, source_id);
        CREATE TABLE IF NOT EXISTS monitor_run_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            worker_instance_id TEXT NOT NULL DEFAULT '',
            level TEXT NOT NULL DEFAULT 'INFO',
            message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES monitor_task_runs(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_run_logs_run ON monitor_run_logs(run_id, id);

        CREATE TABLE IF NOT EXISTS monitor_keyword_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            source_id TEXT NOT NULL DEFAULT 'xhs',
            keyword TEXT NOT NULL,
            cohort TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            phase TEXT NOT NULL DEFAULT 'pending',
            started_at TEXT,
            finished_at TEXT,
            error_message TEXT NOT NULL DEFAULT '',
            stats_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (run_id) REFERENCES monitor_task_runs(id) ON DELETE CASCADE,
            FOREIGN KEY (task_id) REFERENCES monitor_tasks(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_kw_runs_run ON monitor_keyword_runs(run_id, status);
        CREATE INDEX IF NOT EXISTS idx_kw_runs_task ON monitor_keyword_runs(task_id, status);
        """
    )
    conn.execute(
        "UPDATE schema_meta SET value=? WHERE key='db_schema_version'",
        (str(SCHEMA_VERSION),),
    )


def _parse_source_timeouts(row):
    if not row:
        return {}
    keys = row.keys()
    if 'source_timeouts_json' not in keys:
        return {}
    try:
        raw = json.loads(row['source_timeouts_json'] or '{}')
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in raw.items():
        if v is None or v == '':
            continue
        try:
            out[str(k)] = max(60, int(v))
        except (TypeError, ValueError):
            pass
    return out


def _row_partner(row):
    if not row:
        return None
    keys = row.keys()
    return {
        'id': row['id'],
        'name': row['name'],
        'aliases': json.loads(row['aliases_json'] or '[]'),
        'exclude_words': json.loads(row['exclude_words_json'] or '[]'),
        'monitor_keywords': json.loads(row['monitor_keywords_json'] or '[]'),
        'industry_cohort': row['industry_cohort'] if 'industry_cohort' in keys else '',
        'priority_tier': row['priority_tier'] if 'priority_tier' in keys else 'P1',
        'priority_source': row['priority_source'] if 'priority_source' in keys else 'auto',
        'priority_updated_at': row['priority_updated_at'] if 'priority_updated_at' in keys else '',
        'priority_reason': row['priority_reason'] if 'priority_reason' in keys else '',
        'source_timeouts': _parse_source_timeouts(row),
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


def _partner_default_task_map(conn):
    rows = conn.execute(
        """
        SELECT partner_id, task_id FROM (
            SELECT mtp.partner_id, t.id AS task_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY mtp.partner_id
                       ORDER BY t.updated_at DESC, t.id DESC
                   ) AS rn
            FROM monitor_task_partners mtp
            INNER JOIN monitor_tasks t ON t.id = mtp.task_id
        ) WHERE rn = 1
        """,
    ).fetchall()
    return {int(row['partner_id']): int(row['task_id']) for row in rows}


def _partner_intel_count_map(conn):
    out = {}
    for row in conn.execute(
        """
        SELECT partner_id,
               COUNT(*) AS intel_total,
               SUM(CASE WHEN relevance IN ('medium', 'high') THEN 1 ELSE 0 END) AS intel_medium_plus
        FROM intel_records
        WHERE is_duplicate = 0 AND partner_id IS NOT NULL
        GROUP BY partner_id
        """,
    ).fetchall():
        out[int(row['partner_id'])] = {
            'intel_total': int(row['intel_total']),
            'intel_medium_plus': int(row['intel_medium_plus']),
        }
    return out


def _partner_raw_total_map(conn, default_map):
    if not default_map:
        return {}
    out = {}
    for partner_id, task_id in default_map.items():
        cnt = conn.execute(
            'SELECT COUNT(*) FROM raw_records WHERE task_id = ? AND partner_id = ?',
            (task_id, partner_id),
        ).fetchone()[0]
        out[partner_id] = int(cnt)
    return out


def list_partners_with_stats(enabled_only=False):
    partners = list_partners(enabled_only=enabled_only)
    if not partners:
        return []
    conn = get_connection()
    default_map = _partner_default_task_map(conn)
    intel_map = _partner_intel_count_map(conn)
    raw_map = _partner_raw_total_map(conn, default_map)
    result = []
    for p in partners:
        pid = p['id']
        ist = intel_map.get(pid, {'intel_total': 0, 'intel_medium_plus': 0})
        dtid = default_map.get(pid)
        row = dict(p)
        row['stats'] = {
            'default_task_id': dtid,
            'intel_total': ist['intel_total'],
            'intel_medium_plus': ist['intel_medium_plus'],
            'raw_total': raw_map.get(pid, 0),
        }
        result.append(row)
    return result


def get_partner(partner_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM partners WHERE id = ?', (partner_id,)).fetchone()
    return _row_partner(row)


def get_partner_drilldown_context(partner_id):
    """合作方详情钻取：关联任务列表、默认 task_id、情报/源数据计数。"""
    if not get_partner(partner_id):
        return None
    conn = get_connection()
    task_rows = conn.execute(
        """
        SELECT t.id, t.name, t.updated_at
        FROM monitor_tasks t
        INNER JOIN monitor_task_partners mtp ON mtp.task_id = t.id
        WHERE mtp.partner_id = ?
        ORDER BY t.updated_at DESC, t.id DESC
        """,
        (partner_id,),
    ).fetchall()
    tasks = [
        {'id': row['id'], 'name': row['name'] or '', 'updated_at': row['updated_at']}
        for row in task_rows
    ]
    default_task_id = tasks[0]['id'] if tasks else None
    intel_total = conn.execute(
        'SELECT COUNT(*) FROM intel_records WHERE partner_id = ? AND is_duplicate = 0',
        (partner_id,),
    ).fetchone()[0]
    intel_medium_plus = conn.execute(
        """
        SELECT COUNT(*) FROM intel_records
        WHERE partner_id = ? AND is_duplicate = 0 AND relevance IN ('medium', 'high')
        """,
        (partner_id,),
    ).fetchone()[0]
    raw_total = 0
    if default_task_id is not None:
        raw_total = conn.execute(
            'SELECT COUNT(*) FROM raw_records WHERE task_id = ? AND partner_id = ?',
            (default_task_id, partner_id),
        ).fetchone()[0]
    return {
        'partner_id': partner_id,
        'default_task_id': default_task_id,
        'tasks': tasks,
        'counts': {
            'intel_total': intel_total,
            'intel_medium_plus': intel_medium_plus,
            'raw_total': raw_total,
        },
    }


def create_partner(data):
    now = _utc_now()
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO partners(name, aliases_json, exclude_words_json, monitor_keywords_json,
                             industry_cohort, priority_tier, priority_source, priority_updated_at,
                             priority_reason, source_timeouts_json, enabled, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data['name'],
            json.dumps(data.get('aliases') or [], ensure_ascii=False),
            json.dumps(data.get('exclude_words') or [], ensure_ascii=False),
            json.dumps(data.get('monitor_keywords') or [], ensure_ascii=False),
            data.get('industry_cohort') or '',
            data.get('priority_tier') or 'P1',
            data.get('priority_source') or 'auto',
            now if data.get('priority_tier') else '',
            data.get('priority_reason') or '',
            json.dumps(data.get('source_timeouts') or {}, ensure_ascii=False),
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
                            industry_cohort=?, priority_tier=?, priority_source=?,
                            priority_updated_at=?, priority_reason=?, source_timeouts_json=?,
                            enabled=?, notes=?, updated_at=?
        WHERE id=?
        """,
        (
            data.get('name', existing['name']),
            json.dumps(data.get('aliases', existing['aliases']), ensure_ascii=False),
            json.dumps(data.get('exclude_words', existing['exclude_words']), ensure_ascii=False),
            json.dumps(data.get('monitor_keywords', existing['monitor_keywords']), ensure_ascii=False),
            data.get('industry_cohort', existing.get('industry_cohort') or ''),
            data.get('priority_tier', existing.get('priority_tier') or 'P1'),
            data.get('priority_source', existing.get('priority_source') or 'auto'),
            data.get('priority_updated_at', existing.get('priority_updated_at') or ''),
            data.get('priority_reason', existing.get('priority_reason') or ''),
            json.dumps(
                data.get('source_timeouts', existing.get('source_timeouts') or {}),
                ensure_ascii=False,
            ),
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
    business_spec = {}
    if 'business_spec_json' in keys:
        try:
            business_spec = json.loads(row['business_spec_json'] or '{}')
        except Exception:
            business_spec = {}
    return {
        'id': row['id'],
        'name': row['name'] or '',
        'status': row['status'],
        'sources': sources if sources is not None else json.loads(row['sources_json'] or '[]'),
        'partner_ids': partner_ids if partner_ids is not None else [],
        'max_pages': row['max_pages'],
        'fetch_detail': bool(row['fetch_detail']),
        'crawl_mode': row['crawl_mode'] if 'crawl_mode' in keys else 'legacy',
        'business_spec': business_spec if isinstance(business_spec, dict) else {},
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
    crawl_mode = data.get('crawl_mode') or cfg('monitor', 'crawl_mode', default='list_first')
    business_spec = data.get('business_spec') if isinstance(data.get('business_spec'), dict) else {}
    cur = conn.execute(
        """
        INSERT INTO monitor_tasks(name, status, sources_json, max_pages, fetch_detail,
                                  crawl_mode, business_spec_json,
                                  progress_json, created_at, updated_at)
        VALUES (?, 'queued', ?, ?, ?, ?, ?, '{}', ?, ?)
        """,
        (
            data.get('name') or ('监测任务 %s' % now[:16]),
            json.dumps(sources, ensure_ascii=False),
            int(data.get('max_pages') or cfg('monitor', 'default_max_pages', default=2)),
            1 if data.get('fetch_detail', False) else 0,
            crawl_mode,
            json.dumps(business_spec, ensure_ascii=False),
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
        'triage_duration_ms': _json_col('stats_json').get('triage_duration_ms', 0),
        'investigation_crawl_duration_ms': _json_col('stats_json').get(
            'investigation_crawl_duration_ms', 0,
        ),
        'timing_by_source': _json_col('timing_by_source_json'),
        'token_usage': _json_col('token_usage_json'),
        'stats': _json_col('stats_json'),
        'error_message': row['error_message'] or '',
        'stop_requested': bool(row['stop_requested']) if 'stop_requested' in keys else False,
        'pause_requested': bool(row['pause_requested']) if 'pause_requested' in keys else False,
        'source_halt': _json_col('source_halt_json') if 'source_halt_json' in keys else {},
        'worker_state': _json_col('worker_state_json') if 'worker_state_json' in keys else {},
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
    if row and status in ('done', 'failed', 'skipped_overlap', 'paused', 'stopped'):
        conn.execute(
            'UPDATE monitor_tasks SET last_run_id=? WHERE id=?',
            (run_id, row['task_id']),
        )
    conn.commit()
    return get_task_run(run_id)


def _parse_utc_iso(value):
    from datetime import datetime, timezone
    t = str(value or '').strip()
    if not t:
        return None
    if t.endswith('Z'):
        t = t[:-1] + '+00:00'
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def reclaim_stale_task_runs(max_age_sec=None):
    """将超时仍为 running 的 Run 标记为 failed，避免阻塞 can_run。"""
    from config import cfg
    from datetime import datetime, timezone, timedelta

    if max_age_sec is None:
        timeout_cfg = int(cfg('monitor', 'task_timeout_sec') or 7200)
        if timeout_cfg <= 0:
            return 0
        max_age_sec = timeout_cfg + 600
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_sec)
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, task_id, started_at FROM monitor_task_runs
        WHERE status='running' AND (finished_at IS NULL OR finished_at='')
        """
    ).fetchall()
    reclaimed = 0
    for row in rows:
        started = _parse_utc_iso(row['started_at'])
        if started is None or started < cutoff:
            finish_task_run(
                row['id'],
                'failed',
                error_message='stale run reclaimed（进程异常退出或未正常结束）',
            )
            reclaimed += 1
    return reclaimed


def reclaim_orphaned_task_runs():
    """任务已非运行态但 run 仍为 running（重启/停止后未收尾）时立即 failed。"""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT r.id, r.task_id, r.stop_requested, r.pause_requested, t.status AS task_status
        FROM monitor_task_runs r
        JOIN monitor_tasks t ON t.id = r.task_id
        WHERE r.status = 'running'
          AND (r.finished_at IS NULL OR r.finished_at = '')
        """
    ).fetchall()
    reclaimed = 0
    for row in rows:
        stopped = bool(row['stop_requested'])
        paused = bool(row['pause_requested']) if 'pause_requested' in row.keys() else False
        task_status = row['task_status'] or ''
        orphan = task_status not in ('crawling', 'analyzing')
        if not (stopped or paused or orphan):
            continue
        if stopped:
            run_status, msg = 'stopped', '用户终止'
        elif paused:
            run_status, msg = 'paused', '任务已暂停'
        else:
            run_status, msg = 'failed', 'Run 已自动收尾（任务不在运行中）'
        finish_task_run(row['id'], run_status, error_message=msg)
        reclaimed += 1
    return reclaimed


def reclaim_zombie_task_runs(grace_sec=120):
    """
    本进程无活跃 monitor 线程时，将 started_at 超过 grace 的 running run 收尾。
    用于服务重启后解除 can_run 阻塞。
    """
    try:
        from crawler_web import S
        if getattr(S, 'running', False):
            return 0
    except Exception:
        pass

    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(30, int(grace_sec or 120)))
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id FROM monitor_task_runs
        WHERE status='running' AND (finished_at IS NULL OR finished_at='')
        """
    ).fetchall()
    reclaimed = 0
    for row in rows:
        started_row = conn.execute(
            'SELECT started_at FROM monitor_task_runs WHERE id=?', (row['id'],),
        ).fetchone()
        started = _parse_utc_iso(started_row['started_at'] if started_row else None)
        if started is None or started < cutoff:
            finish_task_run(
                row['id'],
                'failed',
                error_message='进程重启后 Run 已自动收尾',
            )
            _sync_task_after_zombie_reclaim(conn, row['id'])
            reclaimed += 1
    return reclaimed


def _sync_task_after_zombie_reclaim(conn, run_id):
    """僵尸 run 收尾后，若任务仍卡在 crawling/analyzing，重置为 queued 以便再次执行。"""
    row = conn.execute(
        """
        SELECT t.id, t.status FROM monitor_tasks t
        JOIN monitor_task_runs r ON r.task_id = t.id
        WHERE r.id=?
        """,
        (run_id,),
    ).fetchone()
    if not row:
        return
    if row['status'] in ('crawling', 'analyzing'):
        now = _utc_now()
        conn.execute(
            """
            UPDATE monitor_tasks
            SET status='queued', error_message='', updated_at=?, progress_json='{}'
            WHERE id=?
            """,
            (now, row['id']),
        )
        conn.commit()


def is_run_pause_requested(run_id):
    with _db_lock:
        conn = get_connection()
        row = conn.execute(
            'SELECT pause_requested FROM monitor_task_runs WHERE id=?', (run_id,),
        ).fetchone()
    if not row:
        return False
    keys = row.keys()
    if 'pause_requested' not in keys:
        return False
    return bool(row['pause_requested'])


def set_run_pause_requested(run_id, value=True):
    with _db_lock:
        conn = get_connection()
        conn.execute(
            'UPDATE monitor_task_runs SET pause_requested=? WHERE id=?',
            (1 if value else 0, run_id),
        )
        conn.commit()


def clear_run_halt_flags(run_id):
    conn = get_connection()
    conn.execute(
        """
        UPDATE monitor_task_runs
        SET stop_requested=0, pause_requested=0, source_halt_json='{}'
        WHERE id=?
        """,
        (run_id,),
    )
    conn.commit()


def get_source_halt_map(run_id):
    with _db_lock:
        conn = get_connection()
        row = conn.execute(
            'SELECT source_halt_json FROM monitor_task_runs WHERE id=?', (run_id,),
        ).fetchone()
    if not row or 'source_halt_json' not in row.keys():
        return {}
    try:
        raw = json.loads(row['source_halt_json'] or '{}')
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def set_source_halt(run_id, source_id, kind):
    """kind: 'pause' | 'stop'。"""
    if not source_id or kind not in ('pause', 'stop'):
        return
    with _db_lock:
        halts = get_source_halt_map(run_id)
        halts[str(source_id)] = kind
        conn = get_connection()
        conn.execute(
            'UPDATE monitor_task_runs SET source_halt_json=? WHERE id=?',
            (json.dumps(halts, ensure_ascii=False), run_id),
        )
        conn.commit()


def clear_source_halt(run_id, source_id=None):
    halts = get_source_halt_map(run_id)
    if not halts:
        return
    if source_id:
        halts.pop(str(source_id), None)
    else:
        halts = {}
    with _db_lock:
        conn = get_connection()
        conn.execute(
            'UPDATE monitor_task_runs SET source_halt_json=? WHERE id=?',
            (json.dumps(halts, ensure_ascii=False), run_id),
        )
        conn.commit()


def count_incomplete_work(task_id, run_id=None):
    """未完成子任务总数：keyword + 队列项。"""
    from intel.crawl_queue import count_incomplete_queue_by_source

    kw = count_incomplete_keyword_runs(task_id, run_id=run_id) if run_id else 0
    queue = sum(count_incomplete_queue_by_source(run_id).values()) if run_id else 0
    return int(kw) + int(queue)


def find_resumable_run_id(task_id, task=None):
    """返回仍有未完成子任务的 Run id（优先 progress.resume_run_id）。"""
    if task is None:
        task = get_monitor_task(task_id)
    if not task:
        return None
    progress = task.get('progress') or {}
    candidates = []
    rid = progress.get('resume_run_id')
    if rid:
        candidates.append(int(rid))
    last_rid = task.get('last_run_id')
    if last_rid:
        last_rid = int(last_rid)
        if last_rid not in candidates:
            candidates.append(last_rid)
    conn = get_connection()
    rows = conn.execute(
        'SELECT id FROM monitor_task_runs WHERE task_id=? ORDER BY id DESC LIMIT 30',
        (task_id,),
    ).fetchall()
    for row in rows:
        run_id = int(row['id'])
        if run_id not in candidates:
            candidates.append(run_id)
    for run_id in candidates:
        if count_incomplete_work(task_id, run_id=run_id) > 0:
            return run_id
    return progress.get('resume_run_id') or task.get('last_run_id')


def aggregate_subtask_timing_by_source(run_id):
    """从 keyword / 队列子任务 phase_timing_ms 汇总 per-source timing。"""
    from intel.crawl_queue import list_queue_items_for_run

    run_row = get_task_run(run_id)
    task = get_monitor_task(run_row['task_id']) if run_row else None
    source_ids = list((task or {}).get('sources') or [])
    by_source = {}

    def _add(source_id, phase_timing):
        sid = (source_id or '').strip()
        if not sid:
            return
        bucket = by_source.setdefault(sid, {
            'crawl_ms': 0,
            'investigation_crawl_ms': 0,
            'analyze_ms': 0,
            'raw_new': 0,
            'intel_written': 0,
        })
        pt = phase_timing or {}
        bucket['crawl_ms'] += int(pt.get('list_crawl_ms') or 0)
        bucket['investigation_crawl_ms'] += int(pt.get('investigation_ms') or 0)
        bucket['analyze_ms'] += int(pt.get('analyze_ms') or 0)

    for kw in list_keyword_runs(run_id=run_id):
        if kw.get('source_id') and kw['source_id'] not in source_ids:
            source_ids.append(kw['source_id'])
        _add(kw.get('source_id'), _keyword_phase_timing(kw))
        stats = kw.get('stats') or {}
        if stats.get('list_count'):
            by_source.setdefault(kw.get('source_id') or 'xhs', {})['raw_new'] = (
                by_source.get(kw.get('source_id') or 'xhs', {}).get('raw_new', 0)
                + int(stats.get('list_count') or 0)
            )

    for sid in source_ids:
        for q in list_queue_items_for_run(run_id, sid):
            elapsed_ms = 0
            if q.get('status') == 'claimed' and q.get('claimed_at'):
                elapsed_ms = _elapsed_ms_since(q['claimed_at'])
            _add(sid, _queue_item_phase_timing(q, elapsed_ms=elapsed_ms))

    return by_source


def merge_run_metrics_from_subtasks(run_id, run_metrics):
    """用子任务 phase_timing 补全 RunMetrics 中缺失的 timing。"""
    if not run_id:
        return run_metrics
    by_source = aggregate_subtask_timing_by_source(run_id)
    if not by_source:
        return run_metrics
    if run_metrics is None:
        from intel.run_metrics import RunMetrics
        run_metrics = RunMetrics()

    crawl_total = 0
    investigation_total = 0
    analyze_total = 0
    for sid, bucket in by_source.items():
        crawl_total += int(bucket.get('crawl_ms') or 0)
        investigation_total += int(bucket.get('investigation_crawl_ms') or 0)
        analyze_total += int(bucket.get('analyze_ms') or 0)
        existing = run_metrics.timing_by_source.get(sid) or {}
        run_metrics.timing_by_source[sid] = {
            'crawl_ms': max(int(existing.get('crawl_ms') or 0), int(bucket.get('crawl_ms') or 0)),
            'investigation_crawl_ms': max(
                int(existing.get('investigation_crawl_ms') or 0),
                int(bucket.get('investigation_crawl_ms') or 0),
            ),
            'analyze_ms': max(int(existing.get('analyze_ms') or 0), int(bucket.get('analyze_ms') or 0)),
            'raw_new': max(int(existing.get('raw_new') or 0), int(bucket.get('raw_new') or 0)),
            'raw_updated': int(existing.get('raw_updated') or 0),
            'intel_written': max(int(existing.get('intel_written') or 0), int(bucket.get('intel_written') or 0)),
        }
    if run_metrics.crawl_duration_ms <= 0 and crawl_total > 0:
        run_metrics.crawl_duration_ms = crawl_total
    if run_metrics.investigation_crawl_duration_ms <= 0 and investigation_total > 0:
        run_metrics.investigation_crawl_duration_ms = investigation_total
    if run_metrics.analyze_duration_ms <= 0 and analyze_total > 0:
        run_metrics.analyze_duration_ms = analyze_total
    return run_metrics


def _timing_from_subtasks_or_run(run_id, run_timing=None):
    """优先使用 Run 记录 timing；缺失时从子任务汇总。"""
    if isinstance(run_timing, dict) and run_timing:
        has_data = any(
            int((bucket or {}).get('crawl_ms') or 0)
            + int((bucket or {}).get('investigation_crawl_ms') or 0)
            + int((bucket or {}).get('analyze_ms') or 0)
            for bucket in run_timing.values()
        )
        if has_data:
            return run_timing
    rebuilt = aggregate_subtask_timing_by_source(run_id)
    if not rebuilt:
        return run_timing if isinstance(run_timing, dict) else {}
    merged = dict(run_timing or {}) if isinstance(run_timing, dict) else {}
    for sid, bucket in rebuilt.items():
        existing = merged.get(sid) or {}
        merged[sid] = {
            'crawl_ms': max(int(existing.get('crawl_ms') or 0), int(bucket.get('crawl_ms') or 0)),
            'investigation_crawl_ms': max(
                int(existing.get('investigation_crawl_ms') or 0),
                int(bucket.get('investigation_crawl_ms') or 0),
            ),
            'analyze_ms': max(int(existing.get('analyze_ms') or 0), int(bucket.get('analyze_ms') or 0)),
            'raw_new': max(int(existing.get('raw_new') or 0), int(bucket.get('raw_new') or 0)),
            'intel_written': max(int(existing.get('intel_written') or 0), int(bucket.get('intel_written') or 0)),
        }
    return merged


def get_source_halt_kind(run_id, source_id):
    if not run_id or not source_id:
        return ''
    halts = get_source_halt_map(run_id)
    return halts.get(str(source_id)) or ''


def list_resume_sources(task_id, run_id, task=None):
    """返回继续执行时需跑的数据源列表。"""
    from intel.crawl_queue import count_incomplete_queue_by_source

    if task is None:
        task = get_monitor_task(task_id)
    sources = list((task or {}).get('sources') or [])
    out = []
    if count_incomplete_keyword_runs(task_id, run_id=run_id) > 0 and 'xhs' in sources:
        out.append('xhs')
    queue_by_source = count_incomplete_queue_by_source(run_id) if run_id else {}
    for sid in sources:
        if sid == 'xhs' and sid in out:
            continue
        if queue_by_source.get(sid, 0) > 0:
            out.append(sid)
    return out


def reset_interrupted_keyword_runs_for_source(run_id, source_id):
    conn = get_connection()
    conn.execute(
        """
        UPDATE monitor_keyword_runs
        SET status='pending', phase='pending', error_message='', finished_at=NULL
        WHERE run_id=? AND source_id=? AND status='running'
        """,
        (run_id, source_id),
    )
    conn.commit()


def get_active_run_for_task(task_id):
    with _db_lock:
        conn = get_connection()
        row = conn.execute(
            """
            SELECT id FROM monitor_task_runs
            WHERE task_id=? AND status='running'
              AND (finished_at IS NULL OR finished_at='')
            ORDER BY id DESC LIMIT 1
            """,
            (task_id,),
        ).fetchone()
    return row['id'] if row else None


def resolve_active_run_id(task_id, task=None):
    """解析任务当前 Run：优先 running 记录，其次 progress/last_run。"""
    run_id = get_active_run_for_task(task_id)
    if run_id:
        return int(run_id)
    if task is None:
        task = get_monitor_task(task_id)
    if not task:
        return None
    progress = task.get('progress') or {}
    for key in ('run_id', 'resume_run_id'):
        val = progress.get(key)
        if val:
            try:
                return int(val)
            except (TypeError, ValueError):
                pass
    if task.get('last_run_id'):
        try:
            return int(task['last_run_id'])
        except (TypeError, ValueError):
            pass
    return None


def reset_interrupted_keyword_runs(run_id):
    """暂停/终止时：运行中的 keyword 子任务回退为 pending，已完成保持 done。"""
    conn = get_connection()
    now = _utc_now()
    conn.execute(
        """
        UPDATE monitor_keyword_runs
        SET status='pending', phase='pending', error_message='', finished_at=NULL
        WHERE run_id=? AND status='running'
        """,
        (run_id,),
    )
    conn.commit()


def cancel_incomplete_keyword_runs(run_id, reason='用户终止'):
    """终止时：取消尚未完成的 keyword 子任务，避免「继续」误恢复。"""
    conn = get_connection()
    now = _utc_now()
    msg = (reason or '用户终止')[:500]
    conn.execute(
        """
        UPDATE monitor_keyword_runs
        SET status='skipped', phase='cancelled', error_message=?, finished_at=?
        WHERE run_id=? AND status IN ('pending', 'running')
        """,
        (msg, now, run_id),
    )
    conn.commit()


def list_incomplete_keyword_runs(task_id, run_id=None):
    conn = get_connection()
    sql = """
        SELECT * FROM monitor_keyword_runs
        WHERE task_id=? AND status IN ('pending', 'failed', 'running')
    """
    params = [task_id]
    if run_id is not None:
        sql += ' AND run_id=?'
        params.append(run_id)
    sql += ' ORDER BY id ASC'
    return [_row_keyword_run(r) for r in conn.execute(sql, params).fetchall()]


def count_incomplete_keyword_runs(task_id, run_id=None):
    conn = get_connection()
    sql = """
        SELECT COUNT(*) AS cnt FROM monitor_keyword_runs
        WHERE task_id=? AND status IN ('pending', 'failed', 'running')
    """
    params = [task_id]
    if run_id is not None:
        sql += ' AND run_id=?'
        params.append(run_id)
    row = conn.execute(sql, params).fetchone()
    return int(row['cnt']) if row else 0


def is_run_stop_requested(run_id):
    with _db_lock:
        conn = get_connection()
        row = conn.execute(
            'SELECT stop_requested FROM monitor_task_runs WHERE id=?', (run_id,),
        ).fetchone()
    if not row:
        return False
    keys = row.keys()
    if 'stop_requested' not in keys:
        return False
    return bool(row['stop_requested'])


def mark_active_runs_stop_requested():
    with _db_lock:
        conn = get_connection()
        conn.execute(
            """
            UPDATE monitor_task_runs SET stop_requested=1
            WHERE status='running' AND (finished_at IS NULL OR finished_at = '')
            """
        )
        conn.commit()


def set_run_stop_requested(run_id, value=True):
    with _db_lock:
        conn = get_connection()
        conn.execute(
            'UPDATE monitor_task_runs SET stop_requested=? WHERE id=?',
            (1 if value else 0, run_id),
        )
        conn.commit()


def append_run_log(run_id, message, level='INFO', worker_instance_id=''):
    if run_id is None:
        return
    try:
        run_id = int(run_id)
    except (TypeError, ValueError):
        return
    now = _utc_now()
    with _db_lock:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO monitor_run_logs(run_id, worker_instance_id, level, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, worker_instance_id or '', level, message or '', now),
        )
        conn.commit()


def list_run_logs(run_id, limit=500):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT * FROM monitor_run_logs WHERE run_id=?
        ORDER BY id ASC LIMIT ?
        """,
        (run_id, int(limit)),
    ).fetchall()
    out = []
    for row in rows:
        keys = row.keys()
        out.append({
            'id': row['id'],
            'run_id': row['run_id'],
            'worker_instance_id': row['worker_instance_id'] if 'worker_instance_id' in keys else '',
            'level': row['level'],
            'message': row['message'],
            'created_at': row['created_at'],
        })
    return out


def update_run_worker_state(run_id, patch):
    with _db_lock:
        conn = get_connection()
        row = conn.execute(
            'SELECT worker_state_json FROM monitor_task_runs WHERE id=?', (run_id,),
        ).fetchone()
        if not row:
            return
        try:
            state = json.loads(row['worker_state_json'] or '{}')
        except Exception:
            state = {}
        if not isinstance(state, dict):
            state = {}
        state.update(patch or {})
        conn.execute(
            'UPDATE monitor_task_runs SET worker_state_json=? WHERE id=?',
            (json.dumps(state, ensure_ascii=False), run_id),
        )
        conn.commit()


def get_task_run(run_id):
    if run_id is None:
        return None
    try:
        run_id = int(run_id)
    except (TypeError, ValueError):
        return None
    with _db_lock:
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


def _row_keyword_run(row):
    if not row:
        return None
    keys = row.keys()
    try:
        stats = json.loads(row['stats_json'] or '{}')
    except Exception:
        stats = {}
    return {
        'id': row['id'],
        'run_id': row['run_id'],
        'task_id': row['task_id'],
        'source_id': row['source_id'],
        'keyword': row['keyword'],
        'cohort': row['cohort'] or '',
        'status': row['status'],
        'phase': row['phase'] or '',
        'started_at': row['started_at'],
        'finished_at': row['finished_at'],
        'error_message': row['error_message'] or '',
        'timeout_sec': int(row['timeout_sec']) if 'timeout_sec' in keys and row['timeout_sec'] else 0,
        'account_id': stats.get('account_id') or '',
        'account_label': stats.get('account_label') or '',
        'stats': stats,
    }


def create_keyword_run(run_id, task_id, source_id, keyword, cohort='', timeout_sec=0):
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO monitor_keyword_runs(
            run_id, task_id, source_id, keyword, cohort, status, phase, timeout_sec
        ) VALUES (?, ?, ?, ?, ?, 'pending', 'pending', ?)
        """,
        (run_id, task_id, source_id, keyword, cohort or '', int(timeout_sec or 0)),
    )
    conn.commit()
    return cur.lastrowid


def get_keyword_run(keyword_run_id):
    conn = get_connection()
    row = conn.execute(
        'SELECT * FROM monitor_keyword_runs WHERE id=?', (keyword_run_id,),
    ).fetchone()
    return _row_keyword_run(row)


def list_keyword_runs(run_id=None, task_id=None, status=None):
    conn = get_connection()
    sql = 'SELECT * FROM monitor_keyword_runs WHERE 1=1'
    params = []
    if run_id is not None:
        sql += ' AND run_id=?'
        params.append(run_id)
    if task_id is not None:
        sql += ' AND task_id=?'
        params.append(task_id)
    if status is not None:
        sql += ' AND status=?'
        params.append(status)
    sql += ' ORDER BY id ASC'
    return [_row_keyword_run(r) for r in conn.execute(sql, params).fetchall()]


def keyword_run_counts(run_id, source_id=None):
    conn = get_connection()
    sql = """
        SELECT status, COUNT(*) AS cnt FROM monitor_keyword_runs
        WHERE run_id=?
    """
    params = [run_id]
    if source_id:
        sql += ' AND source_id=?'
        params.append(source_id)
    sql += ' GROUP BY status'
    rows = conn.execute(sql, params).fetchall()
    counts = {'pending': 0, 'running': 0, 'done': 0, 'failed': 0, 'skipped': 0, 'total': 0}
    for row in rows:
        st = row['status'] or 'pending'
        counts[st] = int(row['cnt'])
        counts['total'] += int(row['cnt'])
    return counts


def keyword_run_counts_by_source(run_id):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT source_id, status, COUNT(*) AS cnt FROM monitor_keyword_runs
        WHERE run_id=? GROUP BY source_id, status
        """,
        (run_id,),
    ).fetchall()
    out = {}
    for row in rows:
        sid = row['source_id'] or ''
        out.setdefault(sid, {'pending': 0, 'running': 0, 'done': 0, 'failed': 0, 'skipped': 0, 'total': 0})
        st = row['status'] or 'pending'
        out[sid][st] = int(row['cnt'])
        out[sid]['total'] += int(row['cnt'])
    return out


def update_keyword_run(keyword_run_id, **fields):
    conn = get_connection()
    allowed = {
        'status', 'phase', 'started_at', 'finished_at', 'error_message', 'stats_json',
    }
    sets = []
    vals = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == 'stats_json' and isinstance(v, dict):
            v = json.dumps(v, ensure_ascii=False)
        sets.append('%s=?' % k)
        vals.append(v)
    if not sets:
        return get_keyword_run(keyword_run_id)
    vals.append(keyword_run_id)
    conn.execute(
        'UPDATE monitor_keyword_runs SET %s WHERE id=?' % ', '.join(sets),
        vals,
    )
    conn.commit()
    return get_keyword_run(keyword_run_id)


def _elapsed_ms_since(iso_ts):
    from datetime import datetime, timezone

    dt = _parse_utc_iso(iso_ts)
    if not dt:
        return 0
    return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() * 1000))


def _active_source_work(run_id, source_id):
    """当前正在执行的子任务（keyword 或队列项）及阶段用时。"""
    conn = get_connection()
    kw = conn.execute(
        """
        SELECT keyword, phase, started_at FROM monitor_keyword_runs
        WHERE run_id=? AND source_id=? AND status='running'
        ORDER BY id DESC LIMIT 1
        """,
        (run_id, source_id),
    ).fetchone()
    if kw:
        return {
            'kind': 'keyword',
            'phase': kw['phase'] or 'list',
            'label': (kw['keyword'] or '')[:40],
            'elapsed_ms': _elapsed_ms_since(kw['started_at']),
        }
    q = conn.execute(
        """
        SELECT phase, payload_json, claimed_at FROM crawl_work_queue
        WHERE run_id=? AND source_id=? AND status='claimed'
        ORDER BY claimed_at DESC LIMIT 1
        """,
        (run_id, source_id),
    ).fetchone()
    if q:
        label = ''
        try:
            payload = json.loads(q['payload_json'] or '{}')
            label = (payload.get('keyword') or payload.get('partner_id') or '')[:40]
        except Exception:
            label = ''
        return {
            'kind': 'queue',
            'phase': q['phase'] or 'crawl',
            'label': str(label) if label else '',
            'elapsed_ms': _elapsed_ms_since(q['claimed_at']),
        }
    return None


def _keyword_phase_summary(run_id, source_id):
    """按 keyword 阶段统计数量与已完成总耗时。"""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT phase, status, COUNT(*) AS cnt
        FROM monitor_keyword_runs
        WHERE run_id=? AND source_id=?
        GROUP BY phase, status
        """,
        (run_id, source_id),
    ).fetchall()
    by_phase = {}
    done_total_ms = 0
    for row in rows:
        phase = row['phase'] or 'pending'
        st = row['status'] or 'pending'
        cnt = int(row['cnt'] or 0)
        bucket = by_phase.setdefault(phase, {'pending': 0, 'running': 0, 'done': 0, 'failed': 0, 'skipped': 0})
        if st in bucket:
            bucket[st] += cnt
        else:
            bucket[st] = bucket.get(st, 0) + cnt
    done_rows = conn.execute(
        """
        SELECT started_at, finished_at FROM monitor_keyword_runs
        WHERE run_id=? AND source_id=? AND status='done'
          AND started_at IS NOT NULL AND started_at != ''
          AND finished_at IS NOT NULL AND finished_at != ''
        """,
        (run_id, source_id),
    ).fetchall()
    for row in done_rows:
        s = _parse_utc_iso(row['started_at'])
        f = _parse_utc_iso(row['finished_at'])
        if s and f:
            done_total_ms += max(0, int((f - s).total_seconds() * 1000))
    return {'by_phase': by_phase, 'done_total_ms': done_total_ms}


def resolve_subtask_detail_status(
    source_id,
    run_status=None,
    run_phase=None,
    queue_status=None,
    queue_phase=None,
):
    """
    统一子任务展示状态：queued | list_crawl | investigation | analyze | done | failed | skipped。
    返回 (code, label)。
    """
    rs = (run_status or 'pending').strip().lower()
    rp = (run_phase or 'pending').strip().lower()
    qs = (queue_status or '').strip().lower() if queue_status else ''
    qp = (queue_phase or '').strip().lower() if queue_phase else ''

    if rs == 'failed' or qs == 'failed':
        return 'failed', '失败'
    if rs == 'skipped' or qs == 'skipped':
        return 'skipped', '已跳过'
    if qs == 'skipped' and rs in ('pending', 'running', ''):
        return 'skipped', '已跳过'
    if rs == 'done' or (qs == 'done' and rs in ('done', 'pending', '')):
        return 'done', '完成'

    active = rs == 'running' or qs == 'claimed'
    if active:
        phase = rp if rs == 'running' else (qp or rp)
        if phase == 'list':
            return 'list_crawl', '爬取列表'
        if phase == 'triage':
            return 'analyze', '分析'
        if phase == 'investigation':
            return 'investigation', '勘察详情'
        if phase == 'analyze':
            return 'analyze', '分析'
        if phase in ('legacy_crawl', 'list_crawl', 'keyword_pipeline', 'crawl'):
            return 'list_crawl', '爬取列表'
        return 'list_crawl', '爬取列表'

    return 'queued', '排队'


def _queue_item_phase_timing(item, elapsed_ms=0):
    """从队列项 payload 或当前执行阶段推断三阶段用时。"""
    payload = (item or {}).get('payload') or {}
    raw = payload.get('_phase_timing_ms') if isinstance(payload, dict) else None
    if isinstance(raw, dict):
        return {
            'list_crawl_ms': int(raw.get('list_crawl_ms') or 0),
            'analyze_ms': int(raw.get('analyze_ms') or 0),
            'investigation_ms': int(raw.get('investigation_ms') or 0),
        }
    phase = (item or {}).get('phase') or ''
    status = (item or {}).get('status') or ''
    timing = {'list_crawl_ms': 0, 'analyze_ms': 0, 'investigation_ms': 0}
    if status == 'claimed' and elapsed_ms > 0:
        if phase in ('legacy_crawl', 'list_crawl', 'keyword_pipeline'):
            timing['list_crawl_ms'] = int(elapsed_ms)
        elif phase == 'investigation':
            timing['investigation_ms'] = int(elapsed_ms)
    return timing


def _keyword_phase_timing(kw):
    """keyword 子任务三阶段用时（含运行中当前阶段增量）。"""
    stats = (kw or {}).get('stats') or {}
    base = stats.get('phase_timing_ms') if isinstance(stats.get('phase_timing_ms'), dict) else {}
    timing = {
        'list_crawl_ms': int((base or {}).get('list_crawl_ms') or 0),
        'analyze_ms': int((base or {}).get('analyze_ms') or 0),
        'investigation_ms': int((base or {}).get('investigation_ms') or 0),
    }
    if (kw or {}).get('status') != 'running':
        return timing
    phase = (kw or {}).get('phase') or 'list'
    extra = _elapsed_ms_since(stats.get('_phase_started_at') or kw.get('started_at'))
    if phase == 'list':
        timing['list_crawl_ms'] += extra
    elif phase == 'triage':
        timing['analyze_ms'] += extra
    elif phase == 'investigation':
        timing['investigation_ms'] += extra
    return timing


def _queue_item_label(source_id, payload, queue_phase=''):
    payload = payload or {}
    if payload.get('keyword'):
        return str(payload['keyword'])[:80]
    if payload.get('partner_id'):
        partner = get_partner(payload.get('partner_id'))
        if partner:
            return (partner.get('name') or ('合作方#' + str(partner.get('id'))))[:80]
    batch = payload.get('keyword_batch') or {}
    kws = batch.get('keywords') or []
    if kws:
        label = '、'.join(str(k) for k in kws[:3])
        if len(kws) > 3:
            label += '…'
        return label[:80]
    if queue_phase == 'investigation':
        n = len(payload.get('items') or [])
        return '勘察批次(%d)' % n if n else '勘察批次'
    return '子任务#' + str(payload.get('partner_id') or '?')


def build_source_subtask_items(run_id, source_id):
    """合并 keyword 子任务与队列项，输出统一子任务列表。"""
    from intel.crawl_queue import list_queue_items_for_run

    keywords = [k for k in list_keyword_runs(run_id=run_id) if (k.get('source_id') or '') == source_id]
    queue_items = list_queue_items_for_run(run_id, source_id)
    queue_by_kr = {}
    orphan_queues = []
    for q in queue_items:
        kr_id = (q.get('payload') or {}).get('keyword_run_id')
        if kr_id:
            queue_by_kr[int(kr_id)] = q
        else:
            orphan_queues.append(q)

    out = []
    seen_queue_ids = set()

    for kw in keywords:
        q = queue_by_kr.get(kw['id'])
        if q:
            seen_queue_ids.add(q['id'])
        code, label = resolve_subtask_detail_status(
            source_id,
            run_status=kw.get('status'),
            run_phase=kw.get('phase'),
            queue_status=q.get('status') if q else None,
            queue_phase=q.get('phase') if q else None,
        )
        elapsed_ms = 0
        if kw.get('status') == 'running' and kw.get('started_at'):
            elapsed_ms = _elapsed_ms_since(kw['started_at'])
        elif q and q.get('status') == 'claimed' and q.get('claimed_at'):
            elapsed_ms = _elapsed_ms_since(q['claimed_at'])
        phase_timing = _keyword_phase_timing(kw)
        out.append({
            'id': 'kw:%s' % kw['id'],
            'kind': 'keyword',
            'keyword_run_id': kw['id'],
            'queue_id': q['id'] if q else None,
            'label': kw.get('keyword') or '',
            'cohort': kw.get('cohort') or '',
            'account_id': (kw.get('stats') or {}).get('account_id'),
            'account_label': (kw.get('stats') or {}).get('account_label'),
            'detail_status': code,
            'detail_label': label,
            'status': kw.get('status'),
            'phase': kw.get('phase'),
            'elapsed_ms': elapsed_ms,
            'phase_timing_ms': phase_timing,
            'timeout_sec': kw.get('timeout_sec') or 0,
            'stats': kw.get('stats') or {},
            'error_message': kw.get('error_message') or (q.get('error_message') if q else '') or (q.get('skip_reason') if q else ''),
        })

    for q in queue_items:
        if q['id'] in seen_queue_ids:
            continue
        code, status_label = resolve_subtask_detail_status(
            source_id,
            queue_status=q.get('status'),
            queue_phase=q.get('phase'),
        )
        elapsed_ms = 0
        if q.get('status') == 'claimed' and q.get('claimed_at'):
            elapsed_ms = _elapsed_ms_since(q['claimed_at'])
        phase_timing = _queue_item_phase_timing(q, elapsed_ms=elapsed_ms)
        out.append({
            'id': 'q:%s' % q['id'],
            'kind': 'queue',
            'keyword_run_id': None,
            'queue_id': q['id'],
            'label': _queue_item_label(source_id, q.get('payload'), q.get('phase') or ''),
            'cohort': (q.get('payload') or {}).get('cohort') or '',
            'detail_status': code,
            'detail_label': status_label,
            'status': q.get('status'),
            'phase': q.get('phase'),
            'elapsed_ms': elapsed_ms,
            'phase_timing_ms': phase_timing,
            'timeout_sec': 0,
            'stats': {},
            'error_message': q.get('error_message') or q.get('skip_reason') or '',
        })

    return out


def _aggregate_source_subtask_status(queue_counts, keyword_counts, halt_kind):
    if halt_kind == 'pause':
        return 'paused'
    if halt_kind == 'stop':
        return 'stopped'
    qc = queue_counts or {}
    kc = keyword_counts or {}
    if qc.get('claimed', 0) > 0 or kc.get('running', 0) > 0:
        return 'running'
    if qc.get('pending', 0) > 0 or kc.get('pending', 0) > 0:
        return 'pending'
    if qc.get('failed', 0) > 0 or kc.get('failed', 0) > 0:
        return 'failed'
    if (qc.get('total', 0) + kc.get('total', 0)) == 0:
        return 'idle'
    return 'done'


def build_run_subtasks_by_source(run_id, task_sources=None, run_timing=None):
    from intel.crawl_queue import run_queue_counts_by_source

    if run_timing is None:
        run_row = get_task_run(run_id)
        run_timing = (run_row or {}).get('timing_by_source') or {}
    run_timing = _timing_from_subtasks_or_run(run_id, run_timing)
    queue_by_source = run_queue_counts_by_source(run_id)
    keyword_by_source = keyword_run_counts_by_source(run_id)
    halts = get_source_halt_map(run_id)
    source_ids = []
    for sid in (task_sources or []):
        if sid and sid not in source_ids:
            source_ids.append(sid)
    for sid in list(queue_by_source.keys()) + list(keyword_by_source.keys()) + list(halts.keys()):
        if sid and sid not in source_ids:
            source_ids.append(sid)
    out = []
    for sid in source_ids:
        qc = queue_by_source.get(sid) or {
            'pending': 0, 'claimed': 0, 'done': 0, 'failed': 0, 'skipped': 0, 'total': 0,
        }
        kc = keyword_by_source.get(sid) or {
            'pending': 0, 'running': 0, 'done': 0, 'failed': 0, 'skipped': 0, 'total': 0,
        }
        halt = halts.get(sid) or ''
        timing = run_timing.get(sid) if isinstance(run_timing, dict) else {}
        if not isinstance(timing, dict):
            timing = {}
        out.append({
            'source_id': sid,
            'status': _aggregate_source_subtask_status(qc, kc, halt),
            'halt': halt or None,
            'queue': qc,
            'keywords': kc,
            'timing': {
                'crawl_ms': int(timing.get('crawl_ms') or 0),
                'investigation_crawl_ms': int(timing.get('investigation_crawl_ms') or 0),
                'analyze_ms': int(timing.get('analyze_ms') or 0),
                'raw_new': int(timing.get('raw_new') or 0),
                'intel_written': int(timing.get('intel_written') or 0),
            },
            'active_work': _active_source_work(run_id, sid),
            'phase_summary': _keyword_phase_summary(run_id, sid),
            'subtask_items': build_source_subtask_items(run_id, sid),
        })
    return out


def sync_task_subtask_progress(task_id, run_id):
    """将 keyword 子任务汇总写入 monitor_tasks.progress_json。"""
    counts = keyword_run_counts(run_id)
    task = get_monitor_task(task_id) or {}
    sources = task.get('sources') or []
    conn = get_connection()
    row = conn.execute('SELECT progress_json FROM monitor_tasks WHERE id=?', (task_id,)).fetchone()
    try:
        progress = json.loads(row['progress_json'] or '{}') if row else {}
    except Exception:
        progress = {}
    progress['subtasks'] = counts
    progress['sources'] = build_run_subtasks_by_source(run_id, sources)
    progress['run_id'] = run_id
    conn.execute(
        'UPDATE monitor_tasks SET progress_json=?, updated_at=? WHERE id=?',
        (json.dumps(progress, ensure_ascii=False), _utc_now(), task_id),
    )
    conn.commit()


def list_failed_keyword_runs(task_id, run_id=None):
    conn = get_connection()
    if run_id:
        rows = conn.execute(
            """
            SELECT * FROM monitor_keyword_runs
            WHERE task_id=? AND run_id=? AND status='failed'
            ORDER BY id ASC
            """,
            (task_id, run_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM monitor_keyword_runs
            WHERE task_id=? AND status='failed'
            ORDER BY id DESC
            """,
            (task_id,),
        ).fetchall()
    return [_row_keyword_run(r) for r in rows]


def list_raw_records_by_ids(task_id, raw_ids):
    if not raw_ids:
        return []
    conn = get_connection()
    placeholders = ','.join('?' * len(raw_ids))
    rows = conn.execute(
        'SELECT * FROM raw_records WHERE task_id=? AND id IN (%s)' % placeholders,
        [task_id] + list(raw_ids),
    ).fetchall()
    return _rows_to_raw_list(rows)


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
    crawl_mode = data.get('crawl_mode', task.get('crawl_mode') or 'legacy')
    business_spec = task.get('business_spec') or {}
    if 'business_spec' in data and isinstance(data.get('business_spec'), dict):
        business_spec = data['business_spec']
    conn.execute(
        """
        UPDATE monitor_tasks SET name=?, sources_json=?, max_pages=?, fetch_detail=?,
                                 crawl_mode=?, business_spec_json=?,
                                 status='queued', error_message='', updated_at=?,
                                 started_at=NULL, finished_at=NULL, progress_json='{}'
        WHERE id=?
        """,
        (
            data.get('name', task['name']),
            json.dumps(sources, ensure_ascii=False),
            int(data.get('max_pages', task['max_pages'])),
            1 if data.get('fetch_detail', task['fetch_detail']) else 0,
            crawl_mode,
            json.dumps(business_spec, ensure_ascii=False),
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
    if status in ('done', 'failed', 'stopped', 'paused'):
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


def insert_raw_records(
    task_id, partner_id, source, keyword, records, run_metrics=None, crawl_phase='legacy',
):
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
                SET payload_json=?, content_hash=?, updated_at=?, partner_id=?, keyword=?,
                    crawl_phase=?
                WHERE id=?
                """,
                (payload_str, ch, now, partner_id, keyword, crawl_phase, existing['id']),
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
                dedup_key, content_hash, crawl_phase, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, partner_id, source, keyword, payload_str, key, ch, crawl_phase, now, now),
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
    return app_today_start_iso()


def _raw_title_summary(payload):
    if not isinstance(payload, dict):
        return ''
    title = (payload.get('title') or '').strip()
    if title:
        return title
    body = (payload.get('body') or payload.get('text') or payload.get('content') or '').strip()
    return body[:80] if body else ''


def _raw_published_at(source, payload, anchor_at=''):
    """从 raw payload 解析规范发布时间（YYYY-MM-DD 或空）。"""
    if not isinstance(payload, dict):
        return ''
    raw = dict(payload)
    anchor = raw.get('_anchor_at') or anchor_at or ''
    if anchor and not raw.get('_anchor_at'):
        raw['_anchor_at'] = anchor
    src = (source or '').lower()
    try:
        if src == 'xhs':
            from reports import structure_xhs_record
            return structure_xhs_record(raw).get('time') or ''
        if src == 'heimao':
            from reports import structure_heimao_record
            return structure_heimao_record(raw).get('time') or ''
    except Exception:
        pass
    from intel.date_parse import parse_published_date
    pub, _ = parse_published_date((payload.get('time') or '').strip(), anchor)
    return pub or ''


def _row_raw_list(row):
    payload = json.loads(row['payload_json'] or '{}')
    intel_id = row['intel_id'] if row['intel_id'] else None
    anchor_at = (row['updated_at'] if 'updated_at' in row.keys() else None) or row['created_at']
    return {
        'id': row['id'],
        'task_id': row['task_id'],
        'partner_id': row['partner_id'],
        'source': row['source'],
        'keyword': row['keyword'],
        'title_summary': _raw_title_summary(payload),
        'published_at': _raw_published_at(row['source'], payload, anchor_at),
        'created_at': row['created_at'],
        'updated_at': anchor_at,
        'intel_id': intel_id,
        'analyze_status': 'analyzed' if intel_id else 'pending',
    }


def _row_raw_detail(row):
    if not row:
        return None
    payload = json.loads(row['payload_json'] or '{}')
    intel_id = row['intel_id'] if row['intel_id'] else None
    anchor_at = (row['updated_at'] if 'updated_at' in row.keys() else None) or row['created_at']
    return {
        'id': row['id'],
        'task_id': row['task_id'],
        'partner_id': row['partner_id'],
        'source': row['source'],
        'keyword': row['keyword'],
        'title_summary': _raw_title_summary(payload),
        'published_at': _raw_published_at(row['source'], payload, anchor_at),
        'payload': payload,
        'dedup_key': row['dedup_key'] if 'dedup_key' in row.keys() else '',
        'content_hash': row['content_hash'] if 'content_hash' in row.keys() else '',
        'created_at': row['created_at'],
        'updated_at': anchor_at,
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
    return _rows_to_raw_list(rows)


def _rows_to_raw_list(rows):
    out = []
    for r in rows:
        keys = r.keys()
        triage = {}
        if 'list_triage_json' in keys:
            try:
                triage = json.loads(r['list_triage_json'] or '{}')
            except Exception:
                triage = {}
        out.append({
            'id': r['id'],
            'task_id': r['task_id'],
            'partner_id': r['partner_id'],
            'source': r['source'],
            'keyword': r['keyword'],
            'payload': json.loads(r['payload_json'] or '{}'),
            'dedup_key': r['dedup_key'] if 'dedup_key' in keys else '',
            'content_hash': r['content_hash'] if 'content_hash' in keys else '',
            'crawl_phase': r['crawl_phase'] if 'crawl_phase' in keys else 'legacy',
            'list_triage': triage,
            'created_at': r['created_at'],
            'updated_at': (r['updated_at'] if 'updated_at' in keys else None) or r['created_at'],
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
            extra_json, raw_record_id, sentiment_score, sentiment_label, confidence, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            data.get('confidence'),
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
        'confidence': row['confidence'] if 'confidence' in row.keys() else None,
        'prompt_version': row['prompt_version'],
        'model': row['model'],
        'schema_version': row['schema_version'],
        'extra': json.loads(row['extra_json'] or '{}'),
        'raw_record_id': row['raw_record_id'],
        'created_at': row['created_at'],
        'analyzed_at': row['created_at'],
    }


_RELEVANCE_ORDER = {'noise': 0, 'low': 1, 'medium': 2, 'high': 3}

_SENTIMENT_LABEL_MAP = {
    'negative': 'negative',
    'neutral': 'neutral',
    'positive': 'positive',
    '负面': 'negative',
    '中性': 'neutral',
    '正面': 'positive',
}


def _normalize_sentiment_label_filter(label):
    if not label:
        return None
    text = str(label).strip()
    if not text:
        return None
    return _SENTIMENT_LABEL_MAP.get(text) or _SENTIMENT_LABEL_MAP.get(text.lower()) or text


def list_intel_records(
    task_id=None,
    partner_id=None,
    source=None,
    relevance_min=None,
    since=None,
    risk_type=None,
    export_tier=None,
    sentiment_label=None,
    sentiment_score_min=None,
    sentiment_score_max=None,
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
    sentiment_label = _normalize_sentiment_label_filter(sentiment_label)
    if sentiment_label:
        where.append('sentiment_label = ?')
        params.append(sentiment_label)
    if sentiment_score_min is not None:
        where.append('sentiment_score >= ?')
        params.append(float(sentiment_score_min))
    if sentiment_score_max is not None:
        where.append('sentiment_score <= ?')
        params.append(float(sentiment_score_max))

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


def fail_running_analysis_jobs(task_id, run_id=None, error_message=''):
    """监测失败时将未完成的 analysis job 标记为 failed。"""
    conn = get_connection()
    now = _utc_now()
    msg = (error_message or '')[:8192]
    if run_id:
        conn.execute(
            """
            UPDATE analysis_jobs SET status='failed', error_message=?, finished_at=?, updated_at=?
            WHERE task_id=? AND run_id=? AND status='running'
            """,
            (msg, now, now, task_id, run_id),
        )
    else:
        conn.execute(
            """
            UPDATE analysis_jobs SET status='failed', error_message=?, finished_at=?, updated_at=?
            WHERE task_id=? AND status='running'
            """,
            (msg, now, now, task_id),
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
    week_ago = (datetime.now(app_tz()) - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S')
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
    if task_id is None:
        return 0
    with _db_lock:
        conn = get_connection()
        row = conn.execute(
            'SELECT COUNT(*) FROM raw_records WHERE task_id = ?',
            (int(task_id),),
        ).fetchone()
    return int(row[0]) if row else 0


def count_intel_records_for_task(task_id, unique_only=True):
    if task_id is None:
        return 0
    sql = 'SELECT COUNT(*) FROM intel_records WHERE task_id = ?'
    params = [int(task_id)]
    if unique_only:
        sql += ' AND is_duplicate = 0'
    with _db_lock:
        row = get_connection().execute(sql, params).fetchone()
    return int(row[0]) if row else 0


def clear_intel_for_task(task_id):
    conn = get_connection()
    conn.execute('DELETE FROM analysis_job_logs WHERE task_id = ?', (task_id,))
    conn.execute('DELETE FROM intel_records WHERE task_id = ?', (task_id,))
    conn.execute('DELETE FROM analysis_jobs WHERE task_id = ?', (task_id,))
    conn.commit()


def _purge_published_before_day(value):
    v = (value or '').strip()
    return v[:10] if v else ''


def _raw_ids_for_purge(task_id, partner_id=None, published_before=None):
    conn = get_connection()
    sql = """
        SELECT id, source, payload_json, created_at, updated_at, partner_id
        FROM raw_records WHERE task_id = ?
    """
    params = [task_id]
    if partner_id is not None:
        sql += ' AND partner_id = ?'
        params.append(partner_id)
    rows = conn.execute(sql, params).fetchall()
    pub_cutoff = _purge_published_before_day(published_before)
    ids = []
    for row in rows:
        if pub_cutoff:
            payload = json.loads(row['payload_json'] or '{}')
            anchor = row['updated_at'] or row['created_at']
            pub = _raw_published_at(row['source'], payload, anchor)
            if not pub or pub >= pub_cutoff:
                continue
        ids.append(int(row['id']))
    return ids


def _intel_purge_where(task_id, partner_id=None, published_before=None):
    where = ['task_id = ?']
    params = [task_id]
    if partner_id is not None:
        where.append('partner_id = ?')
        params.append(partner_id)
    pub_cutoff = _purge_published_before_day(published_before)
    if pub_cutoff:
        where.append("published_at != '' AND published_at < ?")
        params.append(pub_cutoff)
    return ' AND '.join(where), params


def _assert_task_purge_allowed(task_id):
    task = get_monitor_task(task_id)
    if not task:
        return None, '任务不存在'
    if task['status'] in ('crawling', 'analyzing'):
        return None, '任务运行中不可清理'
    return task, None


def purge_raw_records(task_id, partner_id=None, published_before=None, dry_run=False):
    task, err = _assert_task_purge_allowed(task_id)
    if err:
        return {'ok': False, 'msg': err}
    raw_ids = _raw_ids_for_purge(task_id, partner_id=partner_id, published_before=published_before)
    matched = len(raw_ids)
    if dry_run:
        return {'ok': True, 'matched_count': matched, 'deleted_count': 0, 'dry_run': True}
    if not raw_ids:
        return {'ok': True, 'matched_count': 0, 'deleted_count': 0, 'dry_run': False}
    conn = get_connection()
    placeholders = ','.join('?' * len(raw_ids))
    conn.execute(
        'DELETE FROM intel_records WHERE raw_record_id IN (%s)' % placeholders,
        raw_ids,
    )
    conn.execute(
        'DELETE FROM raw_records WHERE id IN (%s)' % placeholders,
        raw_ids,
    )
    conn.commit()
    return {'ok': True, 'matched_count': matched, 'deleted_count': matched, 'dry_run': False}


def purge_intel_records(task_id, partner_id=None, published_before=None, dry_run=False):
    task, err = _assert_task_purge_allowed(task_id)
    if err:
        return {'ok': False, 'msg': err}
    conn = get_connection()
    where_sql, params = _intel_purge_where(task_id, partner_id, published_before)
    matched = conn.execute(
        'SELECT COUNT(*) FROM intel_records WHERE ' + where_sql,
        params,
    ).fetchone()[0]
    if dry_run:
        return {'ok': True, 'matched_count': matched, 'deleted_count': 0, 'dry_run': True}
    cur = conn.execute('DELETE FROM intel_records WHERE ' + where_sql, params)
    conn.commit()
    return {
        'ok': True,
        'matched_count': matched,
        'deleted_count': cur.rowcount,
        'dry_run': False,
    }


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


def update_raw_triage(raw_id, triage_data):
    conn = get_connection()
    now = _utc_now()
    conn.execute(
        'UPDATE raw_records SET list_triage_json=?, updated_at=? WHERE id=?',
        (json.dumps(triage_data or {}, ensure_ascii=False), now, raw_id),
    )
    conn.commit()


def merge_raw_payload(raw_id, payload_patch, crawl_phase='detail'):
    conn = get_connection()
    row = conn.execute('SELECT * FROM raw_records WHERE id=?', (raw_id,)).fetchone()
    if not row:
        return False
    try:
        payload = json.loads(row['payload_json'] or '{}')
    except Exception:
        payload = {}
    if isinstance(payload_patch, dict):
        payload.update(payload_patch)
    ch = raw_content_hash(payload)
    now = _utc_now()
    conn.execute(
        """
        UPDATE raw_records SET payload_json=?, content_hash=?, updated_at=?, crawl_phase=?
        WHERE id=?
        """,
        (json.dumps(payload, ensure_ascii=False), ch, now, crawl_phase, raw_id),
    )
    conn.commit()
    return True


def list_raw_for_triage(task_id):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT * FROM raw_records
        WHERE task_id=? AND crawl_phase IN ('list', 'legacy')
        ORDER BY id ASC
        """,
        (task_id,),
    ).fetchall()
    return _rows_to_raw_list(rows)


def clear_investigation_queue(task_id):
    conn = get_connection()
    conn.execute('DELETE FROM investigation_queue WHERE task_id=?', (task_id,))
    conn.commit()


def enqueue_investigation(task_id, raw_id, url, source, priority_score=0):
    conn = get_connection()
    now = _utc_now()
    existing = conn.execute(
        """
        SELECT id FROM investigation_queue
        WHERE task_id=? AND raw_id=? AND status IN ('pending', 'running')
        """,
        (task_id, raw_id),
    ).fetchone()
    if existing:
        return existing['id']
    cur = conn.execute(
        """
        INSERT INTO investigation_queue(
            task_id, raw_id, url, source, priority_score, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """,
        (task_id, raw_id, url or '', source or '', float(priority_score or 0), now, now),
    )
    conn.commit()
    return cur.lastrowid


def list_investigation_queue(task_id, status='pending'):
    conn = get_connection()
    sql = 'SELECT * FROM investigation_queue WHERE task_id=?'
    params = [task_id]
    if status is not None:
        sql += ' AND status=?'
        params.append(status)
    sql += ' ORDER BY priority_score DESC, id ASC'
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def update_investigation_status(queue_id, status, error_message=''):
    conn = get_connection()
    now = _utc_now()
    conn.execute(
        """
        UPDATE investigation_queue SET status=?, error_message=?, updated_at=?
        WHERE id=?
        """,
        (status, (error_message or '')[:200], now, queue_id),
    )
    conn.commit()


def update_partner_priority(partner_id, tier, source='business', reason=''):
    tier = (tier or 'P1').upper()
    if tier not in ('P0', 'P1', 'P2'):
        tier = 'P1'
    now = _utc_now()
    conn = get_connection()
    conn.execute(
        """
        UPDATE partners SET priority_tier=?, priority_source=?, priority_updated_at=?,
                            priority_reason=?, updated_at=?
        WHERE id=?
        """,
        (tier, source or 'business', now, (reason or '')[:200], now, partner_id),
    )
    conn.commit()
    return get_partner(partner_id)


def list_partners_priority():
    partners = list_partners()
    out = []
    for p in partners:
        out.append({
            'id': p['id'],
            'name': p['name'],
            'priority_tier': p.get('priority_tier') or 'P1',
            'priority_source': p.get('priority_source') or 'auto',
            'priority_updated_at': p.get('priority_updated_at') or '',
            'priority_reason': p.get('priority_reason') or '',
            'industry_cohort': p.get('industry_cohort') or '',
        })
    return out

