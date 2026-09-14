import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# 1. Pagina instellingen (breedbeeld)
st.set_page_config(page_title="Crypto Revenue Dashboard", layout="wide")

# 2. Data ophalen en cachen (zodat de API niet overbelast raakt bij elke klik)
@st.cache_data(ttl=3600)
def load_data():
    url = "https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue"
    try:
        response = requests.get(url)
        data = response.json()
        protocols = data.get('protocols', [])
        
        cleaned_data = []
        for p in protocols:
            cleaned_data.append({
                'Protocol': p.get('name'),
                'Sub_Sector': p.get('category'),
                '24h_Revenue': p.get('total24h', 0) or 0,
                '7d_Revenue': p.get('total7d', 0) or 0,
                '30d_Revenue': p.get('total30d', 0) or 0
            })
            
        df = pd.DataFrame(cleaned_data)
        # Filter protocollen zonder inkomsten eruit
        df = df[df['24h_Revenue'] > 0]
        return df
    except Exception as e:
        st.error(f"Fout bij ophalen data: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("Geen data gevonden. Controleer je internetverbinding of de DeFiLlama API.")
    st.stop()

# 3. Dashboard Titel & Zijbalk
st.title("📊 Crypto Revenue & Fee Dashboard")
st.markdown("Analyseer de meest winstgevende sub-sectoren en protocollen.")

st.sidebar.header("Filters")
sectors = ["All"] + sorted(df['Sub_Sector'].unique().tolist())
selected_sector = st.sidebar.selectbox("Selecteer een Sub-Sector", sectors)

if selected_sector != "All":
    filtered_df = df[df['Sub_Sector'] == selected_sector]
else:
    filtered_df = df

# 4. Tabbladen structuur
tab1, tab2, tab3 = st.tabs(["Industry Overview", "Sector Deep Dive", "Top Protocols"])

with tab1:
    st.subheader("Crypto Industry Revenue (24u)")
    
    total_24h = df['24h_Revenue'].sum()
    total_7d = df['7d_Revenue'].sum()
    total_30d = df['30d_Revenue'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Totale 24u Inkomsten", f"${total_24h:,.0f}")
    col2.metric("Totale 7d Inkomsten", f"${total_7d:,.0f}")
    col3.metric("Totale 30d Inkomsten", f"${total_30d:,.0f}")
    
    st.markdown("### Top 15 Sub-Sectoren")
    sector_grouped = df.groupby('Sub_Sector')['24h_Revenue'].sum().reset_index()
    sector_grouped = sector_grouped.sort_values(by='24h_Revenue', ascending=False).head(15)
    
    fig_sector = px.bar(sector_grouped, x='Sub_Sector', y='24h_Revenue', 
                        labels={'24h_Revenue': '24u Inkomsten (USD)', 'Sub_Sector': 'Sector'})
    st.plotly_chart(fig_sector, use_container_width=True)

with tab2:
    st.subheader(f"Deep Dive: {selected_sector}")
    st.markdown("Sorteer op **24h_Revenue** of **7d_Revenue** om opkomende protocollen binnen deze sector te identificeren.")
    
    display_df = filtered_df.sort_values('24h_Revenue', ascending=False).reset_index(drop=True)
    
    # Prachtige opmaak voor de datatabel
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
    st.subheader("Top 20 Protocollen (Globale Ranking)")
    top_protocols = df.sort_values('24h_Revenue', ascending=False).head(20)
    
    fig_protocols = px.bar(top_protocols, x='Protocol', y='24h_Revenue', color='Sub_Sector',
                           labels={'24h_Revenue': '24u Inkomsten (USD)'})
    st.plotly_chart(fig_protocols, use_container_width=True)