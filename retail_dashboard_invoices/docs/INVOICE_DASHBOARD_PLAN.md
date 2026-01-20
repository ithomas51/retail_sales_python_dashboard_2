# Invoice Dashboard Implementation Plan

> **Version:** 1.0  
> **Created:** January 20, 2026  
> **Status:** Planning

---

## Executive Summary

This plan outlines the development of an **Invoice Dashboard** using the same methodology as the existing Retail Sales Order Dashboard, but with key financial metric changes to reflect invoice-based (billed) data vs. sales order (ordered) data.

---

## 1. Data Source Comparison

### Sales Orders vs Invoices

| Aspect | Sales Orders | Invoices |
|--------|-------------|----------|
| **Data Stage** | Ordered / Pending | Billed / Recognized |
| **Timing** | Point of order entry | Point of billing (may be monthly) |
| **Financial Meaning** | Expected Revenue | Recognized Revenue |
| **Rental Treatment** | One-time charge/allow | Monthly recurring invoices |
| **Key Financial Column** | `Sales Order Detail Allow` | `Invoice Detail Payments` |
| **Outstanding** | N/A | `Invoice Detail Balance` |

### Invoice Data Structure

| Column | Description | Equivalent in Sales Orders |
|--------|-------------|---------------------------|
| `Invoice Number` | Unique invoice ID | N/A (new) |
| `Invoice Sales Order Number` | Link to originating SO | `Sales Order Number` |
| `Invoice Date Created` | When invoice generated | `Sales Order Date Created` |
| `Invoice Date of Service` | DOS for billing | Similar |
| `Invoice Branch` | Branch location | `Sales Order Branch Office` |
| `Invoice SO Classification` | SO type/workflow | Similar classification |
| `Invoice Detail Billing Period` | **Rental period # (1, 2, 3...)** | N/A - key difference |
| `Invoice Detail Payments` | **Collected amount** | N/A - key difference |
| `Invoice Detail Balance` | Outstanding balance | N/A |
| `Invoice Detail Qty` | Quantity billed | `Sales Order Detail Qty` |
| `Invoice Detail Proc Code` | Procedure code | `Sales Order Detail Proc Code` |
| `Invoice Detail Item Name` | Item description | `Sales Order Detail Item Name` |
| `Invoice Detail Item Group` | Category | `Sales Order Detail Item Group` |
| `Policy Payor Level` | Patient/Primary/Secondary/Tertiary | Insurance Flags logic |

---

## 2. Key Financial Metric Changes

### 2.1 Rental vs. Purchase Revenue Recognition

**Sales Order Dashboard (Current):**
```
Rental Revenue = Allow × (1 - Discount) × 1  [One-time calculation]
```

**Invoice Dashboard (Proposed):**
```
Rental Revenue = SUM(Payments) for Billing Period 1..N  [Cumulative monthly]
```

#### Example: Oxygen Concentrator Rental

| Metric | Sales Order View | Invoice View |
|--------|-----------------|--------------|
| **Initial Charge** | $500 Allow | $500 (Period 1) |
| **Month 2** | Same $500 | +$150 (Period 2) |
| **Month 3** | Same $500 | +$150 (Period 3) |
| **Month 12** | Same $500 | +$150 (Period 12) |
| **12-Month Total** | $500 | $2,150 |

### 2.2 Revenue Metrics Translation

| Sales Order Metric | Invoice Equivalent | Formula |
|-------------------|-------------------|---------|
| `Allow` (expected) | `Payments` (collected) | Direct mapping |
| `Charge` (list price) | N/A in invoice | Not available |
| `Discount` | N/A | Pre-applied in payments |
| `net_allow` | `total_payments` | `SUM(Invoice Detail Payments)` |

### 2.3 New Invoice-Specific Metrics

| Metric | Description | Formula |
|--------|-------------|---------|
| **Collected Revenue** | Actual payments received | `SUM(Payments)` |
| **Outstanding Balance** | Unpaid amounts | `SUM(Balance)` |
| **Collection Rate** | % collected vs billed | `Payments / (Payments + Balance) * 100` |
| **Billing Period Distribution** | Rental longevity | `COUNT by Billing Period` |
| **Avg Billing Period** | Average rental length | `AVG(Billing Period)` |
| **Max Billing Period** | Longest active rental | `MAX(Billing Period)` |
| **Recurring Revenue Ratio** | Period > 1 / Total | Rental sustainability |

---

## 3. Retail vs Insurance Classification

### Business Rule

**RETAIL** = Line item is billed to private pay (`Policy Payor Level` = "Patient")

