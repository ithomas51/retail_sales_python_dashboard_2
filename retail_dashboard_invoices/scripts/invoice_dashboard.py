"""
Invoice Dashboard - Interactive Streamlit Application
Provides analytics for invoice data with Retail vs Insurance classification,
billing period analysis, and collection metrics.

Usage:
    streamlit run invoice_dashboard.py -- -i data/brightree/invoices

Features:
- 5-Year dashboard (FY2021 - FY2025)
- Rolling periods: 1mo, 3mo, 6mo, 90d
- Metrics grouped by Branch, then Time Period
- Collection rate visualization
- Rental billing period analysis
"""

import argparse
import sys
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(
    page_title="Invoice Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
DASHBOARD_END_DATE = datetime(2025, 12, 31)  # FY2025 end
DASHBOARD_START_DATE = datetime(2021, 1, 1)  # 5-year start

INVOICE_COLUMNS = {
    'number': 'Invoice Number',
    'status': 'Invoice Status',
    'so_number': 'Invoice Sales Order Number',
    'date_created': 'Invoice Date Created',
    'date_of_service': 'Invoice Date of Service',
    'branch': 'Invoice Branch',
    'so_classification': 'Invoice SO Classification',
    'payor_level': 'Policy Payor Level',
    'payor_name': 'Policy Payor Name',
    'plan_type': 'Policy Plan Type',
    'item_id': 'Invoice Detail Item ID',
    'item_name': 'Invoice Detail Item Name',
    'billing_period': 'Invoice Detail Billing Period',
    'payments': 'Invoice Detail Payments',
    'balance': 'Invoice Detail Balance',
    'qty': 'Invoice Detail Qty',
    'proc_code': 'Invoice Detail Proc Code',
    'item_group': 'Invoice Detail Item Group',
    'referral_type': 'Referral Type'
}


def clean_currency(value):
    """Clean currency string to float."""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).replace('$', '').replace(',', '').strip()
    if not s:
        return 0.0
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return 0.0


@st.cache_data(ttl=3600)
def load_invoice_data(input_dir: str) -> pd.DataFrame:
    """Load and process all invoice CSV files."""
    input_path = Path(input_dir)
    csv_files = sorted(input_path.glob("*.csv"))
    
    if not csv_files:
        st.error(f"No CSV files found in {input_dir}")
        return pd.DataFrame()
    
    all_data = []
    progress_bar = st.progress(0, text="Loading invoice data...")
    
    for i, filepath in enumerate(csv_files):
        df = pd.read_csv(filepath, low_memory=False)
        df['_source_year'] = filepath.stem
        all_data.append(df)
        progress_bar.progress((i + 1) / len(csv_files), text=f"Loading {filepath.name}...")
    
    progress_bar.empty()
    
    combined = pd.concat(all_data, ignore_index=True)
    
    # Parse dates
    if INVOICE_COLUMNS['date_of_service'] in combined.columns:
        combined['invoice_date'] = pd.to_datetime(
            combined[INVOICE_COLUMNS['date_of_service']], 
            format='mixed', errors='coerce'
        )
    else:
        combined['invoice_date'] = pd.NaT
    
    # Classification
    payor_col = INVOICE_COLUMNS['payor_level']
    if payor_col in combined.columns:
        combined['is_retail'] = combined[payor_col].str.strip().str.lower() == 'patient'
        combined['is_insurance'] = combined[payor_col].str.strip().str.lower().isin(['primary', 'secondary', 'tertiary'])
        combined['payor_level_clean'] = combined[payor_col].str.strip()
    else:
        combined['is_retail'] = False
        combined['is_insurance'] = False
        combined['payor_level_clean'] = 'Unknown'
    
    # Clean financial columns
    combined['payments'] = combined[INVOICE_COLUMNS['payments']].apply(clean_currency)
    combined['balance'] = combined[INVOICE_COLUMNS['balance']].apply(clean_currency)
    combined['total_billed'] = combined['payments'] + combined['balance'].abs()
    
    # Billing period
    if INVOICE_COLUMNS['billing_period'] in combined.columns:
        combined['billing_period'] = pd.to_numeric(
            combined[INVOICE_COLUMNS['billing_period']], errors='coerce'
        ).fillna(1).astype(int)
    else:
        combined['billing_period'] = 1
    
    combined['is_recurring'] = combined['billing_period'] > 1
    
    # Quantity
    if INVOICE_COLUMNS['qty'] in combined.columns:
        combined['qty'] = pd.to_numeric(combined[INVOICE_COLUMNS['qty']], errors='coerce').fillna(0)
    else:
        combined['qty'] = 0
    
    # Branch clean
    if INVOICE_COLUMNS['branch'] in combined.columns:
        combined['branch'] = combined[INVOICE_COLUMNS['branch']].fillna('Unknown').str.strip()
    else:
        combined['branch'] = 'Unknown'
    
    return combined


