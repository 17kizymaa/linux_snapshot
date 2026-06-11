"""Tests for budget cap enforcement."""

import sys
sys.path.insert(0, 'scripts')
from generate_list import generate_list

def test_staples_budget_respected():
    result = generate_list('2026-06-15', staples_budget=30, brook_budget=20)
    assert result['staples_budget'] == 30

def test_brook_budget_respected():
    result = generate_list('2026-06-15', staples_budget=50, brook_budget=15)
    assert result['brook_budget'] == 15
