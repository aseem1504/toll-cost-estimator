"""Load the public NHAI fare table (data/nhai_toll_fares_2022_04.csv).

Some plazas list more than one fee revision. Keep the latest one per plaza and vehicle class.
"""
import pandas as pd


def load_fares(path='data/nhai_toll_fares_2022_04.csv'):
    f = pd.read_csv(path, dtype={'plaza_code': str})
    f['_d'] = pd.to_datetime(f['fee_effective_date'], format='%d-%b-%Y', errors='coerce')
    f = f.sort_values('_d').drop_duplicates(['plaza_code', 'tag_class'], keep='last')
    return f.drop(columns='_d').reset_index(drop=True)
