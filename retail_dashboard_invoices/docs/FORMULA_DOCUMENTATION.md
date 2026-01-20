# Invoice Analytics Dashboard - Formula Documentation

This document provides comprehensive documentation of all calculations, metrics, and chart formulas used in the Invoice Analytics Dashboard.

---

## Table of Contents

1. [Key Metrics Panel](#key-metrics-panel)
2. [Collection Rate Calculations](#collection-rate-calculations)
3. [Percentile Calculations](#percentile-calculations)
4. [Weighted Performance Score](#weighted-performance-score)
5. [Chart Formulas](#chart-formulas)
6. [Edge Case Handling](#edge-case-handling)

---

## Key Metrics Panel

### Total Collected
**Formula:**
```
Total Collected = Σ payments
```
**Description:** Sum of all payment amounts in the filtered dataset.

---

### Outstanding Balance
**Formula:**
```
Outstanding Balance = Σ balance
```
**Description:** Sum of all outstanding balance amounts. Negative values indicate credits/overpayments.

**Special Handling:** An asterisk (*) is displayed when credits exist in the dataset.

---

### Collection Rate
See [Collection Rate Calculations](#collection-rate-calculations) section.

---

### Invoice Count
**Formula:**
```
Invoice Count = COUNT(DISTINCT invoice_number)
```
**Description:** Unique count of invoice numbers in the filtered dataset.

---

### Retail Mix
**Formula:**
```
Retail Mix (%) = (retail_items / total_items) × 100
```
Where:
- `retail_items` = Count of items where `is_retail = True`
- `total_items` = Total count of all items

**Interpretation:** Percentage of line items attributed to retail (patient-pay) transactions.

---

### Recurring Items
**Formula:**
```
Recurring Items (%) = (recurring_items / total_items) × 100
```
Where:
- `recurring_items` = Count of items where `is_recurring = True`
- `total_items` = Total count of all items

**Interpretation:** Percentage of items classified as recurring rental billing.

---

## Collection Rate Calculations

### Gross Collection Rate
**Formula:**
```
Gross Collection Rate (%) = (payments / total_billed) × 100
```
Where:
```
total_billed = payments + |balance|
```

**Purpose:** Conservative estimate including all outstanding amounts as potentially collectable.

---

### Net Collection Rate
**Formula:**
```
Net Collection Rate (%) = (payments / net_billed) × 100
```
Where:
```
net_billed = payments + MAX(balance, 0)
```

**Purpose:** Accounts for credits/overpayments by excluding negative balances from the denominator. This provides a more accurate representation when credits exist.

---

### Edge Cases

| Scenario | Gross Rate | Net Rate | Display |
|----------|------------|----------|---------|
| `total_billed = 0` | N/A | N/A | "N/A" |
| `net_billed = 0` | Calculated | N/A | Shows gross only |
| All credits | Calculated | N/A | Shows gross only |

---

## Percentile Calculations

### Percentile Rank Method
**Method:** Linear Interpolation (C=1)

This method is equivalent to:
- NumPy: `np.percentile()` default
- Excel: `PERCENTILE.INC()`
- SciPy: `scipy.stats.percentileofscore(kind='weak')`

**Formula:**
```
percentile_rank = (count_less / (n - 1)) × 100
```
Where:
- `count_less` = Number of values strictly less than the target value
- `n` = Total number of observations

**Reference:** Wikipedia - Percentile (Linear Interpolation Method)

---

### Percentile Interpretation

| Percentile | Interpretation |
|------------|----------------|
| 90th | Top 10% performer |
| 75th | Top 25% performer (Q3) |
| 50th | Median performer (Q2) |
| 25th | Bottom 25% performer (Q1) |
| 10th | Bottom 10% performer |

---

### Tiebreaker Logic
When multiple branches have identical primary values, secondary metrics differentiate rankings:

| Primary Metric | Tiebreaker Metric |
|----------------|-------------------|
| Payments | Invoice Volume |
| Collection Rate | Payment Volume |
| Retail Mix | Total Items |
| Volume (Invoices) | Payment Amount |

**Tiebreaker Formula:**
```
tiebreaker_adjustment = (secondary_normalized) × 0.5 / n
```
Where:
```
secondary_normalized = (secondary_value - sec_min) / (sec_max - sec_min)
```

The adjustment adds a maximum of 0.5 percentile points to differentiate tied values.

---

### Individual Percentile Metrics

#### Payments Percentile
```
Payments_Pctl = percentile_rank(branch_payments, all_branch_payments)
Tiebreaker: branch_invoices
```

#### Collection Rate Percentile
```
Collection_Pctl = percentile_rank(branch_collection_rate, valid_collection_rates)
Tiebreaker: branch_payments
Note: Excludes branches with zero billing (N/A collection rates)
```

#### Retail Mix Percentile
```
Retail_Mix_Pctl = percentile_rank(branch_retail_mix, all_branch_retail_mix)
Tiebreaker: total_items
```

#### Volume Percentile
```
Volume_Pctl = percentile_rank(branch_invoices, all_branch_invoices)
Tiebreaker: branch_payments
```

---

## Weighted Performance Score

### Formula
```
Performance_Score = (Collection_Pctl × 0.40) +
                    (Payments_Pctl × 0.30) +
                    (Volume_Pctl × 0.20) +
                    (Retail_Mix_Pctl × 0.10)
```

### Component Weights

| Component | Weight | Rationale |
|-----------|--------|-----------|
| Collection Rate Percentile | 40% | Primary indicator of revenue cycle efficiency |
| Payments Percentile | 30% | Absolute revenue contribution |
| Volume Percentile | 20% | Service delivery and operational capacity |
| Retail Mix Percentile | 10% | Patient-pay revenue diversification |

### Special Handling
- When `Collection_Pctl = N/A` (zero-billed branch), uses median value (50) as placeholder
- Final score range: 0-100

### Interpretation
| Score Range | Performance Level |
|-------------|-------------------|
| 80-100 | High Performer |
| 60-79 | Above Average |
| 40-59 | Average |
| 20-39 | Below Average |
| 0-19 | Needs Improvement |

---

## Chart Formulas

### 1. Branch Comparison Chart (Horizontal Bar)
**Data Aggregation:**
```sql
SELECT 
    branch,
    SUM(payments) AS total_payments,
    SUM(is_retail) AS retail_items,
    SUM(is_insurance) AS insurance_items,
    COUNT(DISTINCT invoice_number) AS invoices
FROM filtered_data
GROUP BY branch
ORDER BY total_payments DESC
LIMIT 15
```
**Display:** Top 15 branches by total payments, formatted as `$XK`.

---

### 2. Revenue by Payor Type (Pie Chart)
**Data Aggregation:**
```sql
SELECT 
    SUM(CASE WHEN is_retail THEN payments ELSE 0 END) AS retail_payments,
    SUM(CASE WHEN is_insurance THEN payments ELSE 0 END) AS insurance_payments
FROM filtered_data
```
**Display:** Donut chart with 40% hole, showing percentage labels.

---

### 3. Billing Period Distribution (Dual Bar)
**Bucket Definitions:**

| Bucket Label | Period Range (Months) |
|--------------|----------------------|
| Period 1 | 0-1 |
| 2-3 | 2-3 |
| 4-6 | 4-6 |
| 7-12 | 7-12 |
| 13-24 | 13-24 |
| 25-36 | 25-36 |
| 37+ | 37+ |

**Data Aggregation:**
```sql
SELECT 
    period_bucket,
    SUM(payments) AS payments,
    COUNT(*) AS items
FROM filtered_data
GROUP BY period_bucket
```

---

### 4. Collection Rate by Branch (Horizontal Bar)
**Data Aggregation:**
```sql
SELECT 
    branch,
    SUM(payments) AS payments,
    SUM(total_billed) AS total_billed,
    CASE 
        WHEN SUM(total_billed) > 0 
        THEN (SUM(payments) / SUM(total_billed)) × 100
        ELSE 100.0 
    END AS collection_rate
FROM filtered_data
GROUP BY branch
ORDER BY collection_rate DESC
LIMIT 15
```

**Color Coding:**
| Rate | Color | Status |
|------|-------|--------|
| ≥95% | Green (#4CAF50) | Target Met |
| 90-94% | Yellow (#FFC107) | Near Target |
| <90% | Red (#F44336) | Below Target |

**Reference Line:** 95% target (dashed green)

---

### 5. Branch Performance Percentile Chart (Stacked Bar)
**Data Source:** `calculate_branch_percentiles()` function

**Visual Components:**
```
Bar Width = (Collection_Pctl × 0.40) + (Payments_Pctl × 0.30) + 
            (Volume_Pctl × 0.20) + (Retail_Mix_Pctl × 0.10)
```

**Color Legend:**
| Component | Color | Hex |
|-----------|-------|-----|
| Collection Rate (40%) | Blue | #1565C0 |
| Payments (30%) | Green | #43A047 |
| Volume (20%) | Orange | #FB8C00 |
| Retail Mix (10%) | Purple | #8E24AA |

**Reference Lines:**
- 75th percentile (dashed gray)
- 50th percentile/Median (dotted gray)

---

### 6. Procedure Code by Branch Heatmap
**Data Aggregation:**
```sql
SELECT 
    branch,
    proc_code,
    SUM(payments) AS payments
FROM filtered_data
WHERE proc_code IN (top_n_proc_codes)
GROUP BY branch, proc_code
```

**Selection Logic:**
1. Get top N procedure codes by total payment volume
2. Filter to top 15 branches by payment volume
3. Create pivot table (branches × proc codes)

**Colorscale:** Blues (light to dark based on payment amount)
**Text Format:** `$XK` for values ≥$1,000, `$X` otherwise

---

### 7. Year-over-Year Trend (Grouped Bar)
**Data Aggregation:**
```sql
SELECT 
    YEAR(invoice_date) AS year,
    SUM(payments) AS payments,
    SUM(is_retail) AS retail_items,
    SUM(is_insurance) AS insurance_items,
    COUNT(DISTINCT invoice_number) AS invoices
FROM filtered_data
WHERE year BETWEEN 2021 AND 2025
GROUP BY year
```

**Chart Components:**
1. Left panel: Payments by year (single bar, formatted as `$X.XM`)
2. Right panel: Retail vs Insurance items (grouped bars)

---

## Edge Case Handling

### 1. Zero Billing (Collection Rate N/A)
**Condition:** `total_billed = 0` or `net_billed = 0`
**Handling:** Display "N/A" instead of calculated percentage
**Impact:** Branch excluded from collection rate percentile calculations

---

### 2. Negative Balances (Credits)
**Condition:** `balance < 0`
**Handling:**
- `has_credits` flag set to True
- Outstanding Balance shows asterisk (*) with footnote
- Net billed calculation uses `MAX(balance, 0)`

---

### 3. Percentile Ties
**Condition:** Multiple branches have identical metric values
**Handling:** Secondary tiebreaker adds fractional adjustment (max 0.5 percentile points)

---

### 4. Small Sample Sizes
**Thresholds:**

| Branch Count | Warning Level | Message |
|--------------|---------------|---------|
| < 5 | Error | "Insufficient data for percentile analysis" |
| 5-9 | Info | "Statistical significance increases with 10+" |
| ≥ 10 | None | Full analysis enabled |

---

### 5. Missing Procedure Codes
**Condition:** `proc_code IS NULL` or `proc_code = ''`
**Handling:**
- Categorized as `[Unspecified]` in filter options
- Displayed percentage of missing proc codes in analysis section
- Caption: "Note: X.X% of items have unspecified procedure codes"

---

## Data Flow Summary

```
Raw CSV Data
    ↓
load_invoice_data()
    ├── Parse dates, clean currency
    ├── Calculate total_billed, net_billed
    ├── Map payor classifications
    └── Apply proc code mapping
    ↓
get_time_filtered_data()
    └── Apply time period filter
    ↓
User Filters (Branch, Payor, Proc Code)
    ↓
calculate_metrics() → Key Metrics Panel
    ↓
calculate_branch_percentiles() → Performance Tables
    ↓
Chart Creation Functions → Visualizations
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Initial | Base metrics and charts |
| 1.1 | Update | Added N/A handling for collection rates |
| 1.2 | Update | Added secondary tiebreakers for percentiles |
| 1.3 | Update | Added net_billed for credit handling |
| 1.4 | Update | Added small sample warnings |
| 1.5 | Update | Added [Unspecified] proc code category |
| 1.6 | Update | Dynamic proc code filter by payor type |

---

*Document generated for Invoice Analytics Dashboard v1.6*
