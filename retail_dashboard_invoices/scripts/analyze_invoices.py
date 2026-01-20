"""
Invoice Analysis Script - Core Data Processing
Analyzes invoice data from Brightree CSV files, classifies Retail vs Insurance
based on Policy Payor Level, and calculates billing/payment metrics.

Usage:
    python analyze_invoices.py -i data/brightree/invoices -o data/output
    python analyze_invoices.py --input ./invoices --output ./analysis

Outputs:
- invoice_analysis_summary.csv: Year-by-year summary statistics
- invoice_analysis_by_branch.csv: Branch-level breakdown
- retail_invoices.csv: Invoice numbers with retail (Patient) items
- retail_invoice_items.csv: All retail line items filtered
- rental_billing_analysis.csv: Billing period distribution
"""

import argparse
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# Setup logging
logger = logging.getLogger(__name__)

# Column mappings
INVOICE_COLUMNS = {
    'number': 'Invoice Number',
    'status': 'Invoice Status',
    'so_number': 'Invoice Sales Order Number',
    'date_created': 'Invoice Date Created',
    'date_of_service': 'Invoice Date of Service',
    'branch': 'Invoice Branch',
    'so_classification': 'Invoice SO Classification',
    'aging_bucket': 'Invoice Aging Bucket - DOS',
    'patient_id': 'Patient ID',
    'payor_name': 'Policy Payor Name',
    'payor_id': 'Policy Payor ID',
    'payor_level': 'Policy Payor Level',
    'group_name': 'Policy Group Name',
    'insurance_company': 'Policy Insurance Company',
    'plan_type': 'Policy Plan Type',
    'item_id': 'Invoice Detail Item ID',
    'item_name': 'Invoice Detail Item Name',
    'billing_period': 'Invoice Detail Billing Period',
    'payments': 'Invoice Detail Payments',
    'balance': 'Invoice Detail Balance',
    'qty': 'Invoice Detail Qty',
    'proc_code': 'Invoice Detail Proc Code',
    'item_group': 'Invoice Detail Item Group',
    'gl_period': 'Invoice Detail GL Period',
    'referral_type': 'Referral Type'
}


def clean_currency(value):
    """
    Clean currency string to float.
    Handles: $1,234.56, ($100.00), empty strings, null values
    """
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


def safe_parse_date(value):
    """
    Safe parse date to YYYY-MM-DD format string, then to datetime.
    Handles: M/D/YYYY H:MM:SS AM/PM, M/D/YYYY, and various other formats.
    Returns datetime object or pd.NaT.
    """
    if pd.isna(value):
        return pd.NaT
    if isinstance(value, (pd.Timestamp, datetime)):
        return value
    try:
        s = str(value).strip()
        if not s:
            return pd.NaT
        # Try common date formats
        for fmt in [
            '%m/%d/%Y %I:%M:%S %p',  # 9/29/2020 3:06:15 AM
            '%m/%d/%Y %H:%M:%S',      # 9/29/2020 15:06:15
            '%m/%d/%Y',               # 9/29/2020
            '%Y-%m-%d %H:%M:%S',      # 2020-09-29 15:06:15
            '%Y-%m-%d',               # 2020-09-29
        ]:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        # Fallback: try pandas
        return pd.to_datetime(s, errors='coerce')
    except Exception:
        return pd.NaT


# Global proc code mapping dictionary (loaded once)
_PROC_CODE_MAPPING = None


def load_proc_code_mapping(mapping_file: Path = None) -> dict:
    """
    Load proc code mapping from CSV file.
    Maps original proc codes (from originals_pipe) to standardized codes (final5).
    Returns dict: {original_code: final5_code}
    """
    global _PROC_CODE_MAPPING
    if _PROC_CODE_MAPPING is not None:
        return _PROC_CODE_MAPPING
    
    _PROC_CODE_MAPPING = {}
    
    if mapping_file is None:
        # Default location relative to script (in data folder)
        mapping_file = Path(__file__).parent.parent / 'data' / 'mapping_suggestions_DW_fixed.csv'
    
    if not mapping_file.exists():
        logger.warning(f"Proc code mapping file not found: {mapping_file}")
        return _PROC_CODE_MAPPING
    
    try:
        mapping_df = pd.read_csv(mapping_file)
        for _, row in mapping_df.iterrows():
            final5 = str(row['final5']).strip().upper()
            originals = str(row['originals_pipe'])
            # Split by pipe and map each original to final5
            for orig in originals.split('|'):
                orig_clean = orig.strip()
                if orig_clean:
                    # Store both original case and uppercase for matching
                    _PROC_CODE_MAPPING[orig_clean] = final5
                    _PROC_CODE_MAPPING[orig_clean.upper()] = final5
                    _PROC_CODE_MAPPING[orig_clean.lower()] = final5
        logger.info(f"Loaded {len(_PROC_CODE_MAPPING)} proc code mappings from {mapping_file.name}")
    except Exception as e:
        logger.error(f"Error loading proc code mapping: {e}")
    
    return _PROC_CODE_MAPPING


