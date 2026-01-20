"""
Retail Orders Dashboard
Interactive dashboard for analyzing retail sales orders with filtering,
drill-down capabilities, and time-based charts.

Usage:
    streamlit run retail_dashboard.py -- -i data/output
    streamlit run retail_dashboard.py -- --input ./yearly_data
"""
import argparse
import logging
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from glob import glob
from pathlib import Path
import os

# Setup logging
logger = logging.getLogger(__name__)


def get_sales_dir():
    """Get sales directory from command line args or default"""
    # Parse args after -- for streamlit
    parser = argparse.ArgumentParser(description='Retail Orders Dashboard')
    parser.add_argument(
        '-i', '--input',
        default=None,
        help='Path to directory containing *_SalesOrders.csv files'
    )
    
    # Streamlit passes args after '--'
    if '--' in sys.argv:
        args_idx = sys.argv.index('--') + 1
        args = parser.parse_args(sys.argv[args_idx:])
    else:
        args = parser.parse_args([])
    
    if args.input:
        return args.input
    
    # Default path relative to script location
    script_dir = Path(__file__).parent.parent
    return str(script_dir / "data" / "output")

# Set Plotly default template for white backgrounds
import plotly.io as pio
pio.templates.default = "plotly_white"

st.set_page_config(
    page_title="Retail Orders Dashboard",
    page_icon="chart_with_upwards_trend",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enterprise Light Theme - Minimal CSS (colors handled by .streamlit/config.toml)
st.markdown("""
<style>
    /* Hide default branding only - keep sidebar toggle visible */
    #MainMenu, footer {visibility: hidden;}
    
    /* Main container spacing */
    .main .block-container {
        padding: 1.5rem 2rem;
        max-width: 1400px;
    }
    
    /* Metric cards - layout only, no colors */
    [data-testid="stMetric"] {
        border: 1px solid #e1e4e8;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    
    /* Headers - border accent only */
    h1 {
        border-bottom: 2px solid #0366d6;
        padding-bottom: 0.5rem;
        margin-bottom: 0.5rem;
    }
    
    /* DataFrames */
    .stDataFrame {
        border: 1px solid #e1e4e8;
        border-radius: 6px;
    }
    
    /* Dividers */
    hr {
        border-color: #e1e4e8;
        margin: 1.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_all_data(sales_dir: str):
    """Load and process all sales order data"""
    all_data = []
    files = sorted(glob(os.path.join(sales_dir, "*_SalesOrders.csv")))
    
    for file_path in files:
        year = int(os.path.basename(file_path).split('_')[0])
        df = pd.read_csv(file_path, low_memory=False)
        df['year'] = year
        all_data.append(df)
    
    df = pd.concat(all_data, ignore_index=True)
    
    # Process data
    df = process_data(df)
    
    return df


def clean_currency(value):
    """Convert currency string to float"""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).replace('$', '').replace(',', '').strip()
    if not s:
        return 0.0
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    return float(s)


def process_data(df):
    """Process and clean the data"""
    # Parse dates
    df['order_date'] = pd.to_datetime(df['Sales Order Date Created (YYYY-MM-DD)'], errors='coerce')
    
    # Clean currency
    df['charge'] = df['Sales Order Detail Charge'].apply(clean_currency)
    df['allow'] = df['Sales Order Detail Allow'].apply(clean_currency)
    
    # Apply discount
    df['discount_pct'] = pd.to_numeric(df['Sales Order Discount Pct'], errors='coerce').fillna(0)
    df['discount_decimal'] = df['discount_pct'] / 100.0
    df['net_allow'] = df['allow'] * (1 - df['discount_decimal'])
    
    # Insurance classification
    for col in ['Insurance Flags Primary', 'Insurance Flags Secondary', 'Insurance Flags Tertiary']:
        df[col] = df[col].fillna(False)
        df[col] = df[col].astype(str).str.lower().isin(['true', '1', 'yes'])
    
    df['is_retail'] = (
        (~df['Insurance Flags Primary']) & 
        (~df['Insurance Flags Secondary']) & 
        (~df['Insurance Flags Tertiary'])
    )
    
    # Clean proc code
    df['proc_code'] = df['Sales Order Detail Proc Code'].fillna('UNKNOWN').str.strip()
    
    # Clean branch
    df['branch'] = df['Sales Order Branch Office'].fillna('Unknown')
    
    # Quantity
    df['qty'] = pd.to_numeric(df['Sales Order Detail Qty'], errors='coerce').fillna(0)
    
    # Sale Type (Purchase, Rental, etc.)
    df['sale_type'] = df['Sales Order Detail Sale Type'].fillna('Unknown').str.strip()
    
    return df


def get_time_filtered_data(df, period):
    """Filter data by time period - uses fiscal year end 2025 as baseline"""
    today = datetime.now()  # Dynamic current date
    year_end_2025 = datetime(2025, 12, 31)  # Fiscal year end 2025
    year_start_2026 = datetime(2026, 1, 1)  # Start of 2026 for YTD
    
    # Q1 2026 starts Jan 1
    q1_start = datetime(2026, 1, 1)
    
    if period == "90 Days":
        start_date = today - timedelta(days=90)
    elif period == "1 Year":
        # Full year 2025
        start_date = datetime(2025, 1, 1)
        return df[(df['order_date'] >= start_date) & (df['order_date'] <= year_end_2025)]
    elif period == "3 Years":
        # 2023, 2024, 2025 (full years)
        start_date = datetime(2023, 1, 1)
        return df[(df['order_date'] >= start_date) & (df['order_date'] <= year_end_2025)]
    elif period == "5 Years":
        # 2021-2025 (full years from year end 2025)
        start_date = datetime(2021, 1, 1)
        return df[(df['order_date'] >= start_date) & (df['order_date'] <= year_end_2025)]
    elif period == "YTD":
        # Year to date 2026
        return df[df['order_date'] >= year_start_2026]
    elif period == "QTD":
        # Quarter to date (Q1 2026)
        return df[df['order_date'] >= q1_start]
    else:  # All Time
        return df
    
    return df[df['order_date'] >= start_date]


def main():
    st.title("Retail Orders Dashboard")
    st.caption("Retail Sales Orders")
    st.markdown("---")
    
    # Get sales directory from args
    sales_dir = get_sales_dir()
    
    # Load data
    with st.spinner("Loading data..."):
        df = load_all_data(sales_dir)
    
    # Filter to retail only
    retail_df = df[df['is_retail']].copy()
    
    # Sidebar filters
    st.sidebar.header("Filters")
    
    # Time period selector
    time_period = st.sidebar.selectbox(
        "Time Period",
        ["All Time", "YTD", "QTD", "90 Days", "1 Year", "3 Years", "5 Years"],
        index=0
    )
    
    # Apply time filter
    filtered_df = get_time_filtered_data(retail_df, time_period)
    
    # Year filter
    available_years = sorted(filtered_df['year'].unique())
    selected_years = st.sidebar.multiselect(
        "Select Years",
        options=available_years,
        default=available_years
    )
    
    if selected_years:
        filtered_df = filtered_df[filtered_df['year'].isin(selected_years)]
    
    # Branch filter
    available_branches = sorted(filtered_df['branch'].unique())
    selected_branches = st.sidebar.multiselect(
        "Select Branches",
        options=available_branches,
        default=[]
    )
    
    if selected_branches:
        filtered_df = filtered_df[filtered_df['branch'].isin(selected_branches)]
    
    # Proc code filter - all proc codes sorted by revenue
    all_proc_codes = filtered_df.groupby('proc_code')['net_allow'].sum().sort_values(ascending=False).index.tolist()
    selected_proc_codes = st.sidebar.multiselect(
        "Select Proc Codes",
        options=all_proc_codes,
        default=[]
    )
    
    if selected_proc_codes:
        filtered_df = filtered_df[filtered_df['proc_code'].isin(selected_proc_codes)]
    
    # Order number search
    order_search = st.sidebar.text_input("Search Order Number", "")
    if order_search:
        filtered_df = filtered_df[filtered_df['Sales Order Number'].astype(str).str.contains(order_search)]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Showing:** {len(filtered_df):,} items")
    st.sidebar.markdown(f"**From:** {filtered_df['Sales Order Number'].nunique():,} orders")
    
    # Key Metrics Row
    st.subheader("Key Metrics")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Revenue", f"${filtered_df['net_allow'].sum():,.2f}")
    with col2:
        st.metric("Total Orders", f"{filtered_df['Sales Order Number'].nunique():,}")
    with col3:
        st.metric("Total Items", f"{len(filtered_df):,}")
    with col4:
        st.metric("Avg Order Value", f"${filtered_df.groupby('Sales Order Number')['net_allow'].sum().mean():,.2f}")
    with col5:
        st.metric("Total Qty", f"{filtered_df['qty'].sum():,.0f}")
    
    st.markdown("---")
    
    # Time Period Charts
    st.subheader("Time Period Analysis")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["2026 YTD", "Q1 2026 QTD", "90 Days", "FY 2025", "3 Year (2023-2025)", "5 Year (2021-2025)"])
    
    with tab1:
        # YTD 2026
        period_df = get_time_filtered_data(retail_df, "YTD")
        if len(period_df) > 0:
            daily = period_df.groupby(period_df['order_date'].dt.date)['net_allow'].sum().reset_index()
            daily.columns = ['Date', 'Revenue']
            fig = px.area(daily, x='Date', y='Revenue', title="Daily Revenue - 2026 Year to Date")
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("YTD Revenue", f"${period_df['net_allow'].sum():,.2f}")
            with col2:
                st.metric("YTD Orders", f"{period_df['Sales Order Number'].nunique():,}")
            with col3:
                days_elapsed = (datetime(2026, 1, 20) - datetime(2026, 1, 1)).days
                daily_avg = period_df['net_allow'].sum() / max(days_elapsed, 1)
                st.metric("Daily Avg", f"${daily_avg:,.2f}")
        else:
            st.info("No data for 2026 YTD")
    
    with tab2:
        # QTD Q1 2026
        period_df = get_time_filtered_data(retail_df, "QTD")
        if len(period_df) > 0:
            daily = period_df.groupby(period_df['order_date'].dt.date)['net_allow'].sum().reset_index()
            daily.columns = ['Date', 'Revenue']
            fig = px.area(daily, x='Date', y='Revenue', title="Daily Revenue - Q1 2026 Quarter to Date")
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("QTD Revenue", f"${period_df['net_allow'].sum():,.2f}")
            with col2:
                st.metric("QTD Orders", f"{period_df['Sales Order Number'].nunique():,}")
            with col3:
                days_elapsed = (datetime(2026, 1, 20) - datetime(2026, 1, 1)).days
                projected_q1 = (period_df['net_allow'].sum() / max(days_elapsed, 1)) * 90
                st.metric("Q1 Projected", f"${projected_q1:,.2f}")
        else:
            st.info("No data for Q1 2026 QTD")
    
    with tab3:
        period_df = get_time_filtered_data(retail_df, "90 Days")
        if len(period_df) > 0:
            daily = period_df.groupby(period_df['order_date'].dt.date)['net_allow'].sum().reset_index()
            daily.columns = ['Date', 'Revenue']
            fig = px.area(daily, x='Date', y='Revenue', title="Daily Revenue - Last 90 Days")
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("90-Day Revenue", f"${period_df['net_allow'].sum():,.2f}")
            with col2:
                st.metric("90-Day Orders", f"{period_df['Sales Order Number'].nunique():,}")
        else:
            st.info("No data in the last 90 days")
    
    with tab4:
        # FY 2025 (Full Year)
        period_df = get_time_filtered_data(retail_df, "1 Year")
        if len(period_df) > 0:
            monthly = period_df.groupby(period_df['order_date'].dt.to_period('M'))['net_allow'].sum().reset_index()
            monthly['order_date'] = monthly['order_date'].astype(str)
            monthly.columns = ['Month', 'Revenue']
            fig = px.bar(monthly, x='Month', y='Revenue', title="Monthly Revenue - FY 2025 (Jan-Dec)")
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("FY 2025 Revenue", f"${period_df['net_allow'].sum():,.2f}")
            with col2:
                st.metric("FY 2025 Orders", f"{period_df['Sales Order Number'].nunique():,}")
        else:
            st.info("No data for FY 2025")
    
    with tab5:
        # 3 Years (2023-2025)
        period_df = get_time_filtered_data(retail_df, "3 Years")
        if len(period_df) > 0:
            quarterly = period_df.groupby(period_df['order_date'].dt.to_period('Q'))['net_allow'].sum().reset_index()
            quarterly['order_date'] = quarterly['order_date'].astype(str)
            quarterly.columns = ['Quarter', 'Revenue']
            fig = px.bar(quarterly, x='Quarter', y='Revenue', title="Quarterly Revenue - 2023-2025")
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("3-Year Revenue", f"${period_df['net_allow'].sum():,.2f}")
            with col2:
                st.metric("3-Year Orders", f"{period_df['Sales Order Number'].nunique():,}")
        else:
            st.info("No data for 2023-2025")
    
    with tab6:
        # 5 Years (2021-2025)
        period_df = get_time_filtered_data(retail_df, "5 Years")
        if len(period_df) > 0:
            yearly = period_df.groupby(period_df['order_date'].dt.year)['net_allow'].sum().reset_index()
            yearly.columns = ['Year', 'Revenue']
            fig = px.bar(yearly, x='Year', y='Revenue', title="Annual Revenue - 2021-2025")
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("5-Year Revenue", f"${period_df['net_allow'].sum():,.2f}")
            with col2:
                st.metric("5-Year Orders", f"{period_df['Sales Order Number'].nunique():,}")
            with col3:
                avg_annual = period_df['net_allow'].sum() / 5
                st.metric("Avg Annual", f"${avg_annual:,.2f}")
        else:
            st.info("No data for 2021-2025")
    
    st.markdown("---")
    
    # Branch Analysis Section
    st.subheader("Branch Contribution Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Branch Revenue Breakdown
        branch_revenue = filtered_df.groupby('branch').agg({
            'net_allow': 'sum',
            'Sales Order Number': 'nunique',
            'qty': 'sum'
        }).reset_index()
        branch_revenue.columns = ['Branch', 'Revenue', 'Orders', 'Quantity']
        branch_revenue['Revenue %'] = (branch_revenue['Revenue'] / branch_revenue['Revenue'].sum() * 100).round(2)
        branch_revenue = branch_revenue.sort_values('Revenue', ascending=False)
        
        fig = px.pie(
            branch_revenue.head(10), 
            values='Revenue', 
            names='Branch',
            title="Top 10 Branches by Revenue Share",
            hole=0.4
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Branch Performance Table
        st.markdown("**Branch Performance Summary**")
        display_df = branch_revenue.head(15).copy()
        display_df['Revenue'] = display_df['Revenue'].apply(lambda x: f"${x:,.2f}")
        display_df['Revenue %'] = display_df['Revenue %'].apply(lambda x: f"{x:.1f}%")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Branch Trend Over Time
    st.markdown("**Branch Revenue Trend**")
    top_branches = branch_revenue.head(5)['Branch'].tolist()
    branch_trend = filtered_df[filtered_df['branch'].isin(top_branches)].groupby(
        ['year', 'branch']
    )['net_allow'].sum().reset_index()
    
    fig = px.line(
        branch_trend, 
        x='year', 
        y='net_allow', 
        color='branch',
        title="Top 5 Branches - Revenue by Year",
        markers=True
    )
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Sale Type Analysis (Purchase vs Rental)
    st.subheader("Sale Type Analysis")
    
    # Aggregate by sale type
    sale_type_data = filtered_df.groupby('sale_type').agg({
        'net_allow': 'sum',
        'Sales Order Number': 'nunique',
        'qty': 'sum'
    }).reset_index()
    sale_type_data.columns = ['Sale Type', 'Revenue', 'Orders', 'Quantity']
    sale_type_data['Revenue %'] = (sale_type_data['Revenue'] / sale_type_data['Revenue'].sum() * 100).round(2)
    sale_type_data = sale_type_data.sort_values('Revenue', ascending=False)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Pie chart
        fig = px.pie(
            sale_type_data,
            values='Revenue',
            names='Sale Type',
            title="Revenue by Sale Type",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Summary table
        st.markdown("**Sale Type Summary**")
        display_sale_type = sale_type_data.copy()
        display_sale_type['Revenue'] = display_sale_type['Revenue'].apply(lambda x: f"${x:,.2f}")
        display_sale_type['Revenue %'] = display_sale_type['Revenue %'].apply(lambda x: f"{x:.1f}%")
        st.dataframe(display_sale_type, use_container_width=True, hide_index=True)
    
    # Sale Type by Year trend
    sale_type_by_year = filtered_df.groupby(['year', 'sale_type'])['net_allow'].sum().reset_index()
    sale_type_by_year.columns = ['Year', 'Sale Type', 'Revenue']
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.bar(
            sale_type_by_year,
            x='Year',
            y='Revenue',
            color='Sale Type',
            title="Sale Type Revenue by Year",
            barmode='stack',
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.line(
            sale_type_by_year,
            x='Year',
            y='Revenue',
            color='Sale Type',
            title="Sale Type Revenue Trends",
            markers=True,
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Proc Code Analysis
    st.subheader("Procedure Code Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Top Proc Codes
        proc_revenue = filtered_df.groupby('proc_code').agg({
            'net_allow': 'sum',
            'Sales Order Number': 'nunique',
            'qty': 'sum'
        }).reset_index()
        proc_revenue.columns = ['Proc Code', 'Revenue', 'Orders', 'Quantity']
        proc_revenue = proc_revenue.sort_values('Revenue', ascending=False)
        
        fig = px.bar(
            proc_revenue.head(15),
            x='Proc Code',
            y='Revenue',
            title="Top 15 Proc Codes by Revenue",
            color='Revenue',
            color_continuous_scale='Blues'
        )
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Proc Code by Branch Heatmap
        top_procs = proc_revenue.head(10)['Proc Code'].tolist()
        top_branch_list = branch_revenue.head(8)['Branch'].tolist()
        
        heatmap_data = filtered_df[
            (filtered_df['proc_code'].isin(top_procs)) & 
            (filtered_df['branch'].isin(top_branch_list))
        ].groupby(['proc_code', 'branch'])['net_allow'].sum().unstack(fill_value=0)
        
        if len(heatmap_data) > 0:
            fig = px.imshow(
                heatmap_data,
                title="Proc Code Revenue by Branch (Heatmap)",
                labels=dict(x="Branch", y="Proc Code", color="Revenue"),
                color_continuous_scale='RdYlGn'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    # Proc Code Drill-Down
    st.markdown("**Proc Code Drill-Down**")
    
    selected_proc = st.selectbox(
        "Select a Proc Code to analyze",
        options=proc_revenue['Proc Code'].head(25).tolist()
    )
    
    if selected_proc:
        proc_detail = filtered_df[filtered_df['proc_code'] == selected_proc]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Revenue", f"${proc_detail['net_allow'].sum():,.2f}")
        with col2:
            st.metric("Total Orders", f"{proc_detail['Sales Order Number'].nunique():,}")
        with col3:
            st.metric("Avg Unit Price", f"${proc_detail['net_allow'].mean():,.2f}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # By Branch
            proc_by_branch = proc_detail.groupby('branch')['net_allow'].sum().reset_index()
            proc_by_branch.columns = ['Branch', 'Revenue']
            proc_by_branch = proc_by_branch.sort_values('Revenue', ascending=False)
            
            fig = px.bar(
                proc_by_branch.head(10),
                x='Branch',
                y='Revenue',
                title=f"{selected_proc} - Revenue by Branch"
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # By Year
            proc_by_year = proc_detail.groupby('year')['net_allow'].sum().reset_index()
            proc_by_year.columns = ['Year', 'Revenue']
            
            fig = px.line(
                proc_by_year,
                x='Year',
                y='Revenue',
                title=f"{selected_proc} - Revenue by Year",
                markers=True
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Year-over-Year Comparison
    st.subheader("Year-over-Year Comparison")
    
    yoy_data = filtered_df.groupby('year').agg({
        'net_allow': 'sum',
        'Sales Order Number': 'nunique',
        'qty': 'sum'
    }).reset_index()
    yoy_data.columns = ['Year', 'Revenue', 'Orders', 'Quantity']
    yoy_data['YoY Revenue Growth'] = yoy_data['Revenue'].pct_change() * 100
    yoy_data['Avg Order Value'] = yoy_data['Revenue'] / yoy_data['Orders']
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(x=yoy_data['Year'], y=yoy_data['Revenue'], name="Revenue"),
            secondary_y=False
        )
        fig.add_trace(
            go.Scatter(x=yoy_data['Year'], y=yoy_data['Orders'], name="Orders", mode='lines+markers'),
            secondary_y=True
        )
        fig.update_layout(title="Revenue & Orders by Year", height=350)
        fig.update_yaxes(title_text="Revenue ($)", secondary_y=False)
        fig.update_yaxes(title_text="Orders", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.bar(
            yoy_data[yoy_data['YoY Revenue Growth'].notna()],
            x='Year',
            y='YoY Revenue Growth',
            title="Year-over-Year Revenue Growth (%)",
            color='YoY Revenue Growth',
            color_continuous_scale=['red', 'yellow', 'green']
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Data Explorer
    st.subheader("Data Explorer")
    
    with st.expander("View Raw Data"):
        display_columns = [
            'Sales Order Number', 'order_date', 'branch', 'proc_code',
            'Sales Order Detail Item Name', 'qty', 'net_allow', 'year'
        ]
        st.dataframe(
            filtered_df[display_columns].head(500),
            use_container_width=True,
            hide_index=True
        )
        
        # Download button
        csv = filtered_df[display_columns].to_csv(index=False)
        st.download_button(
            label="Download Filtered Data (CSV)",
            data=csv,
            file_name="retail_orders_filtered.csv",
            mime="text/csv"
        )
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"*Dashboard generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Data: {len(df):,} total items, {len(retail_df):,} retail items*"
    )


if __name__ == "__main__":
    main()
