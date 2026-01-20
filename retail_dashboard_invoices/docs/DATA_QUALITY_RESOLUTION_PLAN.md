# Data Quality Issue Resolution Plan

## Document Purpose
Data science recommendations for handling identified calculation issues while preserving data meaningfulness and maximizing visibility.

**Author:** Data Science Team  
**Date:** January 20, 2026  
**Status:** Planning

---

## Executive Summary

Five data quality issues were identified during formula validation. This document provides statistically-sound resolution approaches that prioritize:
1. **Transparency** - Show all data, flag anomalies rather than hide them
2. **Accuracy** - Calculations reflect true business performance
3. **Interpretability** - Users understand what they're seeing

---

## Issue Resolution Matrix

| ID | Issue | Severity | Resolution Strategy | Impact |
|----|-------|----------|---------------------|--------|
| 1 | Collection Rate Edge Cases | LOW | Display "N/A" + exclude from aggregates | Minimal |
| 2 | Negative Balance Logic | MEDIUM | Segment by balance type | Moderate |
| 3 | Percentile Ties | LOW | Secondary sort criteria | Minimal |
| 4 | Small Sample Percentiles | LOW | Warning banner + CI display | Minimal |
| 5 | Missing Proc Codes | LOW | "Unspecified" category | Minimal |

---

## Issue 1: Collection Rate Edge Cases

### Problem
When `total_billed = 0`, collection rate defaults to 100%, which misrepresents performance.

### Data Science Analysis
- **Root Cause:** Division by zero protection returns arbitrary default
- **Frequency:** Likely rare (new accounts, data entry errors, voided invoices)
- **Impact:** Inflates aggregate collection rates if included

### Resolution Approach

**Option A (Recommended): Explicit N/A Display**
```python
def calculate_collection_rate(payments, total_billed):
    if total_billed == 0:
        return None  # Explicit null - display as "N/A"
    return (payments / total_billed) * 100
```

**Display Logic:**
- Individual rows: Show "N/A" 
- Aggregates: Exclude from numerator AND denominator
- Add footnote: "N/A indicates no billable activity in period"

**Why This Works:**
- Preserves data visibility (row still appears)
- Prevents statistical distortion
- User understands the limitation

### Implementation Tasks
- [ ] Modify `calculate_metrics()` to return None for zero-billed
- [ ] Update display formatting to show "N/A" for None values
- [ ] Add exclusion logic in aggregate calculations
- [ ] Add footnote to collection rate displays

---

## Issue 2: Negative Balance Logic

### Problem
Using `abs(balance)` may overstate total billed when credits/overpayments exist.

### Data Science Analysis
- **Negative balances can represent:**
  1. Customer credits (reduce future billing)
  2. Overpayments (refund pending)
  3. Write-off reversals
  4. Data correction entries

- **Current formula:** `total_billed = payments + abs(balance)` 
- **Issue:** A $100 payment with -$20 credit shows $120 billed, but actual billing was $80

### Resolution Approach

**Option A (Recommended): Segment and Display Both**

Create two metrics:
```python
# Gross Billed (current approach - conservative, includes all activity)
gross_billed = payments + abs(balance)

# Net Billed (accounts for credits)  
net_billed = payments + max(balance, 0)  # Only positive balances

# Display both collection rates
gross_collection_rate = payments / gross_billed * 100
net_collection_rate = payments / net_billed * 100 if net_billed > 0 else None
```

**Display Logic:**
- Primary metric: Net Collection Rate (more accurate)
- Secondary metric: Gross Collection Rate (conservative estimate)
- Tooltip explains the difference

**Why This Works:**
- Shows complete picture without hiding data
- Users can choose appropriate metric for their analysis
- Maintains backward compatibility

### Implementation Tasks
- [ ] Add `net_billed` and `gross_billed` columns to data processing
- [ ] Calculate both collection rate variants
- [ ] Update dashboard to display primary (Net) with Gross as secondary
- [ ] Add info tooltip explaining calculation difference

---

## Issue 3: Percentile Ties

### Problem
Branches with identical metric values receive the same percentile rank, providing no differentiation.

### Data Science Analysis
- **Statistical validity:** Tied ranks are mathematically correct
- **Practical issue:** Users want to know relative standing
- **Frequency:** Common for collection rates (many at 100%)

### Resolution Approach

**Option A (Recommended): Secondary Sort Criteria**

When primary metric is tied, use secondary metric for differentiation:

| Primary Metric | Secondary Tiebreaker | Rationale |
|---------------|---------------------|-----------|
| Collection Rate | Payment Volume | Higher volume at same rate = more reliable |
| Payments | Invoice Count | More transactions = more consistent |
| Retail Mix | Total Items | Larger sample = more meaningful |

```python
def calculate_percentile_with_tiebreaker(primary_values, secondary_values):
    # Create composite rank using primary + tiny fraction of secondary
    # This preserves primary ordering while breaking ties
    secondary_normalized = (secondary_values - secondary_values.min()) / 
                           (secondary_values.max() - secondary_values.min() + 1e-10)
    composite = primary_values + secondary_normalized * 0.001
    return composite.rank(pct=True) * 100
```

**Why This Works:**
- Maintains statistical integrity of primary metric
- Provides meaningful differentiation
- Transparent to users (document tiebreaker logic)

