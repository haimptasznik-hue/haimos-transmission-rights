# Phase 2: Feature Store Architecture & Dependency Graph

**Date**: 29 July 2026  
**Status**: Finalized post Phase 1C (Renewable Penetration v1.0 frozen)

---

## 1. Feature Store Dependency Hierarchy

```
AEMO Raw Data (SCADA, NEM data)
        │
        ▼
Historical Feature Store v1.0 (frozen, tagged)
        │
        ▼
Generator Master v1.0 (frozen, tagged)
        │
        ▼
Renewable Penetration Feature Store v1.0 (frozen, tagged)
        │
 ┌──────┼────────────┬────────────┬────────────┐
 ▼      ▼            ▼            ▼            ▼
Weather FCAS    Congestion   Emissions    Curtailment
Features Features Features    Features     Features
 │      │            │            │            │
 └──────────────┬────────────────┘            │
                ▼                             │
    Market Physics Feature Store  ◄───────────┘
          (Phase 2A)
                │
                ▼
    SRA Alpha Feature Store
          (Phase 2B)
                │
                ▼
    Regional Transmission Physics
       Models & Validation
          (Phase 2C)
                │
                ▼
    Market-Clearing & Trading Signals
          (Phase 2D)
```

---

## 2. Phase 1C Frozen Dependencies (Immutable Baselines)

### 2.1 Historical Feature Store v1.0
- **Status**: Frozen (tag: `historical-feature-store-v1.0`)
- **Time Resolution**: Daily aggregates
- **Temporal Coverage**: Historical AEMO data
- **Contract**: Versioned, reproducible from raw AEMO SCADA
- **Dependent Upon**: Generator Master v1.0

### 2.2 Generator Master v1.0
- **Status**: Frozen (tag: `generator-master-v1.0`)
- **Purpose**: DUID-to-Region-to-Fuel classification
- **Point-in-Time**: Current state (immutable snapshot)
- **Contract**: Generator classification locked; no backdating
- **Dependent Upon**: AEMO Generator Master raw data (2026-07 snapshot)

### 2.3 Renewable Penetration Feature Store v1.0
- **Status**: Frozen (tag: `renewable-penetration-v1.0`)
- **Canonical Dataset Hash**: `2d0943d8e0267d026c7d57a51cddf406a25ef89e913401c7dd75f90a1d08d5e1`
- **Hash Contract**: Version 1 (documented, machine-path independent)
- **Time Resolution**: Five-minute intervals
- **Temporal Coverage**: 2023-12 through 2024-07 (8 months)
- **Spatial Coverage**: 6 NEM regions
- **Checkpointing**: Month-by-month with completion markers
- **Checkpoint Reuse**: 8 completed, 8 reused, 0 written, 0 recomputed
- **Archive Formats**: CSV + Parquet (semantic parity proven)
- **PIT Scope**: CURRENT_STATE_ONLY (Generator Master v1.0 classification)
- **Features**:
  - `total_positive_generation_mw` – Total generation capacity online
  - `renewable_positive_generation_mw` – Renewable (wind + solar) generation
  - `matched_positive_generation_mw` – Renewable generation with matched DUID records
  - `unmatched_positive_generation_mw` – Renewable generation without DUID match
  - `renewable_penetration_pct` – Renewable % of total generation
  - `renewable_penetration_known_pct` – Renewable % of matched generation (more conservative)
  - `matched_generation_share_pct` – Proportion of generation with DUID matches
  - `renewable_unit_share_pct` – Renewable units as % of active units
  - `active_unit_count`, `renewable_active_unit_count`, etc.
  - `quality_score` – Data completeness/reliability metric
  - `point_in_time_available` – Generator Master PIT coverage flag

**Key Contract**: This feature store is the authoritative source for regional renewable penetration. All downstream models must reference this v1.0 dataset and its canonical hash; no modifications or re-derivations.

---

## 3. Phase 2A: Market Physics Feature Store

### 3.1 Weather Features (Phase 2A-i)
**Dependencies**: Renewable Penetration v1.0 + Bureau of Meteorology raw data  
**Purpose**: Wind speed, solar irradiance, temperature, cloud cover aligned to 5-min intervals  
**Contract**:
- Time-aligned to renewable penetration intervals (2023-12 to 2024-07)
- Machine learning-ready normalization (e.g., rolling z-score)
- Documented data sources and quality gates
- Seasonal/diurnal effects captured (not detrended)
- Versioned feature engineering pipeline

