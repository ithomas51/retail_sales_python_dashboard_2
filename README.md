
# Retail Sales Order Dashboard (Source Repository)

> **Version:** 1.0  
> **Last Updated:** January 20, 2026

---

## Overview

This repository contains the full source code, scripts, and documentation for the Retail Sales Order Dashboard project. The solution processes Brightree sales order exports, analyzes and classifies data, generates reports, and provides an interactive dashboard for business analytics.

---

## Project Structure

```
sales_2020/
├── retail_dashboard_example/   # Main application code and scripts
│   ├── scripts/                # All processing scripts
│   ├── data/                   # Input and output data
│   ├── run_pipeline.py         # Pipeline orchestrator
│   └── README.md               # Usage and CLI reference
├── docs/                       # Technical documentation
│   ├── DATA_FLOW.md            # Pipeline and CLI details
│   └── TECHNICAL_SPECIFICATION.md # Calculation methodology
└── requirements.txt            # Python dependencies
```

---

## Quick Links

- [Application README & Usage](retail_dashboard_example/README.md)
- [Pipeline & CLI Reference](docs/DATA_FLOW.md)
- [Calculation Methodology](docs/TECHNICAL_SPECIFICATION.md)

---

## Getting Started

1. Review the [Application README](retail_dashboard_example/README.md) for setup, CLI usage, and workflow.
2. See [DATA_FLOW.md](docs/DATA_FLOW.md) for pipeline orchestration and script details.
3. See [TECHNICAL_SPECIFICATION.md](docs/TECHNICAL_SPECIFICATION.md) for business logic and calculation methodology.
4. Install dependencies:
	```bash
	pip install -r requirements.txt
	```
5. Run the pipeline or scripts as described in the application README.

---

## Requirements

- Brightree AdHoc Report: `SalesOrders Line Item Details AdHoc Report`
- Python 3.9+
- See `requirements.txt` for all dependencies

---

*For questions, see documentation or contact the project maintainer.*
