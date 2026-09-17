import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
import pytz

st.set_page_config(page_title="Crypto Alpha Screener", layout="wide")

# 1. Password Protection
def check_password():
    def password_entered():
        if st.session_state["password"] == "Alpha2026": 
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter password", type="password", on_change=password_entered, key="password")
        st.error("Incorrect password")
        return False
    return True

if not check_password():
    st.stop()

# 2. Robust Data Fetching & Merging
@st.cache_data(ttl=3600)
def load_master_data():
    try:
        # A. Fetch Master Protocol List
        proto_res = requests.get("https://api.llama.fi/protocols").json()
        df_protocols = pd.DataFrame(proto_res)[['name', 'slug', 'category', 'mcap']]
        
        # B. Fetch Fees
        fees_res = requests.get("https://api.llama.fi/overview/fees?excludeTotalDataChart=true&dataType=dailyFees").json()
        df_fees = pd.DataFrame(fees_res['protocols'])[['name', 'total24h', 'total7d', 'total30d']]
        df_fees.rename(columns={'total24h': 'Fees_24h', 'total7d': 'Fees_7d', 'total30d': 'Fees_30d'}, inplace=True)
        
        # C. Fetch Revenue
        rev_res = requests.get("https://api.llama.fi/overview/fees?excludeTotalDataChart=true&dataType=dailyRevenue").json()
        df_rev = pd.DataFrame(rev_res['protocols'])[['name', 'total24h', 'total7d', 'total30d']]
        df_rev.rename(columns={'total24h': 'Rev_24h', 'total7d': 'Rev_7d', 'total30d': 'Rev_30d'}, inplace=True)
        
        # Merge datasets
        df = pd.merge(df_fees, df_rev, on='name', how='outer')
        df = pd.merge(df, df_protocols, on='name', how='left')
        
        # Clean & Format
        df.rename(columns={'name': 'Protocol', 'category': 'Sub_Sector'}, inplace=True)
        
        # FIX VOOR DE ERROR: Tekstkolommen expliciet als tekst (string) behandelen
        df['Protocol'] = df['Protocol'].fillna("Unknown").astype(str)
        df['slug'] = df['slug'].fillna("Unknown").astype(str)
        df['Sub_Sector'] = df['Sub_Sector'].fillna("Unknown").astype(str)
        
        # Resterende (numerieke) lege waarden vullen met 0
        df.fillna(0, inplace=True)
        
        # Bucket small sectors into 'Others'
        sector_counts = df['Sub_Sector'].value_counts()
        small_sectors = sector_counts[sector_counts < 3].index
        df['Sub_Sector'] = df['Sub_Sector'].apply(lambda x: 'Others' if x in small_sectors else x)
        
        # Calculate Alpha Metrics
        df['Ann_Fees'] = df['Fees_30d'] * (365/30)
        df['Ann_Rev'] = df['Rev_30d'] * (365/30)
        
        # Valuation Multiples
        df['Price_to_Fees'] = df.apply(lambda x: x['mcap'] / x['Ann_Fees'] if x['Ann_Fees'] > 0 and x['mcap'] > 0 else None, axis=1)
        df['Price_to_Rev'] = df.apply(lambda x: x['mcap'] / x['Ann_Rev'] if x['Ann_Rev'] > 0 and x['mcap'] > 0 else None, axis=1)
        
        # Momentum
        df['Fee_Momentum_%'] = df.apply(lambda x: ((x['Fees_7d']/7) / (x['Fees_30d']/30) - 1) * 100 if x['Fees_30d'] > 0 else 0, axis=1)
        
        # Timestamp with local Brussels timezone
        brussels_tz = pytz.timezone('Europe/Brussels')
        current_time = datetime.now(brussels_tz).strftime("%Y-%m-%d %H:%M:%S CEST")
        
        return df, current_time
    except Exception as e:
        st.error(f"Error compiling master dataset: {e}")
        return pd.DataFrame(), None

