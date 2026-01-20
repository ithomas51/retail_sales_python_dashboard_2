"""
Invoice Analytics Dashboard - Enterprise Streamlit Application
Provides comprehensive analytics for invoice data with Retail vs Insurance classification,
billing period analysis, collection metrics, and peer group benchmarking.

Usage:
    streamlit run invoice_dashboard.py -- -i data/brightree/invoices

Features:
- 5-Year dashboard (FY2021 - FY2025)
- Rolling periods: 1mo, 3mo, 6mo, 90d
- Metrics grouped by Branch, then Time Period
- Collection rate visualization with percentile benchmarking
- Rental billing period analysis
- Procedure code analysis by branch
- Sales order search functionality
- Peer group performance percentiles
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
from scipy import stats

# Page configuration
st.set_page_config(
    page_title="Invoice Analytics Dashboard",
    page_icon=None,
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
    
    # Calculate both gross and net billed amounts
    # Gross: includes absolute value of all balances (conservative estimate)
    # Net: only includes positive balances (accounts for credits/overpayments)
    combined['total_billed'] = combined['payments'] + combined['balance'].abs()
    combined['net_billed'] = combined['payments'] + combined['balance'].clip(lower=0)
    
    # Prepare procedure code display column with explicit "Unspecified" category
    proc_col = INVOICE_COLUMNS['proc_code']
    if proc_col in combined.columns:
        combined['proc_code_display'] = combined[proc_col].fillna('[Unspecified]')
        combined.loc[combined['proc_code_display'].str.strip() == '', 'proc_code_display'] = '[Unspecified]'
    
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
    """
    Calculate key metrics from dataframe.
    
    Collection Rate Calculation:
    - Gross Rate: payments / (payments + abs(balance)) - conservative estimate
    - Net Rate: payments / (payments + max(balance, 0)) - accounts for credits
    - Returns None when total_billed = 0 to display as N/A
    """
    if len(df) == 0:
        return {
            'total_items': 0,
            'total_payments': 0,
            'total_balance': 0,
            'collection_rate': None,  # N/A for no data
            'net_collection_rate': None,
            'unique_invoices': 0,
            'retail_items': 0,
            'insurance_items': 0,
            'retail_payments': 0,
            'insurance_payments': 0,
            'recurring_pct': 0,
            'avg_billing_period': 0,
            'has_credits': False
        }
    
    total_payments = df['payments'].sum()
    total_balance = df['balance'].sum()
    total_billed = df['total_billed'].sum()
    net_billed = df['net_billed'].sum() if 'net_billed' in df.columns else total_billed
    
    # Check for credits (negative balances)
    has_credits = (df['balance'] < 0).any()
    
    # Calculate collection rates - return None for N/A when no billing
    gross_collection_rate = (total_payments / total_billed * 100) if total_billed > 0 else None
    net_collection_rate = (total_payments / net_billed * 100) if net_billed > 0 else None
    
    return {
        'total_items': len(df),
        'total_payments': total_payments,
        'total_balance': total_balance,
        'collection_rate': gross_collection_rate,
        'net_collection_rate': net_collection_rate,
        'unique_invoices': df[INVOICE_COLUMNS['number']].nunique(),
        'retail_items': df['is_retail'].sum(),
        'insurance_items': df['is_insurance'].sum(),
        'retail_payments': df.loc[df['is_retail'], 'payments'].sum(),
        'insurance_payments': df.loc[df['is_insurance'], 'payments'].sum(),
        'recurring_pct': (df['is_recurring'].sum() / len(df) * 100) if len(df) > 0 else 0,
        'avg_billing_period': df['billing_period'].mean(),
        'has_credits': has_credits
    }


def display_metrics_panel(metrics: dict, title: str = "Key Metrics"):
    """Display metrics in a styled panel with N/A handling for edge cases."""
    st.subheader(title)
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("Total Collected", f"${metrics['total_payments']:,.0f}")
    
    with col2:
        balance_display = f"${metrics['total_balance']:,.0f}"
        if metrics.get('has_credits', False):
            balance_display += " *"
        st.metric("Outstanding Balance", balance_display)
    
    with col3:
        # Handle N/A for collection rate when no billing exists
        if metrics['collection_rate'] is None:
            rate_display = "N/A"
        else:
            rate_display = f"{metrics['collection_rate']:.1f}%"
        st.metric("Collection Rate", rate_display)
    
    with col4:
        st.metric("Invoice Count", f"{metrics['unique_invoices']:,}")
    
    with col5:
        retail_pct = (metrics['retail_items'] / metrics['total_items'] * 100) if metrics['total_items'] > 0 else 0
        st.metric("Retail Mix", f"{retail_pct:.1f}%")
    
    with col6:
        st.metric("Recurring Items", f"{metrics['recurring_pct']:.1f}%")
    
    # Show footnotes if applicable
    if metrics.get('has_credits', False):
        st.caption("* Balance includes credits/overpayments (negative balances)")
    if metrics['collection_rate'] is None:
        st.caption("N/A indicates no billable activity in the selected period")


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


def calculate_percentile_rank(value: float, data_series: pd.Series, 
                              secondary_value: float = None, 
                              secondary_series: pd.Series = None) -> float:
    """
    Calculate the percentile rank of a value within a distribution.
    Uses the linear interpolation method (NumPy/Excel PERCENTILE.INC equivalent).
    
    Formula: percentile_rank = (count of values < x) / (n - 1) * 100
    Where n is the total number of observations.
    
    Tiebreaker: When secondary values provided, uses them to differentiate
    tied primary values (adds tiny fraction based on secondary rank).
    
    Reference: Wikipedia - Percentile, Linear Interpolation Method (C=1)
    """
    if len(data_series) == 0:
        return 50.0
    sorted_data = np.sort(data_series.dropna().values)
    n = len(sorted_data)
    if n == 0:
        return 50.0
    if n == 1:
        return 50.0
    
    # Count values strictly less than the given value
    count_less = np.sum(sorted_data < value)
    
    # Apply secondary tiebreaker if provided and there are ties
    count_equal = np.sum(sorted_data == value)
    tiebreaker_adjustment = 0.0
    
    if count_equal > 1 and secondary_value is not None and secondary_series is not None:
        # Normalize secondary value to [0, 1] range
        sec_min = secondary_series.min()
        sec_max = secondary_series.max()
        sec_range = sec_max - sec_min
        if sec_range > 0:
            sec_normalized = (secondary_value - sec_min) / sec_range
            # Add small adjustment (max 0.5 percentile point) to break ties
            tiebreaker_adjustment = sec_normalized * 0.5 / n
    
    # Linear interpolation percentile rank with tiebreaker
    percentile = ((count_less / (n - 1)) * 100 + tiebreaker_adjustment) if n > 1 else 50.0
    return min(max(percentile, 0.0), 100.0)


def calculate_branch_percentiles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate peer group percentiles for each branch across key metrics.
    
    Metrics calculated:
    - Payments Percentile: Branch payments rank vs all branches (tiebreaker: volume)
    - Collection Rate Percentile: Branch collection rate rank (tiebreaker: payments)
    - Retail Mix Percentile: Branch retail percentage rank (tiebreaker: total items)
    - Volume Percentile: Branch invoice count rank (tiebreaker: payments)
    
    Percentile Interpretation:
    - 90th percentile = Top 10% performer
    - 75th percentile = Top 25% performer (Q3)
    - 50th percentile = Median performer (Q2)
    - 25th percentile = Bottom 25% performer (Q1)
    
    Edge Case Handling:
    - Zero-billed branches: Collection rate = None (excluded from percentile)
    """
    agg_dict = {
        'payments': 'sum',
        'total_billed': 'sum',
        'is_retail': 'sum',
        'is_insurance': 'sum',
        INVOICE_COLUMNS['number']: 'nunique'
    }
    
    # Add net_billed if available
    if 'net_billed' in df.columns:
        agg_dict['net_billed'] = 'sum'
    
    branch_metrics = df.groupby('branch').agg(agg_dict).reset_index()
    
    base_cols = ['Branch', 'Payments', 'Total_Billed', 'Retail_Items', 'Insurance_Items', 'Invoices']
    if 'net_billed' in df.columns:
        base_cols.insert(3, 'Net_Billed')
    branch_metrics.columns = base_cols
    
    # Calculate derived metrics with N/A handling for zero-billed
    # Use None for zero-billed branches instead of 100%
    branch_metrics['Collection_Rate'] = branch_metrics.apply(
        lambda row: (row['Payments'] / row['Total_Billed'] * 100) 
                    if row['Total_Billed'] > 0 else None, axis=1
    )
    
    total_items = branch_metrics['Retail_Items'] + branch_metrics['Insurance_Items']
    branch_metrics['Retail_Mix'] = np.where(
        total_items > 0,
        (branch_metrics['Retail_Items'] / total_items * 100),
        0.0
    )
    branch_metrics['Total_Items'] = total_items
    
    # Calculate percentile ranks with secondary tiebreakers
    # Payments: tiebreaker = invoice volume
    branch_metrics['Payments_Pctl'] = branch_metrics.apply(
        lambda row: calculate_percentile_rank(
            row['Payments'], branch_metrics['Payments'],
            row['Invoices'], branch_metrics['Invoices']
        ), axis=1
    )
    
    # Collection Rate: tiebreaker = payment volume (exclude N/A from percentile calc)
    valid_collection = branch_metrics['Collection_Rate'].dropna()
    branch_metrics['Collection_Pctl'] = branch_metrics.apply(
        lambda row: calculate_percentile_rank(
            row['Collection_Rate'], valid_collection,
            row['Payments'], branch_metrics['Payments']
        ) if pd.notna(row['Collection_Rate']) else None, axis=1
    )
    
    # Retail Mix: tiebreaker = total items
    branch_metrics['Retail_Mix_Pctl'] = branch_metrics.apply(
        lambda row: calculate_percentile_rank(
            row['Retail_Mix'], branch_metrics['Retail_Mix'],
            row['Total_Items'], branch_metrics['Total_Items']
        ), axis=1
    )
    
    # Volume: tiebreaker = payments
    branch_metrics['Volume_Pctl'] = branch_metrics.apply(
        lambda row: calculate_percentile_rank(
            row['Invoices'], branch_metrics['Invoices'],
            row['Payments'], branch_metrics['Payments']
        ), axis=1
    )
    
    # Calculate composite performance score (weighted average of percentiles)
    # For branches with N/A collection, use median (50) as placeholder
    # Weights: Collection Rate 40%, Payments 30%, Volume 20%, Retail Mix 10%
    branch_metrics['Performance_Score'] = (
        branch_metrics['Collection_Pctl'].fillna(50.0) * 0.40 +
        branch_metrics['Payments_Pctl'] * 0.30 +
        branch_metrics['Volume_Pctl'] * 0.20 +
        branch_metrics['Retail_Mix_Pctl'] * 0.10
    )
    
    return branch_metrics


