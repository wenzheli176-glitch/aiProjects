# -*- coding: utf-8 -*-
"""partner-cohort-suggest 手动验收项 4.1 / 4.2 的 API+逻辑自动化。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intel.db import create_partner, delete_partner, get_partner, get_connection
from intel.keyword_batch import build_keyword_batches


def test_empty_cohort_save_and_persist():
    """4.2 cohort 留空保存成功。"""
    p = create_partner({
        'name': '__accept_empty_cohort__',
        'aliases': [],
        'industry_cohort': '',
        'enabled': True,
    })
    assert p and (p.get('industry_cohort') or '') == ''
    loaded = get_partner(p['id'])
    assert (loaded.get('industry_cohort') or '') == ''
    delete_partner(p['id'])
    print('OK test_empty_cohort_save_and_persist')


def test_same_cohort_keyword_merge():
    """4.1 同 cohort 合作方合并 keyword_batch。"""
    p1 = create_partner({
        'name': '蔚来汽车验收',
        'aliases': ['NIO'],
        'industry_cohort': '新能源汽车',
        'enabled': True,
    })
    p2 = create_partner({
        'name': '小鹏汽车验收',
        'aliases': [],
        'industry_cohort': '新能源汽车',
        'enabled': True,
    })
    try:
        batches = build_keyword_batches([p1, p2])
        cohort_batches = [b for b in batches if b.get('cohort') == '新能源汽车']
        assert len(cohort_batches) >= 1, batches
        kws = cohort_batches[0]['keywords']
        assert '蔚来汽车验收' in kws
        assert '小鹏汽车验收' in kws
        assert len(cohort_batches[0]['partners']) == 2
        print('OK test_same_cohort_keyword_merge', kws)
    finally:
        if p1:
            delete_partner(p1['id'])
        if p2:
            delete_partner(p2['id'])


def test_suggest_cohort_readonly():
    """推荐 API 不写入 DB。"""
    from crawler_web import app

    before = get_connection().execute(
        "SELECT COUNT(*) FROM partners WHERE industry_cohort='新能源汽车'"
    ).fetchone()[0]
    client = app.test_client()
    r = client.post('/api/partners/suggest-cohort', json={'name': '蔚来汽车验收'})
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('ok') is True
    assert 'candidates' in data
    after = get_connection().execute(
        "SELECT COUNT(*) FROM partners WHERE industry_cohort='新能源汽车'"
    ).fetchone()[0]
    assert before == after
    print('OK test_suggest_cohort_readonly')


if __name__ == '__main__':
    test_empty_cohort_save_and_persist()
    test_same_cohort_keyword_merge()
    test_suggest_cohort_readonly()
    print('ALL ACCEPTANCE OK')
