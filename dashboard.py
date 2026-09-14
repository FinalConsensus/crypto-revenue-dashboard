import requests
import pandas as pd
from datetime import datetime

def fetch_defillama_revenue():
    print("Fetching data from DeFiLlama API...")
    
    # DeFiLlama endpoint for daily revenue
    url = "https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        protocols = data.get('protocols', [])
        
        if not protocols:
            print("No protocol data found.")
            return None
            
        # Extract relevant fields
        cleaned_data = []
        for p in protocols:
            cleaned_data.append({
                'Protocol': p.get('name'),
                'Sub_Sector': p.get('category'),
                'Daily_Revenue_USD': p.get('total24h', 0),
                '7d_Revenue_USD': p.get('total7d', 0),
                '30d_Revenue_USD': p.get('total30d', 0)
            })
            
        df = pd.DataFrame(cleaned_data)
        
        # Clean up missing or zero values
        df = df.fillna(0)
        df = df[df['Daily_Revenue_USD'] > 0] # Filter out inactive protocols
        
        # Sort by highest daily revenue
        df = df.sort_values(by='Daily_Revenue_USD', ascending=False).reset_index(drop=True)
        return df
        
    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
        return None

def main():
    df = fetch_defillama_revenue()
    
    if df is not None:
        # 1. Dashboard Overview: Total Crypto Industry Revenue
        total_daily = df['Daily_Revenue_USD'].sum()
        print(f"\n{'='*50}")
        print(f"TOTAL CRYPTO INDUSTRY DAILY REVENUE: ${total_daily:,.2f}")
        print(f"{'='*50}\n")
        
        # 2. Breakdown per Sub-Sector
        sector_breakdown = df.groupby('Sub_Sector')['Daily_Revenue_USD'].sum().reset_index()
        sector_breakdown = sector_breakdown.sort_values(by='Daily_Revenue_USD', ascending=False)
        
        print("--- REVENUE BY SUB-SECTOR ---")
        print(sector_breakdown.head(10).to_string(index=False, formatters={'Daily_Revenue_USD': '${:,.2f}'.format}))
        print("\n")
        
        # 3. Deep Dive: Top 10 Protocols overall
        print("--- TOP 10 PROTOCOLS BY DAILY REVENUE ---")
        top_10 = df[['Protocol', 'Sub_Sector', 'Daily_Revenue_USD']].head(10)
        print(top_10.to_string(index=False, formatters={'Daily_Revenue_USD': '${:,.2f}'.format}))
        print("\n")
        
        # Export to CSV for further Excel/Dashboard analysis
        date_str = datetime.today().strftime('%Y-%m-%d')
        df.to_csv(f'protocol_revenue_deepdive_{date_str}.csv', index=False)
        sector_breakdown.to_csv(f'sector_revenue_{date_str}.csv', index=False)
        print("Data exported successfully to CSV files.")

if __name__ == "__main__":
    main()