def create_branch_percentile_chart(df: pd.DataFrame) -> go.Figure:
    """Create branch performance percentile chart with peer group comparison."""
    branch_metrics = calculate_branch_percentiles(df)
    
    # Sort by performance score and get top 15
    branch_metrics = branch_metrics.sort_values('Performance_Score', ascending=True).tail(15)
    
    fig = go.Figure()
    
    # Add stacked bar for each percentile component
    fig.add_trace(go.Bar(
        y=branch_metrics['Branch'],
        x=branch_metrics['Collection_Pctl'] * 0.40,
        orientation='h',
        name='Collection Rate (40%)',
        marker_color='#1565C0',
        text=branch_metrics['Collection_Pctl'].apply(lambda x: f'{x:.0f}'),
        textposition='inside'
    ))
    
    fig.add_trace(go.Bar(
        y=branch_metrics['Branch'],
        x=branch_metrics['Payments_Pctl'] * 0.30,
        orientation='h',
        name='Payments (30%)',
        marker_color='#43A047',
        text=branch_metrics['Payments_Pctl'].apply(lambda x: f'{x:.0f}'),
        textposition='inside'
    ))
    
    fig.add_trace(go.Bar(
        y=branch_metrics['Branch'],
        x=branch_metrics['Volume_Pctl'] * 0.20,
        orientation='h',
        name='Volume (20%)',
        marker_color='#FB8C00',
        text=branch_metrics['Volume_Pctl'].apply(lambda x: f'{x:.0f}'),
        textposition='inside'
    ))
    
    fig.add_trace(go.Bar(
        y=branch_metrics['Branch'],
        x=branch_metrics['Retail_Mix_Pctl'] * 0.10,
        orientation='h',
        name='Retail Mix (10%)',
        marker_color='#8E24AA',
        text=branch_metrics['Retail_Mix_Pctl'].apply(lambda x: f'{x:.0f}'),
        textposition='inside'
    ))
    
    # Add reference lines for percentile thresholds
    fig.add_vline(x=75, line_dash="dash", line_color="gray", 
                  annotation_text="75th Pctl")
    fig.add_vline(x=50, line_dash="dot", line_color="gray",
                  annotation_text="Median")
    
    fig.update_layout(
        title='Branch Performance Score by Peer Group Percentile',
        xaxis_title='Weighted Performance Score',
        yaxis_title='Branch',
        barmode='stack',
        height=550,
        template='plotly_white',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig


def create_proc_code_by_branch_chart(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """Create procedure code analysis by branch heatmap."""
    # Determine proc code column to use
    proc_col = '_proc_code_clean' if '_proc_code_clean' in df.columns else INVOICE_COLUMNS['proc_code']
    
    if proc_col not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="Procedure code data not available", 
                          xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    # Get top procedure codes by payment volume
    top_procs = df.groupby(proc_col)['payments'].sum().nlargest(top_n).index.tolist()
    
    # Filter to top proc codes and pivot
    df_filtered = df[df[proc_col].isin(top_procs)]
    pivot_data = df_filtered.pivot_table(
        values='payments',
        index='branch',
        columns=proc_col,
        aggfunc='sum',
        fill_value=0
    )
    
    # Get top 15 branches by total payments
    branch_totals = pivot_data.sum(axis=1).nlargest(15)
    pivot_data = pivot_data.loc[branch_totals.index]
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot_data.values,
        x=pivot_data.columns,
        y=pivot_data.index,
        colorscale='Blues',
        text=np.vectorize(lambda x: f'${x/1000:,.0f}K' if x >= 1000 else f'${x:,.0f}')(pivot_data.values),
        texttemplate='%{text}',
        textfont={"size": 9},
        hovertemplate='Branch: %{y}<br>Proc Code: %{x}<br>Payments: $%{z:,.0f}<extra></extra>'
    ))
    
    fig.update_layout(
        title=f'Top {top_n} Procedure Codes by Branch (Payments)',
        xaxis_title='Procedure Code',
        yaxis_title='Branch',
        height=500,
        template='plotly_white'
    )
    
    return fig


