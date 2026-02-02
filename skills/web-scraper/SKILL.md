---
name: web-scraper
description: >-
  Extract structured data from web pages reliably. Use when a user asks to
  scrape a website, extract data from a webpage, pull prices from a site,
  collect links, gather product listings, download page content, or parse
  HTML for specific information. Handles static HTML and JavaScript-rendered
  pages.
license: Apache-2.0
compatibility: "Requires Python 3.9+ with requests and beautifulsoup4 installed. For JS-rendered pages, requires playwright."
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: automation
  tags: ["scraping", "web", "html", "data-extraction", "beautifulsoup"]
---

# Web Scraper

## Overview

Extract structured data from web pages by parsing HTML, selecting elements with CSS selectors, and outputting clean data in JSON, CSV, or other formats. Handles both static HTML and JavaScript-rendered pages.

## Instructions

When a user asks you to scrape or extract data from a web page, follow these steps:

### Step 1: Assess the target

Determine:
- **URL**: What page to scrape
- **Data needed**: What specific elements to extract (prices, titles, links, tables)
- **Rendering**: Is the page static HTML or does it require JavaScript?
- **Scale**: Single page or multiple pages with pagination?

### Step 2: Fetch the page

**For static HTML:**

```python
import requests
from bs4 import BeautifulSoup

def fetch_page(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")
```

**For JavaScript-rendered pages:**

```python
from playwright.sync_api import sync_playwright

def fetch_js_page(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        content = page.content()
        browser.close()
    return BeautifulSoup(content, "html.parser")
```

### Step 3: Extract data with CSS selectors

Identify the right selectors by inspecting the page structure:

```python
def extract_items(soup, selectors):
    items = []
    containers = soup.select(selectors["container"])

    for container in containers:
        item = {}
        for field, selector in selectors["fields"].items():
            el = container.select_one(selector)
            if el:
                if el.name == "img":
                    item[field] = el.get("src", "")
                elif el.name == "a":
                    item[field] = {"text": el.get_text(strip=True), "href": el.get("href", "")}
                else:
                    item[field] = el.get_text(strip=True)
            else:
                item[field] = None
        items.append(item)

    return items
```

**Usage example:**

```python
selectors = {
    "container": "div.product-card",
    "fields": {
        "name": "h2.product-title",
        "price": "span.price",
        "rating": "span.rating-value",
        "link": "a.product-link",
    }
}
items = extract_items(soup, selectors)
```

### Step 4: Handle pagination

```python
def scrape_all_pages(base_url, selectors, max_pages=10):
    all_items = []
    for page_num in range(1, max_pages + 1):
        url = f"{base_url}?page={page_num}"
        soup = fetch_page(url)
        items = extract_items(soup, selectors)
        if not items:
            break
        all_items.extend(items)
        print(f"Page {page_num}: {len(items)} items (total: {len(all_items)})")
    return all_items
```

### Step 5: Output structured data

```python
import json
import csv

def save_json(data, filename):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

def save_csv(data, filename):
    if not data:
        return
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
```

## Examples

### Example 1: Extract product listings

**User request:** "Scrape all product names and prices from this catalog page"

**Script outline:**
```python
soup = fetch_page("https://example-store.com/catalog")

products = []
for card in soup.select("div.product-item"):
    name = card.select_one("h3.title")
    price = card.select_one("span.price")
    products.append({
        "name": name.get_text(strip=True) if name else "N/A",
        "price": price.get_text(strip=True) if price else "N/A",
    })

save_csv(products, "products.csv")
print(f"Extracted {len(products)} products")
```

**Output:**
```
Extracted 48 products
Saved to products.csv

Preview:
| name                  | price   |
|-----------------------|---------|
| Wireless Keyboard     | $49.99  |
| USB-C Hub 7-port      | $34.99  |
| Ergonomic Mouse       | $29.99  |
```

### Example 2: Extract a data table from a page

**User request:** "Pull the statistics table from this Wikipedia article"

**Script outline:**
```python
soup = fetch_page("https://en.wikipedia.org/wiki/Example_Article")

table = soup.select_one("table.wikitable")
headers = [th.get_text(strip=True) for th in table.select("tr:first-child th")]
rows = []
for tr in table.select("tr")[1:]:
    cells = [td.get_text(strip=True) for td in tr.select("td")]
    if len(cells) == len(headers):
        rows.append(dict(zip(headers, cells)))

save_json(rows, "table_data.json")
print(f"Extracted {len(rows)} rows with columns: {headers}")
```

**Output:**
```
Extracted 25 rows with columns: ['Year', 'Population', 'Growth Rate']
Saved to table_data.json
```

## Guidelines

- Always set a User-Agent header. Requests without one are often blocked.
- Add a timeout (30 seconds) to all HTTP requests to avoid hanging.
- Respect `robots.txt`. Check it before scraping and honor disallow rules.
- Add delays between requests when scraping multiple pages (`time.sleep(1)`). Do not hammer servers.
- Handle missing elements gracefully. Not every item will have every field. Use `None` for missing values.
- If a selector returns no results, the page structure may have changed. Report this to the user rather than returning empty data silently.
- For pages behind login walls, inform the user that authentication is required and ask for guidance.
- Prefer CSS selectors over XPath. They are more readable and sufficient for most cases.
- When scraping tables, always validate that row cell counts match header counts before zipping.
- Output data in the format the user needs. Default to JSON for structured data and CSV for tabular data.
