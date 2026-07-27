# EXTERNAL DRIVER GAP REGISTER

**Stage 2A: External Dataset Assessment and Prioritisation**

**Created:** 2026-07-27
**Status:** IN PROGRESS
**Phase:** Gap identification, source verification, priority scoring

---

## EXECUTIVE SUMMARY

This register identifies, ranks and assesses every external dataset that may materially improve congestion explanation, price-spread forecasting, IRSR/SRA forecasting, and investment decision-making across the NEM.

**Register Structure:**
- dataset_id: unique identifier
- dataset_name: human-readable name
- dataset_family: category (calendar, FCAS, generator, weather, etc.)
- physical_mechanism: how it influences electricity market dynamics
- commercial_relevance: what investment outcome it enables
- target_outcomes: specific SRA/market phenomena it informs
- authoritative_source: primary data provider
- source_url: API, archive, or download path
- historical_coverage: date range available
- update_frequency: publication cadence
- spatial_granularity: regional/station/point-level
- temporal_granularity: 5-min/30-min/hourly/daily
- pit_timestamp_available: whether exact PIT can be determined
- pit_safe_status: SAFE / UNSAFE / CONDITIONAL
- join_keys: interval_timestamp, region, asset_id, etc.
- licence_access: open / restricted / commercial
- estimated_storage_mb: uncompressed monthly size
- acquisition_effort: hours to source and verify
- validation_effort: hours to build one-month validator
- expected_information_gain: low / medium / high
- expected_commercial_impact: low / medium / high / critical
- current_coverage: data available in repository
- blocker: technical, legal, or access barrier if any
- priority_score: computed ranking
- recommended_action: INCLUDE_NOW / INCLUDE_AFTER / DEFER / MONITOR / REJECT

---

## DATASET FAMILIES UNDER ASSESSMENT

### Family 1: PUBLIC HOLIDAYS AND CALENDAR STATE

**Purpose:** Region-specific deterministic calendar features that influence demand, bidding strategy, and interconnector flows.

#### Assessment

| Aspect | Status | Details |
|--------|--------|---------|
| Source Identified | ✓ | Australian Bureau of Statistics, State Government websites, NSWPF Public Holiday Calendar |
| Historical Coverage | ✓ | National holidays: 2000–present; State holidays: 2000–present |
| API Available | ✓ | Multiple sources (no single authoritative API; requires web scraping or manual curation) |
| PIT Safe | ✓ | Calendar dates are deterministic and known in advance |
| License | ✓ | Public domain / CC-BY 4.0 |
| Effort to Source | ✓ | LOW (1–2 hours; mostly curated historical records) |
| Join Key | ✓ | observation_date (5-min interval date component) |
| Expected Info Gain | ✓ | HIGH (calendar dominates short-term demand patterns) |
| Commercial Impact | ✓ | CRITICAL (affects bid strategy, interconnector flows, intervention probability) |

**Datasets:**
1. **AUS_CALENDAR_NATIONAL_PUBLIC_HOLIDAYS** – National public holidays (1 Jan, 25 Apr, 25 Dec, 1 Jan, 26 Jan observed, etc.)
   - Source: Australian Bureau of Statistics (ABS)
   - URL: https://www.abs.gov.au/
   - Coverage: 1950–present
   - Granularity: national (apply to all NEM regions as baseline)
   - PIT: 100% deterministic

2. **AUS_CALENDAR_NSW_PUBLIC_HOLIDAYS** – NSW-specific holidays
   - Source: nsw.gov.au, NSW Public Holidays
   - URL: https://www.nsw.gov.au/
   - Coverage: 1950–present
   - Granularity: NSW1 region
   - PIT: 100% deterministic
   - Notes: Includes Easter Monday, Anzac Day, Queen's Birthday

3. **AUS_CALENDAR_QLD_PUBLIC_HOLIDAYS** – QLD-specific holidays
   - Source: qld.gov.au, Queensland Government
   - URL: https://www.qld.gov.au/
   - Coverage: 1950–present
   - Granularity: QLD1 region
   - PIT: 100% deterministic

4. **AUS_CALENDAR_VIC_PUBLIC_HOLIDAYS** – VIC-specific holidays
   - Source: vic.gov.au, Victoria Government
   - URL: https://www.vic.gov.au/
   - Coverage: 1950–present
   - Granularity: VIC1 region
   - PIT: 100% deterministic

5. **AUS_CALENDAR_SA_PUBLIC_HOLIDAYS** – SA-specific holidays
   - Source: sa.gov.au, South Australia Government
   - URL: https://www.sa.gov.au/
   - Coverage: 1950–present
   - Granularity: SA1 region
   - PIT: 100% deterministic

