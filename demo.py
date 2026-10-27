"""End-to-end demo: python demo.py

1. simulate trucks on a highway with real NHAI fares
2. learn plaza locations from FASTag debits + GPS pings (K-Means)
3. estimate each truck's toll bill from GPS alone and compare with what FASTag actually charged
"""
import os

import pandas as pd

from toll_estimator import simulate
from toll_estimator.crossings import approx_expense_toll, crossed_plazas, crossed_plazas_radius, nhai_coverage
from toll_estimator.fares import load_fares
from toll_estimator.geo import haversine
from toll_estimator.plazas import locate_all

pd.set_option('display.width', 200)
os.makedirs('outputs', exist_ok=True)

fares = load_fares()
plaza_cost = fares.rename(columns={'single_journey': 'cost'})[['plaza_code', 'tag_class', 'cost']]

plazas, pings, debits, trucks = simulate.fleet(fares)
print(f"simulated {len(trucks)} trucks, {len(pings):,} GPS pings, {len(debits)} FASTag debits, {len(plazas)} plazas")
print(f"share of debits whose plaza has a published NHAI fare: {nhai_coverage(debits.plazacode, fares):.0%}")

print("\n=== 1. Where are the plazas? (K-Means on pings around each debit) ===")
found = locate_all(debits, pings)
chk = found.merge(plazas, on='plaza_code', suffixes=('_est', '_true'))
chk['error_m'] = chk.apply(lambda r: haversine([r.longitude_est, r.latitude_est], [r.longitude_true, r.latitude_true]), axis=1).round(0)
print(chk[['plaza_code', 'plaza_name', 'debits_used', 'pings_used', 'error_m']].to_string(index=False))
print(f"median location error: {chk.error_m.median():.0f} m")
found.to_csv('outputs/plaza_locations_estimated.csv', index=False)

print("\n=== 2. Toll bill from GPS alone vs actual FASTag debits ===")
rows = []
for t in trucks.itertuples():
    loc = pings[pings.vehicleId == t.vehicle_id]
    actual = debits[debits.vehicle_id == t.vehicle_id]
    grid = crossed_plazas(loc, found)
    rad = crossed_plazas_radius(loc, found)
    est_grid, _ = approx_expense_toll(grid, t.fastag_class, plaza_cost)
    est_rad, _ = approx_expense_toll(rad, t.fastag_class, plaza_cost)
    rows.append({'vehicle_id': t.vehicle_id, 'class': t.fastag_class, 'actual_crossings': len(actual),
                 'grid_crossings': 0 if grid is None else len(grid), 'radius_crossings': 0 if rad is None else len(rad),
                 'actual_toll': actual.amount.sum(), 'est_grid': est_grid, 'est_radius': est_rad})
res = pd.DataFrame(rows)
res.to_csv('outputs/toll_estimates.csv', index=False)
for m in ['grid', 'radius']:
    err = (res[f'est_{m}'] - res.actual_toll).abs() / res.actual_toll
    rec = (res[f'{m}_crossings'].clip(upper=res.actual_crossings)).sum() / res.actual_crossings.sum()
    print(f"{m:>6} method: crossings found {rec:.0%} | median bill error {err.median():.1%} | "
          f"trucks within 5%: {(err <= 0.05).mean():.0%} | fleet total off by "
          f"{(res[f'est_{m}'].sum() / res.actual_toll.sum() - 1):+.1%}")
print("\nSample:")
print(res.head(8).to_string(index=False))