### Implementation Tasks
- [ ] Modify `calculate_percentile_rank()` to accept secondary metric
- [ ] Implement composite ranking logic
- [ ] Update documentation with tiebreaker rules
- [ ] Add hover text showing tiebreaker used

---

## Issue 4: Small Sample Percentiles

### Problem
With fewer than 10 branches, percentile calculations lack statistical power.

### Data Science Analysis
- **Statistical concern:** n < 10 means each branch represents >10% of distribution
- **Interpretation risk:** Small changes have outsized percentile impact
- **User impact:** May make decisions on unstable metrics

### Resolution Approach

**Option A (Recommended): Warning Banner + Contextual Display**

```python
def display_percentile_section(df):
    branch_count = df['branch'].nunique()
    
    if branch_count < 5:
        st.warning(
            f"Insufficient data for percentile analysis. "
            f"Only {branch_count} branches in selection. Minimum 5 required."
        )
        return None  # Don't show percentiles
    
    elif branch_count < 10:
        st.info(
            f"Note: Percentiles based on {branch_count} branches. "
            f"Statistical significance increases with larger samples."
        )
    
    # Proceed with percentile display
    return calculate_branch_percentiles(df)
```

**Threshold Guidelines:**
| Branch Count | Action |
|--------------|--------|
| < 5 | Hide percentiles, show volume metrics only |
| 5-9 | Show percentiles with info banner |
| 10-29 | Show percentiles with sample size note |
| 30+ | Show percentiles without qualification |

**Why This Works:**
- Prevents misinterpretation
- Still provides value when sample size allows
- Educates users on statistical limitations

### Implementation Tasks
- [ ] Add `branch_count` check before percentile calculations
- [ ] Implement tiered warning/info banners
- [ ] Create fallback display for <5 branches
- [ ] Add sample size indicator to percentile charts

---

## Issue 5: Missing Procedure Codes

### Problem
Null/empty procedure codes are excluded from proc code filter and analysis.

### Data Science Analysis
- **Missing data types:**
  1. **MCAR** (Missing Completely At Random): Safe to exclude
  2. **MAR** (Missing At Random): May bias results
  3. **MNAR** (Missing Not At Random): Systematic issue

- **Business context:** Missing proc codes may indicate:
  - Non-billable services
  - Data entry gaps
  - Legacy system migrations

### Resolution Approach

**Option A (Recommended): Explicit "Unspecified" Category**

```python
def prepare_proc_codes(df):
    proc_col = '_proc_code_clean' if '_proc_code_clean' in df.columns else 'Invoice Detail Proc Code'
    
    # Create display column with explicit category for missing
    df['proc_code_display'] = df[proc_col].fillna('[Unspecified]')
    df.loc[df['proc_code_display'].str.strip() == '', 'proc_code_display'] = '[Unspecified]'
    
    return df
```

**Display Logic:**
- Include "[Unspecified]" in filter dropdown
- Show in heatmap as distinct category
- Calculate and display missing percentage

```python
missing_pct = (df[proc_col].isna().sum() / len(df)) * 100
st.caption(f"Note: {missing_pct:.1f}% of items have unspecified procedure codes")
```

**Why This Works:**
- No data is hidden
- Users see the scope of missing data
- Can analyze unspecified items if meaningful pattern exists

### Implementation Tasks
- [ ] Add `proc_code_display` column in data loading
- [ ] Include "[Unspecified]" in filter options
- [ ] Add missing percentage caption to proc code section
- [ ] Allow filtering to only "[Unspecified]" for investigation

---

## Implementation Priority

### Phase 1: Quick Wins (1-2 hours)
1. Issue 4: Add small sample warning banners
2. Issue 5: Create "[Unspecified]" proc code category

### Phase 2: Core Improvements (2-4 hours)
3. Issue 1: N/A handling for zero-billed collection rates
4. Issue 3: Secondary tiebreaker for percentile ties

### Phase 3: Comprehensive Fix (4-6 hours)
5. Issue 2: Dual collection rate metrics (Net vs Gross)

---

## Validation Checklist

After implementation, validate:

- [ ] Zero-billed branches show "N/A" not 100%
- [ ] Negative balance segments display correctly
- [ ] Tied percentiles are differentiated by secondary metric
- [ ] Warning appears when < 10 branches selected
- [ ] "[Unspecified]" proc code appears in filter
- [ ] Aggregate calculations exclude N/A values
- [ ] All tooltips and footnotes render correctly
- [ ] Export includes all data (including edge cases)

---

## Risk Assessment

| Resolution | Risk Level | Mitigation |
|------------|------------|------------|
| N/A display | Low | Test with edge case data |
| Dual collection rates | Medium | User testing for confusion |
| Tiebreakers | Low | Document clearly |
| Sample warnings | Low | None needed |
| Unspecified category | Low | Verify data integrity |

---

## Appendix: Statistical References

### Percentile Methods Comparison
| Method | When to Use |
|--------|-------------|
| Nearest Rank | Discrete data, exact values |
| Linear Interpolation | Continuous data, smooth distribution |
| Weighted Percentile | When observations have different weights |

### Sample Size Guidelines (Percentile Analysis)
| n | Stability | Recommendation |
|---|-----------|----------------|
| 3-4 | Very Low | Use ranks only |
| 5-9 | Low | Show with warning |
| 10-29 | Moderate | Standard display |
| 30+ | High | Full statistical validity |

---

**Document Version:** 1.0  
**Next Review:** After Phase 1 implementation
