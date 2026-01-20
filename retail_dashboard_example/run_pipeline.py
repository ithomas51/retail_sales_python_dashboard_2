"""
Retail Sales Dashboard Pipeline Orchestrator

Orchestrates the data processing pipeline in the documented flow:
1. py_split_years.py - Split raw data by year
2. analyze_sales_orders.py - Classify and analyze sales orders
3. generate_reports.py - Generate Excel/Plotly reports (optional)
4. retail_dashboard.py - Launch Streamlit dashboard (optional)

Usage:
    # Run full pipeline with dashboard
    python run_pipeline.py -i data/brightree/raw_data.csv --run-dashboard
    
    # Run pipeline without dashboard
    python run_pipeline.py -i data/brightree/87f5502f-c2c2-4930-a276-5daf26fbb34b.csv
    
    # Skip reports, just process data
    python run_pipeline.py -i raw.csv --skip-reports
    
    # Specify custom scripts directory
    python run_pipeline.py -i raw.csv --scripts-dir ./custom_scripts
"""

import argparse
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Setup logging
logger = logging.getLogger(__name__)


def setup_logging(log_dir: Path):
    """Configure logging to file and console"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"run_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logger.info(f"Logging to: {log_file}")
    return log_file


def run_script(script_path: Path, args: list, log_dir: Path) -> bool:
    """Run a Python script with arguments and return success status"""
    cmd = [sys.executable, str(script_path)] + args + ['--log-dir', str(log_dir)]
    logger.info(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                logger.info(f"  {line}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Script failed with exit code {e.returncode}")
        if e.stdout:
            logger.error(f"STDOUT: {e.stdout}")
        if e.stderr:
            logger.error(f"STDERR: {e.stderr}")
        return False


def run_dashboard(script_path: Path, data_dir: Path):
    """Launch Streamlit dashboard"""
    cmd = [sys.executable, '-m', 'streamlit', 'run', str(script_path), '--', '-i', str(data_dir)]
    logger.info(f"Launching dashboard: {' '.join(cmd)}")
    
    try:
        # Run dashboard as foreground process (blocking)
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Dashboard failed: {e}")
    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Retail Sales Dashboard Pipeline Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pipeline Flow:
  1. py_split_years.py      - Split raw CSV by year
  2. analyze_sales_orders.py - Classify Retail vs Insurance
  3. generate_reports.py     - Generate Excel/Charts (optional)
  4. retail_dashboard.py     - Launch Streamlit (optional)

Examples:
  python run_pipeline.py -i data/brightree/raw.csv
  python run_pipeline.py -i raw.csv --run-dashboard
  python run_pipeline.py -i raw.csv --skip-reports --run-dashboard
        """
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Path to raw input CSV file (Brightree export)'
    )
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Output directory for processed data (default: data/output)'
    )
    parser.add_argument(
        '--scripts-dir',
        default=None,
        help='Directory containing processing scripts (default: ./scripts)'
    )
    parser.add_argument(
        '--log-dir',
        default=None,
        help='Directory for log files (default: logs/)'
    )
    parser.add_argument(
        '--skip-reports',
        action='store_true',
        help='Skip report generation (Excel/Charts)'
    )
    parser.add_argument(
        '--run-dashboard',
        action='store_true',
        help='Launch Streamlit dashboard after processing'
    )
    return parser.parse_args()


def main():
    """Main orchestrator function"""
    args = parse_args()
    
    # Resolve paths relative to this script
    script_dir = Path(__file__).parent
    scripts_path = Path(args.scripts_dir) if args.scripts_dir else script_dir / "scripts"
    output_dir = Path(args.output) if args.output else script_dir / "data" / "output"
    log_dir = Path(args.log_dir) if args.log_dir else script_dir / "logs"
    input_file = Path(args.input)
    
    # Validate input file
    if not input_file.exists():
        print(f"ERROR: Input file not found: {input_file}")
        sys.exit(1)
    
    # Validate scripts directory
    if not scripts_path.exists():
        print(f"ERROR: Scripts directory not found: {scripts_path}")
        sys.exit(1)
    
    # Setup logging
    setup_logging(log_dir)
    
    logger.info("=" * 70)
    logger.info("RETAIL SALES DASHBOARD PIPELINE")
    logger.info(f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 70)
    logger.info(f"Input file: {input_file}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Scripts directory: {scripts_path}")
    logger.info(f"Log directory: {log_dir}")
    logger.info("")
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Track pipeline status
    pipeline_success = True
    
    # ========================================
    # STEP 1: Split raw data by year
    # ========================================
    logger.info("-" * 70)
    logger.info("STEP 1: Splitting raw data by year")
    logger.info("-" * 70)
    
    split_script = scripts_path / "py_split_years.py"
    if not split_script.exists():
        logger.error(f"Script not found: {split_script}")
        sys.exit(1)
    
    success = run_script(
        split_script,
        ['-i', str(input_file), '-o', str(output_dir)],
        log_dir
    )
    
    if not success:
        logger.error("STEP 1 FAILED - Aborting pipeline")
        sys.exit(1)
    
    logger.info("STEP 1 COMPLETE")
    
    # ========================================
    # STEP 2: Analyze and classify sales orders
    # ========================================
    logger.info("")
    logger.info("-" * 70)
    logger.info("STEP 2: Analyzing and classifying sales orders")
    logger.info("-" * 70)
    
    analyze_script = scripts_path / "analyze_sales_orders.py"
    if not analyze_script.exists():
        logger.error(f"Script not found: {analyze_script}")
        sys.exit(1)
    
    success = run_script(
        analyze_script,
        ['-i', str(output_dir), '-o', str(output_dir)],
        log_dir
    )
    
    if not success:
        logger.error("STEP 2 FAILED - Aborting pipeline")
        sys.exit(1)
    
    logger.info("STEP 2 COMPLETE")
    
    # ========================================
    # STEP 3: Generate reports (optional)
    # ========================================
    if not args.skip_reports:
        logger.info("")
        logger.info("-" * 70)
        logger.info("STEP 3: Generating reports (Excel/Charts)")
        logger.info("-" * 70)
        
        reports_script = scripts_path / "generate_reports.py"
        if not reports_script.exists():
            logger.warning(f"Script not found: {reports_script} - Skipping reports")
        else:
            reports_dir = output_dir / "reports"
            success = run_script(
                reports_script,
                ['-i', str(output_dir), '-o', str(reports_dir)],
                log_dir
            )
            
            if not success:
                logger.warning("STEP 3 FAILED - Continuing without reports")
                pipeline_success = False
            else:
                logger.info("STEP 3 COMPLETE")
    else:
        logger.info("")
        logger.info("STEP 3: Skipped (--skip-reports)")
    
    # ========================================
    # Summary
    # ========================================
    logger.info("")
    logger.info("=" * 70)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Log directory: {log_dir}")
    
    if pipeline_success:
        logger.info("Status: SUCCESS")
    else:
        logger.info("Status: COMPLETED WITH WARNINGS")
    
    # ========================================
    # STEP 4: Launch dashboard (optional)
    # ========================================
    if args.run_dashboard:
        logger.info("")
        logger.info("-" * 70)
        logger.info("STEP 4: Launching Retail Dashboard")
        logger.info("-" * 70)
        
        dashboard_script = scripts_path / "retail_dashboard.py"
        if not dashboard_script.exists():
            logger.error(f"Script not found: {dashboard_script}")
            sys.exit(1)
        
        run_dashboard(dashboard_script, output_dir)


if __name__ == "__main__":
    main()
