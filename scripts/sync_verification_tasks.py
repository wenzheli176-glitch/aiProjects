#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenSpec 手动验证清单 ↔ 归档 change tasks.md 双向同步。

主清单：openspec/verification-pending.md
用法：
  python scripts/sync_verification_tasks.py status
  python scripts/sync_verification_tasks.py push
  python scripts/sync_verification_tasks.py scan
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PENDING_PATH = ROOT / 'openspec' / 'verification-pending.md'
ARCHIVE_GLOB = 'openspec/changes/archive/*/tasks.md'

TASK_LINE = re.compile(
    r'^- \[(?P<done>[ xX])\] (?P<id>\d+\.\d+) (?P<body>.+)$'
)
ARCHIVE_COMMENT = re.compile(r'<!--\s*archive:\s*(?P<path>.+?)\s*-->')
SECTION_HEADER = re.compile(r'^## (?P<name>.+)$')


@dataclass
class TaskItem:
    task_id: str
    body: str
    done: bool

    def line(self) -> str:
        mark = 'x' if self.done else ' '
        return '- [%s] %s %s' % (mark, self.task_id, self.body)


@dataclass
class ChangeSection:
    slug: str
    archive_rel: str
    tasks: list[TaskItem] = field(default_factory=list)

    @property
    def archive_path(self) -> Path:
        return ROOT / self.archive_rel.replace('/', os_sep())

    def done_count(self) -> int:
        return sum(1 for t in self.tasks if t.done)

    def total(self) -> int:
        return len(self.tasks)

    def complete(self) -> bool:
        return self.total() > 0 and self.done_count() == self.total()


def os_sep() -> str:
    return '\\' if sys.platform == 'win32' else '/'


def parse_pending(text: str) -> list[ChangeSection]:
    sections: list[ChangeSection] = []
    current: ChangeSection | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        m_h = SECTION_HEADER.match(line)
        if m_h:
            current = ChangeSection(slug=m_h.group('name').strip(), archive_rel='')
            sections.append(current)
            continue
        if current is None:
            continue
        m_a = ARCHIVE_COMMENT.match(line.strip())
        if m_a:
            current.archive_rel = m_a.group('path').strip().replace('\\', '/')
            continue
        m_t = TASK_LINE.match(line.strip())
        if m_t:
            current.tasks.append(TaskItem(
                task_id=m_t.group('id'),
                body=m_t.group('body'),
                done=m_t.group('done').lower() == 'x',
            ))
    return sections


def render_pending(sections: list[ChangeSection]) -> str:
    intro = """# OpenSpec 待验证清单

本文件为**唯一待办验证入口**：各已归档 change 中未勾选的「手动验证」项汇总于此。  
验证完成后在本文件勾选 `- [x]`，再运行同步脚本写回对应 archive 的 `tasks.md`。

```bash
# 查看进度
python scripts/sync_verification_tasks.py status

# 将本文件已勾选项同步到各 archive .../tasks.md
python scripts/sync_verification_tasks.py push

# 从 archive 重新扫描未验证项（保留本文件已勾选状态）
python scripts/sync_verification_tasks.py scan
```

---

"""
    parts = [intro]
    for sec in sections:
        parts.append('## %s\n\n' % sec.slug)
        parts.append('<!-- archive: %s -->\n\n' % sec.archive_rel)
        for t in sec.tasks:
            parts.append(t.line() + '\n')
        parts.append('\n')
    return ''.join(parts).rstrip() + '\n'


def load_pending() -> list[ChangeSection]:
    if not PENDING_PATH.is_file():
        return []
    return parse_pending(PENDING_PATH.read_text(encoding='utf-8'))


def save_pending(sections: list[ChangeSection]) -> None:
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(render_pending(sections), encoding='utf-8')


def parse_archive_tasks(path: Path) -> dict[str, bool]:
    """task_id -> done (only manual verification lines)."""
    if not path.is_file():
        return {}
    out: dict[str, bool] = {}
    in_manual = False
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if line.startswith('## ') and '手动验证' in line:
            in_manual = True
            continue
        if in_manual and line.startswith('## '):
            break
        m = TASK_LINE.match(line)
        if m and in_manual:
            out[m.group('id')] = m.group('done').lower() == 'x'
    return out


def slug_from_archive_dir(name: str) -> str:
    m = re.match(r'^\d{4}-\d{2}-\d{2}-(.+)$', name)
    return m.group(1) if m else name


