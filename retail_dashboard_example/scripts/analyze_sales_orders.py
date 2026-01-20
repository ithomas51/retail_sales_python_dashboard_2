"""
Sales Order Insurance Analysis Script - Core Data Processing
Analyzes sales orders from CSV files and classifies them as Retail vs Insurance
based on the insurance flag logic described in insurance_logic_prompt.md

Usage:
    python analyze_sales_orders.py -i data/output -o data/output
    python analyze_sales_orders.py --input ./yearly_data --output ./analysis

Outputs:
- sales_analysis_summary.csv: Year-by-year summary statistics
- sales_analysis_by_branch.csv: Branch-level breakdown
- retail_orders.csv: Single column of order numbers containing any retail items
- retail_line_items.csv: All retail line items filtered into single file
"""

import argparse
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

# Insurance flag columns (item-level - determines actual billing)
INSURANCE_FLAGS = [
    'Insurance Flags Primary',
    'Insurance Flags Secondary', 
    'Insurance Flags Tertiary'
]

# Order-level insurance inclusion columns
ORDER_INSURANCE_INCLUDE = [
    'Insurance Pri Include this payor level on SO',
    'Insurance Sec Include this payor level on SO',
    'Insurance Ter Include this payor level on SO'
]


def safe_bool(value):
    """Convert value to boolean, treating null/empty as False"""
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == 'true'
    return bool(value)


def clean_currency(value):
    """Clean currency string to float"""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace('$', '').replace(',', '').strip() or 0)


def convert_discount_pct(value):
    """
    Convert discount percentage to decimal format.
    Input: 100 = 100%, 10 = 10%, etc.
    Output: 1.0, 0.1, etc.
    """
    if pd.isna(value):
        return 0.0
    try:
        pct = float(value)
        return pct / 100.0
    except (ValueError, TypeError):
        return 0.0


def load_and_process_file(filepath):
    """Load a CSV file and add classification columns"""
    logger.info(f"Processing: {filepath.name}")
    
    df = pd.read_csv(filepath, low_memory=False)
    
    # Convert insurance flag columns to boolean, handling nulls
    for col in INSURANCE_FLAGS:
        if col in df.columns:
            df[col] = df[col].apply(safe_bool)
        else:
            df[col] = False
    
    for col in ORDER_INSURANCE_INCLUDE:
        if col in df.columns:
            df[col] = df[col].apply(safe_bool)
        else:
            df[col] = False
    
    # Classify as Retail or Insurance based on item-level flags
    # RETAIL = ALL three Insurance Flags are False
    # INSURANCE = ANY Insurance Flag is True
    df['is_retail'] = (
        (~df['Insurance Flags Primary']) & 
        (~df['Insurance Flags Secondary']) & 
        (~df['Insurance Flags Tertiary'])
    )
    df['is_insurance'] = ~df['is_retail']
    
    # Determine which insurance levels are billed
    df['bills_primary'] = df['Insurance Flags Primary']
    df['bills_secondary'] = df['Insurance Flags Secondary']
    df['bills_tertiary'] = df['Insurance Flags Tertiary']
    
    # Count how many insurance levels this item bills to
    df['insurance_level_count'] = (
        df['bills_primary'].astype(int) + 
        df['bills_secondary'].astype(int) + 
        df['bills_tertiary'].astype(int)
    )
    
    # Clean charge and allow values
    charge_col = 'Sales Order Detail Charge'
    allow_col = 'Sales Order Detail Allow'
    discount_col = 'Sales Order Discount Pct'
    qty_col = 'Sales Order Detail Qty'
    
    if charge_col in df.columns:
        df['_charge_clean'] = df[charge_col].apply(clean_currency)
    else:
        df['_charge_clean'] = 0.0
    
    if allow_col in df.columns:
        df['_allow_clean'] = df[allow_col].apply(clean_currency)
    else:
        df['_allow_clean'] = 0.0
    
    if discount_col in df.columns:
        df['_discount_decimal'] = df[discount_col].apply(convert_discount_pct)
    else:
        df['_discount_decimal'] = 0.0
    
    # Apply discount: Final = Original * (1 - discount_decimal)
    df['_charge_after_discount'] = df['_charge_clean'] * (1 - df['_discount_decimal'])
    df['_allow_after_discount'] = df['_allow_clean'] * (1 - df['_discount_decimal'])
    
    if qty_col in df.columns:
        df['_qty_clean'] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)
    else:
        df['_qty_clean'] = 0
    
    # Extract year from filename and add as column
    year_label = filepath.stem.split('_')[0]
    df['_source_year'] = year_label
    
    return df


