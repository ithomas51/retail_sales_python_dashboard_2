# Research

## Research Complete - Ready for Review

### Invoice Data Schema (25 columns)
| Column | Type | Notes |
|--------|------|-------|
| `Invoice Number` | ID | Unique invoice identifier |
| `Invoice Status` | Enum | Closed (99.8%), Open, Pending |
| `Invoice Sales Order Number` | FK | Links to Sales Order |
| `Invoice Date Created` | DateTime | Format: `M/D/YYYY H:MM:SS AM/PM` |
| `Invoice Date of Service` | Date | Format: `M/D/YYYY 12:00:00 AM` |
| `Invoice Branch` | String | 21 unique branches |
| `Invoice SO Classification` | Enum | 20 categories |
| `Policy Payor Level` | **Enum** | **Patient/Primary/Secondary/Tertiary** |
| `Invoice Detail Billing Period` | Int | 1-95+ (rental months) |
| `Invoice Detail Payments` | Currency | `$0.00` to `$48,755.25` |
| `Invoice Detail Balance` | Currency | Outstanding AR (includes negatives) |

### Payor Level Distribution (Retail Classification)
| Level | Count | % | Classification |
|-------|-------|---|----------------|
| **Patient** | 11,392 | **56.9%** | **RETAIL** |
| Primary | 6,599 | 33.0% | Insurance |
| Secondary | 1,848 | 9.2% | Insurance |
| Tertiary | 160 | 0.8% | Insurance |

### Billing Period Patterns
| Period | Count | Description |
|--------|-------|-------------|
| 1 | 10,189 (50.9%) | First month / One-time |
| 2-12 | 7,701 (38.5%) | Active rentals |
| 13-36 | 1,900 (9.5%) | Long-term rentals |
| 36+ | ~200 (1%) | Multi-year rentals |

### Data Quality Findings
- **Outstanding Balance**: ~0.26% of items have balance > $0
- **Negative Balances**: Credits/adjustments exist (e.g., `($2.97)`)
- **Payment Range**: $0.01 - $48,755.25, Avg: $145.98
- **Empty Classifications**: 9 rows with blank SO Classification
- **File Sizes**: 127 MB (2020) → 766 MB (2025)

### Top Branches
1. Liberty Lake (3,988)
2. Redmond (2,355)
3. Tacoma (1,994)
4. Everett (1,732)
5. Coeur D'Alene (1,366)

---


