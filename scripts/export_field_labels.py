#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出 static/field-labels.json"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from field_labels import export_field_labels_json

OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'field-labels.json')

if __name__ == '__main__':
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(export_field_labels_json())
    print('Wrote', OUT)