@st.cache_data(ttl=3600)
def load_historical_data(slug, metric="dailyFees"):
    url = f"https://api.llama.fi/summary/fees/{slug}?dataType={metric}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return pd.DataFrame()
        data = response.json()
        chart_data = data.get('totalDataChart', [])
        
        if not chart_data:
            return pd.DataFrame()
            
        df = pd.DataFrame(chart_data, columns=['Timestamp', 'Value'])
        df['Date'] = pd.to_datetime(df['Timestamp'], unit='s')
        return df
    except Exception:
        return pd.DataFrame()

# Load Data
df, last_updated = load_master_data()
if df.empty:
    st.stop()

# 3. Global Sidebar Filters
st.sidebar.title("Global Settings")
st.sidebar.markdown("Filters applied here affect all tabs.")

base_metric = st.sidebar.radio("Analyze Base Metric", ["Fees", "Revenue"])
prefix = "Fees" if base_metric == "Fees" else "Rev"

sectors = ["All"] + sorted([s for s in df['Sub_Sector'].unique() if s != 0 and isinstance(s, str)])
selected_sector = st.sidebar.selectbox("Filter by Sector", sectors)

min_mcap = st.sidebar.number_input("Minimum Market Cap ($)", value=0, step=1000000)
min_cashflow = st.sidebar.number_input(f"Minimum 30d {base_metric} ($)", value=10000, step=10000)

# Apply Global Filters
filtered_df = df.copy()
if selected_sector != "All":
    filtered_df = filtered_df[filtered_df['Sub_Sector'] == selected_sector]

filtered_df = filtered_df[filtered_df['mcap'] >= min_mcap]
filtered_df = filtered_df[filtered_df[f'{prefix}_30d'] >= min_cashflow]

# 4. Dashboard UI
st.title("🚀 Fundamental Alpha Screener")
st.markdown("Identify undervalued, high-cashflow protocols with accelerating momentum.")
if last_updated:
    st.caption(f"🔄 Data last updated: **{last_updated}**")

tab1, tab2, tab3, tab4 = st.tabs(["Valuation Matrix", "Momentum & Growth", "Sector Overview", "Historical Deep Dive"])

with tab1:
    st.subheader(f"Valuation Screener (Price-to-{base_metric})")
    st.markdown(f"Protocols with Tokens. **Lower multiple = cheaper valuation relative to generated {base_metric.lower()}.**")
    
    val_df = filtered_df.dropna(subset=[f'Price_to_{prefix[:3]}']).sort_values(f'Price_to_{prefix[:3]}')
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.dataframe(
            val_df[['Protocol', 'Sub_Sector', 'mcap', f'Ann_{prefix[:3]}', f'Price_to_{prefix[:3]}']].head(25).style.format({
                'mcap': '${:,.0f}',
                f'Ann_{prefix[:3]}': '${:,.0f}',
                f'Price_to_{prefix[:3]}': '{:.2f}x'
            }),
            use_container_width=True, height=500
        )
    with col2:
        fig_scatter = px.scatter(
            val_df, x=f'Ann_{prefix[:3]}', y='mcap', color='Sub_Sector', hover_name='Protocol',
            log_x=True, log_y=True, size_max=60,
            title=f"Valuation Scatter: Market Cap vs Annualized {base_metric} (Log Scale)",
            labels={f'Ann_{prefix[:3]}': f'Annualized {base_metric} ($)', 'mcap': 'Market Cap ($)'}
        )
        if not val_df.empty:
            fig_scatter.add_shape(type="line", line=dict(dash='dash', color="gray"), 
                                  x0=val_df[f'Ann_{prefix[:3]}'].min(), y0=val_df[f'Ann_{prefix[:3]}'].min(), 
                                  x1=val_df[f'Ann_{prefix[:3]}'].max(), y1=val_df[f'Ann_{prefix[:3]}'].max())
        st.plotly_chart(fig_scatter, use_container_width=True)

