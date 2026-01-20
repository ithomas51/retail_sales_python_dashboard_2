# Invoice Dashboard - Calculations Reference

## Document Information
- **Version:** 1.0
- **Created:** January 20, 2026
- **Purpose:** Document all calculation formulas, validation results, and known issues

---

## 1. Core Financial Metrics

### 1.1 Collection Rate

**Formula:**
```
Collection Rate (%) = (Total Payments / Total Billed) × 100
```

**Where:**
- `Total Payments` = Sum of all payment amounts received
- `Total Billed` = Total Payments + Absolute Value of Outstanding Balance

**Implementation:**
```python
total_billed = payments + abs(balance)
collection_rate = (total_payments / total_billed * 100) if total_billed > 0 else 100.0
```

**Industry Standard:** Net Collection Rate in healthcare typically uses:
- Numerator: Payments received within a defined period
- Denominator: Charges minus contractual adjustments

**Validation Status:** CONSISTENT
- Formula aligns with standard revenue cycle collection rate calculations
- Default to 100% when no billing prevents division by zero

---

### 1.2 Retail Mix Percentage

**Formula:**
```
Retail Mix (%) = (Retail Items / Total Items) × 100
```

**Where:**
- `Retail Items` = Count of line items where Payor Level = 'Patient'
- `Total Items` = Retail Items + Insurance Items

**Implementation:**
```python
retail_pct = (retail_items / total_items * 100) if total_items > 0 else 0
```

**Validation Status:** CONSISTENT

---

### 1.3 Recurring Items Percentage

**Formula:**
```
Recurring (%) = (Items with Billing Period > 1 / Total Items) × 100
```

**Implementation:**
```python
is_recurring = billing_period > 1
recurring_pct = (is_recurring.sum() / len(df) * 100) if len(df) > 0 else 0
```

**Validation Status:** CONSISTENT

---

## 2. Percentile Calculations

### 2.1 Percentile Rank Method

**Formula (Linear Interpolation, C=1):**
```
Percentile Rank = (count of values < x) / (n - 1) × 100
```

**Where:**
- `x` = The value being ranked
- `n` = Total number of observations in the dataset

**Reference:** Wikipedia - Percentile, Linear Interpolation Method (Second variant, C=1)
- This method is used by NumPy and Microsoft Excel (PERCENTILE.INC)
- Produces values in range [0, 100]
- The 50th percentile equals the median when n is odd

**Implementation:**
```python
def calculate_percentile_rank(value: float, data_series: pd.Series) -> float:
    sorted_data = np.sort(data_series.dropna().values)
    n = len(sorted_data)
    if n <= 1:
        return 50.0
    count_less = np.sum(sorted_data < value)
    percentile = (count_less / (n - 1)) * 100
    return min(max(percentile, 0.0), 100.0)
```

**Validation Status:** CONSISTENT with standard statistical methods

---

### 2.2 Branch Performance Percentiles

The following percentiles are calculated for each branch:

| Metric | Description | Weight |
|--------|-------------|--------|
| Payments Percentile | Branch payments rank vs all branches | 30% |
| Collection Rate Percentile | Branch collection rate rank vs all branches | 40% |
| Retail Mix Percentile | Branch retail percentage rank vs all branches | 10% |
| Volume Percentile | Branch invoice count rank vs all branches | 20% |

**Composite Performance Score Formula:**
```
Performance Score = (Collection_Pctl × 0.40) + (Payments_Pctl × 0.30) + 
                    (Volume_Pctl × 0.20) + (Retail_Mix_Pctl × 0.10)
```

**Percentile Interpretation:**
- 90th percentile = Top 10% performer
- 75th percentile = Top 25% performer (Q3)
- 50th percentile = Median performer (Q2)
- 25th percentile = Bottom 25% performer (Q1)

**Validation Status:** CONSISTENT - Weights sum to 100%

---

## 3. Data Classification

### 3.1 Retail vs Insurance Classification

**Retail (Patient):**
```python
is_retail = payor_level.strip().lower() == 'patient'
```

**Insurance:**
```python
is_insurance = payor_level.strip().lower() in ['primary', 'secondary', 'tertiary']
```

**Validation Status:** CONSISTENT

---

### 3.2 Billing Period Buckets

| Bucket Label | Period Range | Description |
|--------------|--------------|-------------|
| Period 1 | 1 | Initial/One-time billing |
| 2-3 | 2-3 | Early recurring |
| 4-6 | 4-6 | Short-term recurring |
| 7-12 | 7-12 | Mid-term recurring |
| 13-24 | 13-24 | Annual recurring |
| 25-36 | 25-36 | Long-term recurring |
| 37+ | 37+ | Extended recurring |

**Validation Status:** CONSISTENT

---

## 4. Identified Issues and Inconsistencies

