# HAIMOS Market Physics Engine v1.0 Architecture

Status: **Frozen baseline**  
Release tag: `digital-twin-v1.0`  
Verification scope: **Verified against AEMO C2024Q4**

## Purpose
This document is the architectural contract for the verified baseline.  
It defines what each layer is responsible for, what it must not do, and what future work must preserve.

## Layered Contract

### Layer 1 — Raw AEMO Data
**Responsibility**
- Acquire authoritative AEMO source files.
- Preserve raw payload fidelity and source timestamps.
- Maintain provenance and source identity.

**Must not**
- Apply modeling assumptions.
- Inject synthetic business values.

---

### Layer 2 — Market State Database
**Responsibility**
- Normalize raw datasets into canonical interval-level structures.
- Maintain deterministic schema and lineage.
- Support reproducible point-in-time replay inputs.

**Must not**
- Perform forecasting.
- Encode investment decisions.

---

### Layer 3 — Digital Twin
**Responsibility**
- Reconstruct historical market mechanics from Layer 2.
- Reproduce authoritative IRSR and SRA settlement outputs for verified scopes.
- Provide deterministic reconciliation evidence.

**Current baseline**
- `digital-twin-v1.0` verified against AEMO for `C2024Q4`.

**Must not**
- Use future information in replay.
- Blend simulation with predictive assumptions.

---

### Layer 4 — Forecast Engine
**Responsibility**
- Estimate future state variables using point-in-time-safe information only.
- Produce explicit uncertainty and assumptions.

**Status**
- Not proven in v1 baseline.

---

### Layer 5 — Valuation Engine
**Responsibility**
- Convert forecast outputs into product-level valuation metrics.
- Preserve clear separation between forecast and realised outcomes.

---

### Layer 6 — Investment Engine
**Responsibility**
- Apply decision rules, bid logic, capital constraints, and risk controls.
- Output auditable decision rationales.

---

### Layer 7 — Execution / Portfolio
**Responsibility**
- Simulate or execute portfolio construction, lifecycle management, and P&L accounting.
- Track realized returns and risk metrics.

## Invariants for v1 Freeze
- Settlement mechanics and reconciliation behavior are frozen to the verified baseline.
- Point-in-time integrity is non-negotiable.
- Any layer above Digital Twin must not mutate or reinterpret verified settlement logic.
- Any exception handling must be scoped, auditable, and explicitly documented.

## Transition Principle: v1 → v2
- **v1 answers:** “What happened?”
- **v2 answers:** “What is likely to happen?”

These are different scientific tasks.  
All v2 work must treat v1 as immutable reference physics.