def get_time_filtered_data(df: pd.DataFrame, period: str, reference_date=None) -> pd.DataFrame:
    """Filter data by time period."""
    if reference_date is None:
        reference_date = datetime.now()
    
    if period == "1 Month":
        start_date = reference_date - timedelta(days=30)
        return df[df['invoice_date'] >= start_date]
    elif period == "3 Months":
        start_date = reference_date - timedelta(days=90)
        return df[df['invoice_date'] >= start_date]
    elif period == "6 Months":
        start_date = reference_date - timedelta(days=180)
        return df[df['invoice_date'] >= start_date]
    elif period == "90 Days":
        start_date = reference_date - timedelta(days=90)
        return df[df['invoice_date'] >= start_date]
    elif period == "YTD":
        start_date = datetime(2025, 1, 1)
        return df[(df['invoice_date'] >= start_date) & (df['invoice_date'] <= DASHBOARD_END_DATE)]
    elif period == "QTD":
        # Q4 2025
        start_date = datetime(2025, 10, 1)
        return df[(df['invoice_date'] >= start_date) & (df['invoice_date'] <= DASHBOARD_END_DATE)]
    elif period == "FY 2025":
        return df[(df['invoice_date'] >= datetime(2025, 1, 1)) & 
                  (df['invoice_date'] <= DASHBOARD_END_DATE)]
    elif period == "5 Years":
        return df[(df['invoice_date'] >= DASHBOARD_START_DATE) & 
                  (df['invoice_date'] <= DASHBOARD_END_DATE)]
    else:  # All Time
        return df


def calculate_metrics(df: pd.DataFrame) -> dict:
    """Calculate key metrics from dataframe."""
    if len(df) == 0:
        return {
            'total_items': 0,
            'total_payments': 0,
            'total_balance': 0,
            'collection_rate': 100.0,
            'unique_invoices': 0,
            'retail_items': 0,
            'insurance_items': 0,
            'retail_payments': 0,
            'insurance_payments': 0,
            'recurring_pct': 0,
            'avg_billing_period': 0
        }
    
    total_payments = df['payments'].sum()
    total_balance = df['balance'].sum()
    total_billed = df['total_billed'].sum()
    
    return {
        'total_items': len(df),
        'total_payments': total_payments,
        'total_balance': total_balance,
        'collection_rate': (total_payments / total_billed * 100) if total_billed > 0 else 100.0,
        'unique_invoices': df[INVOICE_COLUMNS['number']].nunique(),
        'retail_items': df['is_retail'].sum(),
        'insurance_items': df['is_insurance'].sum(),
        'retail_payments': df.loc[df['is_retail'], 'payments'].sum(),
        'insurance_payments': df.loc[df['is_insurance'], 'payments'].sum(),
        'recurring_pct': (df['is_recurring'].sum() / len(df) * 100) if len(df) > 0 else 0,
        'avg_billing_period': df['billing_period'].mean()
    }


