"""
Invoice Pipeline Orchestrator
Runs the full invoice data processing pipeline:
1. analyze_invoices.py - Process raw invoice data
2. generate_reports.py - Create Excel workbook and charts
3. (optional) Launch Streamlit dashboard

Usage:
    python run_pipeline.py -i data/brightree/invoices
    python run_pipeline.py -i data/brightree/invoices --run-dashboard
    python run_pipeline.py -i data/brightree/invoices --skip-reports
"""

import argparse
import subprocess
import sys
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)


def setup_logging(log_dir: Path):
    """Configure logging to file and console."""
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


def run_script(script_path: Path, args: list, description: str) -> bool:
    """Run a Python script with arguments."""
    logger.info(f"Running: {description}")
    logger.info(f"  Script: {script_path}")
    logger.info(f"  Args: {' '.join(args)}")
    
    cmd = [sys.executable, str(script_path)] + args
    
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
        
        logger.info(f"  ✓ {description} completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"  ✗ {description} failed with exit code {e.returncode}")
        if e.stdout:
            logger.error(f"  STDOUT: {e.stdout}")
        if e.stderr:
            logger.error(f"  STDERR: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"  ✗ {description} failed: {e}")
        return False


def main():
    """Main pipeline function."""
    parser = argparse.ArgumentParser(
        description='Run the complete invoice data processing pipeline'
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Path to input directory containing invoice CSV files'
    )
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Output directory (default: data/output)'
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
        help='Skip Excel/chart generation'
    )
    parser.add_argument(
        '--run-dashboard',
        action='store_true',
        help='Launch Streamlit dashboard after processing'
    )
    
    args = parser.parse_args()
    
    # Setup paths
    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output).resolve() if args.output else Path("data/output").resolve()
    scripts_dir = Path(args.scripts_dir).resolve() if args.scripts_dir else Path("scripts").resolve()
    log_dir = Path(args.log_dir).resolve() if args.log_dir else Path("logs").resolve()
    
    # Setup logging
    setup_logging(log_dir)
    
    logger.info("=" * 60)
    logger.info("INVOICE PROCESSING PIPELINE")
    logger.info(f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    logger.info(f"Input Directory: {input_dir}")
    logger.info(f"Output Directory: {output_dir}")
    logger.info(f"Scripts Directory: {scripts_dir}")
    logger.info("")
    
    # Validate input directory
    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        sys.exit(1)
    
    csv_files = list(input_dir.glob("*.csv"))
    if not csv_files:
        logger.error(f"No CSV files found in {input_dir}")
        sys.exit(1)
    
    logger.info(f"Found {len(csv_files)} CSV files to process")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    success = True
    
    # Step 1: Analyze invoices
    logger.info("-" * 40)
    logger.info("STEP 1: ANALYZE INVOICES")
    logger.info("-" * 40)
    
    analyze_script = scripts_dir / "analyze_invoices.py"
    if not analyze_script.exists():
        logger.error(f"Script not found: {analyze_script}")
        sys.exit(1)
    
    analyze_args = [
        '-i', str(input_dir),
        '-o', str(output_dir),
        '--log-dir', str(log_dir)
    ]
    
    if not run_script(analyze_script, analyze_args, "Invoice Analysis"):
        logger.error("Pipeline failed at Step 1")
        success = False
    
    # Step 2: Generate reports (optional)
    if success and not args.skip_reports:
        logger.info("-" * 40)
        logger.info("STEP 2: GENERATE REPORTS")
        logger.info("-" * 40)
        
        reports_script = scripts_dir / "generate_reports.py"
        if not reports_script.exists():
            logger.warning(f"Reports script not found: {reports_script}")
            logger.warning("Skipping report generation")
        else:
            reports_output = output_dir / "reports"
            
            reports_args = [
                '-i', str(output_dir),
                '-o', str(reports_output),
                '--log-dir', str(log_dir)
            ]
            
            if not run_script(reports_script, reports_args, "Report Generation"):
                logger.warning("Report generation failed, but continuing...")
    
    # Summary
    logger.info("=" * 60)
    if success:
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
    else:
        logger.info("PIPELINE COMPLETED WITH ERRORS")
    logger.info("=" * 60)
    
    # List output files
    logger.info("Output files:")
    for f in sorted(output_dir.rglob("*")):
        if f.is_file():
            size_kb = f.stat().st_size / 1024
            logger.info(f"  {f.relative_to(output_dir)}: {size_kb:.1f} KB")
    
    # Step 3: Launch dashboard (optional)
    if args.run_dashboard:
        logger.info("-" * 40)
        logger.info("LAUNCHING DASHBOARD")
        logger.info("-" * 40)
        
        dashboard_script = scripts_dir / "invoice_dashboard.py"
        if not dashboard_script.exists():
            logger.error(f"Dashboard script not found: {dashboard_script}")
        else:
            logger.info(f"Starting Streamlit dashboard...")
            logger.info(f"URL: http://localhost:8501")
            logger.info("Press Ctrl+C to stop the dashboard")
            
            try:
                subprocess.run([
                    sys.executable, '-m', 'streamlit', 'run',
                    str(dashboard_script),
                    '--',
                    '-i', str(input_dir)
                ])
            except KeyboardInterrupt:
                logger.info("Dashboard stopped")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
