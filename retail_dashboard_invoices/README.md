# Invoice Dashboard

> **Version:** 1.0  
> **Created:** January 20, 2026  
> **Dashboard Period:** 5-Year (FY2021 - FY2025)

## Overview

Interactive dashboard for analyzing Brightree invoice data with Retail vs Insurance classification, billing period analysis, and collection metrics.

## Key Features

- **5-Year Dashboard** ending FY2025 (December 31, 2025)
- **Rolling Time Periods**: 1mo, 3mo, 6mo, 90d, YTD, QTD
- **Retail Classification**: Patient payor level = Retail (self-pay)
- **Billing Period Analysis**: Rental longevity tracking
- **Collection Metrics**: Payments vs Outstanding Balance
- **Branch Comparison**: All metrics grouped by branch

## Quick Start

### 1. Install Dependencies

```powershell
cd retail_dashboard_invoices
pip install -r requirements.txt
```

### 2. Run Full Pipeline

```powershell
python run_pipeline.py -i data/brightree/invoices --run-dashboard
```

### 3. Run Dashboard Only

```powershell
streamlit run scripts/invoice_dashboard.py -- -i data/brightree/invoices
```

Or use the batch file:

```powershell
.\start_dashboard.bat
```

## Project Structure

```
retail_dashboard_invoices/
├── run_pipeline.py              # Pipeline orchestrator
├── requirements.txt
├── start_dashboard.bat
├── README.md
├── scripts/
│   ├── analyze_invoices.py      # Core data processing
│   ├── generate_reports.py      # Excel/Charts generation
│   └── invoice_dashboard.py     # Streamlit dashboard
├── docs/
│   ├── INVOICE_DASHBOARD_PLAN.md
│   └── TECHNICAL_SPECIFICATION.md
├── logs/
└── data/
    ├── brightree/
    │   └── invoices/            # Raw invoice CSVs
    │       ├── 2020.csv
    │       ├── 2021.csv
    │       ├── 2022.csv
    │       ├── 2023.csv
    │       ├── 2024.csv
    │       └── 2025.csv
    └── output/
        ├── invoice_analysis_summary.csv
        ├── invoice_analysis_by_branch.csv
        ├── rental_billing_analysis.csv
        ├── retail_invoices.csv
        ├── retail_invoice_items.csv
        └── reports/
            ├── sheets/
            │   └── invoice_analysis_marketing.xlsx
            └── charts/
                ├── branch_payments_comparison.html
                ├── billing_period_distribution.html
                ├── collection_rate_by_branch.html
                ├── top_branches.html
                └── yearly_trends.html
```

## Pipeline Steps

### Step 1: Analyze Invoices

```powershell
python scripts/analyze_invoices.py -i data/brightree/invoices -o data/output
```

**Outputs:**
- `invoice_analysis_summary.csv` - Year-by-year summary
- `invoice_analysis_by_branch.csv` - Branch-level breakdown
- `rental_billing_analysis.csv` - Billing period distribution
- `retail_invoices.csv` - Invoice numbers with retail items
- `retail_invoice_items.csv` - All retail line items

### Step 2: Generate Reports

```powershell
python scripts/generate_reports.py -i data/output -o data/output/reports
```

**Outputs:**
- Excel workbook with 4 sheets
- 5 interactive Plotly HTML charts

### Step 3: Launch Dashboard

```powershell
streamlit run scripts/invoice_dashboard.py -- -i data/brightree/invoices
```

**URL:** http://localhost:8501

## Classification Logic

### Retail vs Insurance

| Policy Payor Level | Classification | Description |
|--------------------|----------------|-------------|
| **Patient** | **RETAIL** | Self-pay / Private pay |
| Primary | Insurance | Primary insurance billing |
| Secondary | Insurance | Secondary insurance billing |
| Tertiary | Insurance | Tertiary insurance billing |

### Key Insight

The same Sales Order can have items billed to different payors:
- Some items → Patient (Retail)
- Some items → Primary/Secondary/Tertiary (Insurance)

## Metrics Reference

### Financial Metrics

| Metric | Source | Formula |
|--------|--------|---------|
| Total Payments | `Invoice Detail Payments` | SUM(payments) |
| Outstanding Balance | `Invoice Detail Balance` | SUM(balance) |
| Collection Rate | Calculated | payments / (payments + |balance|) × 100 |

### Billing Period Metrics

| Metric | Description |
|--------|-------------|
| Period 1 | First month / One-time items |
| Period 2+ | Recurring rental items |
| Recurring % | Period 2+ items / Total items |
| Avg Billing Period | Average rental length in months |

### Time Periods

| Period | Definition |
|--------|------------|
| 1 Month | Last 30 days |
| 3 Months | Last 90 days |
| 6 Months | Last 180 days |
| 90 Days | Last 90 days |
| YTD | Jan 1, 2025 → Dec 31, 2025 |
| QTD | Current quarter start → Today |
| FY 2025 | Jan 1, 2025 → Dec 31, 2025 |
| 5 Years | Jan 1, 2021 → Dec 31, 2025 |

## Command Reference

### run_pipeline.py

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i, --input` | Yes | - | Path to invoice CSV directory |
| `-o, --output` | No | `data/output` | Output directory |
| `--scripts-dir` | No | `./scripts` | Scripts directory |
| `--log-dir` | No | `logs/` | Log directory |
| `--skip-reports` | No | False | Skip Excel/chart generation |
| `--run-dashboard` | No | False | Launch Streamlit after processing |

### analyze_invoices.py

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i, --input` | Yes | - | Path to invoice CSV directory |
| `-o, --output` | No | `data/output` | Output directory |
| `--log-dir` | No | `logs/` | Log directory |

### generate_reports.py

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i, --input` | Yes | - | Path to analysis CSV files |
| `-o, --output` | No | `data/output/reports` | Output directory |
| `--log-dir` | No | `logs/` | Log directory |

### invoice_dashboard.py

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i, --input` | No | `data/brightree/invoices` | Path to invoice CSVs |

## Data Source

- **Report:** Brightree Invoice Line Item Report
- **Format:** CSV with 25 columns
- **Volume:** ~1.8 GB across 6 years (2020-2025)
