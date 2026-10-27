# Toll Cost Estimator

Work out what a truck's toll bill should be using only its GPS trail. Find where each toll plaza is using only FASTag debits and GPS pings.

Built in 2020 to 2022 for a fleet running FASTag and GPS products. Fares come from the public NHAI fare table. Everything else in this repo is synthetic.

## The problem

Tolls are one of the biggest running costs for a truck in India. Fleet owners wanted three things:

1. Before a trip: what will this route cost in tolls?
2. After a trip: was I charged right? Double debits and wrong-class charges were common.
3. For trucks with GPS but a FASTag from another provider: what did they likely spend?

All three need two facts. Where exactly is each toll plaza? And which plazas did this truck cross? Neither was available as clean data. The in-house plaza table had gaps, and public lists did not always match the plaza codes on FASTag transactions.

## How it works

**Step 1. Find the plazas.** Every FASTag debit says "this truck paid at plaza X at time T." If the same truck has GPS, the ping closest to time T says where it was. For each plaza:

1. take GPS pings within 10 seconds of each debit
2. round them to about 110 m cells and keep the busiest cell, which drops trucks that were still approaching or already past
3. run K-Means with one cluster on what is left; the centre is the plaza

**Step 2. Spot crossings on any GPS trail.** Keep the slow pings (under 20 km/h, since trucks queue at the booth). Match them to a plaza. Pings at the same plaza more than an hour apart count as separate crossings.

**Step 3. Price it.** Look up the fare for the truck's FASTag class. If the truck crosses the same plaza again within 24 hours, charge that leg at half fare. This matches the NHAI rule for return journeys. In the public fare table, the return fare is half the single fare at the median plaza.

## Results on synthetic data

`python demo.py` simulates 40 trucks on a fictional 700 km highway with 10 plazas. GPS noise, dropped pings and a toll-reader clock that is off by up to a minute are all built in. Fares are real NHAI fares for those plaza codes.

Plaza locations land within 8 m of the truth at the median, from about 60 debits each.

| Matching method | Crossings found | Median bill error | Trucks within 5% | Fleet total |
|---|---|---|---|---|
| Original: 2-decimal grid cell | 94% | 5.3% | 45% | -7.5% |
| Added: real distance, 400 m radius | 100% | 0.0% | 100% | -1.1% |

## What the numbers say

The grid method has a blind spot. It snaps each ping to a cell about 1.1 km wide and asks whether that cell holds a plaza. When a plaza sits near a cell edge, a truck queuing on the other side of the line lands in the next cell and the crossing is missed. Nothing looks wrong. The bill is just quietly low. Matching by real distance removes the edge problem.

The leftover 1.1% gap is not a matching problem. It comes from the half-fare shortcut. NHAI return fares are close to half, but not exactly half at every plaza. Using the fare table's own return column would close it. It is a small thing, but it is the kind of rounding a finance team will find before you do.

## Run it

```bash
pip install -r requirements.txt
python demo.py
pytest
```

## Repo layout

```
toll_estimator/
  plazas.py      plaza location from debits + pings (K-Means), ported from the original
  crossings.py   grid matching (original), radius matching (added), fare rule, NHAI coverage
  fares.py       loads the NHAI fare table, keeps the latest fee revision per plaza and class
  simulate.py    synthetic highway, trucks, pings and FASTag debits
data/
  nhai_toll_fares_2022_04.csv   public NHAI fee table (April 2022), cleaned
notebooks/original/              the real notebooks, cleaned (see the README inside)
```

## What changed from the original code

- Pings and debits come in as DataFrames instead of internal API and Redshift calls.
- The radius matcher and the comparison against true crossings are new.
- The fare table loader removes repeated fee revisions so each plaza and class has one price.

## Data and privacy

The fare table is public NHAI data (April 2022). Plaza codes and names in the demo are real so the fare lookup works, but their positions on the fictional highway are made up. Trucks, trips, pings and debits are all synthetic. The original notebooks had their outputs, credentials, hosts and vehicle IDs removed before upload.