def analyze_dataframe(df, year_label):
    """Generate summary statistics for a dataframe"""
    total_items = len(df)
    retail_items = df['is_retail'].sum()
    insurance_items = df['is_insurance'].sum()
    
    primary_count = df['bills_primary'].sum()
    secondary_count = df['bills_secondary'].sum()
    tertiary_count = df['bills_tertiary'].sum()
    
    multi_payor_items = (df['insurance_level_count'] > 1).sum()
    unique_orders = df['Sales Order Number'].nunique()
    
    total_charges = df['_charge_after_discount'].sum()
    total_allowed = df['_allow_after_discount'].sum()
    retail_charges = df.loc[df['is_retail'], '_charge_after_discount'].sum()
    insurance_charges = df.loc[df['is_insurance'], '_charge_after_discount'].sum()
    retail_allowed = df.loc[df['is_retail'], '_allow_after_discount'].sum()
    insurance_allowed = df.loc[df['is_insurance'], '_allow_after_discount'].sum()
    
    gross_charges = df['_charge_clean'].sum()
    gross_allowed = df['_allow_clean'].sum()
    total_discount = gross_allowed - total_allowed
    
    total_qty = df['_qty_clean'].sum()
    
    return {
        'Year': year_label,
        'Total Line Items': total_items,
        'Unique Orders': unique_orders,
        'Retail Items': int(retail_items),
        'Insurance Items': int(insurance_items),
        'Retail %': round(retail_items / total_items * 100, 2) if total_items > 0 else 0,
        'Insurance %': round(insurance_items / total_items * 100, 2) if total_items > 0 else 0,
        'Primary Billing': int(primary_count),
        'Secondary Billing': int(secondary_count),
        'Tertiary Billing': int(tertiary_count),
        'Multi-Payor Items': int(multi_payor_items),
        'Total Quantity': int(total_qty),
        'Gross Allow': round(gross_charges, 2),
        'Total Discount': round(total_discount, 2),
        'Total Revenue': round(total_charges, 2),
        'Retail Revenue': round(retail_charges, 2),
        'Insurance Revenue': round(insurance_charges, 2),
        'Gross Allowed': round(gross_allowed, 2),
        'Total Allowed': round(total_allowed, 2),
        'Retail Allowed': round(retail_allowed, 2),
        'Insurance Allowed': round(insurance_allowed, 2)
    }


def analyze_by_branch(df, year_label):
    """Analyze data by branch office"""
    branch_col = 'Sales Order Branch Office'
    if branch_col not in df.columns:
        return pd.DataFrame()
    
    results = []
    for branch in df[branch_col].unique():
        if pd.isna(branch):
            branch_name = "Unknown"
            branch_df = df[df[branch_col].isna()]
        else:
            branch_name = branch
            branch_df = df[df[branch_col] == branch]
        
        stats = {
            'Year': year_label,
            'Branch': branch_name,
            'Total Items': len(branch_df),
            'Retail Items': int(branch_df['is_retail'].sum()),
            'Insurance Items': int(branch_df['is_insurance'].sum()),
            'Retail %': round(branch_df['is_retail'].sum() / len(branch_df) * 100, 2) if len(branch_df) > 0 else 0,
            'Insurance %': round(branch_df['is_insurance'].sum() / len(branch_df) * 100, 2) if len(branch_df) > 0 else 0,
            'Unique Orders': branch_df['Sales Order Number'].nunique(),
            'Total Revenue': round(branch_df['_allow_after_discount'].sum(), 2),
            'Retail Revenue': round(branch_df.loc[branch_df['is_retail'], '_allow_after_discount'].sum(), 2),
            'Insurance Revenue': round(branch_df.loc[branch_df['is_insurance'], '_allow_after_discount'].sum(), 2),
            'Total Allowed': round(branch_df['_allow_after_discount'].sum(), 2)
        }
        results.append(stats)
    
    return pd.DataFrame(results)


