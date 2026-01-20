# Technical Specification: Retail Sales Dashboard

> **Version:** 1.0  
> **Last Updated:** January 20, 2026  
> **Status:** Validated

---

## Table of Contents

1. [Overview](#1-overview)
2. [Data Source](#2-data-source)
3. [Retail Classification Logic](#3-retail-classification-logic)
4. [Revenue Calculation](#4-revenue-calculation)
5. [Currency Parsing](#5-currency-parsing)
6. [Time Period Definitions](#6-time-period-definitions)
7. [Metrics Reference](#7-metrics-reference)
8. [Validation Summary](#8-validation-summary)

---

## 1. Overview

This document is the **single source of truth** for all calculations, classifications, and business logic used in the Retail Sales Dashboard. It consolidates and supersedes previous calculation documentation.

**Covered Scripts:**
- `scripts/py_split_years.py` - Date transformation
- `scripts/analyze_sales_orders.py` - Classification and aggregation
- `scripts/retail_dashboard.py` - Interactive dashboard

---

## 2. Data Source

### Input
- **Report:** Brightree `SalesOrders Line Item Details AdHoc Report`
- **Format:** CSV with ~50 columns per line item
- **Volume:** ~1.3 million line items (2020-2026)

### Key Source Columns

| Column | Data Type | Description |
|--------|-----------|-------------|
| `Sales Order Number` | Integer | Unique order identifier |
| `Sales Order Date Created` | Date string | Order creation date |
| `Sales Order Discount Pct` | Integer | Order-level discount (0-100) |
| `Sales Order Branch Office` | String | Branch location |
| `Sales Order Detail Charge` | Currency string | List price (`$65.00`) |
| `Sales Order Detail Allow` | Currency string | Collectible amount |
| `Sales Order Detail Qty` | Float | Item quantity |
| `Sales Order Detail Proc Code` | String | Procedure/billing code |
| `Sales Order Detail Sale Type` | String | Purchase or Rental |
| `Insurance Flags Primary` | Boolean | Primary insurance billing flag |
| `Insurance Flags Secondary` | Boolean | Secondary insurance billing flag |
| `Insurance Flags Tertiary` | Boolean | Tertiary insurance billing flag |

---

## 3. Retail Classification Logic

### Business Rule

An item is classified as **RETAIL** when **ALL THREE** insurance flags are False.

```python
# Both analyze_sales_orders.py and retail_dashboard.py use this logic
is_retail = (
    (~df['Insurance Flags Primary']) & 
    (~df['Insurance Flags Secondary']) & 
    (~df['Insurance Flags Tertiary'])
)
is_insurance = ~is_retail
```

### Decision Table

| Primary | Secondary | Tertiary | Classification |
|---------|-----------|----------|----------------|
| False | False | False | **RETAIL** |
| True | False | False | Insurance |
| False | True | False | Insurance |
| False | False | True | Insurance |
| True | True | False | Insurance |
| True | False | True | Insurance |
| False | True | True | Insurance |
| True | True | True | Insurance |

### Null Handling

| Value | Treated As |
|-------|------------|
| `null` | False |
| `NaN` | False |
| Empty string | False |
| `"False"` | False |
| `"True"` | True |
| `"true"` | True |
| `1` | True |
| `0` | False |

**Implementation:**
```python
def safe_bool(value):
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == 'true'
    return bool(value)
```

---

## 4. Revenue Calculation

### Formula

Revenue is calculated using the **Allow** field (collectible amount) with discount applied:

```python
# Step 1: Convert percentage to decimal
discount_decimal = discount_pct / 100.0

# Step 2: Apply discount
net_allow = allow * (1 - discount_decimal)
```

### Why Allow vs Charge?

| Field | Definition | Use Case |
|-------|------------|----------|
| `Charge` | List price / full billing rate | Gross revenue reporting |
| `Allow` | Collectible amount (contracted rate) | **Actual revenue reporting** |

**Finding:** ~24% of items have Allow < Charge (insurance contracted rates). Using Allow captures the **actual collectible** amount.

### Calculation Examples

| Allow | Discount Pct | Discount Decimal | Net Allow |
|-------|--------------|------------------|-----------|
| $100.00 | 0 | 0.00 | $100.00 |
| $100.00 | 10 | 0.10 | $90.00 |
| $100.00 | 25 | 0.25 | $75.00 |
| $100.00 | 50 | 0.50 | $50.00 |
| $100.00 | 100 | 1.00 | $0.00 |

### Script Consistency

| Component | Revenue Source | Formula | Status |
|-----------|----------------|---------|--------|
| `analyze_sales_orders.py` | `_allow_after_discount` | `allow * (1 - decimal)` | ✅ |
| `retail_dashboard.py` | `net_allow` | `allow * (1 - decimal)` | ✅ |

---

## 5. Currency Parsing

### Input Formats Handled

| Format | Example | Parsed Value |
|--------|---------|--------------|
| Dollar sign | `$65.00` | 65.0 |
| Thousands comma | `$1,234.56` | 1234.56 |
| No prefix | `65.00` | 65.0 |
| Accounting negative | `($100.00)` | -100.0 |
| Empty/null | `""`, `null` | 0.0 |

### Implementation

```python
def clean_currency(value):
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).replace('$', '').replace(',', '').strip()
    if not s:
        return 0.0
    # Handle accounting format negatives: (123.45) → -123.45
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    return float(s)
```

---

## 6. Time Period Definitions

### Reference Framework

The dashboard uses **dynamic dating** with `datetime.now()` for current operations.

### Period Definitions

| Period | Start Date | End Date | Description |
|--------|------------|----------|-------------|
| **YTD** | Jan 1 of current year | Today | Year-to-date |
| **QTD** | Q1 start (Jan 1) | Today | Quarter-to-date |
| **90 Days** | Today - 90 days | Today | Rolling 90-day window |
| **1 Year (FY 2025)** | Jan 1, 2025 | Dec 31, 2025 | Complete fiscal year |
| **3 Years** | Jan 1, 2023 | Dec 31, 2025 | Complete years 2023-2025 |
| **5 Years** | Jan 1, 2021 | Dec 31, 2025 | Complete years 2021-2025 |
| **All Time** | Earliest record | Latest record | No date filter |

### Implementation

```python
def get_time_filtered_data(df, period):
    today = datetime.now()
    year_end_2025 = datetime(2025, 12, 31)
    
    if period == "90 Days":
        start_date = today - timedelta(days=90)
        return df[df['order_date'] >= start_date]
    elif period == "1 Year":
        return df[(df['order_date'] >= datetime(2025, 1, 1)) & 
                  (df['order_date'] <= year_end_2025)]
    elif period == "3 Years":
        return df[(df['order_date'] >= datetime(2023, 1, 1)) & 
                  (df['order_date'] <= year_end_2025)]
    # ... etc
```

---

## 7. Metrics Reference

### Key Dashboard Metrics

| Metric | Formula | Notes |
|--------|---------|-------|
| Total Revenue | `SUM(net_allow)` | After discount |
| Total Orders | `COUNT(DISTINCT order_number)` | Unique orders |
| Total Items | `COUNT(*)` | Line items |
| Avg Order Value | `SUM(net_allow) / COUNT(DISTINCT order)` | Mean per order |
| Total Qty | `SUM(qty)` | Units sold |
| Revenue % | `(branch_rev / total_rev) * 100` | Contribution |
| YoY Growth | `(curr - prev) / prev * 100` | Year-over-year |

### Projected Metrics

| Metric | Formula | Example |
|--------|---------|---------|
| Q1 Projected | `(QTD Revenue / days_elapsed) * 90` | 19 days → 90 days |
| Daily Avg | `YTD Revenue / days_elapsed` | Total / days |
| Avg Annual | `5yr Revenue / 5` | 5-year average |

### Aggregation Levels

| View | Aggregation |
|------|-------------|
| Daily charts | `GROUP BY DATE(order_date)` |
| Monthly charts | `GROUP BY MONTH(order_date)` |
| Quarterly charts | `GROUP BY QUARTER(order_date)` |
| Annual charts | `GROUP BY YEAR(order_date)` |

---

## 8. Validation Summary

### Mathematical Verification

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| Retail + Insurance = Total | 1,301,875 | 1,301,875 | ✅ |
| Gross - Discount = Net | $142,185,717.52 | $142,185,717.52 | ✅ |
| Retail + Insurance Revenue = Total | $142,185,717.51 | $142,185,717.52 | ✅ ($0.01 rounding) |

### Known Data Characteristics

| Item | Count | Value | Notes |
|------|-------|-------|-------|
| Items without proc code | 1,497 | $136,294 | 0.29% of retail |
| Float rounding variance | - | ~$0.01 | Across 1.3M records |

### Script Consistency

| Logic | `analyze_sales_orders.py` | `retail_dashboard.py` | Match |
|-------|--------------------------|----------------------|-------|
| Retail filter | All 3 flags FALSE | All 3 flags FALSE | ✅ |
| Revenue source | Allow | Allow | ✅ |
| Discount formula | `* (1 - decimal)` | `* (1 - decimal)` | ✅ |
| Null handling | `safe_bool()` | `.fillna(False)` | ✅ |

---

## Appendix: Column Mapping

### Calculated Columns

| Script | Column | Source | Calculation |
|--------|--------|--------|-------------|
| `analyze_sales_orders.py` | `_charge_clean` | `Sales Order Detail Charge` | `clean_currency()` |
| `analyze_sales_orders.py` | `_allow_clean` | `Sales Order Detail Allow` | `clean_currency()` |
| `analyze_sales_orders.py` | `_discount_decimal` | `Sales Order Discount Pct` | `pct / 100.0` |
| `analyze_sales_orders.py` | `_charge_after_discount` | Calculated | `charge * (1 - decimal)` |
| `analyze_sales_orders.py` | `_allow_after_discount` | Calculated | `allow * (1 - decimal)` |
| `retail_dashboard.py` | `charge` | `Sales Order Detail Charge` | `clean_currency()` |
| `retail_dashboard.py` | `allow` | `Sales Order Detail Allow` | `clean_currency()` |
| `retail_dashboard.py` | `discount_decimal` | `Sales Order Discount Pct` | `pct / 100.0` |
| `retail_dashboard.py` | `net_allow` | Calculated | `allow * (1 - decimal)` |
| `retail_dashboard.py` | `is_retail` | Calculated | All 3 flags FALSE |

---

*This document supersedes: CALCULATION_VALIDATION.md, CALCULATION_VALIDATION_REPORT.md, DASHBOARD_CALCULATIONS_METHODOLOGY.md*
