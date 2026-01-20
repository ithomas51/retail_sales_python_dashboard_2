# Data Flow: Raw Data to Retail Dashboard

> **Last Updated:** January 20, 2026  
> **Version:** 2.0

## Overview

This document describes the data pipeline from raw Brightree sales order exports to the interactive Streamlit dashboard.

---

## Project Structure

```
retail_dashboard_example/
├── run_pipeline.py              # Pipeline orchestrator
├── scripts/
│   ├── py_split_years.py        # Step 1: Split raw data by year
│   ├── analyze_sales_orders.py  # Step 2: Classify & analyze
│   ├── generate_reports.py      # Step 3: Excel/Charts (optional)
│   └── retail_dashboard.py      # Step 4: Streamlit dashboard
├── data/
│   ├── brightree/               # Raw input data
│   │   └── *.csv
│   └── output/                  # Processed output
│       ├── *_SalesOrders.csv    # Yearly files
│       ├── sales_analysis_*.csv # Analysis files
│       └── reports/             # Charts & Excel
│           ├── sheets/
│           └── charts/
└── logs/                        # Timestamped log files
```

---

## Data Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  RAW DATA                                                                   │
│  data/brightree/87f5502f-c2c2-4930-a276-5daf26fbb34b.csv                   │
│  (Brightree SalesOrders Line Item Details AdHoc Report)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: py_split_years.py                                                  │
│  Location: scripts/py_split_years.py                                        │
│                                                                             │
│  Command:                                                                   │
│  python scripts/py_split_years.py -i data/brightree/raw.csv -o data/output │
│                                                                             │
│  Processing:                                                                │
│  - Parses 'Sales Order Date Created' → 'Sales Order Date Created (YYYY-MM-DD)'│
│  - Drops rows with invalid dates                                            │
│  - Groups by year and writes separate files                                 │
│                                                                             │
│  Output: data/output/                                                       │
│    - 2020_SalesOrders.csv                                                   │
│    - 2021_SalesOrders.csv                                                   │
│    - 2022_SalesOrders.csv                                                   │
│    - 2023_SalesOrders.csv                                                   │
│    - 2024_SalesOrders.csv                                                   │
│    - 2025_SalesOrders.csv                                                   │
│    - 2026_SalesOrders.csv                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: analyze_sales_orders.py                                            │
│  Location: scripts/analyze_sales_orders.py                                  │
│                                                                             │
│  Command:                                                                   │
│  python scripts/analyze_sales_orders.py -i data/output -o data/output      │
│                                                                             │
│  Processing:                                                                │
│  - Classifies items as Retail vs Insurance (see Retail Classification)     │
│  - Cleans currency values (strips $, commas, handles negatives)             │
│  - Applies discount formula (see Revenue Calculation)                       │
│  - Aggregates by year and branch                                            │
│                                                                             │
│  Output: data/output/                                                       │
│    - sales_analysis_summary.csv (yearly summaries with totals)              │
│    - sales_analysis_by_branch.csv (branch-level breakdown)                  │
│    - retail_orders.csv (order numbers with retail items)                    │
│    - retail_line_items.csv (all retail line items)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3 (Optional): generate_reports.py                                     │
│  Location: scripts/generate_reports.py                                      │
│                                                                             │
│  Command:                                                                   │
│  python scripts/generate_reports.py -i data/output -o data/output/reports  │
│                                                                             │
│  Reads: data/output/sales_analysis_*.csv                                   │
│                                                                             │
│  Output: data/output/reports/                                               │
│    - sheets/sales_analysis_marketing.xlsx (Excel workbook)                  │
│    - charts/branch_items_comparison.html                                    │
│    - charts/branch_charges_comparison.html                                  │
│    - charts/branch_mix_percentage.html                                      │
│    - charts/yearly_trends.html                                              │
│    - charts/top_branches.html                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: retail_dashboard.py                                                │
│  Location: scripts/retail_dashboard.py                                      │
│                                                                             │
│  Command:                                                                   │
│  streamlit run scripts/retail_dashboard.py -- -i data/output               │
│                                                                             │
│  Reads: data/output/*_SalesOrders.csv                                      │
│  (Processes data in-memory, filters to retail items only)                   │
│                                                                             │
│  Features:                                                                   │
│    - Interactive filters (Time, Year, Branch, Proc Code)                    │
│    - Key metrics (Revenue, Orders, Items, AOV, Qty)                         │
│    - Time period analysis (YTD, QTD, 90 Days, FY, 3yr, 5yr)                │
│    - Branch contribution analysis                                            │
│    - Sale type analysis (Purchase vs Rental)                                │
│    - Procedure code analysis with drill-down                                │
│    - Year-over-Year comparison                                              │
│    - Data explorer with CSV download                                        │
│                                                                             │
│  URL: http://localhost:8501                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Option 1: Pipeline Orchestrator (Recommended)

```powershell
cd retail_dashboard_example

# Full pipeline with dashboard
python run_pipeline.py -i data/brightree/87f5502f-c2c2-4930-a276-5daf26fbb34b.csv --run-dashboard

# Pipeline without dashboard
python run_pipeline.py -i data/brightree/raw.csv

# Skip reports, just process and launch dashboard
python run_pipeline.py -i data/brightree/raw.csv --skip-reports --run-dashboard
```

### Option 2: Run Scripts Individually

```powershell
cd retail_dashboard_example

# Step 1: Split raw data by year
python scripts/py_split_years.py -i data/brightree/raw.csv -o data/output

# Step 2: Analyze and classify
python scripts/analyze_sales_orders.py -i data/output -o data/output

# Step 3: Generate reports (optional)
python scripts/generate_reports.py -i data/output -o data/output/reports

# Step 4: Launch dashboard
streamlit run scripts/retail_dashboard.py -- -i data/output
```

---

## CLI Reference

### run_pipeline.py
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i, --input` | Yes | - | Path to raw input CSV (Brightree export) |
| `-o, --output` | No | `data/output` | Output directory for processed data |
| `--scripts-dir` | No | `./scripts` | Directory containing processing scripts |
| `--log-dir` | No | `logs/` | Directory for log files |
| `--skip-reports` | No | False | Skip Excel/chart generation |
| `--run-dashboard` | No | False | Launch Streamlit after processing |

### py_split_years.py
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i, --input` | Yes | - | Path to raw input CSV file |
| `-o, --output` | No | `data/output` | Output directory for yearly files |
| `--log-dir` | No | `logs/` | Directory for log files |

### analyze_sales_orders.py
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i, --input` | Yes | - | Directory containing `*_SalesOrders.csv` files |
| `-o, --output` | No | `data/output` | Output directory for analysis files |
| `--log-dir` | No | `logs/` | Directory for log files |

### generate_reports.py
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i, --input` | Yes | - | Directory containing `sales_analysis_*.csv` files |
| `-o, --output` | No | `data/output/reports` | Output directory for reports |
| `--log-dir` | No | `logs/` | Directory for log files |

### retail_dashboard.py
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i, --input` | No | `../data/output` | Directory containing `*_SalesOrders.csv` files |

---

## Key Scripts

| Script | Purpose |
|--------|---------|
| `run_pipeline.py` | Orchestrates full pipeline with optional steps |
| `py_split_years.py` | Splits raw data into yearly CSV files |
| `analyze_sales_orders.py` | Core processing, Retail/Insurance classification |
| `generate_reports.py` | Excel workbooks and static Plotly charts |
| `retail_dashboard.py` | Interactive Streamlit dashboard |

---

## Data Definitions

### Retail Classification

An item is **RETAIL** when ALL three insurance flags are FALSE:

```python
is_retail = (
    (~df['Insurance Flags Primary']) & 
    (~df['Insurance Flags Secondary']) & 
    (~df['Insurance Flags Tertiary'])
)
```

| Condition | Classification |
|-----------|----------------|
| All 3 flags = FALSE | **RETAIL** |
| Any flag = TRUE | **INSURANCE** |

**Source columns:**
- `Insurance Flags Primary`
- `Insurance Flags Secondary`
- `Insurance Flags Tertiary`

### Revenue Calculation

Revenue uses the **Allow** field (collectible amount) with discount applied:

```python
# Convert percentage to decimal
discount_decimal = discount_pct / 100.0

# Apply discount
net_allow = allow * (1 - discount_decimal)
```

| Field | Source Column | Description |
|-------|---------------|-------------|
| `allow` | `Sales Order Detail Allow` | Collectible amount |
| `discount_pct` | `Sales Order Discount Pct` | Discount percentage (e.g., 10 = 10%) |
| `net_allow` | Calculated | Final revenue after discount |

**Example:**
- Allow = $100.00
- Discount = 10%
- Net Allow = $100.00 × (1 - 0.10) = **$90.00**

### Currency Cleaning

Currency values are cleaned to handle various formats:

```python
def clean_currency(value):
    # Handle: $1,234.56, (1234.56), empty strings, null
    if pd.isna(value):
        return 0.0
    s = str(value).replace('$', '').replace(',', '').strip()
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]  # Handle accounting negatives
    return float(s)
```

### Sale Types

| Sale Type | Description |
|-----------|-------------|
| **Purchase** | Customer buys the item outright |
| **Rental** | Customer rents the item (recurring billing) |

---

## Output Files

### From py_split_years.py

| File | Description |
|------|-------------|
| `{YYYY}_SalesOrders.csv` | All line items for that year |

### From analyze_sales_orders.py

| File | Description |
|------|-------------|
| `sales_analysis_summary.csv` | Year-by-year summary with TOTAL row |
| `sales_analysis_by_branch.csv` | Branch-level breakdown by year |
| `retail_orders.csv` | Order numbers containing retail items |
| `retail_line_items.csv` | All retail line items (filtered) |

### From generate_reports.py

| File | Description |
|------|-------------|
| `sheets/sales_analysis_marketing.xlsx` | Formatted Excel workbook |
| `charts/branch_items_comparison.html` | Retail vs Insurance items by branch |
| `charts/branch_charges_comparison.html` | Revenue comparison by branch |
| `charts/branch_mix_percentage.html` | Retail/Insurance mix % |
| `charts/yearly_trends.html` | Year-over-year analysis |
| `charts/top_branches.html` | Top 10 branches by revenue |

---

## Logging

All scripts log to timestamped files in `logs/`:

```
logs/
├── run_pipeline_20260120_143022.log
├── py_split_years_20260120_143022.log
├── analyze_sales_orders_20260120_143025.log
└── generate_reports_20260120_143028.log
```

Log format:
```
2026-01-20 14:30:22,123 - INFO - Processing: 2025_SalesOrders.csv
```