def search_sales_orders(df: pd.DataFrame, search_term: str) -> pd.DataFrame:
    """Search for sales orders by number or partial match."""
    if not search_term or len(search_term) < 2:
        return pd.DataFrame()
    
    so_col = INVOICE_COLUMNS['so_number']
    inv_col = INVOICE_COLUMNS['number']
    
    # Search in both sales order and invoice number columns
    mask = pd.Series(False, index=df.index)
    
    if so_col in df.columns:
        mask |= df[so_col].astype(str).str.contains(search_term, case=False, na=False)
    
    if inv_col in df.columns:
        mask |= df[inv_col].astype(str).str.contains(search_term, case=False, na=False)
    
    results = df[mask].copy()
    
    # Select relevant columns for display
    display_cols = [
        inv_col, so_col, INVOICE_COLUMNS['date_of_service'], 'branch',
        INVOICE_COLUMNS['item_name'], 'payments', 'balance', 'payor_level_clean'
    ]
    available_cols = [c for c in display_cols if c in results.columns]
    
    return results[available_cols].drop_duplicates().head(100)


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
    st.title("Invoice Analytics Dashboard")
    st.markdown("**5-Year Analysis (FY2021 - FY2025) | Reporting Period: January 1, 2021 - December 31, 2025**")
    
    # Load data first
    with st.spinner("Loading invoice data..."):
        df = load_invoice_data(args.input)
    
    if df.empty:
        st.error("No data loaded. Check the input directory path.")
        return
    
    # Sidebar filters
    st.sidebar.header("Filters")
    
    # Time period filter
    time_periods = ["5 Years", "FY 2025", "YTD", "QTD", "6 Months", "3 Months", "90 Days", "1 Month"]
    selected_period = st.sidebar.selectbox("Time Period", time_periods, index=0)
    
    # Apply time filter first
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
    
    # Procedure Code filter
    st.sidebar.divider()
    st.sidebar.subheader("Procedure Code Filter")
    proc_col = '_proc_code_clean' if '_proc_code_clean' in filtered_df.columns else INVOICE_COLUMNS['proc_code']
    if proc_col in filtered_df.columns:
        # Get top proc codes for filter options, including Unspecified
        top_proc_codes = filtered_df.groupby(proc_col)['payments'].sum().nlargest(49).index.tolist()
        
        # Add Unspecified option if there are missing proc codes
        has_missing = filtered_df[proc_col].isna().any() or (filtered_df[proc_col].str.strip() == '').any()
        if has_missing:
            filter_options = ['[Unspecified]'] + top_proc_codes
        else:
            filter_options = top_proc_codes
        
        selected_proc_codes = st.sidebar.multiselect(
            "Procedure Codes (Top 50 by Volume)",
            options=filter_options,
            default=[]
        )
        if selected_proc_codes:
            if '[Unspecified]' in selected_proc_codes:
                # Include both null and empty string proc codes
                unspec_mask = filtered_df[proc_col].isna() | (filtered_df[proc_col].str.strip() == '')
                other_codes = [c for c in selected_proc_codes if c != '[Unspecified]']
                if other_codes:
                    filtered_df = filtered_df[unspec_mask | filtered_df[proc_col].isin(other_codes)]
                else:
                    filtered_df = filtered_df[unspec_mask]
            else:
                filtered_df = filtered_df[filtered_df[proc_col].isin(selected_proc_codes)]
    
    # Sales Order Search
    st.sidebar.divider()
    st.sidebar.subheader("Sales Order Search")
    so_search = st.sidebar.text_input("Search Invoice/SO Number", placeholder="Enter number...")
    
    # Calculate and display metrics
    metrics = calculate_metrics(filtered_df)
    display_metrics_panel(metrics, f"Key Metrics - {selected_period}")
    
    st.divider()
    
    # Sales Order Search Results (if search is active)
    if so_search and len(so_search) >= 2:
        st.subheader("Sales Order Search Results")
        search_results = search_sales_orders(df, so_search)
        if len(search_results) > 0:
            st.markdown(f"**Found {len(search_results)} matching records**")
            st.dataframe(search_results, use_container_width=True, hide_index=True)
        else:
            st.info("No matching records found. Try a different search term.")
        st.divider()
    
    # Main charts - Row 1
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(create_branch_comparison(filtered_df), use_container_width=True)
    
    with col2:
        st.plotly_chart(create_retail_insurance_chart(filtered_df), use_container_width=True)
    
    # Main charts - Row 2
    col3, col4 = st.columns(2)
    
    with col3:
        st.plotly_chart(create_billing_period_chart(filtered_df), use_container_width=True)
    
    with col4:
        st.plotly_chart(create_collection_rate_by_branch(filtered_df), use_container_width=True)
    
    # Peer Group Percentile Analysis (full width)
    st.divider()
    st.subheader("Branch Performance Benchmarking")
    
    # Small sample size warning for percentile analysis
    branch_count = filtered_df['branch'].nunique()
    if branch_count < 5:
        st.warning(
            f"Insufficient data for percentile analysis. "
            f"Only {branch_count} branches in selection. Minimum 5 required for meaningful comparison."
        )
    elif branch_count < 10:
        st.info(
            f"Note: Percentiles based on {branch_count} branches. "
            f"Statistical significance increases with larger samples (10+ recommended)."
        )
    
    if branch_count >= 5:
        st.plotly_chart(create_branch_percentile_chart(filtered_df), use_container_width=True)
    else:
        st.caption("Percentile chart hidden due to insufficient branch count. Select more branches to enable.")
    
    # Procedure Code Analysis by Branch
    st.divider()
    st.subheader("Procedure Code Analysis by Branch")
    
    # Show missing proc code statistics
    proc_col = '_proc_code_clean' if '_proc_code_clean' in filtered_df.columns else INVOICE_COLUMNS['proc_code']
    if proc_col in filtered_df.columns:
        missing_count = filtered_df[proc_col].isna().sum() + (filtered_df[proc_col].str.strip() == '').sum()
        missing_pct = (missing_count / len(filtered_df)) * 100 if len(filtered_df) > 0 else 0
        if missing_pct > 0:
            st.caption(f"Note: {missing_pct:.1f}% of items have unspecified procedure codes")
    
    proc_top_n = st.slider("Number of top procedure codes to display", min_value=5, max_value=20, value=10)
    st.plotly_chart(create_proc_code_by_branch_chart(filtered_df, top_n=proc_top_n), use_container_width=True)
    
    # Yearly trend (full width)
    st.plotly_chart(create_yearly_trend(df), use_container_width=True)
    
    # Branch Performance Summary with Percentiles
    st.subheader("Branch Performance Summary with Peer Percentiles")
    
    branch_perf = calculate_branch_percentiles(filtered_df)
    branch_perf = branch_perf.sort_values('Performance_Score', ascending=False)
    
    # Format for display with N/A handling
    display_perf = branch_perf[[
        'Branch', 'Payments', 'Collection_Rate', 'Retail_Mix', 'Invoices',
        'Payments_Pctl', 'Collection_Pctl', 'Retail_Mix_Pctl', 'Volume_Pctl', 'Performance_Score'
    ]].copy()
    
    display_perf['Payments'] = display_perf['Payments'].apply(lambda x: f"${x:,.0f}")
    display_perf['Collection_Rate'] = display_perf['Collection_Rate'].apply(
        lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A"
    )
    display_perf['Retail_Mix'] = display_perf['Retail_Mix'].apply(lambda x: f"{x:.1f}%")
    display_perf['Payments_Pctl'] = display_perf['Payments_Pctl'].apply(lambda x: f"{x:.0f}")
    display_perf['Collection_Pctl'] = display_perf['Collection_Pctl'].apply(
        lambda x: f"{x:.0f}" if pd.notna(x) else "N/A"
    )
    display_perf['Retail_Mix_Pctl'] = display_perf['Retail_Mix_Pctl'].apply(lambda x: f"{x:.0f}")
    display_perf['Volume_Pctl'] = display_perf['Volume_Pctl'].apply(lambda x: f"{x:.0f}")
    display_perf['Performance_Score'] = display_perf['Performance_Score'].apply(lambda x: f"{x:.1f}")
    
    display_perf.columns = [
        'Branch', 'Payments', 'Collection %', 'Retail Mix %', 'Invoices',
        'Pay Pctl', 'Coll Pctl', 'Retail Pctl', 'Vol Pctl', 'Perf Score'
    ]
    
    st.dataframe(display_perf, use_container_width=True, hide_index=True)
    
    # Data explorer
    with st.expander("Data Explorer"):
        st.markdown(f"**Total Records:** {len(filtered_df):,}")
        
        sample_cols = [
            INVOICE_COLUMNS['number'],
            INVOICE_COLUMNS['so_number'],
            INVOICE_COLUMNS['date_of_service'],
            'branch',
            INVOICE_COLUMNS['so_classification'],
            'payor_level_clean',
            INVOICE_COLUMNS['item_name'],
            INVOICE_COLUMNS['proc_code'],
            '_proc_code_clean',
            'billing_period',
            'payments',
            'balance'
        ]
        available_cols = [c for c in sample_cols if c in filtered_df.columns]
        
        st.dataframe(filtered_df[available_cols].head(100), use_container_width=True)
        
        # Download button
        csv = filtered_df[available_cols].to_csv(index=False)
        st.download_button(
            label="Export to CSV",
            data=csv,
            file_name=f"invoice_data_{selected_period.replace(' ', '_').lower()}.csv",
            mime="text/csv"
        )


if __name__ == "__main__":
    main()
