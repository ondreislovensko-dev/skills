---
title: "Automate PDF Invoice Processing"
slug: automate-pdf-invoice-processing
description: "Build an automated pipeline that extracts data from PDF invoices, validates and normalizes the information, exports to spreadsheets, and feeds into a billing system."
skills: [pdf-analyzer, data-extractor, excel-processor, billing-automation]
category: business
tags: [pdf, invoices, automation, data-extraction, billing, accounting]
---

# Automate PDF Invoice Processing

## The Problem

Marta manages accounts payable for a mid-size agency that receives 200+ vendor invoices per month as PDF attachments. Each vendor uses a different format — some are machine-generated PDFs, some are scanned paper invoices, and a few are just photos of receipts. She manually opens each one, types the amounts into a spreadsheet, cross-references with purchase orders, and enters everything into the billing system. It takes two full days every month and errors creep in regularly.

The worst part isn't the time — it's the mistakes nobody catches. A transposed digit on a $4,300 invoice becomes $43,000 in the spreadsheet, and nobody notices until the vendor calls asking where their payment went. Last quarter, a duplicate invoice slipped through and the agency paid the same vendor twice. Getting the refund took six weeks.

## The Solution

Using the **pdf-analyzer**, **data-extractor**, **excel-processor**, and **billing-automation** skills, the agent builds a pipeline that classifies incoming PDFs by type, extracts structured data from each one, validates the math and flags anomalies, produces a formatted Excel report, and pushes approved invoices into the billing system — all in under 10 minutes for a 200-invoice batch.

## Step-by-Step Walkthrough

### Step 1: Classify Incoming Invoice PDFs

Marta drops 50 sample invoices from her top vendors into a folder and asks the agent to figure out what they're dealing with:

```text
I have a folder of 50 sample invoice PDFs from our top vendors. They're
a mix of machine-generated PDFs, scanned documents, and a few image-only
PDFs. Analyze them and tell me what we're dealing with — which ones have
extractable text, which need OCR, and what the common layouts look like.
```

The classification results break down into three tiers:

| PDF Type | Count | Notes |
|---|---|---|
| Machine-generated (extractable text) | 32 (64%) | Clean text layer, structured layouts from QuickBooks, Xero, FreshBooks |
| Scanned documents (need OCR) | 14 (28%) | Image-only pages — 10 high-res (300+ DPI), 4 low-res (150 DPI or less) |
| Image-based (photos/screenshots) | 4 (8%) | Phone photos embedded as single-page PDFs — 2 rotated, 1 with poor lighting |

Four distinct layout patterns emerge across the samples:

- **Pattern A (38%)** — Header with logo, invoice number top-right, table of line items, total at bottom-right. Standard accounting software output.
- **Pattern B (26%)** — Letterhead style, amounts inline with descriptions, no table structure.
- **Pattern C (20%)** — European format with comma decimals, DD.MM.YYYY dates, and a VAT breakdown section.
- **Pattern D (16%)** — Minimal: just amounts and a reference number, no line items at all.

The classifier goes into `invoice_pipeline/classifiers.py` — it auto-detects PDF type and layout pattern for each incoming file.

### Step 2: Extract Structured Data from Each Invoice

Next, building the actual extraction engine:

```text
Build the extraction pipeline. For each invoice, I need: vendor name,
invoice number, invoice date, due date, currency, line items (description,
quantity, unit price, total), subtotal, tax, and grand total. Handle the
European date and number formats too.
```

The extraction script (`invoice_pipeline/extract.py`) uses three strategies depending on the PDF type:

**Machine-generated PDFs** get the cleanest treatment — `pdfplumber` extracts text directly, regex patterns match invoice numbers (`INV-\d+`, `#\d+`, `Invoice \d+`), and `pdfplumber.extract_tables()` pulls line items. Date detection handles MM/DD/YYYY, DD.MM.YYYY, YYYY-MM-DD, and long-form dates like "January 5, 2025."

**Scanned documents** go through OCR via Tesseract with pre-processing: deskew, contrast enhancement, binarization. The same regex patterns apply to the OCR output, and each field gets a confidence score based on Tesseract's confidence values.

**Low-quality images** get enhanced pre-processing — adaptive thresholding, noise removal, multiple OCR passes with different PSM modes. Anything below 70% confidence gets flagged for manual review.

Every invoice produces a clean JSON record:

```json
{
  "vendor": "Bright Studio Design",
  "invoiceNumber": "INV-2025-0847",
  "invoiceDate": "2025-01-15",
  "dueDate": "2025-02-14",
  "currency": "EUR",
  "lineItems": [
    { "description": "Logo redesign", "qty": 1, "unitPrice": 2500.00, "total": 2500.00 },
    { "description": "Brand guidelines document", "qty": 1, "unitPrice": 1800.00, "total": 1800.00 }
  ],
  "subtotal": 4300.00,
  "tax": 817.00,
  "taxRate": 0.19,
  "grandTotal": 5117.00,
  "confidence": 0.94,
  "flags": []
}
```

### Step 3: Validate Extracted Data and Flag Anomalies

Raw extraction isn't enough — the math needs to check out:

```text
Add validation rules: line items should sum to subtotal, tax should match
the rate times subtotal, due date should be after invoice date, and no
required field should be empty. Also check for duplicate invoice numbers
across the batch.
```

The validation engine (`invoice_pipeline/validate.py`) runs five rules on every invoice:

1. **Line item math** — `sum(lineItems.total)` must equal subtotal (tolerance: +/-$0.02 for rounding). Each line item: `qty * unitPrice` must equal `total` (+/-$0.01).
2. **Tax calculation** — Tax must equal `subtotal * taxRate` (+/-$0.05). Auto-detects common rates: 19%, 21%, 20%, 7%, 10%, 25%.
3. **Date logic** — Due date must be after invoice date. Invoice date must not be in the future.
4. **Required fields** — Vendor, invoice number, invoice date, and grand total must not be empty.
5. **Duplicate detection** — Checks the `invoiceNumber + vendor` combination against the current batch and historical records in `processed_invoices.json`.

Against the 50-sample batch: 39 invoices (78%) pass clean, 6 (12%) have minor rounding flags, and 5 (10%) need human review — 3 from OCR issues, 2 from missing fields. That 10% review rate is the target: low enough to be useful, high enough to catch real problems.

### Step 4: Export to a Structured Excel Report

```text
Generate an Excel report with three sheets: a summary of all invoices,
a detailed line-items sheet, and a flagged-for-review sheet. Add
conditional formatting — highlight overdue invoices in red, flag
amounts over $10,000 in yellow.
```

The Excel report (`reports/invoices_{YYYY-MM}.xlsx`) has three sheets:

**Invoice Summary** — Every invoice on one row: vendor, invoice number, date, due date, currency, subtotal, tax, total, status. Sorted by due date ascending. Red fill on overdue unpaid invoices, yellow fill on amounts over $10,000, green text on paid. Auto-filter and frozen header row.

**Line Items** — Every line item across all invoices: invoice number, vendor, description, qty, unit price, line total. Grouped by invoice number with Excel SUBTOTAL formulas per invoice.

**Needs Review** — Only flagged invoices: invoice number, vendor, flag type, flag detail, confidence score, and a hyperlink to the original PDF. This is the sheet Marta actually works from — she reviews the 8-12% that need attention and ignores the rest.

File size for a 200-invoice batch: roughly 350KB.

### Step 5: Push Approved Invoices into the Billing System

```text
After I review the flagged invoices and fix any issues, push all approved
invoices into our billing system. We use a REST API — I'll give you the
endpoint. Create payment schedules based on due dates and send a summary
notification.
```

The billing sync script (`invoice_pipeline/sync_billing.py`) reads from `invoice_data/approved.json` — after Marta reviews flagged items, she moves the fixed ones from flagged to approved.

For each approved invoice, it hits `POST /api/v1/payables` with the mapped fields: vendor ID (looked up from `vendor_map.json`), amount, currency, due date, reference number, and line items. New vendors get auto-created via `POST /api/v1/vendors`. Every API call and response is logged to an audit trail.

Payment scheduling groups invoices by due-date week and creates batch files: overdue invoices first, then by amount descending. The summary notification tells Marta exactly where things stand:

> **February 2025 Invoice Processing Complete**
> Processed: 207 invoices | Total value: EUR 148,392.00
> Approved and synced: 198 | Flagged for review: 9
> New vendors created: 3 | Next payment batch: EUR 42,100 due Feb 21

## Real-World Example

Kai handles procurement for a growing design studio with 40 freelance contractors. Monthly invoice processing was eating three days of admin time, and payment delays were straining contractor relationships — two freelancers had already threatened to stop taking jobs.

After setting up the pipeline, the PDF folder gets batch-processed in under 10 minutes. The Excel report goes to the finance lead for a quick review of flagged items, and approved invoices sync to the billing system automatically. Processing time dropped from three days to two hours (mostly the 8-12% that get flagged), and late payments dropped to near zero. The two unhappy freelancers got paid on time for the first time in months.