This means the specific line item is billed only to the patient (self-pay), regardless of whether insurance exists on the Sales Order. The same SO can have some items billed to insurance and others billed to Patient (retail).

### Proposed Logic (Invoices)

Uses `Policy Payor Level` column:
```python
is_retail = df['Policy Payor Level'] == 'Patient'
is_insurance = df['Policy Payor Level'].isin(['Primary', 'Secondary', 'Tertiary'])
```

### Example: Mixed Billing on Same Sales Order

| SO Number | Invoice | Item | Policy Payor Level | Classification |
|-----------|---------|------|-------------------|----------------|
| 1010078 | 5182889 | Concentrator 5 Liter | **Patient** | **RETAIL** |
| 1010078 | 5133804 | E Tank | Primary | Insurance |

### Classification Mapping

| Policy Payor Level | Classification | Notes |
|-------------------|----------------|-------|
| `Patient` | **RETAIL** | Self-pay / Private pay - billed directly to patient |
| `Primary` | **INSURANCE** | Primary insurance billing |
| `Secondary` | **INSURANCE** | Secondary insurance billing |
| `Tertiary` | **INSURANCE** | Tertiary insurance billing |

---

## 4. Pipeline Architecture

### Parallel to Existing Sales Order Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  RAW INVOICE DATA                                               │
│  data/brightree/invoices/YYYY.csv                               │
│  (Brightree Invoice Line Item Report)                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: analyze_invoices.py                                    │
│                                                                 │
│  Processing:                                                    │
│  - Classifies as Retail (Patient) vs Insurance                  │
│  - Cleans currency values for Payments/Balance                  │
│  - Calculates billing period metrics                            │
│  - Aggregates by year and branch                                │
│                                                                 │
│  Output:                                                        │
│    - invoice_analysis_summary.csv                               │
│    - invoice_analysis_by_branch.csv                             │
│    - retail_invoices.csv (invoice numbers)                      │
│    - retail_invoice_items.csv (line items)                      │
│    - rental_analysis.csv (billing period metrics)               │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: generate_invoice_reports.py                            │
│                                                                 │
│  Output:                                                        │
│    - sheets/invoice_analysis_marketing.xlsx                     │
│    - charts/branch_payments_comparison.html                     │
│    - charts/billing_period_distribution.html                    │
│    - charts/collection_rate_by_branch.html                      │
│    - charts/rental_trends.html                                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: invoice_dashboard.py (Streamlit)                       │
│                                                                 │
│  Features:                                                      │
│    - Collected Revenue metrics                                  │
│    - Outstanding Balance tracking                               │
│    - Collection Rate analysis                                   │
│    - Rental billing period analysis                             │
│    - Recurring vs One-time revenue breakdown                    │
│    - Branch contribution analysis                               │
│    - SO Classification analysis                                 │
│    - Year-over-Year comparison                                  │
│                                                                 │
│  URL: http://localhost:8502                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Dashboard Features

### 5.1 Key Metrics Panel (Grouped by Branch, then Time Period)

**Primary Grouping:** Branch → Time Period

| Metric | Description | Icon |
|--------|-------------|------|
| **Total Collected** | Sum of all payments | 💰 |
| **Outstanding Balance** | Unpaid amounts | ⏳ |
| **Collection Rate** | Payments / Total billed | 📊 |
| **Total Invoices** | Unique invoice count | 📋 |
| **Avg Payment** | Mean payment per item | 💵 |
| **Recurring %** | Billing period > 1 | 🔄 |

### 5.2 Time Period Filters

**5-Year Dashboard with FY2025 End Period**

Rolling Periods:
- **1 Month** (30 days rolling)
- **3 Months** (90 days rolling)
- **6 Months** (180 days rolling)
- **90 Days** (rolling)

Fixed Periods:
- **YTD** (Jan 1, 2025 → Today)
- **QTD** (Current quarter start → Today)
- **FY 2025** (Jan 1, 2025 → Dec 31, 2025)
- **5 Years** (Jan 1, 2021 → Dec 31, 2025)

### 5.3 New Analysis Views

#### Billing Period Analysis
- Distribution of items by billing period (1, 2, 3...36+)
- Average billing period by item group
- Revenue by billing period cohort

#### Collection Analysis
- Collection rate by branch
- Collection rate by payor level
- Outstanding balance aging

#### Rental Sustainability
- Recurring revenue trend
- Active rental count over time
- Rental churn analysis

#### SO Classification Analysis
- Revenue by workflow type (CPAP, O2, Rehab, etc.)
- Retail vs Insurance by classification
- Referral type breakdown

---

## 6. Technical Specification

### 6.1 Data Processing Functions

