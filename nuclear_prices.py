```python
import matplotlib.pyplot as plt

# Sample data: Average price of nuclear-generated electricity in Europe (in EUR/MWh)
years = [2018, 2019, 2020, 2021, 2022]
countries = ['France', 'Germany', 'Sweden', 'Poland', 'Netherlands', 
             'Belgium', 'Switzerland', 'Austria', 'Hungary', 'Italy']

# Prices for each country over the years
prices = {
    'France': [75.5, 76.2, 78.1, 79.4, 80.0],
    'Germany': [85.3, 86.7, 88.9, 90.1, 91.5],
    'Sweden': [95.6, 96.8, 98.1, 99.2, 100.5],
    'Poland': [65.4, 66.7, 68.3, 69.8, 71.0],
    'Netherlands': [80.9, 82.1, 83.6, 84.9, 86.2],
    'Belgium': [88.5, 89.7, 91.0, 92.3, 93.8],
    'Switzerland': [105.4, 106.7, 108.1, 109.6, 111.0],
    'Austria': [90.2, 91.5, 92.9, 94.3, 95.7],
    'Hungary': [60.8, 61.9, 63.4, 64.8, 66.1],
    'Italy': [85.0, 86.2, 87.6, 88.9, 90.2]
}

# Plotting
plt.figure(figsize=(12, 7))
for country in countries:
    plt.plot(years, prices[country], label=country)

# Adding title and labels
plt.title('Average Price of Nuclear-Generated Electricity in Europe (2018-2022)')
plt.xlabel('Year')
plt.ylabel('Price (EUR/MWh)')

# Adding legend
plt.legend(title='Country', bbox_to_anchor=(1.05, 1), loc='upper left')

# Show plot
plt.tight_layout()
plt.show()
```
This script creates a line graph showing the average price of nuclear-generated electricity in EUR/MWh for each country over five years (2018 to 2022). The data is plotted with different lines for each country and includes a legend, title, and axis labels.