def clean_proc_code(value) -> str:
    """
    Clean and standardize procedure code using mapping file.
    Returns standardized HCPCS code (final5) or original if not mapped.
    """
    if pd.isna(value):
        return 'UNKNOWN'
    
    orig = str(value).strip()
    if not orig:
        return 'UNKNOWN'
    
    mapping = load_proc_code_mapping()
    
    # Try exact match first
    if orig in mapping:
        return mapping[orig]
    
    # Try uppercase
    if orig.upper() in mapping:
        return mapping[orig.upper()]
    
    # No mapping found - return uppercase original
    return orig.upper()


def parse_date(value):
    """
    Parse date string to datetime.
    Handles: M/D/YYYY H:MM:SS AM/PM format
    """
    if pd.isna(value):
        return pd.NaT
    try:
        # Try common formats
        for fmt in ['%m/%d/%Y %I:%M:%S %p', '%m/%d/%Y %H:%M:%S', '%m/%d/%Y']:
            try:
                return pd.to_datetime(value, format=fmt)
            except ValueError:
                continue
        # Fallback to pandas inference
        return pd.to_datetime(value)
    except Exception:
        return pd.NaT


def load_and_process_file(filepath):
    """Load a CSV file and add classification/metric columns."""
    logger.info(f"Processing: {filepath.name}")
    
    df = pd.read_csv(filepath, low_memory=False)
    
    # Extract year from filename
    year_label = filepath.stem
    df['_source_year'] = year_label
    
    # === SAFE DATE PARSING (at very beginning of pipeline) ===
    # Parse dates using safe_parse_date -> outputs YYYY-MM-DD compatible datetime
    if INVOICE_COLUMNS['date_created'] in df.columns:
        df['_date_created'] = df[INVOICE_COLUMNS['date_created']].apply(safe_parse_date)
    else:
        df['_date_created'] = pd.NaT
    
    if INVOICE_COLUMNS['date_of_service'] in df.columns:
        df['_date_of_service'] = df[INVOICE_COLUMNS['date_of_service']].apply(safe_parse_date)
    else:
        df['_date_of_service'] = pd.NaT
    
    # === CLEAN PROC CODES (early in pipeline) ===
    # Map raw proc codes to standardized HCPCS codes using mapping file
    if INVOICE_COLUMNS['proc_code'] in df.columns:
        df['_proc_code_clean'] = df[INVOICE_COLUMNS['proc_code']].apply(clean_proc_code)
    else:
        df['_proc_code_clean'] = 'UNKNOWN'
    
    # Classify as Retail or Insurance based on Policy Payor Level
    # RETAIL = Patient (self-pay / private pay)
    # INSURANCE = Primary, Secondary, or Tertiary
    payor_col = INVOICE_COLUMNS['payor_level']
    if payor_col in df.columns:
        df['is_retail'] = df[payor_col].str.strip().str.lower() == 'patient'
        df['is_insurance'] = df[payor_col].str.strip().str.lower().isin(['primary', 'secondary', 'tertiary'])
        df['payor_level_clean'] = df[payor_col].str.strip()
    else:
        df['is_retail'] = False
        df['is_insurance'] = False
        df['payor_level_clean'] = 'Unknown'
    
    # Clean payment and balance values
    payments_col = INVOICE_COLUMNS['payments']
    balance_col = INVOICE_COLUMNS['balance']
    
    if payments_col in df.columns:
        df['_payments'] = df[payments_col].apply(clean_currency)
    else:
        df['_payments'] = 0.0
    
    if balance_col in df.columns:
        df['_balance'] = df[balance_col].apply(clean_currency)
    else:
        df['_balance'] = 0.0
    
    # Calculate total billed and collection rate
    df['_total_billed'] = df['_payments'] + df['_balance'].abs()
    df['_collection_rate'] = np.where(
        df['_total_billed'] > 0,
        (df['_payments'] / df['_total_billed'] * 100).round(2),
        100.0
    )
    
    # Parse billing period for rental analysis
    billing_period_col = INVOICE_COLUMNS['billing_period']
    if billing_period_col in df.columns:
        df['_billing_period'] = pd.to_numeric(df[billing_period_col], errors='coerce').fillna(1).astype(int)
    else:
        df['_billing_period'] = 1
    
    # Classify recurring vs new
    df['is_recurring'] = df['_billing_period'] > 1
    df['is_new'] = df['_billing_period'] == 1
    
    # Clean quantity
    qty_col = INVOICE_COLUMNS['qty']
    if qty_col in df.columns:
        df['_qty'] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)
    else:
        df['_qty'] = 0
    
    return df


