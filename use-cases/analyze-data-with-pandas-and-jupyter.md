---
title: Analyze Data with Pandas and Jupyter
slug: analyze-data-with-pandas-and-jupyter
description: >-
  Use Pandas in Jupyter notebooks for data analysis — clean messy datasets,
  explore patterns, create visualizations, generate reports, and export
  results for business stakeholders.
skills:
  - pandas
  - docker-compose
category: data
tags:
  - pandas
  - data-analysis
  - jupyter
  - python
  - visualization
---

# Analyze Data with Pandas and Jupyter

Kaori's marketing team sends her CSV exports from 5 different tools asking "what happened last quarter?" She spends hours in Excel trying to merge, clean, and pivot data. Pandas automates the tedious parts: read any format, clean messy data, merge multiple sources, compute metrics, and produce visualizations — all in a reproducible Jupyter notebook she can re-run when next quarter's data arrives.

## Step 1: Set Up Jupyter Environment

```bash
pip install jupyter pandas matplotlib seaborn plotly openpyxl
jupyter lab
```

## Step 2: Load and Clean Data

```python
# analysis.ipynb
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Read from multiple sources
users = pd.read_csv("exports/users.csv", parse_dates=["created_at", "last_active_at"])
events = pd.read_csv("exports/events.csv", parse_dates=["timestamp"])
revenue = pd.read_excel("exports/revenue.xlsx", sheet_name="Q4")

# Quick overview
print(f"Users: {len(users):,} rows, {users.columns.tolist()}")
print(f"Events: {len(events):,} rows")
print(f"Revenue: {len(revenue):,} rows")
users.info()
users.describe()

# Clean: handle missing values, normalize formats
users["email"] = users["email"].str.lower().str.strip()
users["plan"] = users["plan"].fillna("free").str.lower()
users["country"] = users["country"].fillna("Unknown")

# Remove duplicates
users = users.drop_duplicates(subset="email", keep="last")

# Parse dates that came in mixed formats
users["signup_date"] = pd.to_datetime(users["created_at"]).dt.date

print(f"After cleaning: {len(users):,} users")
```

## Step 3: Exploratory Analysis

```python
# User growth over time
daily_signups = users.groupby("signup_date").size().reset_index(name="signups")
daily_signups["cumulative"] = daily_signups["signups"].cumsum()

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

ax1.plot(daily_signups["signup_date"], daily_signups["signups"])
ax1.set_title("Daily Signups")
ax1.set_xlabel("Date")

ax2.plot(daily_signups["signup_date"], daily_signups["cumulative"])
ax2.set_title("Cumulative Users")
ax2.set_xlabel("Date")

plt.tight_layout()
plt.show()

# Plan distribution
plan_counts = users["plan"].value_counts()
print("\nPlan Distribution:")
print(plan_counts)
print(f"\nPaid conversion rate: {(plan_counts.drop('free', errors='ignore').sum() / len(users) * 100):.1f}%")

# Users by country (top 10)
top_countries = users["country"].value_counts().head(10)
top_countries.plot(kind="barh", figsize=(10, 5), title="Users by Country (Top 10)")
plt.xlabel("Number of Users")
plt.tight_layout()
plt.show()
```

## Step 4: Cohort Analysis

```python
# Monthly retention cohorts
users["cohort_month"] = pd.to_datetime(users["created_at"]).dt.to_period("M")
events["event_month"] = pd.to_datetime(events["timestamp"]).dt.to_period("M")

# Merge to get cohort for each event
event_cohorts = events.merge(
    users[["user_id", "cohort_month"]], on="user_id", how="left"
)

# Build cohort table
cohort_data = event_cohorts.groupby(["cohort_month", "event_month"])["user_id"].nunique().reset_index()
cohort_data.columns = ["cohort", "month", "active_users"]

# Pivot to retention matrix
cohort_sizes = users.groupby("cohort_month")["user_id"].nunique()
retention = cohort_data.pivot(index="cohort", columns="month", values="active_users")

# Calculate retention percentages
for col in retention.columns:
    retention[col] = retention[col] / cohort_sizes * 100

# Heatmap
plt.figure(figsize=(12, 8))
sns.heatmap(retention.iloc[-6:, :6], annot=True, fmt=".0f", cmap="YlOrRd_r",
            vmin=0, vmax=100, cbar_kws={"label": "Retention %"})
plt.title("Monthly Retention by Cohort")
plt.xlabel("Month")
plt.ylabel("Signup Cohort")
plt.tight_layout()
plt.show()
```

## Step 5: Revenue Analysis

```python
# Monthly revenue by plan
monthly_revenue = revenue.groupby([
    pd.to_datetime(revenue["date"]).dt.to_period("M"),
    revenue["plan"]
])["amount"].sum().unstack(fill_value=0)

monthly_revenue.plot(kind="bar", stacked=True, figsize=(12, 6),
                     color=["#60a5fa", "#818cf8", "#a78bfa"])
plt.title("Monthly Revenue by Plan")
plt.ylabel("Revenue ($)")
plt.xlabel("Month")
plt.legend(title="Plan")
plt.tight_layout()
plt.show()

# Key metrics
total_revenue = revenue["amount"].sum()
mrr = revenue[revenue["type"] == "subscription"].groupby(
    pd.to_datetime(revenue["date"]).dt.to_period("M")
)["amount"].sum().iloc[-1]

arpu = total_revenue / users[users["plan"] != "free"].nunique()

print(f"\n📊 Q4 Summary:")
print(f"  Total Revenue: ${total_revenue:,.2f}")
print(f"  Current MRR: ${mrr:,.2f}")
print(f"  ARPU (paid): ${arpu:,.2f}")
print(f"  Total Users: {len(users):,}")
print(f"  Paid Users: {len(users[users['plan'] != 'free']):,}")
print(f"  Conversion Rate: {len(users[users['plan'] != 'free']) / len(users) * 100:.1f}%")
```

## Step 6: Export Results

```python
# Export to Excel with multiple sheets
with pd.ExcelWriter("output/q4_report.xlsx", engine="openpyxl") as writer:
    daily_signups.to_excel(writer, sheet_name="Daily Signups", index=False)
    plan_counts.to_frame("count").to_excel(writer, sheet_name="Plan Distribution")
    monthly_revenue.to_excel(writer, sheet_name="Revenue by Plan")
    retention.to_excel(writer, sheet_name="Retention Cohorts")

# Save figures
fig.savefig("output/user_growth.png", dpi=150, bbox_inches="tight")

print("✅ Report exported to output/q4_report.xlsx")
```

## Summary

Kaori runs the notebook every quarter: drop in new CSV exports, hit "Run All," and the entire analysis refreshes — daily signups, plan distribution, cohort retention heatmap, revenue by plan, and key metrics. What took her 4 hours in Excel takes 30 seconds in Pandas. The notebook is version-controlled so she can see how metrics changed quarter over quarter. The cohort retention analysis showed that users who didn't complete onboarding in the first week had 80% churn — leading to a product fix that improved retention by 15%.