6. **AUS_CALENDAR_TAS_PUBLIC_HOLIDAYS** – TAS-specific holidays
   - Source: tas.gov.au, Tasmania Government
   - URL: https://www.tas.gov.au/
   - Coverage: 1950–present
   - Granularity: TAS1 region
   - PIT: 100% deterministic

7. **AUS_CALENDAR_SCHOOL_HOLIDAYS** – State school holiday calendars
   - Source: Department of Education (each state)
   - Coverage: 1980–present (not all states have digital historical records)
   - Granularity: state-level
   - Notes: NSW, VIC, QLD have reliable digital records; SA, TAS, WA available but scattered
   - Blocker: TAS and WA school holiday data may require manual curation

8. **AUS_CALENDAR_WEEKENDS_BUSINESS_DAYS** – Structural calendar features
   - Derived from observation_timestamp
   - Features: is_weekday, is_saturday, is_sunday, days_since_friday, days_to_monday, etc.
   - PIT: 100% deterministic

9. **AUS_CALENDAR_DAYLIGHT_SAVING_TRANSITIONS** – DST boundaries
   - NSW, VIC, SA, TAS, QLD (regional)
   - Coverage: 1971–present
   - Granularity: state-level
   - Source: Australian Department of Infrastructure

10. **AUS_CALENDAR_FINANCIAL_YEAR** – FY1 (Jul–Jun) indicators
    - Derived from month
    - Features: is_fy_start_q, is_fy_mid_q, is_fy_end_q, fy_number
    - PIT: 100% deterministic

**Storage Estimate:** ~2 MB (compressed CSV)
**Effort:** 1–2 hours to curate and validate
**Priority Score:** CRITICAL (deterministic, high info gain, no external dependency)

---

### Family 2: FCAS PRICES AND ENABLEMENT

**Purpose:** Frequency Control Ancillary Services pricing and availability, which directly influences bidding and interconnector opportunity cost.

#### Assessment

| Aspect | Status | Details |
|--------|--------|---------|
| Source Identified | ✓ | AEMO Public Data Hub, MMS, NEM-Review, NEMWEB |
| Historical Coverage | ? | FCAS pricing: Feb 2015–present; FCAS enablement: partial (2019–present) |
| API Available | ✓ | NEMWEB tables (FCAS_PRICES, FCAS_AVAILABILITY) |
| PIT Safe | ✓ | Published post-dispatch (known by dispatch_end_time + 10 min) |
| License | ✓ | Public – AEMO open data |
| Effort to Source | ✓ | MEDIUM (3–4 hours; requires NEMWEB scraping and MMSDM lookup) |
| Join Key | ✓ | interval_timestamp, service_type (regulation/contingency), service_class (6s/60s/5m) |
| Expected Info Gain | ✓ | HIGH (FCAS often binding, influences bids and interconnector flows) |
| Commercial Impact | ✓ | CRITICAL (affects SRA fair value, transmission congestion) |

**Datasets:**
1. **AEMO_FCAS_PRICES** – Historical FCAS causer-pays pricing
   - Source: NEMWEB, table FCAS_PRICES
   - URL: https://www.nemweb.com.au/ (download via MMSDM monthly bundles)
   - Table/API: FCAS_PRICES (or PRICE_SET in MMS)
   - Historical: Feb 2015–present
   - Granularity: service type (regulation raise/lower, contingency raise/lower, fast-raise)
   - Temporal: 5-minute interval prices
   - PIT: dispatch_datetime + 10 min (post-dispatch)
   - Schema: date, regionid, fcas_type, price, units ($/service)
   - Blocker: Table name varies across MMSDM versions; requires schema mapping

2. **AEMO_FCAS_ENABLEMENT_BY_DUID** – FCAS capability by generating unit
   - Source: NEMWEB, UIGF tables, Unit Commitment tables
   - Table: FCAS_AVAILABILITY, UNIT_SCADA (related) or derived from BIDS
   - Historical: 2019–present (partial; earlier data may require reconstruction from BIDS)
   - Granularity: per DUID
   - Temporal: 5-minute
   - PIT: dispatch_end_time + 5 min
   - Schema: date, duid, fcas_lower_reg, fcas_upper_reg, fcas_contingency, units (MW)
   - Blocker: Pre-2019 data requires bid reconstruction

3. **AEMO_FCAS_RESERVE_CONDITIONS** – LOR events, administered pricing triggers
   - Source: AEMO website, System Operation Reports
   - URL: https://www.aemo.com.au/operational-toolbox/system-operation
   - Historical: 2006–present
   - Granularity: NEM-wide (event-level)
   - PIT: published post-event (typically +1 day)
   - Blocker: Data is semi-structured (PDF reports, not machine-readable tables)

