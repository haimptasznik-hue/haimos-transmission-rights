# Feature Store Data Dictionary

| Feature | Definition |
|---|---|
| interval_timestamp_utc | Canonical five-minute UTC interval timestamp. |
| dispatchregionsum_total_demand_mw | See source dataset-specific naming convention. |
| dispatchregionsum_nsw_demand_mw | See source dataset-specific naming convention. |
| dispatchregionsum_qld_demand_mw | See source dataset-specific naming convention. |
| dispatchregionsum_sa_demand_mw | See source dataset-specific naming convention. |
| dispatchregionsum_tas_demand_mw | See source dataset-specific naming convention. |
| dispatchregionsum_vic_demand_mw | See source dataset-specific naming convention. |
| dispatchinterconnectorres_interconnector_count | See source dataset-specific naming convention. |
| dispatchinterconnectorres_net_flow_mw | See source dataset-specific naming convention. |
| dispatchinterconnectorres_metered_flow_mw | See source dataset-specific naming convention. |
| dispatchinterconnectorres_total_abs_flow_mw | See source dataset-specific naming convention. |
| dispatchinterconnectorres_export_limit_mw | See source dataset-specific naming convention. |
| dispatchinterconnectorres_import_limit_mw | See source dataset-specific naming convention. |
| dispatchinterconnectorres_directional_limit_mw | See source dataset-specific naming convention. |
| dispatchinterconnectorres_utilisation_pct | See source dataset-specific naming convention. |
| dispatchinterconnectorres_over_limit_count | See source dataset-specific naming convention. |
| dispatchinterconnectorres_limit_invalid_count | See source dataset-specific naming convention. |
| dispatchinterconnectorres_latest_publication_timestamp | See source dataset-specific naming convention. |
| qni_flow_mw | See source dataset-specific naming convention. |
| qni_utilisation_pct | See source dataset-specific naming convention. |
| qni_directional_limit_mw | See source dataset-specific naming convention. |
| qni_over_limit_count | See source dataset-specific naming convention. |
| dispatchinterconnectorres_intervention1_excluded | See source dataset-specific naming convention. |
| dispatchinterconnectorres_intervention_pair_diff_count | See source dataset-specific naming convention. |
| observation_timestamp_utc | Time the physical market observation applies to. |
| effective_timestamp_utc | Effective time used for PIT-safe querying (currently interval timestamp). |
| publication_timestamp_utc | Latest known publication/change timestamp from source where available. |
| source | Primary source family for the interval record. |
| point_in_time_available | Boolean PIT-availability flag for canonical interval row. |
| quality_score | Interval-level non-null completeness score across feature columns (0-100). |
| lineage_hash | Deterministic hash of source file lineage used for this build. |
