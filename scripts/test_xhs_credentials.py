# -*- coding: utf-8 -*-
"""xhs 账号池单元测试。"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def _tmpdir():
    td = tempfile.mkdtemp(prefix='xhs_cred_test_')
    os.makedirs(os.path.join(td, 'credentials', 'xhs'), exist_ok=True)
    os.makedirs(os.path.join(td, 'chrome_profiles', 'xhs'), exist_ok=True)
    return td


def test_migration_and_pick():
    import intel.xhs_credentials as xc

    td = _tmpdir()
    legacy_cookie = os.path.join(td, 'credentials', 'xhs_cookies.json')
    legacy_prof = os.path.join(td, 'chrome_profiles', 'xhs_0')
    os.makedirs(legacy_prof, exist_ok=True)
    with open(legacy_cookie, 'w', encoding='utf-8') as f:
        json.dump([{'name': 'web_session', 'value': 'x', 'domain': '.xiaohongshu.com'}], f)

    old_base = config.BASE_DIR
    old_acc_dir = xc._ACCOUNTS_DIR
    old_acc_file = xc._ACCOUNTS_FILE
    old_legacy = xc._LEGACY_COOKIE
    old_prof_root = xc._PROFILE_ROOT
    old_legacy_prof = xc._LEGACY_PROFILE
    try:
        config.BASE_DIR = td
        xc._ACCOUNTS_DIR = os.path.join(td, 'credentials', 'xhs')
        xc._ACCOUNTS_FILE = os.path.join(xc._ACCOUNTS_DIR, 'accounts.json')
        xc._LEGACY_COOKIE = legacy_cookie
        xc._LEGACY_PROFILE = legacy_prof
        xc._PROFILE_ROOT = os.path.join(td, 'chrome_profiles', 'xhs')
        assert xc.ensure_migrated_acc_default() is True
        data = xc.load_accounts()
        assert len(data['accounts']) == 1
        assert data['accounts'][0]['id'] == 'acc-default'

        xc.create_account('B号')
        xc.create_account('C号')
        picks = []
        for _ in range(4):
            acc = xc.pick_account_for_keyword(diagnose_fn=lambda _a: True)
            picks.append(acc['id'])
        assert picks[0] != picks[1]
        print('OK test_migration_and_pick', picks)
    finally:
        config.BASE_DIR = old_base
        xc._ACCOUNTS_DIR = old_acc_dir
        xc._ACCOUNTS_FILE = old_acc_file
        xc._LEGACY_COOKIE = old_legacy
        xc._PROFILE_ROOT = old_prof_root
        xc._LEGACY_PROFILE = old_legacy_prof
        shutil.rmtree(td, ignore_errors=True)


def test_cooldown_skip():
    import intel.xhs_credentials as xc

    td = _tmpdir()
    acc_file = os.path.join(td, 'credentials', 'xhs', 'accounts.json')
    doc = {
        'version': 1,
        'accounts': [
            {'id': 'acc-a', 'label': 'A', 'enabled': True, 'cooldown_until': '2099-01-01T00:00:00Z',
             'cookies_file': 'credentials/xhs/a.json', 'user_data_dir': 'chrome_profiles/xhs/a'},
            {'id': 'acc-b', 'label': 'B', 'enabled': True, 'cooldown_until': None,
             'cookies_file': 'credentials/xhs/b.json', 'user_data_dir': 'chrome_profiles/xhs/b'},
        ],
        'rotation': {'cursor': 0},
    }
    with open(acc_file, 'w', encoding='utf-8') as f:
        json.dump(doc, f)
    old_base = config.BASE_DIR
    old_acc_file = xc._ACCOUNTS_FILE
    old_acc_dir = xc._ACCOUNTS_DIR
    try:
        config.BASE_DIR = td
        xc._ACCOUNTS_FILE = acc_file
        xc._ACCOUNTS_DIR = os.path.dirname(acc_file)
        eligible = xc.eligible_accounts()
        assert len(eligible) == 1
        assert eligible[0]['id'] == 'acc-b'
        print('OK test_cooldown_skip')
    finally:
        config.BASE_DIR = old_base
        xc._ACCOUNTS_FILE = old_acc_file
        xc._ACCOUNTS_DIR = old_acc_dir
        shutil.rmtree(td, ignore_errors=True)


def test_pick_skip_failed_diagnose():
    import intel.xhs_credentials as xc

    td = _tmpdir()
    acc_file = os.path.join(td, 'credentials', 'xhs', 'accounts.json')
    doc = {
        'version': 1,
        'accounts': [
            {'id': 'acc-a', 'label': 'A', 'enabled': True, 'cookies_file': 'c', 'user_data_dir': 'p'},
            {'id': 'acc-b', 'label': 'B', 'enabled': True, 'cookies_file': 'c', 'user_data_dir': 'p'},
        ],
        'rotation': {'cursor': 0},
    }
    with open(acc_file, 'w', encoding='utf-8') as f:
        json.dump(doc, f)
    old_base = config.BASE_DIR
    old_acc_file = xc._ACCOUNTS_FILE
    old_acc_dir = xc._ACCOUNTS_DIR
    try:
        config.BASE_DIR = td
        xc._ACCOUNTS_FILE = acc_file
        xc._ACCOUNTS_DIR = os.path.dirname(acc_file)
        acc = xc.pick_account_for_keyword(diagnose_fn=lambda a: a['id'] == 'acc-b')
        assert acc['id'] == 'acc-b'
        print('OK test_pick_skip_failed_diagnose')
    finally:
        config.BASE_DIR = old_base
        xc._ACCOUNTS_FILE = old_acc_file
        xc._ACCOUNTS_DIR = old_acc_dir
        shutil.rmtree(td, ignore_errors=True)


if __name__ == '__main__':
    test_migration_and_pick()
    test_cooldown_skip()
    test_pick_skip_failed_diagnose()
    print('ALL OK')
