import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime

def fetch_and_plot_gold_btc():
    """
    Fetches 30-day historical data for Gold (XAUUSD) and Bitcoin (BTC-USD) 
    and plots them on a dual-axis graph with shared x-axis.
    
    Returns:
        bool: True if plot was generated successfully, False otherwise
    """
    # Print header
    print("\n" + "="*50 + "\nGold and BTC prices\n" + "="*50 + "\n")
    
    # Define ticker symbols
    gold_ticker = "XAUUSD=X"
    btc_ticker = "BTC-USD"
    
    # Fetch data for 30 days
    try:
        # Download data for 30 days
        gold_data = yf.download(gold_ticker, period="30d", interval="1d")
        btc_data = yf.download(btc_ticker, period="30d", interval="1d")
        
        # Check if data is available
        if gold_data.empty or btc_data.empty:
            print("Error: One or both datasets are empty.")
            return False
            
        # Validate that both datasets have identical dates
        if not (gold_data.index == btc_data.index).all():
            print("Error: Data timestamps do not align. Skipping plot.")
            return False
            
        # Ensure we have at least 10 data points for both
        if len(gold_data) < 10 or len(btc_data) < 10:
            print("Warning: Less than 10 data points available for at least one asset. Skipping plot.")
            return False
            
        # Create plot
        fig, ax1 = plt.subplots(figsize=(14, 7))
        
        # Plot Gold (left y-axis)
        color = 'tab:orange'
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Gold Price (USD)', color=color)
        ax1.plot(gold_data.index, gold_data['Close'], marker='o', linestyle='-', linewidth=2, color=color, label='Gold (XAUUSD)')
        ax1.tick_params(axis='y', labelcolor=color)
        
        # Create second y-axis for BTC
        ax2 = ax1.twinx()
        color = 'tab:blue'
        ax2.set_ylabel('BTC Price (USD)', color=color)
        ax2.plot(btc_data.index, btc_data['Close'], marker='s', linestyle='-', linewidth=2, color=color, label='BTC (BTC-USD)')
        ax2.tick_params(axis='y', labelcolor=color)
        
        # Format x-axis dates
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Set title
        plt.title('Gold and Bitcoin Prices Comparison (30-Day)', fontsize=16)
        
        # Add legend
        ax1.legend(loc='upper left')
        ax2.legend(loc='upper right')
        
        # Save the plot
        plt.savefig('gold_btc_graph.png', dpi=150, bbox_inches='tight')
        plt.show()
        
        print("✅ Plot saved as 'gold_btc_graph.png'")
        return True
        
    except Exception as e:
        print(f"❌ Error occurred: {str(e)}")
        print("Falling back to default message...")
        # Fallback: display message and return
        print("Data unavailable. Please check internet connection or try again later.")
        return False
    finally:
        # Ensure we handle any potential cleanup (though no explicit cleanup needed)
        pass


# Main execution
if __name__ == "__main__":
    # Run the function
    success = fetch_and_plot_gold_btc()
    if not success:
        print("⚠️  Plot generation failed. Check logs for details.")