def analyze_dataframe(df, year_label):
    """Generate summary statistics for a dataframe."""
    total_items = len(df)
    if total_items == 0:
        return None
    
    retail_items = df['is_retail'].sum()
    insurance_items = df['is_insurance'].sum()
    
    # Unique counts
    unique_invoices = df[INVOICE_COLUMNS['number']].nunique()
    unique_orders = df[INVOICE_COLUMNS['so_number']].nunique()
    unique_patients = df[INVOICE_COLUMNS['patient_id']].nunique() if INVOICE_COLUMNS['patient_id'] in df.columns else 0
    
    # Financial metrics
    total_payments = df['_payments'].sum()
    total_balance = df['_balance'].sum()
    total_billed = df['_total_billed'].sum()
    
    retail_payments = df.loc[df['is_retail'], '_payments'].sum()
    insurance_payments = df.loc[df['is_insurance'], '_payments'].sum()
    
    retail_balance = df.loc[df['is_retail'], '_balance'].sum()
    insurance_balance = df.loc[df['is_insurance'], '_balance'].sum()
    
    # Collection rate
    overall_collection_rate = (total_payments / total_billed * 100) if total_billed > 0 else 100.0
    
    # Billing period metrics
    recurring_items = df['is_recurring'].sum()
    new_items = df['is_new'].sum()
    avg_billing_period = df['_billing_period'].mean()
    max_billing_period = df['_billing_period'].max()
    
    # Quantity
    total_qty = df['_qty'].sum()
    
    return {
        'Year': year_label,
        'Total Line Items': total_items,
        'Unique Invoices': unique_invoices,
        'Unique Orders': unique_orders,
        'Unique Patients': unique_patients,
        'Retail Items': int(retail_items),
        'Insurance Items': int(insurance_items),
        'Retail %': round(retail_items / total_items * 100, 2) if total_items > 0 else 0,
        'Insurance %': round(insurance_items / total_items * 100, 2) if total_items > 0 else 0,
        'Total Payments': round(total_payments, 2),
        'Total Balance': round(total_balance, 2),
        'Total Billed': round(total_billed, 2),
        'Collection Rate %': round(overall_collection_rate, 2),
        'Retail Payments': round(retail_payments, 2),
        'Insurance Payments': round(insurance_payments, 2),
        'Retail Balance': round(retail_balance, 2),
        'Insurance Balance': round(insurance_balance, 2),
        'New Items (Period 1)': int(new_items),
        'Recurring Items (Period 2+)': int(recurring_items),
        'Recurring %': round(recurring_items / total_items * 100, 2) if total_items > 0 else 0,
        'Avg Billing Period': round(avg_billing_period, 2),
        'Max Billing Period': int(max_billing_period),
        'Total Quantity': round(total_qty, 2)
    }


def analyze_by_branch(df, year_label):
    """Analyze data by branch office."""
    branch_col = INVOICE_COLUMNS['branch']
    if branch_col not in df.columns:
        return pd.DataFrame()
    
    results = []
    for branch in df[branch_col].unique():
        if pd.isna(branch):
            branch_name = "Unknown"
            branch_df = df[df[branch_col].isna()]
        else:
            branch_name = str(branch).strip()
            branch_df = df[df[branch_col] == branch]
        
        if len(branch_df) == 0:
            continue
        
        stats = {
            'Year': year_label,
            'Branch': branch_name,
            'Total Items': len(branch_df),
            'Retail Items': int(branch_df['is_retail'].sum()),
            'Insurance Items': int(branch_df['is_insurance'].sum()),
            'Retail %': round(branch_df['is_retail'].sum() / len(branch_df) * 100, 2),
            'Insurance %': round(branch_df['is_insurance'].sum() / len(branch_df) * 100, 2),
            'Unique Invoices': branch_df[INVOICE_COLUMNS['number']].nunique(),
            'Total Payments': round(branch_df['_payments'].sum(), 2),
            'Retail Payments': round(branch_df.loc[branch_df['is_retail'], '_payments'].sum(), 2),
            'Insurance Payments': round(branch_df.loc[branch_df['is_insurance'], '_payments'].sum(), 2),
            'Total Balance': round(branch_df['_balance'].sum(), 2),
            'Collection Rate %': round(
                branch_df['_payments'].sum() / branch_df['_total_billed'].sum() * 100, 2
            ) if branch_df['_total_billed'].sum() > 0 else 100.0,
            'Recurring Items': int(branch_df['is_recurring'].sum()),
            'Recurring %': round(branch_df['is_recurring'].sum() / len(branch_df) * 100, 2),
            'Avg Billing Period': round(branch_df['_billing_period'].mean(), 2)
        }
        results.append(stats)
    
    return pd.DataFrame(results)