def discover_archive_sections() -> list[ChangeSection]:
    sections: list[ChangeSection] = []
    for path in sorted(ROOT.glob(ARCHIVE_GLOB.replace('/', os_sep()))):
        rel = path.relative_to(ROOT).as_posix()
        slug = slug_from_archive_dir(path.parent.name)
        tasks_map = parse_archive_tasks(path)
        if not tasks_map:
            continue
        items = [
            TaskItem(task_id=tid, body='', done=done)
            for tid, done in sorted(tasks_map.items(), key=lambda x: x[0])
        ]
        sections.append(ChangeSection(slug=slug, archive_rel=rel, tasks=items))
    return sections


def merge_scan(existing: list[ChangeSection]) -> list[ChangeSection]:
    """Rescan archives; preserve done flags and bodies from pending where possible."""
    old_by_slug = {s.slug: s for s in existing}
    merged: list[ChangeSection] = []
    for disc in discover_archive_sections():
        old = old_by_slug.get(disc.slug)
        archive_path = ROOT / disc.archive_rel
        archive_map = parse_archive_tasks(archive_path)
        tasks: list[TaskItem] = []
        old_tasks = {t.task_id: t for t in old.tasks} if old else {}
        for tid in sorted(archive_map.keys()):
            done = archive_map[tid]
            body = ''
            if tid in old_tasks:
                body = old_tasks[tid].body
                if old_tasks[tid].done:
                    done = True
            if not body:
                body = _read_body_from_archive(archive_path, tid) or tid
            if not done and old and tid in old_tasks:
                done = old_tasks[tid].done
            tasks.append(TaskItem(task_id=tid, body=body, done=done))
        if tasks:
            merged.append(ChangeSection(
                slug=disc.slug,
                archive_rel=disc.archive_rel,
                tasks=tasks,
            ))
    return merged


def _read_body_from_archive(path: Path, task_id: str) -> str:
    prefix = '- [ ] %s ' % task_id
    prefix_done = '- [x] %s ' % task_id
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if line.startswith(prefix):
            return line[len(prefix):]
        if line.startswith(prefix_done):
            return line[len(prefix_done):]
    return ''


def push_to_archives(sections: list[ChangeSection]) -> list[str]:
    messages: list[str] = []
    for sec in sections:
        path = ROOT / sec.archive_rel.replace('/', os_sep())
        if not path.is_file():
            messages.append('[skip] 找不到 %s' % sec.archive_rel)
            continue
        text = path.read_text(encoding='utf-8')
        updated = text
        changed = 0
        for t in sec.tasks:
            if not t.done:
                continue
            old = '- [ ] %s ' % t.task_id
            new = '- [x] %s ' % t.task_id
            if old in updated:
                updated = updated.replace(old, new, 1)
                changed += 1
        if changed:
            path.write_text(updated, encoding='utf-8')
            messages.append('[push] %s：同步 %d 项' % (sec.slug, changed))
        if sec.complete():
            messages.append('[done] %s：全部验证已完成 ✓' % sec.slug)
    return messages


def cmd_status(sections: list[ChangeSection]) -> int:
    total = sum(s.total() for s in sections)
    done = sum(s.done_count() for s in sections)
    print('清单: %s' % PENDING_PATH.relative_to(ROOT))
    print('进度: %d/%d\n' % (done, total))
    for sec in sections:
        mark = '✓' if sec.complete() else ' '
        print('  [%s] %s  %d/%d  → %s' % (
            mark, sec.slug, sec.done_count(), sec.total(), sec.archive_rel,
        ))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='OpenSpec 验证清单同步')
    parser.add_argument(
        'command',
        choices=('status', 'push', 'scan'),
        help='status=进度 | push=写回 archive | scan=从 archive 重建清单',
    )
    args = parser.parse_args()

    if args.command == 'scan':
        existing = load_pending()
        merged = merge_scan(existing)
        save_pending(merged)
        print('已更新 %s（%d 个 change）' % (
            PENDING_PATH.relative_to(ROOT), len(merged),
        ))
        return cmd_status(merged)

    sections = load_pending()
    if not sections:
        print('未找到 %s，请先运行 scan' % PENDING_PATH, file=sys.stderr)
        return 1

    if args.command == 'status':
        return cmd_status(sections)

    if args.command == 'push':
        msgs = push_to_archives(sections)
        for m in msgs:
            print(m)
        if not msgs:
            print('无已勾选项需要同步')
        return cmd_status(sections)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