**Storage Estimate:** ~50 MB (5-min FCAS prices, Feb 2015–present)
**Effort:** 3–4 hours (NEMWEB navigation + schema confirmation)
**Priority Score:** HIGH (direct influence on SRA payout, high info gain)

---

### Family 3: GENERATOR AVAILABILITY AND OUTAGES

**Purpose:** Unit-level availability, outage status, and ramp-rate changes that influence congestion and bidding.

#### Assessment

| Aspect | Status | Details |
|--------|--------|---------|
| Source Identified | ✓ | AEMO PASA, UIGF, Unit Commitment, Outage Schedule reports |
| Historical Coverage | ✓ | PASA (3.5y forward): 2015–present; Availability data: 2010–present |
| API Available | ✓ | NEMWEB tables (UNIT_SCADA, INTERCONNECTOR_RESULTS, PARTICIPANT_REGISTRATION) |
| PIT Safe | ✓ | CONDITIONAL (some data published post-dispatch, some forecast) |
| License | ✓ | Public – AEMO |
| Effort to Source | ✓ | MEDIUM-HIGH (4–6 hours; multiple tables, schema versioning) |
| Join Key | ✓ | interval_timestamp, duid |
| Expected Info Gain | ✓ | HIGH (outages create congestion, influence bids) |
| Commercial Impact | ✓ | HIGH (affects congestion probability, SRA payout timing) |

**Datasets:**
1. **AEMO_PASA_AVAILABILITY** – PASA maximum capacity and ramp-rate bids
   - Source: NEMWEB, PASA_CONSTRAINTS or UNIT_COMMITMENT tables
   - Table: PASA_CONSTRAINTS, UNIT_COMMITMENT
   - Historical: 2010–present (PASA runs started in 2010)
   - Granularity: per DUID
   - Temporal: 30-min or hourly (published daily for next 7 days)
   - PIT: published day-ahead (known by 0600 AEST for next day)
   - Schema: datetime, duid, max_avail, min_stable, ramp_up, ramp_down
   - Blocker: Historical PASA runs may not be archived for all DUIDs; requires MMSDM deep-dive

2. **AEMO_UNIT_SCADA_REAL_OUTPUT** – Realized unit output vs availability
   - Source: NEMWEB, table UNIT_SCADA
   - Table: UNIT_SCADA
   - Historical: 2010–present
   - Granularity: 5-minute per DUID
   - Schema: timestamp, duid, scada_value (MW), units
   - PIT: dispatch_datetime + 10 min (post-dispatch)
   - Usage: availability_ratio = scada_value / pasa_max

3. **AEMO_OUTAGE_SCHEDULE** – Planned and forced outages
   - Source: AEMO Outage Schedule (web portal + emails)
   - URL: https://www.aemo.com.au/ (manual reports, not APIs)
   - Historical: 2005–present (partial; recent years more complete)
   - Granularity: per unit, event-level
   - PIT: announced outages are known in advance (known by planning phase)
   - Blocker: Historical outage data is semi-structured (emails, PDFs, manual records); no unified database

4. **AEMO_GENERATOR_REGISTRATION** – Commissioning dates, retirement dates, fuel types
   - Source: AEMO Registered Generator List, NEMWEB GENCONDATA
   - URL: https://www.aemo.com.au/
   - Historical: 1995–present (registration dates)
   - Granularity: per DUID
   - Schema: duid, fuel_type, commissioning_date, retirement_date, status
   - PIT: static (registration data)
   - Usage: filter to active generators, identify mothballed units

5. **AEMO_UIGF** – Unit Initial Generation Forecast (UIGF)
   - Source: NEMWEB, UIGF_UNIT_LEVEL or DISPATCH_UNIT_LEVEL tables
   - Historical: 2015–present
   - Granularity: per DUID
   - Temporal: 5-minute forecast for next 40+ hours
   - PIT: published at dispatch interval t for intervals t to t+40h
   - Schema: datetime, duid, uigf_mw
   - Blocker: Requires forward-looking joins; increases complexity

**Storage Estimate:** ~100 MB (UNIT_SCADA + PASA availability, 2010–present)
**Effort:** 4–6 hours (multiple tables, schema verification)
**Priority Score:** HIGH (major driver of congestion and outage-induced spreads)

---

### Family 4: DETAILED GENERIC CONSTRAINTS

**Purpose:** Constraint definitions, RHS/LHS, binding frequency, and marginal values that directly explain interconnector flows and congestion.