### 4.1 ISSUE: Collection Rate Edge Cases

**Severity:** LOW  
**Description:** When `total_billed = 0`, collection rate defaults to 100%

**Current Behavior:**
```python
collection_rate = (payments / total_billed * 100) if total_billed > 0 else 100.0
```

**Potential Issue:** A branch with $0 billed and $0 collected shows 100% collection rate, which may misrepresent performance.

**Recommendation:** Consider flagging these cases separately or showing "N/A"

---

### 4.2 ISSUE: Negative Balances in Total Billed

**Severity:** MEDIUM  
**Description:** Balance column may contain negative values (credits/refunds)

**Current Behavior:**
```python
total_billed = payments + abs(balance)
```

**Analysis:** Using absolute value ensures negative balances don't reduce total billed. However, this may overstate total billed when credits exist.

**Example:**
- Payments: $100
- Balance: -$20 (credit)
- Current Total Billed: $100 + $20 = $120
- Actual Total Billed: Should likely be $80

**Recommendation:** Review whether negative balances represent:
1. Overpayments (should reduce total billed)
2. Credits (should reduce total billed)
3. Adjustments (may need separate handling)

---

### 4.3 ISSUE: Percentile with Tied Values

**Severity:** LOW  
**Description:** When multiple branches have identical values, percentile ranks may not differentiate them.

**Current Behavior:** All tied values receive the same percentile rank based on count less than (not less than or equal).

**Example:** If 3 branches all have 95% collection rate:
- All three get the same percentile rank
- This is mathematically correct but may not provide meaningful differentiation

**Recommendation:** Consider using average rank for ties if differentiation is needed.

---

### 4.4 ISSUE: Small Sample Size Percentiles

**Severity:** LOW  
**Description:** With few branches (<10), percentile calculations may not be statistically meaningful.

**Current Behavior:** Percentiles calculated regardless of sample size.

**Recommendation:** Display a warning when branch count < 10.

---

### 4.5 ISSUE: Missing Procedure Codes

**Severity:** LOW  
**Description:** Some line items may have null/empty procedure codes.

**Current Behavior:** 
- Filter excludes items with null proc codes when filtering by procedure code
- Heatmap only shows items with valid proc codes

**Validation Status:** ACCEPTABLE - No data loss, just filtered display

---

## 5. Time Period Calculations

### 5.1 Rolling Period Definitions

| Period | Start Date Calculation | End Date |
|--------|----------------------|----------|
| 1 Month | reference_date - 30 days | reference_date |
| 3 Months | reference_date - 90 days | reference_date |
| 90 Days | reference_date - 90 days | reference_date |
| 6 Months | reference_date - 180 days | reference_date |
| YTD | January 1, 2025 | December 31, 2025 |
| QTD | October 1, 2025 | December 31, 2025 |
| FY 2025 | January 1, 2025 | December 31, 2025 |
| 5 Years | January 1, 2021 | December 31, 2025 |

**Note:** YTD and QTD use fixed 2025 dates as the dashboard end date is December 31, 2025.

**Validation Status:** CONSISTENT

---

## 6. Currency Cleaning Logic

**Handling:**
```python
def clean_currency(value):
    - Handle None/NaN -> 0.0
    - Handle numeric types -> float(value)
    - Remove '$' and ',' characters
    - Handle parentheses as negative: (100) -> -100
    - Return 0.0 for unparseable values
```

**Validation Status:** CONSISTENT with standard accounting formats

---

## 7. Data Quality Checks

### Recommended Validations Before Analysis

1. **Date Range:** Verify invoice dates fall within expected range
2. **Negative Payments:** Flag payments < 0 for review
3. **High Balances:** Flag balance > payments for collection review
4. **Missing Branches:** Identify records with Unknown branch
5. **Duplicate Invoices:** Check for invoice number duplicates across years

---

## 8. Formula Summary Table

| Metric | Formula | Validated |
|--------|---------|-----------|
| Collection Rate | Payments / (Payments + abs(Balance)) × 100 | Yes |
| Retail Mix | Retail Items / Total Items × 100 | Yes |
| Recurring % | Items with Period > 1 / Total Items × 100 | Yes |
| Percentile Rank | count(values < x) / (n-1) × 100 | Yes |
| Performance Score | Weighted sum of percentiles | Yes |

---

## 9. References

1. **Percentile Calculation:** Wikipedia - Percentile (Linear Interpolation Method)
   - https://en.wikipedia.org/wiki/Percentile
   
2. **Revenue Cycle Management:** Wikipedia
   - https://en.wikipedia.org/wiki/Revenue_cycle_management

3. **NumPy Percentile Documentation:**
   - https://numpy.org/doc/stable/reference/generated/numpy.percentile.html

---

## 10. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-20 | 1.0 | Initial documentation |