with tab2:
    st.subheader("Momentum Screener")
    st.markdown("Protocols where the 7-day daily average is outperforming the 30-day daily average.")
    
    mom_df = filtered_df.sort_values('Fee_Momentum_%', ascending=False)
    
    st.dataframe(
        mom_df[['Protocol', 'Sub_Sector', f'{prefix}_24h', f'{prefix}_7d', f'{prefix}_30d', 'Fee_Momentum_%']].style.format({
            f'{prefix}_24h': '${:,.0f}',
            f'{prefix}_7d': '${:,.0f}',
            f'{prefix}_30d': '${:,.0f}',
            'Fee_Momentum_%': '{:,.2f}%'
        }).background_gradient(subset=['Fee_Momentum_%'], cmap="RdYlGn", vmin=-50, vmax=50),
        use_container_width=True, height=600
    )

with tab3:
    st.subheader("Sector Dominance")
    sector_grouped = filtered_df.groupby('Sub_Sector').agg({
        f'{prefix}_24h': 'sum',
        f'{prefix}_30d': 'sum',
        'mcap': 'sum'
    }).reset_index().sort_values(f'{prefix}_30d', ascending=False)
    
    fig_sector = px.bar(sector_grouped, x='Sub_Sector', y=f'{prefix}_30d', 
                        title=f"Total 30-Day {base_metric} by Sector",
                        labels={f'{prefix}_30d': f'30d {base_metric} ($)', 'Sub_Sector': 'Sector'})
    st.plotly_chart(fig_sector, use_container_width=True)

with tab4:
    st.subheader("Historical Trajectory & Aggregation")
    
    protocol_list = sorted([p for p in filtered_df['Protocol'].tolist() if isinstance(p, str)])
    
    selected_protocols = st.multiselect(
        "Select Protocol(s) to view or aggregate (e.g., compare or combine multiple versions)", 
        options=protocol_list,
        default=[protocol_list[0]] if protocol_list else []
    )
    
    if selected_protocols:
        days = st.radio("Timeframe", [30, 90, 180, 365], index=1, horizontal=True, format_func=lambda x: f"{x} Days")
        api_metric = "dailyFees" if base_metric == "Fees" else "dailyRevenue"
        
        combined_hist_df = pd.DataFrame()
        
        for prot in selected_protocols:
            slug_match = df[df['Protocol'] == prot]['slug'].values
            if len(slug_match) > 0 and isinstance(slug_match[0], str):
                slug = slug_match[0]
                with st.spinner(f"Fetching {api_metric} for {prot}..."):
                    temp_df = load_historical_data(slug, api_metric)
                    if not temp_df.empty:
                        temp_df['Protocol'] = prot
                        combined_hist_df = pd.concat([combined_hist_df, temp_df])
        
        if not combined_hist_df.empty:
            cutoff_date = pd.to_datetime("today") - pd.Timedelta(days=days)
            filtered_hist = combined_hist_df[combined_hist_df['Date'] >= cutoff_date]
            
            agg_df = filtered_hist.groupby('Date')['Value'].sum().reset_index()
            
            fig_trend = px.line(agg_df, x='Date', y='Value', 
                                title=f"Aggregated Daily {base_metric} for: {', '.join(selected_protocols)}",
                                labels={'Value': f'Daily {base_metric} ($)', 'Date': 'Date'})
            
            agg_df['7D_MA'] = agg_df['Value'].rolling(window=7).mean()
            fig_trend.add_scatter(x=agg_df['Date'], y=agg_df['7D_MA'], mode='lines', name='7-Day Moving Avg', line=dict(dash='dot', color='orange'))
            
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.error(f"No historical {base_metric} data available. Try switching the global Base Metric in the sidebar.")

st.markdown("---")
st.markdown("💡 *Data provided by [DeFiLlama](https://defillama.com/)*")