def setup_logging(log_dir: Path):
    """Configure logging to file and console"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"analyze_sales_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logger.info(f"Logging to: {log_file}")


def main(input_dir: Path, output_dir: Path):
    """Main analysis function - builds source of truth data"""
    logger.info("=" * 60)
    logger.info("SALES ORDER DATA PROCESSING")
    logger.info(f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all CSV files
    csv_files = sorted(input_dir.glob("*_SalesOrders.csv"))
    
    if not csv_files:
        logger.error(f"No CSV files found in {input_dir}")
        return
    
    logger.info(f"Found {len(csv_files)} files to process")
    
    all_summaries = []
    all_branch_data = []
    all_data = []
    
    # Process each file
    for filepath in csv_files:
        year_label = filepath.stem.split('_')[0]
        df = load_and_process_file(filepath)
        all_data.append(df)
        
        summary = analyze_dataframe(df, year_label)
        all_summaries.append(summary)
        
        branch_df = analyze_by_branch(df, year_label)
        if not branch_df.empty:
            all_branch_data.append(branch_df)
    
    # Combine all data into single dataframe
    logger.info("Consolidating data...")
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Create summary dataframe with totals
    summary_df = pd.DataFrame(all_summaries)
    totals = {
        'Year': 'TOTAL',
        'Total Line Items': summary_df['Total Line Items'].sum(),
        'Unique Orders': summary_df['Unique Orders'].sum(),
        'Retail Items': summary_df['Retail Items'].sum(),
        'Insurance Items': summary_df['Insurance Items'].sum(),
        'Retail %': round(summary_df['Retail Items'].sum() / summary_df['Total Line Items'].sum() * 100, 2),
        'Insurance %': round(summary_df['Insurance Items'].sum() / summary_df['Total Line Items'].sum() * 100, 2),
        'Primary Billing': summary_df['Primary Billing'].sum(),
        'Secondary Billing': summary_df['Secondary Billing'].sum(),
        'Tertiary Billing': summary_df['Tertiary Billing'].sum(),
        'Multi-Payor Items': summary_df['Multi-Payor Items'].sum(),
        'Total Quantity': summary_df['Total Quantity'].sum(),
        'Gross Allow': round(summary_df['Gross Allow'].sum(), 2),
        'Total Discount': round(summary_df['Total Discount'].sum(), 2),
        'Total Revenue': round(summary_df['Total Revenue'].sum(), 2),
        'Retail Revenue': round(summary_df['Retail Revenue'].sum(), 2),
        'Insurance Revenue': round(summary_df['Insurance Revenue'].sum(), 2),
        'Gross Allowed': round(summary_df['Gross Allowed'].sum(), 2),
        'Total Allowed': round(summary_df['Total Allowed'].sum(), 2),
        'Retail Allowed': round(summary_df['Retail Allowed'].sum(), 2),
        'Insurance Allowed': round(summary_df['Insurance Allowed'].sum(), 2)
    }
    summary_df = pd.concat([summary_df, pd.DataFrame([totals])], ignore_index=True)
    
    # === OUTPUT 1: Summary CSV ===
    summary_file = output_dir / "sales_analysis_summary.csv"
    summary_df.to_csv(summary_file, index=False)
    logger.info(f"Saved: {summary_file.name}")
    
    # === OUTPUT 2: Branch Analysis CSV ===
    if all_branch_data:
        branch_summary = pd.concat(all_branch_data, ignore_index=True)
        branch_file = output_dir / "sales_analysis_by_branch.csv"
        branch_summary.to_csv(branch_file, index=False)
        logger.info(f"Saved: {branch_file.name}")
    
    # === OUTPUT 3: Retail Orders (single column of order numbers with any retail items) ===
    # Orders that contain at least one retail item (may also have insurance items)
    retail_order_numbers = combined_df.loc[combined_df['is_retail'], 'Sales Order Number'].unique()
    retail_orders_df = pd.DataFrame({'Sales Order Number': sorted(retail_order_numbers)})
    retail_orders_file = output_dir / "retail_orders.csv"
    retail_orders_df.to_csv(retail_orders_file, index=False)
    logger.info(f"Saved: {retail_orders_file.name} ({len(retail_orders_df):,} orders)")
    
    # === OUTPUT 4: Retail Line Items (filtered retail items only) ===
    retail_items_df = combined_df[combined_df['is_retail']].copy()
    
    # Select relevant columns for retail analysis
    retail_columns = [
        'Sales Order Number',
        'Sales Order Date Created (YYYY-MM-DD)',
        'Sales Order Branch Office',
        'Sales Order Status',
        'Sales Order Discount Pct',
        'Patient Key',
        'Sales Order Detail Item Id',
        'Sales Order Detail Item Name',
        'Sales Order Detail Item Description',
        'Sales Order Detail Proc Code',
        'Sales Order Detail Qty',
        'Sales Order Detail Charge',
        'Sales Order Detail Allow',
        'Sales Order Detail Taxable',
        'Sales Order Detail Sale Type',
        'Sales Order Detail Item Group',
        '_source_year',
        '_charge_clean',
        '_allow_clean',
        '_discount_decimal',
        '_charge_after_discount',
        '_allow_after_discount',
        '_qty_clean'
    ]
    
    # Keep only columns that exist
    available_cols = [col for col in retail_columns if col in retail_items_df.columns]
    retail_items_export = retail_items_df[available_cols]
    
    retail_items_file = output_dir / "retail_line_items.csv"
    retail_items_export.to_csv(retail_items_file, index=False)
    logger.info(f"Saved: {retail_items_file.name} ({len(retail_items_export):,} items)")
    
    # Log summary
    logger.info("=" * 60)
    logger.info("PROCESSING COMPLETE")
    logger.info("=" * 60)
    
    total_row = summary_df[summary_df['Year'] == 'TOTAL'].iloc[0]
    logger.info(f"Total Line Items: {int(total_row['Total Line Items']):,}")
    logger.info(f"  - Retail: {int(total_row['Retail Items']):,} ({total_row['Retail %']:.1f}%)")
    logger.info(f"  - Insurance: {int(total_row['Insurance Items']):,} ({total_row['Insurance %']:.1f}%)")
    logger.info(f"Retail Orders (with any retail items): {len(retail_orders_df):,}")
    logger.info(f"Retail Line Items: {len(retail_items_export):,}")
    logger.info(f"Outputs saved to: {output_dir}")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Analyze sales orders and classify as Retail vs Insurance'
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Path to input directory containing *_SalesOrders.csv files'
    )
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Output directory path (default: data/output)'
    )
    parser.add_argument(
        '--log-dir',
        default=None,
        help='Directory for log files (default: logs/)'
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    input_dir = Path(args.input)
    
    # Default output to data/output if not specified
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path("data/output")
    
    # Setup logging
    log_dir = Path(args.log_dir) if args.log_dir else Path("logs")
    setup_logging(log_dir)
    
    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)
    
    main(input_dir, output_dir)