#### Assessment

| Aspect | Status | Details |
|--------|--------|---------|
| Source Identified | ✓ | NEMWEB, MMS GENCONDATA, DISPATCHCONSTRAINT tables |
| Historical Coverage | ✓ | Constraint definitions: 2005–present; Marginal values: 2010–present |
| API Available | ✓ | NEMWEB tables (DISPATCHCONSTRAINT, GENCONDATA, CONSTRAINT_SUMMARY) |
| PIT Safe | ✓ | Post-dispatch only (marginal values published +10 min) |
| License | ✓ | Public – AEMO |
| Effort to Source | ✓ | MEDIUM-HIGH (4–5 hours; complex schema) |
| Join Key | ✓ | interval_timestamp, constraint_id, region |
| Expected Info Gain | ✓ | CRITICAL (constraints ARE the congestion mechanism) |
| Commercial Impact | ✓ | CRITICAL (directly explains interconnector flows, SRA payouts) |

**Datasets:**
1. **AEMO_DISPATCHCONSTRAINT_MARGINAL_VALUES** – Constraint marginal factors ($ per MW)
   - Source: NEMWEB, table DISPATCHCONSTRAINT
   - Historical: 2010–present
   - Granularity: 5-minute per constraint_id
   - Schema: datetime, constraint_id, rhs, lhs, marginal_value, binding_flag
   - PIT: dispatch_datetime + 10 min
   - Usage: identifies which constraints bind in each interval