def analyze_billing_periods(df, year_label):
    """Analyze billing period distribution for rental analysis."""
    results = []
    
    # Group billing periods into buckets
    period_buckets = [
        (1, 1, 'Period 1 (New)'),
        (2, 3, 'Period 2-3'),
        (4, 6, 'Period 4-6'),
        (7, 12, 'Period 7-12'),
        (13, 24, 'Period 13-24'),
        (25, 36, 'Period 25-36'),
        (37, 999, 'Period 37+')
    ]
    
    for start, end, label in period_buckets:
        bucket_df = df[(df['_billing_period'] >= start) & (df['_billing_period'] <= end)]
        if len(bucket_df) == 0:
            continue
        
        stats = {
            'Year': year_label,
            'Billing Period Bucket': label,
            'Period Start': start,
            'Period End': end,
            'Item Count': len(bucket_df),
            'Item %': round(len(bucket_df) / len(df) * 100, 2),
            'Total Payments': round(bucket_df['_payments'].sum(), 2),
            'Payment %': round(bucket_df['_payments'].sum() / df['_payments'].sum() * 100, 2) if df['_payments'].sum() > 0 else 0,
            'Retail Items': int(bucket_df['is_retail'].sum()),
            'Insurance Items': int(bucket_df['is_insurance'].sum()),
            'Avg Payment': round(bucket_df['_payments'].mean(), 2)
        }
        results.append(stats)
    
    return pd.DataFrame(results)