def display_metrics_panel(metrics: dict, title: str = "Key Metrics"):
    """Display metrics in a styled panel."""
    st.subheader(title)
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("💰 Total Collected", f"${metrics['total_payments']:,.0f}")
    
    with col2:
        st.metric("⏳ Outstanding", f"${metrics['total_balance']:,.0f}")
    
    with col3:
        st.metric("📊 Collection Rate", f"{metrics['collection_rate']:.1f}%")
    
    with col4:
        st.metric("📋 Invoices", f"{metrics['unique_invoices']:,}")
    
    with col5:
        retail_pct = (metrics['retail_items'] / metrics['total_items'] * 100) if metrics['total_items'] > 0 else 0
        st.metric("🛒 Retail %", f"{retail_pct:.1f}%")
    
    with col6:
        st.metric("🔄 Recurring %", f"{metrics['recurring_pct']:.1f}%")


def create_branch_comparison(df: pd.DataFrame) -> go.Figure:
    """Create branch comparison chart."""
    branch_data = df.groupby('branch').agg({
        'payments': 'sum',
        'is_retail': 'sum',
        'is_insurance': 'sum',
        INVOICE_COLUMNS['number']: 'nunique'
    }).reset_index()
    branch_data.columns = ['Branch', 'Total Payments', 'Retail Items', 'Insurance Items', 'Invoices']
    branch_data = branch_data.sort_values('Total Payments', ascending=True).tail(15)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=branch_data['Branch'],
        x=branch_data['Total Payments'],
        orientation='h',
        marker_color='#1E88E5',
        text=branch_data['Total Payments'].apply(lambda x: f'${x/1000:,.0f}K'),
        textposition='inside',
        name='Total Payments'
    ))
    
    fig.update_layout(
        title='Top 15 Branches by Payments',
        xaxis_title='Total Payments ($)',
        yaxis_title='Branch',
        height=500,
        template='plotly_white'
    )
    
    return fig


def create_retail_insurance_chart(df: pd.DataFrame) -> go.Figure:
    """Create retail vs insurance breakdown chart."""
    retail_payments = df.loc[df['is_retail'], 'payments'].sum()
    insurance_payments = df.loc[df['is_insurance'], 'payments'].sum()
    
    fig = go.Figure(data=[
        go.Pie(
            labels=['Retail (Patient)', 'Insurance'],
            values=[retail_payments, insurance_payments],
            hole=0.4,
            marker_colors=['#43A047', '#1565C0'],
            textinfo='percent+label',
            textposition='outside'
        )
    ])
    
    fig.update_layout(
        title='Revenue by Payor Type',
        height=400,
        template='plotly_white'
    )
    
    return fig


def create_billing_period_chart(df: pd.DataFrame) -> go.Figure:
    """Create billing period distribution chart."""
    # Create buckets
    df_copy = df.copy()
    df_copy['period_bucket'] = pd.cut(
        df_copy['billing_period'],
        bins=[0, 1, 3, 6, 12, 24, 36, 999],
        labels=['Period 1', '2-3', '4-6', '7-12', '13-24', '25-36', '37+']
    )
    
    bucket_data = df_copy.groupby('period_bucket', observed=True).agg({
        'payments': 'sum',
        INVOICE_COLUMNS['number']: 'count'
    }).reset_index()
    bucket_data.columns = ['Period', 'Payments', 'Items']
    
    fig = make_subplots(rows=1, cols=2, specs=[[{"type": "bar"}, {"type": "bar"}]],
                        subplot_titles=('Items by Billing Period', 'Payments by Billing Period'))
    
    fig.add_trace(
        go.Bar(x=bucket_data['Period'], y=bucket_data['Items'], 
               marker_color='#7B1FA2', name='Items'),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(x=bucket_data['Period'], y=bucket_data['Payments'],
               marker_color='#00897B', name='Payments',
               text=bucket_data['Payments'].apply(lambda x: f'${x/1000:,.0f}K'),
               textposition='outside'),
        row=1, col=2
    )
    
    fig.update_layout(
        title='Rental Billing Period Distribution',
        height=400,
        template='plotly_white',
        showlegend=False
    )
    
    return fig


