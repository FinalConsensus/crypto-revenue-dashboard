import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# 1. Page settings
st.set_page_config(page_title="Crypto Revenue Dashboard", layout="wide")

# 2. Password Protection Mechanism
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        # Je kunt hier je eigen wachtwoord instellen
        if st.session_state["password"] == "FC753": 
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Remove password from memory
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

# Stop the script if the password is wrong or not entered
if not check_password():
    st.stop()

# 3. Data Fetching Functions
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
                'Slug': p.get('module'), # The unique ID needed for historical data
                'Sub_Sector': p.get('category'),
                '24h_Revenue': p.get('total24h', 0) or 0,
                '7d_Revenue': p.get('total7d', 0) or 0,
                '30d_Revenue': p.get('total30d', 0) or 0
            })
            
        df = pd.DataFrame(cleaned_data)
        df = df[df['24h_Revenue'] > 0] # Filter out inactive protocols
        return df
    except Exception as e:
        st.error(f"Error fetching overview data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_historical_data(slug):
    url = f"https://api.llama.fi/summary/fees/{slug}?dataType=dailyRevenue"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        chart_data = data.get('totalDataChart', [])
        
        if not chart_data:
            return pd.DataFrame()
            
        # Chart data comes as a list of [timestamp, value]
        df = pd.DataFrame(chart_data, columns=['Timestamp', 'Revenue'])
        df['Date'] = pd.to_datetime(df['Timestamp'], unit='s')
        return df
    except Exception as e:
        return pd.DataFrame()

# Load the main dataset
df = load_overview_data()

if df.empty:
    st.warning("No data found. Check your internet connection or the DeFiLlama API.")
    st.stop()

# 4. Dashboard Title & Sidebar
st.title("📊 Crypto Revenue & Fee Dashboard")
st.markdown("Analyze the most profitable sub-sectors and protocols across the crypto industry.")

st.sidebar.header("Filters & Navigation")
sectors = ["All"] + sorted(df['Sub_Sector'].unique().tolist())
selected_sector = st.sidebar.selectbox("Select a Sub-Sector", sectors)

if selected_sector != "All":
    filtered_df = df[df['Sub_Sector'] == selected_sector]
else:
    filtered_df = df

# 5. Tabs Structure
tab1, tab2, tab3, tab4 = st.tabs(["Industry Overview", "Sector Deep Dive", "Top Protocols", "Historical Trends"])

with tab1:
    st.subheader("Crypto Industry Revenue (24h)")
    
    total_24h = df['24h_Revenue'].sum()
    total_7d = df['7d_Revenue'].sum()
    total_30d = df['30d_Revenue'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total 24h Revenue", f"${total_24h:,.0f}")
    col2.metric("Total 7d Revenue", f"${total_7d:,.0f}")
    col3.metric("Total 30d Revenue", f"${total_30d:,.0f}")
    
    st.markdown("### Top 15 Sub-Sectors")
    sector_grouped = df.groupby('Sub_Sector')['24h_Revenue'].sum().reset_index()
    sector_grouped = sector_grouped.sort_values(by='24h_Revenue', ascending=False).head(15)
    
    fig_sector = px.bar(sector_grouped, x='Sub_Sector', y='24h_Revenue', 
                        labels={'24h_Revenue': '24h Revenue (USD)', 'Sub_Sector': 'Sector'})
    fig_sector.update_layout(xaxis_title="", yaxis_title="Revenue (USD)")
    st.plotly_chart(fig_sector, use_container_width=True)

with tab2:
    st.subheader(f"Deep Dive: {selected_sector}")
    st.markdown("Sort by **24h_Revenue** or **7d_Revenue** to identify emerging protocols within this sector.")
    
    # Hide the technical 'Slug' column from the user interface
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
    st.subheader("Protocol Historical Revenue")
    st.markdown("Select a protocol to view its historical daily revenue trend.")
    
    # Create an alphabetical list of protocols for the dropdown
    protocol_list = sorted(filtered_df['Protocol'].tolist())
    selected_protocol = st.selectbox("Select Protocol", protocol_list)
    
    if selected_protocol:
        # Find the unique identifier (slug) for the selected protocol
        slug = filtered_df[filtered_df['Protocol'] == selected_protocol]['Slug'].iloc[0]
        
        with st.spinner(f"Fetching historical data for {selected_protocol}..."):
            hist_df = load_historical_data(slug)
            
        if not hist_df.empty:
            # Let user select timeframe
            days = st.radio("Select Timeframe", [30, 90, 180, 365], index=1, horizontal=True, format_func=lambda x: f"Last {x} Days")
            
            # Filter data based on selected timeframe
            cutoff_date = pd.to_datetime("today") - pd.Timedelta(days=days)
            hist_df = hist_df[hist_df['Date'] >= cutoff_date]
            
            # Draw the line chart
            fig_trend = px.line(hist_df, x='Date', y='Revenue', 
                                title=f"{selected_protocol} - Daily Revenue Trend",
                                labels={'Revenue': 'Daily Revenue (USD)', 'Date': 'Date'})
            fig_trend.update_layout(xaxis_title="", yaxis_title="Revenue (USD)")
            
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info(f"No historical data available for {selected_protocol}.")

# 6. Footer / Attribution
st.markdown("---")
st.markdown("💡 *Data powered by [DeFiLlama](https://defillama.com/)*")