```python
def classify_payor(df):
    """Classify as Retail or Insurance based on Policy Payor Level"""
    df['is_retail'] = df['Policy Payor Level'] == 'Patient'
    df['is_insurance'] = df['Policy Payor Level'].isin(['Primary', 'Secondary', 'Tertiary'])
    return df

def calculate_billing_metrics(df):
    """Calculate rental/recurring billing metrics"""
    df['billing_period'] = pd.to_numeric(df['Invoice Detail Billing Period'], errors='coerce').fillna(1)
    df['is_recurring'] = df['billing_period'] > 1
    df['is_new'] = df['billing_period'] == 1
    return df

def clean_payments(df):
    """Clean payment and balance currency fields"""
    df['payments'] = df['Invoice Detail Payments'].apply(clean_currency)
    df['balance'] = df['Invoice Detail Balance'].apply(clean_currency)
    df['total_billed'] = df['payments'] + df['balance']
    df['collection_rate'] = np.where(
        df['total_billed'] > 0,
        (df['payments'] / df['total_billed'] * 100).round(2),
        100.0
    )
    return df
```

### 6.2 Key Aggregations

```python
# Summary by Year
summary = df.groupby('invoice_year').agg({
    'Invoice Number': 'nunique',
    'payments': 'sum',
    'balance': 'sum',
    'is_retail': 'sum',
    'is_insurance': 'sum',
    'is_recurring': 'sum',
    'billing_period': 'mean'
}).reset_index()

# By Branch
branch_summary = df.groupby(['invoice_year', 'Invoice Branch']).agg({
    'payments': 'sum',
    'balance': 'sum',
    'is_retail': 'sum',
    'is_insurance': 'sum'
}).reset_index()

# Rental Analysis
rental_analysis = df.groupby('billing_period').agg({
    'payments': 'sum',
    'Invoice Number': 'count'
}).reset_index()
```

### 6.3 Revenue Comparison Notes

| Scenario | Sales Order Shows | Invoice Shows | Difference |
|----------|------------------|---------------|------------|
| **New Purchase** | $500 Allow | $500 Payment | Same |
| **Active Rental (Month 12)** | $500 Allow (unchanged) | $150/mo × 12 = $1,800 | +$1,300 |
| **Cancelled Rental** | $500 Allow | $150 × 3 = $450 | -$50 |
| **Unpaid Balance** | $500 Allow | $0 Payment + $500 Balance | $0 collected |

---

## 7. Implementation Phases

### Phase 1: Data Analysis (Week 1)
- [ ] Create `analyze_invoices.py` script
- [ ] Implement payor-level classification
- [ ] Implement billing period analysis
- [ ] Generate summary and branch CSVs
- [ ] Create rental analysis CSV

### Phase 2: Report Generation (Week 1-2)
- [ ] Create `generate_invoice_reports.py`
- [ ] Build Excel workbook with invoice-specific sheets
- [ ] Create Plotly charts for billing analysis

### Phase 3: Dashboard Development (Week 2-3)
- [ ] Create `invoice_dashboard.py` Streamlit app
- [ ] Implement collection rate visualization
- [ ] Implement rental period analysis
- [ ] Add SO classification breakdown
- [ ] Add branch comparison views

### Phase 4: Integration (Week 3)
- [ ] Create `run_invoice_pipeline.py` orchestrator
- [ ] Update documentation
- [ ] Add comparison views (SO vs Invoice)
- [ ] Testing and validation

---

## 8. Output Files

### From analyze_invoices.py

| File | Description |
|------|-------------|
| `invoice_analysis_summary.csv` | Year-by-year summary |
| `invoice_analysis_by_branch.csv` | Branch-level breakdown |
| `retail_invoices.csv` | Invoice numbers with retail items |
| `retail_invoice_items.csv` | All retail invoice line items |
| `rental_billing_analysis.csv` | Billing period distribution |

### From generate_invoice_reports.py

| File | Description |
|------|-------------|
| `sheets/invoice_analysis_marketing.xlsx` | Formatted Excel workbook |
| `charts/branch_payments_comparison.html` | Revenue by branch |
| `charts/billing_period_distribution.html` | Rental periods chart |
| `charts/collection_rate_by_branch.html` | Collection metrics |
| `charts/rental_trends.html` | Recurring revenue trends |
| `charts/classification_breakdown.html` | SO Classification analysis |

---

## 9. Key Business Insights Available

### From Invoice Data (Not Available in Sales Orders)

1. **Actual Collections** - What was really received vs expected
2. **Outstanding Balances** - AR aging and collection issues
3. **Rental Longevity** - How long rentals stay active
4. **Revenue Timing** - When revenue is recognized (not ordered)
5. **Payor Performance** - Which payors pay vs leave balance
6. **True Retail Revenue** - Self-pay collections

