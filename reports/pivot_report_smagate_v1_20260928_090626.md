# Pivot Report: smagate_v1

**Generated**: 2026-09-28T09:06:26+00:00
**Source Strategy**: smagate_v1
**Recommendation**: pivot

---

## Stagnation Diagnosis

**Triggers Fired**: 1
**Score Trajectory**: [64]

- **tail_risk** [high]: Structural risk: max_drawdown_pct=59.3765% > 35%; Risk Management score=0 <= 5

---

## Pivot Proposals

### 1. pivot_smagate_v1_inv_tail_risk_statistical_pairs

**Technique**: assumption_inversion
**Target Archetype**: statistical_pairs
**Entry Family**: research_only

**What Changed**:
- signal: Inversion: risk -> tighten
- horizon: 112d -> 20d
- risk: stop 0.594 -> 0.04

**Why**: Reduce tail exposure

**Scores**: quality=0.85, novelty=0.91, combined=0.87

### 2. pivot_smagate_v1_inv_tail_risk_mean_reversion_pullback

**Technique**: assumption_inversion
**Target Archetype**: mean_reversion_pullback
**Entry Family**: research_only

**What Changed**:
- signal: Inversion: risk -> tighten
- horizon: 112d -> 7d
- risk: stop 0.594 -> 0.04

**Why**: Reduce tail exposure

**Scores**: quality=0.75, novelty=0.91, combined=0.81

### 3. pivot_smagate_v1_inv_tail_risk_event_driven_fade

**Technique**: assumption_inversion
**Target Archetype**: event_driven_fade
**Entry Family**: research_only

**What Changed**:
- signal: Inversion: risk -> tighten
- horizon: 112d -> 5d
- risk: stop 0.594 -> 0.04

**Why**: Reduce tail exposure

**Scores**: quality=0.70, novelty=0.91, combined=0.78

---

## Summary

| Rank | Proposal | Archetype | Combined | Category |
|------|----------|-----------|----------|----------|
| 1 | pivot_smagate_v1_inv_tail_risk_statistical_pairs | statistical_pairs | 0.87 | research_only |
| 2 | pivot_smagate_v1_inv_tail_risk_mean_reversion_pullback | mean_reversion_pullback | 0.81 | research_only |
| 3 | pivot_smagate_v1_inv_tail_risk_event_driven_fade | event_driven_fade | 0.78 | research_only |
