import pandas as pd

from toll_estimator.crossings import approx_expense_toll
from toll_estimator.fares import load_fares


def test_fares_one_row_per_plaza_class():
    f = load_fares()
    assert not f.duplicated(['plaza_code', 'tag_class']).any()
    assert (f.return_journey <= f.single_journey).mean() > 0.95


def test_return_within_24h_is_half_fare():
    crossed = pd.DataFrame({'plaza_code': ['000001', '000001'], 'time_diff': [5 * 3600, 86401]})
    cost = pd.DataFrame({'plaza_code': ['000001'], 'tag_class': [7], 'cost': [200.0]})
    total, _ = approx_expense_toll(crossed, 7, cost)
    assert total == 300.0
