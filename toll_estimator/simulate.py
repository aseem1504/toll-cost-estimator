"""Synthetic highway, plazas, trucks, pings and FASTag debits.

Fares are real (public NHAI fare table in data/). Plaza positions, trucks and trips are made
up: we pick real plaza codes so the fare lookup works, then drop them along a fictional
corridor. Do not read the coordinates as the real location of those plazas.
"""
import numpy as np
import pandas as pd

from .geo import haversine

CLASSES = [6, 7, 12]  # upto 3 axle, bus/truck (2 axle), 4-6 axle


def corridor(rng, n_points=400):
    """A wiggly ~700 km road heading north-east from around (73.0E, 19.0N)."""
    lon, lat = 73.0, 19.0
    pts, heading = [], np.deg2rad(40)
    for _ in range(n_points):
        heading += rng.normal(0, 0.04)
        lon += 0.016 * np.cos(heading)
        lat += 0.016 * np.sin(heading)
        pts.append((lon, lat))
    return np.array(pts)


def pick_plazas(fares, road, rng, n=10):
    ok = fares.groupby('plaza_code').tag_class.apply(lambda s: set(CLASSES) <= set(s))
    codes = rng.choice(ok[ok].index.values, size=n, replace=False)
    idx = np.linspace(20, len(road) - 20, n).astype(int)
    pl = pd.DataFrame({'plaza_code': codes, 'road_idx': idx,
                       'longitude': road[idx, 0], 'latitude': road[idx, 1]})
    names = fares.drop_duplicates('plaza_code').set_index('plaza_code').plaza_name
    pl['plaza_name'] = pl.plaza_code.map(names)
    return pl


def _drive(road, plazas, start_t, reverse, rng, step=30):
    """Pings every `step` seconds; the truck slows to cross each plaza and stops at dhabas."""
    path = road[::-1] if reverse else road
    pidx = set((len(road) - 1 - plazas.road_idx) if reverse else plazas.road_idx)
    t, rows, crossings = start_t, [], []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        seg = haversine(a, b)
        speed = rng.normal(48, 6)
        if i in pidx:
            speed = rng.uniform(5, 12)  # queue at the booth
            crossings.append((i, t))
        n = max(1, int(seg / (speed / 3.6) / step))
        for k in range(n):
            f = k / n
            lon, lat = a + (b - a) * f
            if rng.random() > 0.12:  # ~12% of pings never arrive (network gaps)
                rows.append((t, [round(lon + rng.normal(0, 1.2e-4), 6), round(lat + rng.normal(0, 1.2e-4), 6)],
                             round(max(0, speed + rng.normal(0, 3)), 1)))
            t += step
        if rng.random() < 0.015:  # tea break, slow pings away from plazas
            for _ in range(rng.integers(30, 120)):
                rows.append((t, [round(b[0], 6), round(b[1], 6)], 0.0))
                t += step
    code_at = dict(zip((len(road) - 1 - plazas.road_idx) if reverse else plazas.road_idx, plazas.plaza_code))
    # the toll reader clock and the GPS clock never agree exactly
    debits = [(code_at[i], ts + int(rng.normal(0, 25))) for i, ts in crossings]
    return rows, debits, t


def fleet(fares, n_trucks=40, seed=3, start_ts=1_650_000_000):
    rng = np.random.default_rng(seed)
    road = corridor(rng)
    plazas = pick_plazas(fares, road, rng)
    single = fares.set_index(['plaza_code', 'tag_class']).single_journey
    ret = fares.set_index(['plaza_code', 'tag_class']).return_journey
    pings, debits, trucks = [], [], []
    for k in range(n_trucks):
        vid, cls = 300000 + k, int(rng.choice(CLASSES))
        t0 = start_ts + int(rng.integers(0, 86400))
        rows, deb, t_end = _drive(road, plazas, t0, False, rng)
        last_seen = {}
        legs = [deb]
        if rng.random() < 0.6:  # comes back; sometimes inside 24 h, sometimes after
            wait = int(rng.choice([3, 10, 30]) * 3600)
            rows2, deb2, _ = _drive(road, plazas, t_end + wait, True, rng)
            rows += rows2
            legs.append(deb2)
        for leg in legs:
            for code, ts in leg:
                prev = last_seen.get(code)
                amount = ret[(code, cls)] if prev is not None and ts - prev < 86400 else single[(code, cls)]
                debits.append({'vehicle_id': vid, 'plazacode': str(code), 'time': ts, 'amount': float(amount)})
                last_seen[code] = ts
        pings.append(pd.DataFrame([{'vehicleId': vid, 'time': r[0], 'location': r[1], 'speed': r[2]} for r in rows]))
        trucks.append({'vehicle_id': vid, 'fastag_class': cls})
    return plazas, pd.concat(pings, ignore_index=True), pd.DataFrame(debits), pd.DataFrame(trucks)
