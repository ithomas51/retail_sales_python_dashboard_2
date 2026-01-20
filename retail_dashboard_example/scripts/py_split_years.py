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


def load_and_transform_dates(input_path):
    """Load CSV and create standardized date column."""
    df = pd.read_csv(input_path)
    
    # convert Sales Order Date Created column to YYYY-MM-DD format safely
    # errors='coerce' will convert invalid dates to NaT (Not a Time)
    df['Sales Order Date Created (YYYY-MM-DD)'] = pd.to_datetime(
        df['Sales Order Date Created'], errors='coerce'
    ).dt.strftime('%Y-%m-%d')
    
    # Remove rows with invalid dates
    df = df.dropna(subset=['Sales Order Date Created (YYYY-MM-DD)'])
    
    # Position the new column at index 1
    cols = list(df.columns)
    cols.insert(1, cols.pop(cols.index('Sales Order Date Created (YYYY-MM-DD)')))
    df = df[cols]
    
    return df


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
    
    # Load and transform data
    logger.info(f"Loading data from {args.input}...")
    df = load_and_transform_dates(args.input)
    logger.info(f"Loaded {len(df)} records with valid dates")
    
    # Split by year and save
    logger.info(f"Splitting data by year into {args.output}/...")
    files_created = split_by_year(df, args.output)
    
    # Report results
    logger.info(f"Successfully created {len(files_created)} year-based CSV files:")
    for file in sorted(files_created):
        logger.info(f"  - {file}")


if __name__ == "__main__":
    main()