def create_yearly_trend(df: pd.DataFrame) -> go.Figure:
    """Create yearly trend chart."""
    df_copy = df.copy()
    df_copy['year'] = pd.to_datetime(df_copy['invoice_date']).dt.year
    
    yearly = df_copy.groupby('year').agg({
        'payments': 'sum',
        'is_retail': 'sum',
        'is_insurance': 'sum',
        INVOICE_COLUMNS['number']: 'nunique'
    }).reset_index()
    yearly.columns = ['Year', 'Payments', 'Retail Items', 'Insurance Items', 'Invoices']
    yearly = yearly[(yearly['Year'] >= 2021) & (yearly['Year'] <= 2025)]
    yearly['Year'] = yearly['Year'].astype(str)
    
    fig = make_subplots(rows=1, cols=2, 
                        subplot_titles=('Total Payments by Year', 'Retail vs Insurance Items'))
    
    fig.add_trace(
        go.Bar(x=yearly['Year'], y=yearly['Payments'], marker_color='#1E88E5',
               text=yearly['Payments'].apply(lambda x: f'${x/1e6:.1f}M'),
               textposition='outside', name='Payments'),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(x=yearly['Year'], y=yearly['Retail Items'], marker_color='#43A047', name='Retail'),
        row=1, col=2
    )
    fig.add_trace(
        go.Bar(x=yearly['Year'], y=yearly['Insurance Items'], marker_color='#1565C0', name='Insurance'),
        row=1, col=2
    )
    
    fig.update_layout(
        title='Year-over-Year Analysis (FY2021 - FY2025)',
        height=400,
        template='plotly_white',
        barmode='group'
    )
    
    return fig


def create_collection_rate_by_branch(df: pd.DataFrame) -> go.Figure:
    """Create collection rate by branch chart."""
    branch_data = df.groupby('branch').agg({
        'payments': 'sum',
        'total_billed': 'sum'
    }).reset_index()
    
    branch_data['collection_rate'] = np.where(
        branch_data['total_billed'] > 0,
        (branch_data['payments'] / branch_data['total_billed'] * 100).round(1),
        100.0
    )
    branch_data = branch_data.sort_values('collection_rate', ascending=True).tail(15)
    
    colors = branch_data['collection_rate'].apply(
        lambda x: '#4CAF50' if x >= 95 else ('#FFC107' if x >= 90 else '#F44336')
    )
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=branch_data['branch'],
        x=branch_data['collection_rate'],
        orientation='h',
        marker_color=colors,
        text=branch_data['collection_rate'].apply(lambda x: f'{x:.1f}%'),
        textposition='outside'
    ))
    
    fig.add_vline(x=95, line_dash="dash", line_color="green", 
                  annotation_text="95% Target")
    
    fig.update_layout(
        title='Collection Rate by Branch',
        xaxis_title='Collection Rate (%)',
        xaxis_range=[0, 105],
        height=500,
        template='plotly_white'
    )
    
    return fig


