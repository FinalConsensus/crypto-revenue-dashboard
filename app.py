import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="Crypto Revenue Dashboard", layout="wide")

# 1. Password Protection Mechanism
def check_password():
    def password_entered():
        if st.session_state["password"] == "Admin123": 
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Please enter the password to access the dashboard", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Please enter the password to access the dashboard", type="password", on_change=password_entered, key="password")
        st.error("Incorrect password")
        return False
    return True

if not check_password():
    st.stop()

# 2. Data Fetching Functions
@st.cache_data(ttl=3600)
def load_overview_data():
    url = "https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        protocols = data.get('protocols', [])
        
        cleaned_data = []
        for p in protocols:
            cleaned_data.append({
                'Protocol': p.get('name'),
                'Slug': p.get('module'),
                'Sub_Sector': p.get('category'),
                '24h_Revenue': p.get('total24h', 0) or 0,
                '7d_Revenue': p.get('total7d', 0) or 0,
                '30d_Revenue': p.get('total30d', 0) or 0
            })
            
        df = pd.DataFrame(cleaned_data)
        df = df[df['24h_Revenue'] > 0] 
        
        # --- NEW: Bucket small sub-sectors into 'Others' ---
        sector_counts = df['Sub_Sector'].value_counts()
        small_sectors = sector_counts[sector_counts < 3].index
        df['Sub_Sector'] = df['Sub_Sector'].apply(lambda x: 'Others' if x in small_sectors else x)
        
        return df
    except Exception as e:
        st.error(f"Error fetching overview data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_historical_data(slug, metric="dailyRevenue"):
    # Metric parameter allows switching between Revenue and Fees
    url = f"https://api.llama.fi/summary/fees/{slug}?dataType={metric}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        chart_data = data.get('totalDataChart', [])
        
        if not chart_data:
            return pd.DataFrame()
            
        df = pd.DataFrame(chart_data, columns=['Timestamp', 'Value'])
        df['Date'] = pd.to_datetime(df['Timestamp'], unit='s')
        return df
    except Exception:
        return pd.DataFrame()

df = load_overview_data()

if df.empty:
    st.warning("No data found. Check your internet connection or the DeFiLlama API.")
    st.stop()

# 3. Dashboard Title & Sidebar
st.title("📊 Crypto Revenue & Fee Dashboard")
st.markdown("Analyze the most profitable sub-sectors and protocols across the crypto industry.")

st.sidebar.header("Filters & Navigation")
sectors = ["All"] + sorted(df['Sub_Sector'].unique().tolist())
selected_sector = st.sidebar.selectbox("Select a Sub-Sector", sectors)

if selected_sector != "All":
    filtered_df = df[df['Sub_Sector'] == selected_sector]
else:
    filtered_df = df

# 4. Tabs Structure
tab1, tab2, tab3, tab4 = st.tabs(["Industry Overview", "Sector Deep Dive", "Top Protocols", "Historical Trends"])

with tab1:
    st.subheader("Crypto Industry Revenue (24h)")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total 24h Revenue", f"${df['24h_Revenue'].sum():,.0f}")
    col2.metric("Total 7d Revenue", f"${df['7d_Revenue'].sum():,.0f}")
    col3.metric("Total 30d Revenue", f"${df['30d_Revenue'].sum():,.0f}")
    
    st.markdown("### Top Sub-Sectors")
    sector_grouped = df.groupby('Sub_Sector')['24h_Revenue'].sum().reset_index()
    sector_grouped = sector_grouped.sort_values(by='24h_Revenue', ascending=False)
    
    fig_sector = px.bar(sector_grouped, x='Sub_Sector', y='24h_Revenue', 
                        labels={'24h_Revenue': '24h Revenue (USD)', 'Sub_Sector': 'Sector'})
    fig_sector.update_layout(xaxis_title="", yaxis_title="Revenue (USD)")
    st.plotly_chart(fig_sector, use_container_width=True)

with tab2:
    st.subheader(f"Deep Dive: {selected_sector}")
    st.markdown("Sort by **24h_Revenue** or **7d_Revenue** to identify emerging protocols.")
    
    display_df = filtered_df.drop(columns=['Slug']).sort_values('24h_Revenue', ascending=False).reset_index(drop=True)
    
    st.dataframe(
        display_df.style.format({
            '24h_Revenue': '${:,.0f}',
            '7d_Revenue': '${:,.0f}',
            '30d_Revenue': '${:,.0f}'
        }),
        use_container_width=True,
        height=600
    )

with tab3:
    st.subheader("Top 20 Protocols (Global Ranking)")
    top_protocols = df.sort_values('24h_Revenue', ascending=False).head(20)
    
    fig_protocols = px.bar(top_protocols, x='Protocol', y='24h_Revenue', color='Sub_Sector',
                           labels={'24h_Revenue': '24h Revenue (USD)', 'Protocol': 'Protocol'})
    fig_protocols.update_layout(xaxis_title="", yaxis_title="Revenue (USD)")
    st.plotly_chart(fig_protocols, use_container_width=True)

with tab4:
    st.subheader("Protocol Historical Data (Aggregation Mode)")
    
    # Toggle between Fees and Revenue
    metric_choice = st.radio("Select Metric to Display (Crucial if Revenue is missing):", ["Revenue", "Fees"], horizontal=True)
    api_metric = "dailyRevenue" if metric_choice == "Revenue" else "dailyFees"
    
    protocol_list = sorted(filtered_df['Protocol'].tolist())
    
    # Multi-select allows aggregating multiple protocols (e.g. Pump.fun + PumpSwap)
    selected_protocols = st.multiselect(
        "Select Protocol(s) to view or aggregate", 
        options=protocol_list,
        default=[protocol_list[0]] if protocol_list else []
    )
    
    if selected_protocols:
        days = st.radio("Select Timeframe", [30, 90, 180, 365], index=1, horizontal=True, format_func=lambda x: f"Last {x} Days")
        
        combined_hist_df = pd.DataFrame()
        
        # Fetch data for each selected protocol and combine
        for prot in selected_protocols:
            slug = filtered_df[filtered_df['Protocol'] == prot]['Slug'].iloc[0]
            with st.spinner(f"Fetching {metric_choice} data for {prot}..."):
                temp_df = load_historical_data(slug, api_metric)
                if not temp_df.empty:
                    temp_df['Protocol'] = prot
                    combined_hist_df = pd.concat([combined_hist_df, temp_df])
        
        if not combined_hist_df.empty:
            cutoff_date = pd.to_datetime("today") - pd.Timedelta(days=days)
            filtered_hist = combined_hist_df[combined_hist_df['Date'] >= cutoff_date]
            
            # Aggregate values by Date
            agg_df = filtered_hist.groupby('Date')['Value'].sum().reset_index()
            
            project_name = " + ".join(selected_protocols)
            fig_trend = px.line(agg_df, x='Date', y='Value', 
                                title=f"{project_name} - Aggregated Daily {metric_choice}",
                                labels={'Value': f'Daily {metric_choice} (USD)', 'Date': 'Date'})
            fig_trend.update_layout(xaxis_title="", yaxis_title=f"{metric_choice} (USD)")
            
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info(f"No historical {metric_choice} data available for the selected protocol(s). Try switching the metric toggle.")

# 5. Footer / Attribution
st.markdown("---")
st.markdown("💡 *Data powered by [DeFiLlama](https://defillama.com/)*")