**Output**: `weather_features_v1.parquet` (time-aligned with renewable penetration v1.0)

### 3.2 FCAS Features (Phase 2A-ii)
**Dependencies**: Renewable Penetration v1.0 + AEMO FCAS raw data  
**Purpose**: Frequency Control Ancillary Services requirement proxies  
**Contract**:
- Aligned to renewable penetration intervals
- Derived from publicly available FCAS eligibility and historical callouts
- Documented methodology for synthetic FCAS estimation
- Versioned FCAS feature definitions

**Output**: `fcas_features_v1.parquet` (time-aligned)

### 3.3 Congestion Features (Phase 2A-iii)
**Dependencies**: Renewable Penetration v1.0 + NEM congestion pricing data  
**Purpose**: Regional interconnector flow proxies and congestion indicators  
**Contract**:
- Five-minute interval alignment
- Documented congestion thresholds per corridor
- Versioned corridor definitions (unchanged from Phase 1B)
- Handling of off-target periods

**Output**: `congestion_features_v1.parquet` (time-aligned)

### 3.4 Emissions Intensity Features (Phase 2A-iv)
**Dependencies**: Renewable Penetration v1.0 + Generator Master v1.0 + emission factors  
**Purpose**: Regional CO2 intensity proxy (tCO2/MWh equivalent)  
**Contract**:
- Derived from fuel classification (Generator Master v1.0)
- Renewable penetration incorporated (renewable = 0 emissions proxy)
- Documented emission factors per fuel type
- Versioned methodology for non-matched generators

**Output**: `emissions_intensity_features_v1.parquet` (time-aligned)

### 3.5 Curtailment Features (Phase 2A-v)
**Dependencies**: Renewable Penetration v1.0 + AEMO curtailment notices  
**Purpose**: Renewable curtailment probability and magnitude estimates  
**Contract**:
- Aligned to renewable penetration intervals
- Documented curtailment event definitions
- Seasonal and regional curtailment patterns captured
- Versioned curtailment forecasting methodology

**Output**: `curtailment_features_v1.parquet` (time-aligned)

---

## 4. Phase 2B: SRA Alpha Feature Store

**Dependencies**: All Phase 2A feature stores + Renewable Penetration v1.0  
**Purpose**: Aggregated market physics features for Stochastic Risk Analysis (SRA)  
**Contract**:
- Composite features combining weather, FCAS, congestion, emissions, curtailment
- Documented feature engineering (e.g., PCA, cross-features, lagged features)
- Train/validation/test split methodology (time-series aware)
- Documented alpha signal definitions and performance benchmarks
- Versioned backtesting framework

**Output**: `sra_alpha_features_v1.parquet` (time-aligned, with alpha signals)

---

## 5. Phase 2C: Regional Transmission Physics Models

**Dependencies**: Renewable Penetration v1.0 + Market Physics Feature Store v1.0  
**Purpose**: Physics-informed models for congestion, losses, stability  
**Contract**:
- Regional transmission topology (frozen at versioning point)
- Renewable penetration impact on system dynamics
- Documented model assumptions and validation gates
- Sensitivity analysis to generator classification (PIT lock)
- Versioned model checkpoints and prediction intervals

**Output**: Regional transmission physics models (e.g., neural networks, ODEs)

---

## 6. Phase 2D: Market-Clearing & Trading Signals

**Dependencies**: Renewable Penetration v1.0 + SRA Alpha Features v1.0 + Regional Physics Models v1.0  
**Purpose**: Real-time and forward-looking trading signal generation  
**Contract**:
- Documented signal generation logic (deterministic)
- Backtest results reproducible from Phase 2A–2C outputs
- Portfolio construction methodology
- Risk management and position limits
- Versioned signal versioning for rollback/comparison

**Output**: Trading signals, portfolio allocations, risk reports

---

## 7. Immutability & Versioning Rules

### 7.1 Phase 1C Freeze Policy
- **Renewable Penetration v1.0**: DO NOT modify
- **Generator Master v1.0**: DO NOT modify
- **Historical Feature Store v1.0**: DO NOT modify
- Any enhancements or corrections go into v2.0+ (new git branch, new tag)