def main():
    """Main dashboard function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', default='data/brightree/invoices',
                        help='Path to invoice CSV files')
    
    # Handle Streamlit's argument passing
    try:
        if '--' in sys.argv:
            args_start = sys.argv.index('--') + 1
            args = parser.parse_args(sys.argv[args_start:])
        else:
            args = parser.parse_args([])
    except SystemExit:
        args = argparse.Namespace(input='data/brightree/invoices')
    
    # Title
    st.title("📊 Invoice Dashboard")
    st.markdown("**5-Year Analysis (FY2021 - FY2025) | Ending Period: December 31, 2025**")
    
    # Sidebar filters
    st.sidebar.header("Filters")
    
    # Time period filter
    time_periods = ["5 Years", "FY 2025", "YTD", "QTD", "6 Months", "3 Months", "90 Days", "1 Month"]
    selected_period = st.sidebar.selectbox("Time Period", time_periods, index=0)
    
    # Load data
    with st.spinner("Loading invoice data..."):
        df = load_invoice_data(args.input)
    
    if df.empty:
        st.error("No data loaded. Check the input directory path.")
        return
    
    # Apply time filter
    filtered_df = get_time_filtered_data(df, selected_period)
    
    # Branch filter
    branches = sorted(filtered_df['branch'].unique())
    selected_branches = st.sidebar.multiselect("Branch", branches, default=branches)
    
    if selected_branches:
        filtered_df = filtered_df[filtered_df['branch'].isin(selected_branches)]
    
    # Payor type filter
    payor_filter = st.sidebar.radio("Payor Type", ["All", "Retail Only", "Insurance Only"])
    if payor_filter == "Retail Only":
        filtered_df = filtered_df[filtered_df['is_retail']]
    elif payor_filter == "Insurance Only":
        filtered_df = filtered_df[filtered_df['is_insurance']]
    
    # Calculate and display metrics
    metrics = calculate_metrics(filtered_df)
    display_metrics_panel(metrics, f"Key Metrics - {selected_period}")
    
    st.divider()
    
    # Main charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(create_branch_comparison(filtered_df), use_container_width=True)
    
    with col2:
        st.plotly_chart(create_retail_insurance_chart(filtered_df), use_container_width=True)
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.plotly_chart(create_billing_period_chart(filtered_df), use_container_width=True)
    
    with col4:
        st.plotly_chart(create_collection_rate_by_branch(filtered_df), use_container_width=True)
    
    # Yearly trend (full width)
    st.plotly_chart(create_yearly_trend(df), use_container_width=True)
    
    # Branch breakdown table
    st.subheader("📋 Branch Summary")
    
    branch_summary = filtered_df.groupby('branch').agg({
        'payments': 'sum',
        'balance': 'sum',
        'is_retail': 'sum',
        'is_insurance': 'sum',
        'is_recurring': 'sum',
        INVOICE_COLUMNS['number']: 'nunique',
        'billing_period': 'mean'
    }).reset_index()
    
    branch_summary.columns = ['Branch', 'Payments', 'Balance', 'Retail Items', 
                               'Insurance Items', 'Recurring Items', 'Invoices', 'Avg Period']
    branch_summary['Retail %'] = (branch_summary['Retail Items'] / 
                                   (branch_summary['Retail Items'] + branch_summary['Insurance Items']) * 100).round(1)
    branch_summary['Total Billed'] = branch_summary['Payments'] + branch_summary['Balance'].abs()
    branch_summary['Collection %'] = np.where(
        branch_summary['Total Billed'] > 0,
        (branch_summary['Payments'] / branch_summary['Total Billed'] * 100).round(1),
        100.0
    )
    
    branch_summary = branch_summary.sort_values('Payments', ascending=False)
    
    # Format for display
    display_df = branch_summary[['Branch', 'Invoices', 'Payments', 'Balance', 
                                  'Retail %', 'Collection %', 'Avg Period']].copy()
    display_df['Payments'] = display_df['Payments'].apply(lambda x: f"${x:,.0f}")
    display_df['Balance'] = display_df['Balance'].apply(lambda x: f"${x:,.0f}")
    display_df['Retail %'] = display_df['Retail %'].apply(lambda x: f"{x:.1f}%")
    display_df['Collection %'] = display_df['Collection %'].apply(lambda x: f"{x:.1f}%")
    display_df['Avg Period'] = display_df['Avg Period'].apply(lambda x: f"{x:.1f}")
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Data explorer
    with st.expander("🔍 Data Explorer"):
        st.markdown(f"**Total Records:** {len(filtered_df):,}")
        
        sample_cols = [
            INVOICE_COLUMNS['number'],
            INVOICE_COLUMNS['date_of_service'],
            'branch',
            INVOICE_COLUMNS['so_classification'],
            'payor_level_clean',
            INVOICE_COLUMNS['item_name'],
            'billing_period',
            'payments',
            'balance'
        ]
        available_cols = [c for c in sample_cols if c in filtered_df.columns]
        
        st.dataframe(filtered_df[available_cols].head(100), use_container_width=True)
        
        # Download button
        csv = filtered_df[available_cols].to_csv(index=False)
        st.download_button(
            label="📥 Download Filtered Data (CSV)",
            data=csv,
            file_name=f"invoice_data_{selected_period.replace(' ', '_').lower()}.csv",
            mime="text/csv"
        )


if __name__ == "__main__":
    main()
