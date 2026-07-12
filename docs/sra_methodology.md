# SRA Methodology

## Product definition

For this repository, an SRA product is modeled as:

- directional interconnector,
- unit category,
- relevant quarter,
- tranche context,
- allocation type,
- maximum units,
- unit proportion.

A unit is not a physical MW right. It is a proportional entitlement to accumulated IRSR for the relevant category and quarter.

## Core economic interpretation

Value depends on:

- expected regional price separation,
- expected directional notional flow,
- losses and counter-price effects,
- outage and constraint conditions,
- auction microstructure and liquidity.

## Lifecycle states

- bid drafted
- bid submitted
- allocated
- offered for cancellation
- cancelled
- assigned
- expired
- settled
- revised

## MVP methodology boundary

The initial implementation intentionally stops short of:

- automated auction submission,
- bilateral legal transfer execution,
- participant-specific prudential logic,
- legal interpretation of assignment eligibility.

## Worked example logic

If a category has 1,000 maximum units, each unit represents 0.1% of distributable IRSR. Holding 40 units represents 4.0% entitlement. If expected IRSR is $4,000,000, expected gross distribution is $160,000. Per-unit gross value is $4,000 before discounts and overlays.
