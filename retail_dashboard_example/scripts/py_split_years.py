"""
Split sales orders CSV by year into separate files.

Usage:
    # Basic usage with default output directory (output/)
    python py_split_years.py -i sales_data.csv
    
    # Specify custom output directory
    python py_split_years.py -i sales_data.csv -o data/raw
    
    # Using long-form arguments
    python py_split_years.py --input all_sales.csv --output yearly_data

Examples:
    # Process all sales orders and output to 'output/' directory
    python py_split_years.py -i 2020_YTD_SalesOrders.csv
    
    # Process and save to specific directory
    python py_split_years.py -i 87f5502f-c2c2-4930-a276-5daf26fbb34b.csv -o data/raw
"""

import os
import argparse
import logging
from datetime import datetime
from pathlib import Path
import pandas as pd

# Setup logging
logger = logging.getLogger(__name__)

# Proc Code normalization rules
XZERO_CODES = {'XERO', 'ZERO', 'XZERO', 'XXXXX', 'X9999', 'ZXERO', 'XZRO', 'WARRANTY'}
E1399_PREFIX = 'E1399'

# Manual override mappings for specific malformed proc codes
# Format: 'CLEANED_UPPER_VALUE': 'CORRECTED_VALUE'
MANUAL_OVERRIDES = {
    "'E0184": 'E0184',      # Extra quote prefix
    '1399': 'E1399',        # Missing E prefix
    '1399NU': 'E1399',      # Missing E prefix with suffix
    "A7520'": 'A7520',      # Extra quote suffix
    'A92701': 'A9270',      # Extra digit
    'E00295': 'E0295',      # Extra leading zero
    'E01399': 'E1399',      # Extra leading zero
    'E0627NU': 'E0627',     # Extra suffix
    'E199': 'E1399',        # Truncated
    'E399': 'E1399',        # Truncated
    'E635': 'E0635',        # Missing leading zero
}


def clean_proc_code(value):
    """
    Clean and normalize Sales Order Detail Proc Code.
    
    Rules:
    - UPPERCASE, TRIM
    - Apply manual overrides for known malformed codes
    - If not length 5, set to XZERO
    - Combine XZERO variants: XERO, ZERO, XZERO, XXXXX, X9999 -> XZERO
    - Combine E1399 variants: E1399RR, E1399XX, etc. -> E1399
    
    Returns: (cleaned_value, original_value, override_reason or None)
    """
    if pd.isna(value):
        return 'XZERO', str(value), 'NULL/NaN value'
    
    original = str(value)
    cleaned = original.strip().upper()
    
    # Check for manual overrides first
    if cleaned in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[cleaned], original, f'Manual override: {original} -> {MANUAL_OVERRIDES[cleaned]}'
    
    # Check for XZERO variants
    if cleaned in XZERO_CODES:
        return 'XZERO', original, f'XZERO variant: {original}'
    
    # Check for E1399 variants (starts with E1399 but has extra chars)
    if cleaned.startswith(E1399_PREFIX) and cleaned != E1399_PREFIX:
        return 'E1399', original, f'E1399 variant: {original}'
    
    # Check length - must be exactly 5 characters
    if len(cleaned) != 5:
        return 'XZERO', original, f'Invalid length ({len(cleaned)}): {original}'
    
    # No override needed
    return cleaned, original, None


def clean_proc_codes_column(df):
    """
    Apply proc code cleaning to the DataFrame.
    Returns the cleaned DataFrame and a list of override records.
    """
    overrides = []
    cleaned_codes = []
    
    for idx, value in enumerate(df['Sales Order Detail Proc Code']):
        cleaned, original, reason = clean_proc_code(value)
        cleaned_codes.append(cleaned)
        
        if reason:
            overrides.append({
                'Row': idx + 2,  # +2 for 1-based index and header row
                'Original': original,
                'Cleaned': cleaned,
                'Reason': reason
            })
    
    df['Sales Order Detail Proc Code'] = cleaned_codes
    return df, overrides


