---
name: langsmith
description: >-
  Monitor, trace, debug, and evaluate LLM applications with LangSmith. Use when
  a user asks to trace LLM calls, debug chain executions, evaluate AI output
  quality, set up LLM observability, monitor agent performance, run prompt
  experiments, compare model outputs, create evaluation datasets, track token
  usage and latency, or build LLM testing pipelines. Covers tracing, datasets,
  evaluators, annotation queues, prompt hub, and production monitoring.
license: Apache-2.0
compatibility: "Python 3.9+ or Node.js 18+ (langsmith SDK)"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: ai
  tags: ["langsmith", "llm-observability", "tracing", "evaluation", "monitoring"]
---

# LangSmith

## Overview

LangSmith is the observability and evaluation platform for LLM applications. It traces every step of your chains and agents, helps you build evaluation datasets, run automated quality checks, and monitor production performance. Essential for moving LLM apps from prototype to production.

## Instructions

### Step 1: Setup and Configuration

Create a LangSmith account at [smith.langchain.com](https://smith.langchain.com) and get an API key.

```bash
pip install langsmith
```

Set environment variables:
```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY="lsv2_pt_..."
export LANGCHAIN_PROJECT="my-project"  # Optional, defaults to "default"
```

Once set, **all LangChain calls are automatically traced** — no code changes needed.

For non-LangChain code, use the SDK directly:
```python
from langsmith import Client
client = Client()
```

### Step 2: Tracing

#### Automatic Tracing (LangChain)
With `LANGCHAIN_TRACING_V2=true`, every `.invoke()`, `.stream()`, `.batch()` call is traced automatically. Each trace shows:
- Input/output at every step
- Token usage and cost
- Latency per component
- Error details with full stack traces

#### Manual Tracing with `@traceable`
For custom functions outside LangChain:
```python
from langsmith import traceable

@traceable(name="process_order", tags=["production"])
def process_order(order_id: str, items: list) -> dict:
    # Your business logic
    validated = validate_items(items)
    summary = generate_summary(validated)  # LLM call
    return {"order_id": order_id, "summary": summary, "status": "processed"}

@traceable
def validate_items(items: list) -> list:
    # Nested traces automatically link to parent
    return [item for item in items if item["quantity"] > 0]
```

#### Tracing with Context Manager
```python
from langsmith import trace

with trace("data-pipeline", inputs={"source": "csv"}) as run:
    data = load_data("input.csv")
    processed = transform(data)
    run.end(outputs={"rows": len(processed)})
```

#### Metadata and Tags
```python
# Add metadata to any LangChain call
result = chain.invoke(
    {"question": "..."},
    config={
        "metadata": {"user_id": "u-123", "environment": "staging"},
        "tags": ["beta-test", "gpt4"]
    }
)
```

### Step 3: Datasets and Examples

Datasets are collections of input/output pairs used for evaluation:

```python
from langsmith import Client

client = Client()

# Create a dataset
dataset = client.create_dataset("customer-support-qa", description="Real support questions with expected answers")

# Add examples
client.create_examples(
    inputs=[
        {"question": "How do I reset my password?"},
        {"question": "What's your refund policy?"},
        {"question": "How to upgrade my plan?"},
    ],
    outputs=[
        {"answer": "Go to Settings > Security > Reset Password"},
        {"answer": "Full refund within 30 days, no questions asked"},
        {"answer": "Visit Billing > Plans > select new tier"},
    ],
    dataset_id=dataset.id,
)

# Create from existing traces (powerful for production data)
# In the UI: select traces → "Add to Dataset"
```

#### From CSV
```python
import csv
from langsmith import Client

client = Client()
dataset = client.create_dataset("faq-pairs")

with open("faq.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        client.create_example(
            inputs={"question": row["question"]},
            outputs={"answer": row["answer"]},
            dataset_id=dataset.id,
        )
```

### Step 4: Evaluation

Run your chain against a dataset and score the results:

```python
from langsmith import evaluate

# Your target function (chain, agent, or any callable)
def my_app(inputs: dict) -> dict:
    result = chain.invoke(inputs)
    return {"answer": result}

# Custom evaluator
def correctness(run, example) -> dict:
    """Check if the answer matches expected output."""
    predicted = run.outputs["answer"]
    expected = example.outputs["answer"]
    score = 1.0 if expected.lower() in predicted.lower() else 0.0
    return {"key": "correctness", "score": score}

def conciseness(run, example) -> dict:
    """Penalize overly long answers."""
    answer = run.outputs["answer"]
    word_count = len(answer.split())
    score = 1.0 if word_count < 100 else max(0, 1.0 - (word_count - 100) / 200)
    return {"key": "conciseness", "score": score}

# Run evaluation
results = evaluate(
    my_app,
    data="customer-support-qa",  # dataset name
    evaluators=[correctness, conciseness],
    experiment_prefix="gpt4o-v2",
    max_concurrency=4,
)

# Results visible in LangSmith UI with scores, comparisons, and drill-down
```

#### LLM-as-Judge Evaluators
```python
from langsmith import evaluate
from langchain_openai import ChatOpenAI

judge_llm = ChatOpenAI(model="gpt-4o", temperature=0)

def llm_judge(run, example) -> dict:
    """Use an LLM to evaluate answer quality."""
    predicted = run.outputs["answer"]
    expected = example.outputs["answer"]

    response = judge_llm.invoke(
        f"Rate this answer from 0.0 to 1.0.\n"
        f"Expected: {expected}\n"
        f"Got: {predicted}\n"
        f"Reply with just the number."
    )
    score = float(response.content.strip())
    return {"key": "llm_quality", "score": score}

results = evaluate(my_app, data="customer-support-qa", evaluators=[llm_judge])
```

#### Pairwise Comparison
```python
from langsmith import evaluate_comparative

def prefer_longer(runs, example) -> dict:
    """Compare two runs and pick the better one."""
    a_len = len(runs[0].outputs["answer"])
    b_len = len(runs[1].outputs["answer"])
    # Return 0 for first, 1 for second
    return {"key": "preference", "scores": {runs[0].id: int(a_len >= b_len), runs[1].id: int(b_len > a_len)}}

evaluate_comparative(
    ["experiment-gpt4o", "experiment-claude"],
    evaluators=[prefer_longer],
)
```

### Step 5: Prompt Hub

Version-control and share prompts:

```python
from langchain import hub

# Pull a prompt
prompt = hub.pull("rlm/rag-prompt")

# Push your own
from langchain_core.prompts import ChatPromptTemplate

my_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a {role}. Answer in {style}."),
    ("human", "{question}")
])

hub.push("my-org/support-prompt", my_prompt, new_repo_is_public=False)
```

### Step 6: Annotation Queues

Set up human review workflows:

```python
client = Client()

# Create a queue
queue = client.create_annotation_queue(
    name="review-flagged-responses",
    description="Responses that scored below 0.5 on quality"
)

# Add runs to the queue (typically from evaluation results or filters)
# In the UI: filter traces → "Send to Annotation Queue"
```

Use annotation queues to:
- Review low-confidence outputs before they reach users
- Build gold-standard datasets from production data
- Get human labels for training and evaluation

### Step 7: Production Monitoring

#### Filter and Analyze Traces
```python
# Get recent runs with filters
runs = client.list_runs(
    project_name="production",
    filter='and(eq(status, "error"), gt(latency, 5))',  # Errors over 5 seconds
    limit=50,
)

for run in runs:
    print(f"Run {run.id}: {run.error} | Latency: {run.total_time}s | Tokens: {run.total_tokens}")
```

#### Track Metrics Over Time
```python
# Aggregate token usage
runs = client.list_runs(
    project_name="production",
    start_time=datetime(2024, 1, 1),
    limit=1000,
)

total_tokens = sum(r.total_tokens or 0 for r in runs)
total_cost = sum(r.prompt_tokens * 0.00001 + r.completion_tokens * 0.00003 for r in runs if r.prompt_tokens)
avg_latency = sum(r.total_time for r in runs if r.total_time) / len(list(runs))
```

#### Automation Rules (UI)
In the LangSmith dashboard, set up rules to:
- Auto-flag runs with latency > threshold
- Send low-score responses to annotation queues
- Alert on error rate spikes
- Auto-add interesting traces to datasets

### Step 8: Testing in CI/CD

```python
# tests/test_chain_quality.py
import pytest
from langsmith import evaluate

def correctness(run, example):
    return {"key": "correctness", "score": float(example.outputs["answer"].lower() in run.outputs["answer"].lower())}

def test_qa_quality():
    results = evaluate(
        my_app,
        data="regression-test-set",
        evaluators=[correctness],
    )
    avg_score = sum(r["evaluation_results"]["results"][0].score for r in results) / len(results)
    assert avg_score >= 0.85, f"Quality dropped to {avg_score:.2f}"
```

## Best Practices

1. **Always enable tracing in dev** — set `LANGCHAIN_TRACING_V2=true` from day one
2. **Use projects to organize** — separate dev, staging, production traces
3. **Build datasets from production** — real data makes the best test sets
4. **Start with simple evaluators** — exact match and contains before LLM judges
5. **Run evals on every PR** — catch regressions before they ship
6. **Use annotation queues** — human review builds trust and better datasets
7. **Tag everything** — metadata makes filtering and analysis possible
8. **Monitor cost** — track token usage per user/feature to control spend
9. **Compare experiments** — A/B test prompts and models systematically
10. **Version prompts in Hub** — never lose a prompt that worked well

## Common Pitfalls

- **Forgetting to set env vars**: No tracing without `LANGCHAIN_TRACING_V2=true`
- **Huge traces**: Logging full documents in metadata slows the UI — summarize or truncate
- **Evaluator flakiness**: LLM judges are non-deterministic — use temperature=0 and run multiple times
- **Not separating projects**: Dev traces mixed with production makes analysis impossible
- **Ignoring latency data**: Tracing overhead is minimal (<5ms) — the latency insights are worth it