### Comparative Analysis (Sales Order + Invoice)

| Metric | Sales Order | Invoice | Insight |
|--------|------------|---------|---------|
| Expected vs Collected | ✓ | ✓ | Collection efficiency |
| Order → Invoice Gap | ✓ | ✓ | Billing cycle time |
| Rental Lifetime Value | Estimated | **Actual** | True rental revenue |
| Write-offs | Not visible | Visible | Financial impact |

---

## 10. Folder Structure

**NEW: Separate project directory `retail_dashboard_invoices`**

```
sales_2020/
├── retail_dashboard_example/        # Existing Sales Order Dashboard
│   └── ...
│
└── retail_dashboard_invoices/       # NEW Invoice Dashboard
    ├── README.md
    ├── requirements.txt
    ├── run_pipeline.py              # Pipeline orchestrator
    ├── start_dashboard.bat
    ├── scripts/
    │   ├── analyze_invoices.py      # Core data processing
    │   ├── generate_reports.py      # Excel/Charts generation
    │   └── invoice_dashboard.py     # Streamlit dashboard
    ├── docs/
    │   └── TECHNICAL_SPECIFICATION.md
    ├── logs/
    └── data/
        ├── brightree/
        │   └── invoices/            # Raw invoice data
        │       ├── 2020.csv
        │       ├── 2021.csv
        │       ├── 2022.csv
        │       ├── 2023.csv
        │       ├── 2024.csv
        │       └── 2025.csv
        └── output/
            ├── invoice_analysis_summary.csv
            ├── invoice_analysis_by_branch.csv
            ├── retail_invoices.csv
            ├── retail_invoice_items.csv
            ├── rental_billing_analysis.csv
            └── reports/
                ├── sheets/
                │   └── invoice_analysis_marketing.xlsx
                └── charts/
                    ├── branch_payments_comparison.html
                    ├── billing_period_distribution.html
                    ├── collection_rate_by_branch.html
                    └── rental_trends.html
```

---

## Appendix A: Sample Data Patterns

### Invoice Billing Period Examples (from 2020 data)

| Billing Period | Count | % of Total | Description |
|---------------|-------|------------|-------------|
| 1 | 5,358 | 53.6% | First month / One-time |
| 2-3 | 1,376 | 13.8% | Early rental months |
| 4-12 | 2,402 | 24.0% | Active rentals |
| 13-24 | 578 | 5.8% | Long-term rentals |
| 25-36 | 180 | 1.8% | Extended rentals |
| 36+ | 105 | 1.1% | Multi-year rentals |

### Policy Payor Level Distribution (from 2020 sample)

| Payor Level | Count | % |
|-------------|-------|---|
| Patient (Retail) | 2,841 | 56.8% |
| Primary | 1,741 | 34.8% |
| Secondary | 363 | 7.3% |
| Tertiary | 54 | 1.1% |

---

## Appendix B: Column Reference

### Invoice CSV Columns

1. `Invoice Number` - Unique invoice identifier
2. `Invoice Status` - Open/Closed
3. `Invoice Sales Order Number` - Link to originating SO
4. `Invoice Date Created` - Invoice generation date
5. `Invoice Date of Service` - DOS for billing
6. `Invoice Branch` - Branch location
7. `Invoice SO Classification` - Workflow type
8. `Invoice Aging Bucket - DOS` - Aging bucket
9. `Patient ID` - Patient identifier
10. `Policy Payor Name` - Name of payor
11. `Policy Payor ID` - Payor identifier
12. `Policy Payor Level` - Patient/Primary/Secondary/Tertiary
13. `Policy Group Name` - Group classification
14. `Policy Insurance Company` - Insurance company name
15. `Policy Plan Type` - Medicare/Medicaid/Commercial/etc.
16. `Invoice Detail Item ID` - Item identifier
17. `Invoice Detail Item Name` - Item description
18. `Invoice Detail Billing Period` - **Rental period number**
19. `Invoice Detail Payments` - **Collected amount**
20. `Invoice Detail Balance` - **Outstanding balance**
21. `Invoice Detail Qty` - Quantity billed
22. `Invoice Detail Proc Code` - Procedure code
23. `Invoice Detail Item Group` - Item category
24. `Invoice Detail GL Period` - GL posting period
25. `Referral Type` - Patient/Facility/etc.

---

*This plan establishes the framework for building an Invoice Dashboard that complements the existing Sales Order Dashboard by providing actual billed/collected revenue analysis with proper recurring rental revenue recognition.*