### 7.2 Phase 2 Feature Store Versioning
- Each Phase 2 component is versioned independently (e.g., `weather_features_v2`, `fcas_features_v2`)
- Version increments only for material changes to feature definitions or engineering pipelines
- Canonical hashes documented for reproducibility (following Phase 1C precedent)
- Checkpoint reuse tracking for efficient re-derivation
- Regression tests for feature stability across versions

### 7.3 Backwards Compatibility
- Downstream models pinned to specific feature store versions
- Version mismatches detected at model training time (explicit contract violations)
- Migration path defined for version upgrades (e.g., retraining, cross-validation)

---

## 8. Deployment & Auditing

### 8.1 Reproducibility Checklist
- [ ] Feature store version explicitly specified in model config
- [ ] Canonical hash documented and verified before backtesting
- [ ] Checkpoint reuse evidence recorded (reused vs. recomputed)
- [ ] Semantic parity tests passing (e.g., CSV vs. Parquet)
- [ ] Documentation consistency across metadata, lineage, validation
- [ ] Regression tests passing (5+ tests per feature store)
- [ ] Hygiene scans clean (no secrets, temp files, absolute paths in artifacts)

### 8.2 Audit Trail
- Commit hashes and tags recorded in model configurations
- Feature store dependencies frozen at model training time
- Backtest results reproducible from frozen feature store versions
- Any generation changes require new feature store version + retraining

---

## 9. Example: Downstream Model Dependency

```python
# model_config.yaml
feature_store_versions:
  renewable_penetration: renewable-penetration-v1.0
  generator_master: generator-master-v1.0
  weather_features: weather-features-v1.0
  fcas_features: fcas-features-v1.0
  congestion_features: congestion-features-v1.0
  emissions_intensity: emissions-intensity-v1.0

canonical_hashes:
  renewable_penetration: "2d0943d8e0267d026c7d57a51cddf406a25ef89e913401c7dd75f90a1d08d5e1"
  weather_features: "to_be_computed_when_v1_0_released"
  ...

backtest_window:
  start: 2024-01-01  # Renewable Penetration v1.0 coverage
  end: 2024-07-31   # Renewable Penetration v1.0 coverage

training_params:
  validation_split: 0.2  # Time-series aware
  test_split: 0.1
  random_seed: 42

reproducibility_requirements:
  verified_canonical_hashes: true
  semantic_parity_tests_passing: true
  regression_tests_passing: true
  hygiene_scans_clean: true
  feature_store_versions_pinned: true
```

---

## 10. Handoff Summary

**Phase 1C delivered**:
- ✅ Immutable renewable penetration feature store with versioned hash contract
- ✅ Checkpoint reuse proven and documented
- ✅ Semantic parity across archive formats
- ✅ Regression tests covering path invariance and semantic identity
- ✅ Clear separation of canonical data, stable provenance, and mutable operational evidence
- ✅ Documentation synchronized across metadata, lineage, validation, and markdown

**Phase 2 priorities**:
1. Design and implement Phase 2A feature stores (weather, FCAS, congestion, emissions, curtailment)
2. Establish same versioning, hashing, and testing discipline for each Phase 2 component
3. Create composite feature store (Phase 2B) aggregating Phase 2A outputs
4. Develop transmission physics models (Phase 2C) validated against Phase 1B empirical results
5. Integrate into trading signal pipeline (Phase 2D) with explicit version pinning

---

## 11. References

- Phase 1C Final Report: `renewable-penetration-v1.0` tag and commit `ae25577`
- Hash Contract v1 Specification: `src/transmission_rights/services/aemo/regional_renewable_penetration_feature_store.py`
- Validation & Lineage: `data/derived/renewable_penetration_v1/RENEWABLE_PENETRATION_V1_VALIDATION.md`, `RENEWABLE_PENETRATION_V1_LINEAGE.md`
- Regression Tests: `tests/services/aemo/test_regional_renewable_penetration_feature_store.py`

---

**Prepared by**: Haim Ptasznik  
**Repository**: haimos-transmission-rights  
**Branch**: preservation/phase6-market-physics  
**Timestamp**: 2026-07-29
