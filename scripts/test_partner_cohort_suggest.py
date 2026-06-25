# -*- coding: utf-8 -*-
"""partner cohort 推荐：归一化、排序、API 校验。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intel.partner_cohort_suggest import (
    _build_candidate_items,
    normalize_to_existing,
    suggest_cohort_candidates,
)


def test_normalize_exact_and_containment():
    existing = ['新能源汽车', '消费电子']
    c, matched = normalize_to_existing('新能源汽车', existing)
    assert c == '新能源汽车' and matched
    c2, m2 = normalize_to_existing('新能源汽车经销商', existing)
    assert c2 == '新能源汽车' and m2
    c3, m3 = normalize_to_existing('全新行业', existing)
    assert c3 == '全新行业' and not m3
    print('OK test_normalize_exact_and_containment')


def test_existing_first_sort():
    existing = ['新能源汽车', '传统乘用车']
    counts = {'新能源汽车': 3, '传统乘用车': 1}
    items = _build_candidate_items(
        ['新能源整车', '新能源汽车', '传统乘用车'],
        existing,
        counts,
        max_candidates=5,
    )
    assert items[0]['cohort'] == '新能源汽车'
    assert items[0]['source'] == 'existing'
    assert items[0]['partner_count'] == 3
    new_items = [i for i in items if i.get('is_new')]
    if new_items:
        assert all(i['partner_count'] <= items[0]['partner_count'] for i in items if not i.get('is_new'))
    print('OK test_existing_first_sort', [i['cohort'] for i in items])


def test_empty_name_raises():
    try:
        suggest_cohort_candidates('')
        assert False, 'expected ValueError'
    except ValueError as e:
        assert 'name' in str(e)
    print('OK test_empty_name_raises')


def test_api_empty_name_400():
    from crawler_web import app

    client = app.test_client()
    r = client.post('/api/partners/suggest-cohort', json={'name': '  '})
    assert r.status_code == 400, r.get_data(as_text=True)
    data = r.get_json()
    assert data.get('ok') is False
    print('OK test_api_empty_name_400')


if __name__ == '__main__':
    test_normalize_exact_and_containment()
    test_existing_first_sort()
    test_empty_name_raises()
    test_api_empty_name_400()
    print('ALL OK')
