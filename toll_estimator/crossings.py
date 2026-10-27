"""Which plazas did a truck cross, and when? Then what did it cost?

Ported from notebooks/original/02_plaza_geofences_on_raw_pings.ipynb and 03_toll_cost_predict.ipynb.

`crossed_plazas` is the original grid method: slow pings (speed < 20) are snapped to a
2-decimal grid (~1.1 km cells) and matched to the plaza's cell. Pings at the same plaza
more than one hour apart count as separate crossings.

`crossed_plazas_radius` is an added variant that matches by real distance instead of grid
cell, so a plaza sitting near a cell edge is not missed. The demo compares the two.

`approx_expense_toll` applies the fare rule from the original: full fare, unless the truck
crosses the same plaza again within 24 hours, in which case that leg is half fare. This
matches how NHAI prices return journeys (the public fare table has return ~= 0.5 x single).
"""
import numpy as np
import pandas as pd

from .geo import haversine


def _grid_key(lat, lon):
    return str(int(round(lat, 2) * 100)) + str(int(round(lon, 2) * 100))


def plaza_grid(plaza_data):
    p = plaza_data.dropna().copy()
    p['loc_str'] = p.apply(lambda r: _grid_key(r['latitude'], r['longitude']), axis=1)
    return p


def _visits(crossed):
    """One row per visit, with time_diff = gap to the next visit of the same plaza."""
    out = []
    for key in crossed['key'].unique():
        u = crossed[crossed['key'] == key].sort_values('time', ascending=False).copy()
        u['time_diff'] = u['time'].shift(1) - u['time']
        u.iloc[0, u.columns.get_loc('time_diff')] = 86401
        out.append(u[u['time_diff'] > 3600].copy())
    return pd.concat(out) if out else pd.DataFrame(columns=list(crossed.columns) + ['time_diff'])


def crossed_plazas(loc, plaza_data):
    loc = loc[loc['speed'] < 20].copy()
    if loc.empty:
        return None
    loc[['longitude', 'latitude']] = pd.DataFrame(loc.location.values.tolist(), index=loc.index)
    loc['key'] = [_grid_key(a, b) for a, b in zip(loc.latitude, loc.longitude)]
    grid = plaza_grid(plaza_data)
    crossed = loc[loc['key'].isin(grid['loc_str'])][['vehicleId', 'time', 'key']]
    visits = _visits(crossed)
    return visits.merge(grid[['plaza_code', 'loc_str']], left_on='key', right_on='loc_str', how='left')


def crossed_plazas_radius(loc, plaza_data, radius_m=400):
    loc = loc[loc['speed'] < 20].copy()
    if loc.empty:
        return None
    P = plaza_data[['plaza_code', 'latitude', 'longitude']].dropna().values
    keys = []
    for lon, lat in loc.location:
        best, best_d = None, radius_m
        for code, plat, plon in P:
            if abs(plat - lat) > 0.01 or abs(plon - lon) > 0.01:
                continue
            d = haversine([lon, lat], [plon, plat])
            if d < best_d:
                best, best_d = code, d
        keys.append(best)
    loc['key'] = keys
    crossed = loc[loc['key'].notna()][['vehicleId', 'time', 'key']]
    visits = _visits(crossed)
    visits['plaza_code'] = visits['key']
    return visits


def approx_expense_toll(plazas_crossed, fastag_class, plaza_cost):
    """plaza_cost columns: plaza_code, tag_class, cost (single journey fare)."""
    if plazas_crossed is None or plazas_crossed.empty:
        return 0.0, plazas_crossed
    cost = plaza_cost[plaza_cost['tag_class'] == fastag_class][['plaza_code', 'cost']]
    pc = plazas_crossed.merge(cost, on='plaza_code', how='left')
    pc['final_cost'] = np.where(pc['time_diff'] > 86400, pc['cost'], pc['cost'] / 2)
    return float(pc['final_cost'].sum()), pc


def nhai_coverage(txn_plaza_codes, fares):
    """Share of toll transactions whose plaza has a published NHAI fare
    (from notebooks/original/05_nhai_fare_rules_coverage.ipynb)."""
    codes = pd.Series(txn_plaza_codes).astype(str).str.zfill(6)
    return codes.isin(set(fares['plaza_code'])).mean()