2. **AEMO_GENCONDATA_CONSTRAINT_DEFINITIONS** – GENCON static data
   - Source: NEMWEB, table GENCONDATA
   - Historical: 2005–present
   - Granularity: per constraint_id (static)
   - Schema: constraint_id, constraint_description, constraint_type, lhs_constant, rhs_constant
   - PIT: static (constraint definitions don't change frequently)
   - Usage: maps constraint_id to English description

3. **AEMO_CONSTRAINT_BINDING_FREQUENCY** – Statistical summary of binding events
   - Derived: aggregate DISPATCHCONSTRAINT.binding_flag over monthly windows
   - Usage: identifies which constraints are frequently binding (material to congestion)

**Storage Estimate:** ~200 MB (5-min constraint marginal values, 2010–present; ~10,000 constraint_ids)
**Effort:** 4–5 hours (schema deep-dive, constraint_id mapping)
**Priority Score:** CRITICAL (constraints ARE congestion; essential for SRA fair value)

---

### Family 5: NETWORK OUTAGES AND TOPOLOGY STATE

**Purpose:** Transmission line outages and topology changes that alter congestion patterns and constraint effectiveness.

#### Assessment

| Aspect | Status | Details |
|--------|--------|---------|
| Source Identified | ~ | AEMO Outage Schedule (interconnectors), NEMWEB constraint changes |
| Historical Coverage | ~ | Recent: 2015–present; Historical: incomplete |
| API Available | ~ | Semi-structured (AEMO reports, web scraping possible) |
| PIT Safe | ✓ | CONDITIONAL (announced outages known in advance; unexpected faults not) |
| License | ✓ | Public |
| Effort to Source | ⚠ | HIGH (6–8 hours; requires manual curation or web scraping) |
| Join Key | ✓ | interval_timestamp, interconnector_id or line_id |
| Expected Info Gain | ✓ | HIGH (outages explain congestion and constraint changes) |
| Commercial Impact | ✓ | HIGH (affects SRA payout magnitude and timing) |

**Datasets:**
1. **AEMO_PLANNED_TRANSMISSION_OUTAGES** – Scheduled maintenance on major interconnectors
   - Source: AEMO Outage Schedule (web portal)
   - URL: https://www.aemo.com.au/ (manual, email-based distribution)
   - Historical: 2010–present (partial; recent years more complete)
   - Granularity: per interconnector or transmission line
   - Blocker: Not machine-readable; requires manual curation or OCR

2. **AEMO_CONSTRAINT_CHANGES_DUE_TO_OUTAGES** – Constraint RHS/LHS changes
   - Source: Inferred from DISPATCHCONSTRAINT RHS changes linked to outage dates
   - Derived: Compare constraint definitions across outage periods
   - Blocker: Requires manual audit to confirm causal link

3. **AEMO_INTERCONNECTOR_UPGRADES** – Major topology changes (e.g., HVDC commissioning)
   - Source: AEMO Strategic Reports, Network Development Plans
   - URL: https://www.aemo.com.au/
   - Historical: 2005–present
   - Blocker: Data is qualitative; requires manual annotation of effective dates

**Storage Estimate:** ~5 MB (event-level records, sparse)
**Effort:** 6–8 hours (web scraping, manual curation, causal audit)
**Priority Score:** MEDIUM-HIGH (high info gain; effort required for curation)
**Blocker:** Data requires significant manual curation; recommend deferring until Priority 1–3 complete

---

### Family 6: DUID-LEVEL SCADA AND GENERATION MIX

**Purpose:** Real-time unit output by fuel type, aggregated to regional generation mix (coal vs gas vs renewables vs hydro vs battery).

#### Assessment

| Aspect | Status | Details |
|--------|--------|---------|
| Source Identified | ✓ | NEMWEB UNIT_SCADA, PARTICIPANT_REGISTRATION (fuel type map) |
| Historical Coverage | ✓ | 2010–present |
| API Available | ✓ | NEMWEB tables |
| PIT Safe | ✓ | Post-dispatch (+10 min) |
| License | ✓ | Public – AEMO |
| Effort to Source | ✓ | MEDIUM (2–3 hours; already partially ingested in historical FS) |
| Join Key | ✓ | interval_timestamp, duid, region |
| Expected Info Gain | ✓ | HIGH (generation mix drives price and interconnector flows) |
| Commercial Impact | ✓ | CRITICAL (fundamental to demand/supply balance) |

**Datasets:**
1. **AEMO_UNIT_SCADA_AGGREGATED_BY_FUEL** – Regional generation by fuel type
   - Source: NEMWEB UNIT_SCADA + PARTICIPANT_REGISTRATION
   - Derived: Group UNIT_SCADA by fuel_type (from PARTICIPANT_REGISTRATION)
   - Historical: 2010–present
   - Granularity: 5-minute per region per fuel type
   - Schema: datetime, region, fuel_type, total_mw
   - Fuel types: COAL, GAS, HYDRO, WIND, SOLAR, BATTERY, OIL, BIOMASS, Other
   - PIT: post-dispatch (+10 min)

2. **AEMO_RENEWABLE_PENETRATION** – Renewable generation as % of total
   - Derived: (wind + solar) / total_generation
   - Historical: 2010–present
   - Granularity: 5-minute per region
   - Usage: proxy for grid stability, RoCoF risk

3. **AEMO_BATTERY_CHARGE_STATE** – Battery charging/discharging mode (if available via BIDS or UNIT_SCADA)
   - Source: NEMWEB UNIT_SCADA (charge modes detected by negative ramp or negative output)
   - Blocker: Requires intra-hour trajectory data to confirm charging mode; SCADA alone insufficient

**Storage Estimate:** ~30 MB (regional fuel-type aggregates, 2010–present)
**Effort:** 2–3 hours (leverage existing UNIT_SCADA ingestion)
**Priority Score:** CRITICAL (generation mix is fundamental driver of price and congestion)

---

### Family 7: WEATHER

**Purpose:** Temperature, wind, solar irradiance, rainfall, and severe-weather indicators that influence demand and renewable output.

#### Assessment

| Aspect | Status | Details |
|--------|--------|---------|
| Source Identified | ✓ | Australian Bureau of Meteorology (BOM), ECMWF, OpenWeatherMap |
| Historical Coverage | ✓ | BOM: 1910–present; ECMWF: 1979–present |
| API Available | ✓ | BOM Data API, OpenWeatherMap API |
| PIT Safe | ✓ | CONDITIONAL (observations are final; forecasts vary) |
| License | ✓ | BOM: CC-BY 4.0; ECMWF: restricted (requires subscription) |
| Effort to Source | ✓ | MEDIUM (3–4 hours; BOM API navigation) |
| Join Key | ✓ | interval_timestamp, station_id or lat/lon |
| Expected Info Gain | ✓ | HIGH (weather drives demand and renewable output) |
| Commercial Impact | ✓ | HIGH (affects demand forecasts, renewable output, congestion patterns) |

**Datasets:**
1. **BOM_TEMPERATURE_OBSERVATIONS** – Daily max/min temperature by region
   - Source: Bureau of Meteorology, Climate Data Online
   - URL: http://www.bom.gov.au/climate/data/
   - API: http://www.bom.gov.au/climate/data-services/
   - Historical: 1910–present
   - Granularity: daily per station (interpolate to 5-min for feature store)
   - Spatial: major regional centres (Sydney, Melbourne, Brisbane, Adelaide, Hobart, Canberra)
   - Schema: date, station_id, temp_max_c, temp_min_c, temp_mean_c
   - PIT: published daily at 0900 AEST

2. **BOM_WIND_SPEED_OBSERVATIONS** – Wind speed and direction
   - Source: BOM Climate Data Online
   - URL: http://www.bom.gov.au/climate/data/
   - Historical: 1970–present
   - Granularity: 3-hourly or daily (major stations only)
   - Blocker: 5-minute wind data not routinely available from BOM; requires ECMWF or commercial provider

3. **BOM_SOLAR_IRRADIANCE** – Global Horizontal Irradiance (GHI)
   - Source: BOM Solar Data, ECMWF reanalysis
   - URL: http://www.bom.gov.au/climate/data/
   - Historical: 1990–present (BOM); 1979–present (ECMWF)
   - Granularity: daily (BOM); 3-hourly (ECMWF)
   - Blocker: BOM data is limited; ECMWF requires API key (commercial)

4. **BOM_RAINFALL_OBSERVATIONS** – Daily rainfall
   - Source: BOM Climate Data Online
   - Historical: 1910–present
   - Granularity: daily per station
   - Usage: proxy for hydrology, flooding risk

5. **BOM_HEATWAVE_INDICATORS** – Apparent temperature, heat index
   - Source: derived from BOM temperature + humidity
   - Usage: identify periods of extreme demand (air-conditioner load)

6. **BOM_SEVERE_WEATHER_ALERTS** – Cyclone, thunderstorm, extreme-wind warnings
   - Source: BOM Severe Weather Warnings (RSS feed)
   - URL: http://www.bom.gov.au/
   - Historical: 2010–present (RSS archive)
   - Granularity: event-level per region
   - PIT: issued in real-time

**Storage Estimate:** ~50 MB (daily BOM observations, 1910–present; aggregated to regions)
**Effort:** 3–4 hours (BOM API navigation, spatial interpolation)
**Priority Score:** HIGH (weather drives demand and renewable output; high commercial impact)

---

### Family 8: DEMAND STATE AND DEMAND ANOMALIES

**Purpose:** Load forecasts, demand revisions, and demand-side participation that influence interconnector flows.

#### Assessment

| Aspect | Status | Details |
|--------|--------|---------|
| Source Identified | ✓ | AEMO DEMAND_FORECAST, DISPATCHLOAD tables |
| Historical Coverage | ✓ | 2010–present |
| API Available | ✓ | NEMWEB tables |
| PIT Safe | ✓ | CONDITIONAL (forecast updates at each dispatch interval) |
| License | ✓ | Public – AEMO |
| Effort to Source | ✓ | MEDIUM (2–3 hours; standard NEMWEB download) |
| Join Key | ✓ | interval_timestamp, region |
| Expected Info Gain | ✓ | HIGH (demand is half the supply/demand balance) |
| Commercial Impact | ✓ | CRITICAL (affects interconnector flows, SRA payouts) |

**Datasets:**
1. **AEMO_DISPATCHLOAD** – Actual demand by region (semi-scheduled + scheduled)
   - Source: NEMWEB table DISPATCHLOAD
   - Historical: 2010–present
   - Granularity: 5-minute per region (NSW1, QLD1, VIC1, SA1, TAS1)
   - Schema: timestamp, region, total_demand_mw
   - PIT: dispatch_datetime + 10 min
   - Note: Includes semi-scheduled generation offset (e.g., rooftop PV curtailment effect)

2. **AEMO_DEMAND_FORECAST** – AEMO's 40+ hour demand forecast
   - Source: NEMWEB table DISPATCHLOAD or DEMAND_FORECAST
   - Historical: 2010–present
   - Granularity: 5-minute per region
   - Temporal: published every 5 min for next 40+ hours
   - PIT: published at dispatch interval t for intervals t to t+40h
   - Usage: compare forecast vs actual to identify forecast error, demand-side surprises

3. **AEMO_DEMAND_REVISION_INDEX** – Cumulative demand forecast revisions
   - Derived: Compare demand_forecast(t, for_time=T) across t for fixed T
   - Usage: track how demand expectations evolve over 24h leading window

4. **AEMO_DEMAND_RESPONSE_PARTICIPATION** – Interruptible load, DMIS participation
   - Source: AEMO reports, participant registrations
   - Historical: 2015–present
   - Blocker: Data is mostly qualitative; machine-readable version not readily available

**Storage Estimate:** ~30 MB (5-min demand, 2010–present; regional level)
**Effort:** 2–3 hours (standard NEMWEB download)
**Priority Score:** CRITICAL (demand is half of supply/demand balance; essential for SRA fair value)

---

### Family 9: STRUCTURAL AND REGIME-CHANGE INDICATORS

**Purpose:** Long-term structural shifts (renewable capacity growth, transmission upgrades, market rule changes) that alter baseline congestion patterns.

#### Assessment

| Aspect | Status | Details |
|--------|--------|---------|
| Source Identified | ~ | AEMO Capacity Reports, Network Development Plans, Gazette publications |
| Historical Coverage | ~ | 2000–present (fragmented) |
| API Available | ✗ | No; requires manual curation or web scraping |
| PIT Safe | ✓ | Static (announced changes are known in advance) |
| License | ✓ | Public |
| Effort to Source | ⚠ | HIGH (6–10 hours; requires manual research and annotation) |
| Join Key | ✓ | effective_date, region (optional) |
| Expected Info Gain | ✓ | MEDIUM-HIGH (explains multi-year trends) |
| Commercial Impact | ✓ | MEDIUM-HIGH (affects baseline congestion, SRA payout trends) |

**Datasets:**
1. **AEMO_RENEWABLE_CAPACITY_ADDITIONS** – New renewable generation commissioning
   - Source: AEMO Generation and Capacity Reports, Network Development Plans
   - URL: https://www.aemo.com.au/planning/forecasting-and-planning
   - Historical: 2000–present (estimates; recent years more accurate)
   - Granularity: per project or annual aggregate by region
   - Schema: effective_date, region, capacity_mw, technology (wind/solar/hydro/battery)
   - Blocker: Requires manual curation of commissioning dates from multiple sources

2. **AEMO_TRANSMISSION_UPGRADES** – Major transmission line upgrades and new interconnectors
   - Source: AEMO Network Development Plans, AER reports
   - URL: https://www.aemo.com.au/planning/forecasting-and-planning
   - Historical: 2000–present
   - Blocker: Requires manual identification of commissioning dates and impact on congestion

3. **NEM_MARKET_RULE_CHANGES** – Rule changes that affect bidding or dispatch
   - Source: Australian Energy Market Commission (AEMC), AER, AEMO
   - URL: https://www.aemc.gov.au/
   - Historical: 2000–present
   - Granularity: event-level (rule change effective date)
   - Schema: effective_date, rule_change_name, description, impact
   - Blocker: No machine-readable registry; requires manual research

4. **AUS_COAL_RETIREMENT_ANNOUNCEMENTS** – Coal power station retirement dates
   - Source: Press releases, ASX announcements, AEMO capacity reports
   - Historical: 2000–present
   - Granularity: per power station
   - Blocker: Requires manual curation; some dates are uncertain/flexible

5. **AUS_BATTERY_CAPACITY_ADDITIONS** – Battery energy storage system (BESS) commissioning
   - Source: AEMO Capacity Reports, ASX announcements
   - Historical: 2016–present (BESSs are recent)
   - Granularity: per BESS project
   - Schema: effective_date, duid, capacity_mw, location, technology (lithium/other)

**Storage Estimate:** ~1 MB (sparse event-level data)
**Effort:** 6–10 hours (research-heavy; manual annotation)
**Priority Score:** MEDIUM (useful for explaining multi-year trends; not immediately critical for next-month SRA forecasts)
**Blocker:** Data curation is labour-intensive; recommend deferring until Priority 1–4 complete

---

### Family 10: HYDROLOGY AND FUEL SUPPLY CONDITIONS

**Purpose:** Water storages, fuel costs (coal, gas), supply constraints that influence bidding and congestion.

#### Assessment

| Aspect | Status | Details |
|--------|--------|---------|
| Source Identified | ~ | BOM, AEMO, commodity exchanges, ASX |
| Historical Coverage | ~ | BOM storages: 1970–present; Fuel prices: 1990–present |
| API Available | ~ | BOM API (limited); Commodity data: third-party APIs (costly) |
| PIT Safe | ✓ | CONDITIONAL (storage levels final; fuel prices are real-time markets) |
| License | ~ | BOM: CC-BY 4.0; Commodity prices: commercial terms vary |
| Effort to Source | ⚠ | HIGH (4–6 hours; commodity data requires research) |
| Join Key | ✓ | interval_timestamp, region or facility_id |
| Expected Info Gain | ✓ | MEDIUM-HIGH (supply constraints influence bids) |
| Commercial Impact | ✓ | MEDIUM-HIGH (affects bidding strategy, SRA fair value) |

**Datasets:**
1. **BOM_RESERVOIR_STORAGE_LEVELS** – Water storage in major dams
   - Source: BOM Water Resources Data, Snowy Hydro reports
   - URL: http://www.bom.gov.au/water/
   - Historical: 1970–present
   - Granularity: weekly per major reservoir (Snowy, Blowering, Tumut, etc.)
   - Schema: date, reservoir_name, storage_ml, storage_pct
   - PIT: published weekly (known at end of reporting week)
   - Blocker: Different states use different reporting formats

2. **COAL_FUEL_PRICES** – Thermal coal spot prices
   - Source: IceWeatherLynch (Newcastle export prices), ASX commodity data
   - URL: https://www.asxenergyechange.com.au/ (futures); IceWeatherLynch (spot)
   - Historical: 1990–present (prices available)
   - Granularity: daily spot or weekly average
   - Blocker: Historical spot data requires subscription; ASX futures data is public but forward-looking only

3. **GAS_FUEL_PRICES** – Natural gas spot and futures prices
   - Source: ASX Energy Exchange (Australian Gas), Henry Hub (US reference), LNG spot prices
   - URL: https://www.asxenergyechange.com.au/
   - Historical: 2000–present (ASX Australian Gas futures)
   - Granularity: daily settlement prices
   - Blocker: Limited transparency in physical gas spot market; ASX futures data is forward-looking

4. **SNOWY_HYDRO_INFLOW_FORECASTS** – Inflow projections for major hydro systems
   - Source: Snowy Hydro reports, BOM weather forecasts
   - URL: https://www.snowyhydro.com.au/
   - Historical: 2010–present (forecast data; actual inflows reconstructible from storage)
   - Blocker: Forecast data not machine-readable; requires manual curation

**Storage Estimate:** ~10 MB (weekly storage, daily fuel prices, 1970–present)
**Effort:** 4–6 hours (commodity data research, BOM API navigation)
**Priority Score:** MEDIUM (useful for medium-term trends; less critical for 5-min congestion forecasting)
**Blocker:** Fuel price data requires subscription; storage data is public but semi-structured

---

### Family 11–20: ADDITIONAL CANDIDATE FAMILIES

Due to length constraints, additional families (DUID fuel-type aggregation, battery charge/discharge, renewable curtailment proxies, distributed solar, industrial load proxies, major recurring events, bridge days, pre/post-holiday indicators) are listed here with brief assessment:

**11. DUID FUEL-TYPE MAPPING & AGGREGATION**
- Status: PARTIALLY AVAILABLE (PARTICIPANT_REGISTRATION exists; aggregation needed)
- Effort: 1 hour
- Priority: HIGH

**12. BATTERY CHARGE/DISCHARGE PATTERNS**
- Status: Can be inferred from UNIT_SCADA (negative output = charging)
- Effort: 2 hours
- Priority: MEDIUM

**13. RENEWABLE CURTAILMENT PROXIES**
- Status: Requires UIGF comparison (forecast vs actual); limited historical data
- Effort: 3 hours
- Priority: MEDIUM

**14. ROOFTOP PV SEMI-SCHEDULED OFFSETS**
- Status: Embedded in DISPATCHLOAD; difficult to separate
- Effort: 4 hours (causal inference required)
- Priority: MEDIUM

**15. MAJOR INDUSTRIAL-LOAD PROXIES**
- Status: Not directly available; requires reverse-engineering from regional demand patterns
- Effort: 6 hours (causal inference + validation)
- Priority: LOW

**16. MAJOR RECURRING EVENTS** (sports, festivals, cultural events)
- Status: Not available; requires manual curation
- Effort: 5 hours
- Priority: LOW (unless calibrated to specific demand anomalies)

**17. SCHOOL HOLIDAYS** (previously listed in Family 1)
- Status: Available per state
- Effort: 1 hour
- Priority: HIGH

**18. BRIDGE DAYS & PRE/POST-HOLIDAY INDICATORS** (previously listed in Family 1)
- Status: Derived from calendar
- Effort: 0.5 hours
- Priority: MEDIUM

**19. DAYLIGHT-SAVING TRANSITIONS** (previously listed in Family 1)
- Status: Available, state-specific
- Effort: 0.5 hours
- Priority: MEDIUM

**20. INDUSTRIAL LOAD PARTICIPATION (DMIS)**
- Status: Limited availability; requires AEMO reports
- Effort: 3 hours
- Priority: LOW

---

## PROGRESS UPDATE

**Status:** Building gap register, sourcing verification in progress
**Families Assessed:** 10 (comprehensive); 11–20 (brief assessment)
**Datasets Identified:** 60+ candidate datasets
**Priority Families Emerging:** Calendar (CRITICAL), FCAS (HIGH), Generator availability (HIGH), Constraints (CRITICAL), Demand (CRITICAL), Generation mix (CRITICAL)
**Blockers Identified:** Network topology (curation-heavy), fuel prices (commercial), outage history (incomplete)
**Next:** Complete source verification, compute priority scores, rank families, return recommendations

