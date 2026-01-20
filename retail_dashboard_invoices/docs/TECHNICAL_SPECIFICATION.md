# Technical Specification: Invoice Dashboard

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
7. [Billing Period Analysis](#7-billing-period-analysis)
8. [Metrics Reference](#8-metrics-reference)

---

## 1. Overview

This document is the **single source of truth** for all calculations, classifications, and business logic used in the Invoice Dashboard. It provides complete technical documentation for the invoice analysis pipeline.

**Covered Scripts:**
- `scripts/analyze_invoices.py` - Core data processing
- `scripts/generate_reports.py` - Excel/Charts generation
- `scripts/invoice_dashboard.py` - Interactive Streamlit dashboard
- `run_pipeline.py` - Pipeline orchestration

**Dashboard Scope:**
- **Time Range:** 5-Year (FY2021 - FY2025)
- **End Date:** December 31, 2025
- **Primary Grouping:** Branch → Time Period

---

## 2. Data Source

### Input
- **Report:** Brightree Invoice Line Item Report
- **Format:** CSV with 25 columns per line item
- **Files:** Yearly files (2020.csv - 2025.csv)
- **Volume:** ~1.8 GB total

### Key Source Columns

| Column | Data Type | Description |
|--------|-----------|-------------|
| `Invoice Number` | Integer | Unique invoice identifier |
| `Invoice Sales Order Number` | Integer | Link to originating Sales Order |
| `Invoice Date Created` | DateTime | Invoice generation timestamp |
| `Invoice Date of Service` | Date | Date of service for billing |
| `Invoice Branch` | String | Branch location |
| `Invoice SO Classification` | String | Workflow type |
| `Policy Payor Level` | String | **Patient/Primary/Secondary/Tertiary** |
| `Invoice Detail Billing Period` | Integer | **Rental month number (1, 2, 3...)** |
| `Invoice Detail Payments` | Currency | **Collected payment amount** |
| `Invoice Detail Balance` | Currency | **Outstanding balance** |
| `Invoice Detail Qty` | Float | Quantity billed |
| `Invoice Detail Proc Code` | String | Procedure/billing code |
| `Invoice Detail Item Name` | String | Item description |
| `Invoice Detail Item Group` | String | Item category |

---

## 3. Retail Classification Logic

### Business Rule

An item is classified as **RETAIL** when `Policy Payor Level` = "Patient"

This indicates the line item is billed directly to the patient (self-pay/private pay), regardless of whether insurance exists on the originating Sales Order.

```python
# Classification logic
is_retail = df['Policy Payor Level'].str.strip().str.lower() == 'patient'
is_insurance = df['Policy Payor Level'].str.strip().str.lower().isin(['primary', 'secondary', 'tertiary'])
```

### Decision Table

| Policy Payor Level | Classification | Description |
|-------------------|----------------|-------------|
| Patient | **RETAIL** | Self-pay / Private pay |
| Primary | **INSURANCE** | Primary insurance billing |
| Secondary | **INSURANCE** | Secondary insurance billing |
| Tertiary | **INSURANCE** | Tertiary insurance billing |

### Mixed Billing Example

The same Sales Order can have items billed to different payors:

| SO Number | Invoice | Item | Policy Payor Level | Classification |
|-----------|---------|------|-------------------|----------------|
| 1010078 | 5182889 | Concentrator 5 Liter | **Patient** | **RETAIL** |
| 1010078 | 5133804 | E Tank | Primary | Insurance |

### Distribution (from research)

| Payor Level | % of Items |
|-------------|------------|
| Patient (Retail) | ~57% |
| Primary | ~33% |
| Secondary | ~9% |
| Tertiary | ~1% |

---

## 4. Revenue Calculation

### Key Difference from Sales Orders

| Aspect | Sales Order | Invoice |
|--------|-------------|---------|
| **Revenue Field** | `Sales Order Detail Allow` (expected) | `Invoice Detail Payments` (collected) |
| **Outstanding** | Not tracked | `Invoice Detail Balance` |
| **Rental** | One-time value | Monthly recurring invoices |

### Formula

```python
# Total collected revenue
total_payments = df['Invoice Detail Payments'].apply(clean_currency).sum()

# Outstanding balance
total_balance = df['Invoice Detail Balance'].apply(clean_currency).sum()

# Total billed (for collection rate)
total_billed = total_payments + abs(total_balance)

# Collection rate
collection_rate = (total_payments / total_billed) * 100
```

### Rental Revenue Recognition

For recurring rentals, revenue accumulates over multiple billing periods:

| Month | Sales Order View | Invoice View |
|-------|-----------------|--------------|
| 1 | $500 Allow | $150 Payment (Period 1) |
| 2 | $500 Allow (same) | +$150 Payment (Period 2) |
| 3 | $500 Allow (same) | +$150 Payment (Period 3) |
| ... | ... | ... |
| 12 | $500 Allow (same) | +$150 Payment (Period 12) |
| **Total** | **$500** | **$1,800** |

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
    try:
        return float(s)
    except ValueError:
        return 0.0
```

---

## 6. Time Period Definitions

### Dashboard Reference

- **Dashboard End Date:** December 31, 2025 (FY2025)
- **Dashboard Start Date:** January 1, 2021 (5-year lookback)

### Period Definitions

| Period | Start Date | End Date | Description |
|--------|------------|----------|-------------|
| **1 Month** | Today - 30 days | Today | Rolling 30-day window |
| **3 Months** | Today - 90 days | Today | Rolling 90-day window |
| **6 Months** | Today - 180 days | Today | Rolling 180-day window |
| **90 Days** | Today - 90 days | Today | Rolling 90-day window |
| **YTD** | Jan 1, 2025 | Dec 31, 2025 | Year-to-date |
| **QTD** | Q4 start (Oct 1) | Today | Quarter-to-date |
| **FY 2025** | Jan 1, 2025 | Dec 31, 2025 | Full fiscal year |
| **5 Years** | Jan 1, 2021 | Dec 31, 2025 | Complete 5-year range |

### Implementation

```python
DASHBOARD_END_DATE = datetime(2025, 12, 31)
DASHBOARD_START_DATE = datetime(2021, 1, 1)

def get_time_filtered_data(df, period):
    if period == "1 Month":
        start_date = reference_date - timedelta(days=30)
        return df[df['invoice_date'] >= start_date]
    elif period == "5 Years":
        return df[(df['invoice_date'] >= DASHBOARD_START_DATE) & 
                  (df['invoice_date'] <= DASHBOARD_END_DATE)]
    # ... etc
```

---

## 7. Billing Period Analysis

### Concept

The `Invoice Detail Billing Period` field indicates the month number for recurring rentals:
- **Period 1:** First month or one-time purchase
- **Period 2+:** Recurring rental months

### Billing Period Buckets

| Bucket | Range | Description |
|--------|-------|-------------|
| Period 1 (New) | 1 | First month / One-time |
| Period 2-3 | 2-3 | Early rental |
| Period 4-6 | 4-6 | Active rental |
| Period 7-12 | 7-12 | Established rental |
| Period 13-24 | 13-24 | Long-term rental |
| Period 25-36 | 25-36 | Extended rental |
| Period 37+ | 37+ | Multi-year rental |

### Distribution (from research)

| Period Range | % of Items | Description |
|-------------|------------|-------------|
| 1 | ~51% | First month / One-time |
| 2-12 | ~39% | Active rentals |
| 13-36 | ~9% | Long-term rentals |
| 37+ | ~1% | Multi-year rentals |

### Recurring Classification

```python
df['billing_period'] = pd.to_numeric(df['Invoice Detail Billing Period'], errors='coerce').fillna(1)
df['is_recurring'] = df['billing_period'] > 1
df['is_new'] = df['billing_period'] == 1
```

---

## 8. Metrics Reference

### Key Dashboard Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| Total Payments | `SUM(payments)` | Collected revenue |
| Total Balance | `SUM(balance)` | Outstanding AR |
| Collection Rate | `payments / (payments + \|balance\|) × 100` | % collected |
| Unique Invoices | `COUNT(DISTINCT invoice_number)` | Invoice count |
| Retail Items | `COUNT WHERE is_retail = True` | Patient-billed items |
| Insurance Items | `COUNT WHERE is_insurance = True` | Insurance-billed items |
| Retail % | `retail_items / total_items × 100` | Retail proportion |
| Recurring % | `(period > 1) / total × 100` | Rental sustainability |
| Avg Billing Period | `AVG(billing_period)` | Mean rental months |

### Branch-Level Metrics

| Metric | Description |
|--------|-------------|
| Total Items | Line items for branch |
| Total Payments | Collected revenue |
| Retail Payments | Revenue from Patient items |
| Insurance Payments | Revenue from insurance items |
| Collection Rate | Branch collection efficiency |
| Recurring Items | Items with billing period > 1 |

### Aggregation Levels

| View | Aggregation |
|------|-------------|
| Summary | `GROUP BY year` |
| Branch | `GROUP BY branch, year` |
| Billing | `GROUP BY billing_period_bucket` |
| Daily | `GROUP BY DATE(invoice_date)` |

---

## Appendix A: Column Reference

### Invoice CSV Columns (25 total)

| # | Column Name | Type | Notes |
|---|-------------|------|-------|
| 1 | Invoice Number | Integer | Unique ID |
| 2 | Invoice Status | String | Open/Closed/Pending |
| 3 | Invoice Sales Order Number | Integer | FK to SO |
| 4 | Invoice Date Created | DateTime | Generation timestamp |
| 5 | Invoice Date of Service | Date | DOS for billing |
| 6 | Invoice Branch | String | Branch location |
| 7 | Invoice SO Classification | String | Workflow type |
| 8 | Invoice Aging Bucket - DOS | String | Aging category |
| 9 | Patient ID | Integer | Patient identifier |
| 10 | Policy Payor Name | String | Payor display name |
| 11 | Policy Payor ID | Integer | Payor identifier |
| 12 | Policy Payor Level | String | **Patient/Primary/Secondary/Tertiary** |
| 13 | Policy Group Name | String | Group classification |
| 14 | Policy Insurance Company | String | Insurance company |
| 15 | Policy Plan Type | String | Medicare/Medicaid/Commercial |
| 16 | Invoice Detail Item ID | String | Item identifier |
| 17 | Invoice Detail Item Name | String | Item description |
| 18 | Invoice Detail Billing Period | Integer | **Rental month (1, 2, 3...)** |
| 19 | Invoice Detail Payments | Currency | **Collected amount** |
| 20 | Invoice Detail Balance | Currency | **Outstanding balance** |
| 21 | Invoice Detail Qty | Float | Quantity billed |
| 22 | Invoice Detail Proc Code | String | Procedure code |
| 23 | Invoice Detail Item Group | String | Item category |
| 24 | Invoice Detail GL Period | String | GL posting period |
| 25 | Referral Type | String | Patient/Facility/etc. |

---

## Appendix B: Output Files

### From analyze_invoices.py

| File | Description | Rows |
|------|-------------|------|
| `invoice_analysis_summary.csv` | Year-by-year summary | 7 (6 years + TOTAL) |
| `invoice_analysis_by_branch.csv` | Branch-level breakdown | ~120 (branches × years) |
| `rental_billing_analysis.csv` | Billing period distribution | ~42 (7 buckets × 6 years) |
| `retail_invoices.csv` | Invoice numbers | Variable |
| `retail_invoice_items.csv` | All retail line items | Variable |

### From generate_reports.py

| File | Description |
|------|-------------|
| `sheets/invoice_analysis_marketing.xlsx` | 4-sheet Excel workbook |
| `charts/branch_payments_comparison.html` | Branch revenue comparison |
| `charts/billing_period_distribution.html` | Rental periods pie charts |
| `charts/collection_rate_by_branch.html` | Collection metrics |
| `charts/yearly_trends.html` | Year-over-year analysis |
| `charts/top_branches.html` | Top 10 branches |

---

*This document supersedes all previous invoice dashboard specifications.*
