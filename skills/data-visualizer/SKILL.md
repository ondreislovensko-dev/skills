---
name: data-visualizer
description: >-
  Generate charts and data visualizations from datasets. Use when a user asks
  to create a chart, plot data, visualize trends, make a bar chart, line graph,
  scatter plot, histogram, heatmap, or any other data visualization. Produces
  publication-quality charts from CSV, JSON, Excel, or inline data.
license: Apache-2.0
compatibility: "Requires Python 3.9+ with matplotlib and pandas installed. Optional: seaborn, plotly."
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: data-ai
  tags: ["visualization", "charts", "matplotlib", "plotting", "data"]
---

# Data Visualizer

## Overview

Generate publication-quality charts and data visualizations from datasets using Python. Supports bar charts, line graphs, scatter plots, histograms, pie charts, heatmaps, and multi-panel layouts.

## Instructions

When a user asks you to visualize data or create a chart, follow these steps:

### Step 1: Load and inspect the data

```python
import pandas as pd

df = pd.read_csv("data.csv")  # or read_excel, read_json
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(df.describe())
```

Understand the data before choosing a chart type. Check data types, ranges, and cardinality of categorical columns.

### Step 2: Choose the right chart type

| Data relationship | Chart type | When to use |
|---|---|---|
| Categories vs values | Bar chart | Comparing discrete groups |
| Trend over time | Line chart | Time series with continuous x-axis |
| Two numeric variables | Scatter plot | Correlation or distribution |
| Distribution of one variable | Histogram | Frequency analysis |
| Parts of a whole | Pie/donut chart | Proportions (use only for < 7 categories) |
| Three variables | Bubble chart | Scatter with size encoding |
| Matrix of values | Heatmap | Correlation matrices, pivot tables |
| Multiple distributions | Box plot | Comparing distributions across groups |

### Step 3: Generate the chart

Use this base template:

```python
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

def setup_chart(title, xlabel, ylabel, figsize=(10, 6)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_title(title, fontsize=16, fontweight="bold", pad=15)
    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return fig, ax
```

**Bar chart:**
```python
fig, ax = setup_chart("Revenue by Region", "Region", "Revenue ($)")
bars = ax.bar(df["region"], df["revenue"], color="#2563eb")
ax.bar_label(bars, fmt="$%.0f", padding=3)
ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("${x:,.0f}"))
plt.tight_layout()
plt.savefig("revenue_by_region.png", dpi=150)
```

**Line chart:**
```python
fig, ax = setup_chart("Monthly Active Users", "Month", "Users")
ax.plot(df["month"], df["users"], marker="o", linewidth=2, color="#2563eb")
ax.fill_between(df["month"], df["users"], alpha=0.1, color="#2563eb")
ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("{x:,.0f}"))
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("monthly_users.png", dpi=150)
```

**Scatter plot:**
```python
fig, ax = setup_chart("Price vs Rating", "Price ($)", "Rating")
scatter = ax.scatter(df["price"], df["rating"], c=df["sales"],
                     cmap="viridis", alpha=0.7, s=50)
plt.colorbar(scatter, label="Sales Volume")
plt.tight_layout()
plt.savefig("price_vs_rating.png", dpi=150)
```

### Step 4: Apply styling best practices

```python
# Clean, professional style
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
})
```

Rules for clear charts:
- Remove top and right spines
- Add data labels to bar charts
- Use color meaningfully, not decoratively
- Format axis numbers (commas, currency, percentages)
- Rotate x-axis labels if they overlap
- Add a legend only when there are multiple series
- Use `tight_layout()` to prevent label clipping

### Step 5: Save and report

```python
plt.savefig("chart.png", dpi=150, bbox_inches="tight")
print(f"Chart saved to chart.png")
```

Always save at 150 DPI minimum. Use `bbox_inches="tight"` to avoid clipped labels.

## Examples

### Example 1: Sales dashboard with multiple charts

**User request:** "Create a dashboard showing sales by region, monthly trend, and top products"

**Output:** A 3-panel figure saved as `sales_dashboard.png`:

```python
fig, axes = plt.subplots(1, 3, figsize=(18, 6))

# Panel 1: Bar chart of sales by region
axes[0].bar(regions, sales, color=["#2563eb", "#16a34a", "#dc2626", "#f59e0b"])
axes[0].set_title("Sales by Region")

# Panel 2: Line chart of monthly trend
axes[1].plot(months, monthly_sales, marker="o", color="#2563eb")
axes[1].set_title("Monthly Sales Trend")

# Panel 3: Horizontal bar of top 10 products
axes[2].barh(products[:10], product_sales[:10], color="#2563eb")
axes[2].set_title("Top 10 Products")

plt.suptitle("Q4 2024 Sales Dashboard", fontsize=18, fontweight="bold")
plt.tight_layout()
plt.savefig("sales_dashboard.png", dpi=150)
```

### Example 2: Correlation heatmap

**User request:** "Show me which variables are correlated in this dataset"

**Output:**

```python
import seaborn as sns

corr = df.select_dtypes(include="number").corr()
fig, ax = plt.subplots(figsize=(10, 8))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0,
            square=True, linewidths=0.5, ax=ax)
ax.set_title("Feature Correlation Matrix", fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig("correlation_heatmap.png", dpi=150)
```

## Guidelines

- Always inspect the data first. Do not blindly plot columns that may contain nulls or wrong data types.
- Choose chart types based on the data relationship, not user preference alone. If someone asks for a pie chart with 20 categories, suggest a bar chart instead and explain why.
- Use consistent colors within a project. Define a palette at the top of the script.
- Format numbers on axes: use commas for thousands, currency symbols for money, percent signs for ratios.
- For time series, ensure the x-axis is sorted chronologically.
- When plotting multiple series, use distinct colors and a legend. Avoid more than 6-7 series on one chart.
- Default to PNG at 150 DPI. Use SVG if the user needs vector output.
- If the dataset has more than 10,000 points, consider aggregation or sampling before plotting.
- Label everything: title, axis labels, units. A chart without labels is useless.