def print_override_report(overrides):
    """Print a summary report of proc code overrides to terminal."""
    if not overrides:
        logger.info("No proc code overrides were applied.")
        return
    
    # Group overrides by reason type
    xzero_variants = [o for o in overrides if 'XZERO variant' in o['Reason']]
    e1399_variants = [o for o in overrides if 'E1399 variant' in o['Reason']]
    manual_overrides = [o for o in overrides if 'Manual override' in o['Reason']]
    invalid_length = [o for o in overrides if 'Invalid length' in o['Reason']]
    null_values = [o for o in overrides if 'NULL/NaN' in o['Reason']]
    
    print("\n" + "=" * 80)
    print("PROC CODE OVERRIDE REPORT")
    print("=" * 80)
    
    print(f"\nTotal Overrides: {len(overrides):,}")
    print("-" * 40)
    
    # Summary by category
    print(f"\n{'Category':<25} {'Count':>10}")
    print("-" * 40)
    print(f"{'XZERO Variants':<25} {len(xzero_variants):>10,}")
    print(f"{'E1399 Variants':<25} {len(e1399_variants):>10,}")
    print(f"{'Manual Overrides':<25} {len(manual_overrides):>10,}")
    print(f"{'Invalid Length':<25} {len(invalid_length):>10,}")
    print(f"{'NULL/NaN Values':<25} {len(null_values):>10,}")
    
    # Unique original values for XZERO variants
    if xzero_variants:
        unique_xzero = set(o['Original'] for o in xzero_variants)
        print(f"\nXZERO Variants Found ({len(unique_xzero)} unique):")
        for val in sorted(unique_xzero):
            count = sum(1 for o in xzero_variants if o['Original'] == val)
            print(f"  {val:<20} -> XZERO  ({count:,} occurrences)")
    
    # Unique original values for E1399 variants
    if e1399_variants:
        unique_e1399 = set(o['Original'] for o in e1399_variants)
        print(f"\nE1399 Variants Found ({len(unique_e1399)} unique):")
        for val in sorted(unique_e1399):
            count = sum(1 for o in e1399_variants if o['Original'] == val)
            print(f"  {val:<20} -> E1399  ({count:,} occurrences)")
    
    # Manual overrides
    if manual_overrides:
        unique_manual = set((o['Original'], o['Cleaned']) for o in manual_overrides)
        print(f"\nManual Overrides Applied ({len(unique_manual)} unique mappings):")
        for orig, cleaned in sorted(unique_manual):
            count = sum(1 for o in manual_overrides if o['Original'] == orig)
            print(f"  {orig:<20} -> {cleaned:<6}  ({count:,} occurrences)")
    
    # Sample of invalid length codes
    if invalid_length:
        unique_invalid = set(o['Original'] for o in invalid_length)
        print(f"\nInvalid Length Codes ({len(unique_invalid)} unique, showing up to 20):")
        for val in sorted(unique_invalid)[:20]:
            count = sum(1 for o in invalid_length if o['Original'] == val)
            print(f"  '{val}' (len={len(str(val).strip())}) -> XZERO  ({count:,} occurrences)")
        if len(unique_invalid) > 20:
            print(f"  ... and {len(unique_invalid) - 20} more unique values")
    
    print("\n" + "=" * 80 + "\n")
    
    logger.info(f"Proc code override report: {len(overrides):,} total overrides applied")


def load_and_transform_dates(input_path):
    """Load CSV and create standardized date column."""
    df = pd.read_csv(input_path, low_memory=False)
    
    # convert Sales Order Date Created column to YYYY-MM-DD format safely
    # errors='coerce' will convert invalid dates to NaT (Not a Time)
    date_col = pd.to_datetime(df['Sales Order Date Created'], errors='coerce')
    df['Sales Order Date Created (YYYY-MM-DD)'] = date_col.dt.strftime('%Y-%m-%d')
    
    # Remove rows with invalid dates (NaT becomes NaN after strftime)
    df = df.dropna(subset=['Sales Order Date Created (YYYY-MM-DD)'])
    
    # Position the new column at index 1
    cols = list(df.columns)
    cols.insert(1, cols.pop(cols.index('Sales Order Date Created (YYYY-MM-DD)')))
    df = df[cols]
    
    return df


def load_and_clean_data(input_path):
    """Load CSV, transform dates, and clean proc codes."""
    df = load_and_transform_dates(input_path)
    
    # Clean proc codes
    logger.info("Cleaning Sales Order Detail Proc Code column...")
    df, overrides = clean_proc_codes_column(df)
    
    return df, overrides


def split_by_year(df, output_dir):
    """Split DataFrame by year and save to separate CSV files."""
    # Create directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract year from 'Sales Order Date Created (YYYY-MM-DD)' and split DataFrame
    df['Year'] = df['Sales Order Date Created (YYYY-MM-DD)'].str[:4]
    
    files_created = []
    for year, group in df.groupby('Year'):
        filename = f"{output_dir}/{year}_SalesOrders.csv"
        group.drop(columns=['Year'], inplace=True)  # Drop the temporary 'Year' column
        group.to_csv(filename, index=False)
        files_created.append(filename)
    
    return files_created


def setup_logging(log_dir: Path):
    """Configure logging to file and console"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"py_split_years_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logger.info(f"Logging to: {log_file}")


def main():
    """Main function to parse arguments and process sales data."""
    parser = argparse.ArgumentParser(
        description='Split sales orders CSV by year into separate files.'
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Path to input CSV file containing all years of sales data'
    )
    parser.add_argument(
        '-o', '--output',
        default='data/output',
        help='Output directory path (default: data/output)'
    )
    parser.add_argument(
        '--log-dir',
        default=None,
        help='Directory for log files (default: logs/)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_dir = Path(args.log_dir) if args.log_dir else Path("logs")
    setup_logging(log_dir)
    
    # Load, transform dates, and clean proc codes
    logger.info(f"Loading data from {args.input}...")
    df, overrides = load_and_clean_data(args.input)
    logger.info(f"Loaded {len(df)} records with valid dates")
    
    # Print proc code override report to terminal
    print_override_report(overrides)
    
    # Split by year and save
    logger.info(f"Splitting data by year into {args.output}/...")
    files_created = split_by_year(df, args.output)
    
    # Report results
    logger.info(f"Successfully created {len(files_created)} year-based CSV files:")
    for file in sorted(files_created):
        logger.info(f"  - {file}")


if __name__ == "__main__":
    main()