def setup_logging(log_dir: Path):
    """Configure logging to file and console."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"analyze_invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
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
    """Main analysis function - processes all invoice files."""
    logger.info("=" * 60)
    logger.info("INVOICE DATA PROCESSING")
    logger.info(f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all CSV files
    csv_files = sorted(input_dir.glob("*.csv"))
    
    if not csv_files:
        logger.error(f"No CSV files found in {input_dir}")
        return
    
    logger.info(f"Found {len(csv_files)} files to process")
    
    all_summaries = []
    all_branch_data = []
    all_billing_data = []
    all_data = []
    
    # Process each file
    for filepath in csv_files:
        year_label = filepath.stem
        logger.info(f"Loading {filepath.name}...")
        
        df = load_and_process_file(filepath)
        all_data.append(df)
        
        logger.info(f"  Rows: {len(df):,}")
        
        summary = analyze_dataframe(df, year_label)
        if summary:
            all_summaries.append(summary)
        
        branch_df = analyze_by_branch(df, year_label)
        if not branch_df.empty:
            all_branch_data.append(branch_df)
        
        billing_df = analyze_billing_periods(df, year_label)
        if not billing_df.empty:
            all_billing_data.append(billing_df)
    
    # Combine all data
    logger.info("Consolidating data...")
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Create summary with totals
    summary_df = pd.DataFrame(all_summaries)
    
    # Calculate totals row
    totals = {
        'Year': 'TOTAL',
        'Total Line Items': summary_df['Total Line Items'].sum(),
        'Unique Invoices': summary_df['Unique Invoices'].sum(),
        'Unique Orders': summary_df['Unique Orders'].sum(),
        'Unique Patients': summary_df['Unique Patients'].sum(),
        'Retail Items': summary_df['Retail Items'].sum(),
        'Insurance Items': summary_df['Insurance Items'].sum(),
        'Retail %': round(summary_df['Retail Items'].sum() / summary_df['Total Line Items'].sum() * 100, 2),
        'Insurance %': round(summary_df['Insurance Items'].sum() / summary_df['Total Line Items'].sum() * 100, 2),
        'Total Payments': round(summary_df['Total Payments'].sum(), 2),
        'Total Balance': round(summary_df['Total Balance'].sum(), 2),
        'Total Billed': round(summary_df['Total Billed'].sum(), 2),
        'Collection Rate %': round(
            summary_df['Total Payments'].sum() / summary_df['Total Billed'].sum() * 100, 2
        ) if summary_df['Total Billed'].sum() > 0 else 100.0,
        'Retail Payments': round(summary_df['Retail Payments'].sum(), 2),
        'Insurance Payments': round(summary_df['Insurance Payments'].sum(), 2),
        'Retail Balance': round(summary_df['Retail Balance'].sum(), 2),
        'Insurance Balance': round(summary_df['Insurance Balance'].sum(), 2),
        'New Items (Period 1)': summary_df['New Items (Period 1)'].sum(),
        'Recurring Items (Period 2+)': summary_df['Recurring Items (Period 2+)'].sum(),
        'Recurring %': round(
            summary_df['Recurring Items (Period 2+)'].sum() / summary_df['Total Line Items'].sum() * 100, 2
        ),
        'Avg Billing Period': round(summary_df['Avg Billing Period'].mean(), 2),
        'Max Billing Period': summary_df['Max Billing Period'].max(),
        'Total Quantity': round(summary_df['Total Quantity'].sum(), 2)
    }
    summary_df = pd.concat([summary_df, pd.DataFrame([totals])], ignore_index=True)
    
    # === OUTPUT 1: Summary CSV ===
    summary_file = output_dir / "invoice_analysis_summary.csv"
    summary_df.to_csv(summary_file, index=False)
    logger.info(f"Saved: {summary_file.name}")
    
    # === OUTPUT 2: Branch Analysis CSV ===
    if all_branch_data:
        branch_summary = pd.concat(all_branch_data, ignore_index=True)
        branch_file = output_dir / "invoice_analysis_by_branch.csv"
        branch_summary.to_csv(branch_file, index=False)
        logger.info(f"Saved: {branch_file.name}")
    
    # === OUTPUT 3: Billing Period Analysis CSV ===
    if all_billing_data:
        billing_summary = pd.concat(all_billing_data, ignore_index=True)
        billing_file = output_dir / "rental_billing_analysis.csv"
        billing_summary.to_csv(billing_file, index=False)
        logger.info(f"Saved: {billing_file.name}")
    
    # === OUTPUT 4: Retail Invoices (unique invoice numbers) ===
    retail_invoice_numbers = combined_df.loc[combined_df['is_retail'], INVOICE_COLUMNS['number']].unique()
    retail_invoices_df = pd.DataFrame({'Invoice Number': sorted(retail_invoice_numbers)})
    retail_invoices_file = output_dir / "retail_invoices.csv"
    retail_invoices_df.to_csv(retail_invoices_file, index=False)
    logger.info(f"Saved: {retail_invoices_file.name} ({len(retail_invoices_df):,} invoices)")
    
    # === OUTPUT 5: Retail Invoice Items (all retail line items) ===
    retail_items_df = combined_df[combined_df['is_retail']].copy()
    
    # Select relevant columns
    retail_columns = [
        INVOICE_COLUMNS['number'],
        INVOICE_COLUMNS['so_number'],
        INVOICE_COLUMNS['date_of_service'],
        INVOICE_COLUMNS['branch'],
        INVOICE_COLUMNS['so_classification'],
        INVOICE_COLUMNS['payor_level'],
        INVOICE_COLUMNS['item_id'],
        INVOICE_COLUMNS['item_name'],
        INVOICE_COLUMNS['billing_period'],
        INVOICE_COLUMNS['payments'],
        INVOICE_COLUMNS['balance'],
        INVOICE_COLUMNS['qty'],
        INVOICE_COLUMNS['proc_code'],
        '_proc_code_clean',
        INVOICE_COLUMNS['item_group'],
        '_source_year',
        '_date_created',
        '_date_of_service',
        '_payments',
        '_balance',
        '_billing_period',
        '_collection_rate'
    ]
    
    available_cols = [col for col in retail_columns if col in retail_items_df.columns]
    retail_items_export = retail_items_df[available_cols]
    
    retail_items_file = output_dir / "retail_invoice_items.csv"
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
    logger.info(f"Total Payments: ${total_row['Total Payments']:,.2f}")
    logger.info(f"  - Retail: ${total_row['Retail Payments']:,.2f}")
    logger.info(f"  - Insurance: ${total_row['Insurance Payments']:,.2f}")
    logger.info(f"Collection Rate: {total_row['Collection Rate %']:.1f}%")
    logger.info(f"Recurring Items: {int(total_row['Recurring Items (Period 2+)']):,} ({total_row['Recurring %']:.1f}%)")
    logger.info(f"Outputs saved to: {output_dir}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Analyze invoice data and classify as Retail vs Insurance'
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Path to input directory containing invoice CSV files'
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
    
    # Default output
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path("data/output")
    
    # Setup logging
    log_dir = Path(args.log_dir) if args.log_dir else Path("logs")
    setup_logging(log_dir)
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    main(input_dir, output_dir)
