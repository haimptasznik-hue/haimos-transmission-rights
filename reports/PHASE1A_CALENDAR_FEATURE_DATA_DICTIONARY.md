# Phase 1A Calendar Feature Data Dictionary

- feature_definition_version: 2.0.0-regional

## Regional Calendar Columns (per region: nsw, qld, vic, sa, tas)

| Suffix | Description |
|---|---|
| local_timestamp | Region-local timezone timestamp derived from observation UTC |
| local_date | Region-local calendar date (YYYY-MM-DD) |
| local_hour | Region-local hour (0-23) |
| local_day_of_week | Region-local weekday number (Monday=0..Sunday=6) |
| weekend_flag | 1 if local day is Saturday/Sunday else 0 |
| business_day_flag | 1 if weekday and not public holiday else 0 |
| public_holiday_flag | 1 if region holiday applies on local date else 0 |
| public_holiday_name | Official holiday name for region/local date else empty |
| pre_holiday_flag | 1 if next local day is a region holiday else 0 |
| post_holiday_flag | 1 if prior local day is a region holiday else 0 |
| bridge_day_flag | 1 for working-day bridge between holidays else 0 |
| daylight_saving_flag | 1 if DST active in region at local timestamp else 0 |
| daylight_saving_transition_flag | 1 at DST offset transition intervals else 0 |
| Easter_period_flag | 1 if local date in Easter event window else 0 |
| Christmas_New_Year_period_flag | 1 if local date in Christmas/New Year window else 0 |
| working_day_count_in_month | Count of business days in region-local month |

## Metadata Columns

| Column | Description |
|---|---|
| calendar_feature_definition_version | Calendar feature schema version identifier |
| holiday_source_lineage | Holiday source lineage description |
| holiday_jurisdiction_lineage | Region-to-jurisdiction lineage mapping |