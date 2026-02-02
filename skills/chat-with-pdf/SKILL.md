---
name: chat-with-pdf
description: >-
  Answer questions about PDF content, summarize documents, and extract key
  information from any PDF file. Use when a user asks to chat with a PDF, ask
  questions about a document, find specific information in a PDF, get a summary
  of a PDF, or understand what a PDF document says. Works with reports, papers,
  manuals, and any text-based PDF.
license: Apache-2.0
compatibility: "Requires Python 3.9+ with pdfplumber or PyMuPDF (fitz) installed"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: documents
  tags: ["pdf", "qa", "summarization", "document", "search"]
  use-cases:
    - "Ask specific questions about a lengthy research paper or report"
    - "Get a quick summary of a PDF document without reading the whole thing"
    - "Find and extract specific data points buried in a large document"
  agents: [claude-code, openai-codex, gemini-cli, cursor]
---

# Chat with PDF

## Overview

Enable conversational question-answering over PDF documents. This skill extracts text from PDFs, indexes the content by page and section, and answers user questions with precise citations back to the source material. Supports summarization, fact extraction, comparison, and free-form Q&A.

## Instructions

When a user wants to ask questions about a PDF or get information from a PDF, follow these steps:

### Step 1: Load and extract the PDF content

Read the full text from the PDF file, preserving page boundaries:

```python
import pdfplumber

def extract_pdf(pdf_path):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                pages.append({"page": i + 1, "text": text.strip()})
    return pages
```

### Step 2: Index the content for retrieval

Organize the extracted text so you can locate relevant sections quickly:
1. Split text into paragraphs or logical sections
2. Track page numbers for each section
3. Identify headings, titles, and structural markers
4. Note any tables or lists for structured data queries

For large documents (50+ pages), create a table of contents by scanning for heading patterns (all caps lines, numbered sections, bold markers).

### Step 3: Answer the user's question

Based on the question type, use the appropriate strategy:

**Factual questions** ("What is the revenue for Q3?"):
- Search for keywords and surrounding context
- Extract the specific data point
- Cite the page number

**Summary requests** ("Summarize this document"):
- Extract text from all pages
- Identify the document structure (intro, body, conclusion)
- Produce a concise summary covering key points
- Keep summaries proportional: 1-2 paragraphs for short docs, section-by-section for long docs

**Comparison questions** ("How do the Q1 and Q2 numbers compare?"):
- Locate both data sets in the document
- Extract relevant figures
- Present a side-by-side comparison

**Explanation requests** ("Explain section 4.2"):
- Locate the exact section
- Provide the content with added context and clarification

### Step 4: Format the response with citations

Always include page references so the user can verify:
```
Based on the document:

[Answer to the question]

Sources: Page 12, paragraph 3; Page 15, Table 2
```

### Step 5: Handle follow-up questions

Maintain context from previous questions in the conversation. If the user asks a follow-up, reference both the document content and the prior answer.

## Examples

### Example 1: Ask a specific question about a report

**User request:** "What were the total sales figures mentioned in quarterly-report.pdf?"

**Actions taken:**
1. Extract text from quarterly-report.pdf (28 pages)
2. Search for sales-related keywords: "total sales", "revenue", "net sales"
3. Find relevant data on pages 5 and 12

**Output:**
```
From quarterly-report.pdf:

Total sales figures found:
- Q1 2024: $4.2M (Page 5, Executive Summary)
- Q2 2024: $5.1M (Page 5, Executive Summary)
- Q3 2024: $4.8M (Page 12, Financial Results table)
- YTD Total: $14.1M (Page 12)

Q2 showed the strongest performance at $5.1M, representing a 21% increase
over Q1. Q3 declined slightly by 5.9% compared to Q2.

Sources: Pages 5, 12
```

### Example 2: Summarize a long document

**User request:** "Give me a summary of this 80-page technical manual"

**Actions taken:**
1. Extract all 80 pages of text
2. Identify document structure from headings
3. Summarize each major section

**Output:**
```
Summary of Technical Manual: XR-500 System Administration Guide (80 pages)

1. Installation (Pages 1-15): System requirements, step-by-step setup for
   Linux and Windows, network configuration, and initial security setup.

2. Configuration (Pages 16-35): Core settings, user management, role-based
   access control, database connections, and logging setup.

3. Operations (Pages 36-55): Daily monitoring procedures, backup and restore
   workflows, performance tuning, and scaling guidelines.

4. Troubleshooting (Pages 56-72): Common error codes with solutions, diagnostic
   commands, log analysis, and escalation procedures.

5. Appendices (Pages 73-80): CLI reference, configuration file templates,
   and glossary of terms.

Key takeaway: The manual covers full lifecycle administration of the XR-500
system, with emphasis on security configuration and operational monitoring.

Would you like me to dive deeper into any section?
```

### Example 3: Find specific information

**User request:** "Does this contract mention anything about data retention?"

**Actions taken:**
1. Extract contract text
2. Search for data retention terms: "data retention", "data storage", "retention period", "data deletion"
3. Report findings

**Output:**
```
Yes, data retention is addressed in two places:

1. Section 7.3 - Data Handling (Page 9):
   "Service Provider shall retain Customer Data for a period not exceeding
   90 days following contract termination."

2. Section 12.1 - Compliance (Page 14):
   References GDPR Article 17 right to erasure and commits to deleting
   personal data within 30 days of a valid deletion request.

Note: There is no mention of data retention during the active contract period
or backup retention policies. You may want to clarify these terms.

Sources: Pages 9, 14
```

## Guidelines

- Always cite page numbers when referencing document content so users can verify answers.
- For large PDFs, extract and process text in chunks rather than loading everything into memory at once.
- If the PDF contains scanned images rather than text, inform the user that OCR is needed and suggest the pdf-ocr skill.
- When the answer is not found in the document, explicitly state that rather than guessing.
- Maintain conversational context so follow-up questions work naturally.
- For tables and structured data, present results in formatted tables rather than prose.
- If the document is encrypted or password-protected, inform the user and ask for the password.
