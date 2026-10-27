"""Find where each toll plaza physically sits, using only FASTag debits and GPS pings.

Ported from notebooks/original/01_toll_plaza_location_kmeans.ipynb.

Idea: a FASTag debit tells you *when* a truck was at plaza X. The GPS ping closest to that
moment tells you *where* the truck was. Stack enough of those and the plaza falls out.

Steps (unchanged from the original):
  1. for every debit, take the truck's pings within +-10 seconds of the debit time
  2. round the points to 3 decimals (~110 m cells) and keep only the most common cell,
     which throws away pings from trucks that were still approaching or already past
  3. K-Means with one cluster on what is left; the centre is the plaza location
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans


def pings_around(pings, vehicle_id, t, window=10):
    p = pings[(pings.vehicleId == vehicle_id) & (pings.time >= t - window) & (pings.time <= t + window)]
    return p


def plaza_centroid(plazacode, debits, pings, max_debits=200):
    try:
        d = debits[debits['plazacode'] == str(plazacode)].head(max_debits)
        data_lat_longs = pd.concat([pings_around(pings, r.vehicle_id, r.time) for r in d.itertuples()])
        if data_lat_longs.empty:
            return None
        data_lat_longs = data_lat_longs.copy()
        data_lat_longs[['longitude', 'latitude']] = pd.DataFrame(data_lat_longs.location.values.tolist(),
                                                                 index=data_lat_longs.index)
        data_lat_longs['latitude'] = data_lat_longs['latitude'].round(3)
        data_lat_longs['longitude'] = data_lat_longs['longitude'].round(3)
        data_lat_longs['loc_str'] = data_lat_longs.apply(
            lambda row: str(int(row['latitude'] * 1000)) + str(int(row['longitude'] * 1000)), axis=1)
        data_lat_longs = data_lat_longs[data_lat_longs['loc_str'] == data_lat_longs['loc_str'].value_counts().idxmax()]
        X = np.array(data_lat_longs['location'].tolist())
        kmeans = KMeans(n_clusters=1, init='k-means++', n_init=10, random_state=0)
        kmeans.fit_predict(X)
        lon, lat = kmeans.cluster_centers_[0]
        return [plazacode, lat, lon, len(d), len(X)]
    except Exception as e:
        print(e)
        return None


def locate_all(debits, pings):
    rows = [plaza_centroid(c, debits, pings) for c in debits['plazacode'].unique()]
    rows = [r for r in rows if r]
    return pd.DataFrame(rows, columns=['plaza_code', 'latitude', 'longitude', 'debits_used', 'pings_used'])
