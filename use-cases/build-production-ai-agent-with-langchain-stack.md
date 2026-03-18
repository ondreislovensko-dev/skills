---
title: "Build a Production AI Agent with the LangChain Stack"
slug: build-production-ai-agent-with-langchain-stack
description: "Create a multi-step RAG agent with LangGraph, trace and debug with LangSmith, and evaluate quality before shipping to production."
skills: [langchain, langgraph, langsmith]
category: data-ai
tags: [langchain, langgraph, langsmith, rag, agents, production, evaluation]
---

# Build a Production AI Agent with the LangChain Stack

## The Problem

Dani is the lead engineer at a 15-person B2B SaaS company that sells project management software. Their support team handles 400 tickets a day, and 60% are questions that could be answered from existing documentation — API guides, changelogs, troubleshooting pages, and knowledge base articles spread across 1,200 pages.

They tried a basic RAG chatbot: embed docs, retrieve top-k, prompt GPT. It worked for demos. In production, it hallucinated pricing that changed two months ago, gave irrelevant answers when questions needed multi-step reasoning ("How do I migrate from v2 webhooks to v3 and update my auth?"), and there was no way to tell which answers were good and which were garbage.

The numbers: 35% of AI answers required human correction. Support agents stopped trusting the bot and started ignoring it. The $2,400/month in API costs produced negative ROI because bad answers increased ticket resolution time instead of reducing it.

Dani needs an agent that can reason through multi-step questions, knows when to search vs. ask for clarification, gets evaluated before every deployment, and has full observability so the team can debug failures in minutes instead of days.

## The Solution

Using the **langchain**, **langgraph**, and **langsmith** skills, the workflow builds a stateful RAG agent with LangGraph for multi-step reasoning, LangChain for retrieval and tool integration, and LangSmith for tracing, evaluation, and monitoring — turning a flaky chatbot into a production system that blocks its own deployment when quality drops.

## Step-by-Step Walkthrough

### Step 1: Build the Document Pipeline

Before any agent logic, 1,200 markdown files need to become searchable vectors. The pipeline loads docs from the `/docs` folder, splits them with overlap so context isn't lost at chunk boundaries, and stores them in Chroma with metadata filters for doc type, version, and last-updated date:

```python
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

# Load all markdown docs with metadata
loader = DirectoryLoader("./docs", glob="**/*.md", show_progress=True)
docs = loader.load()

# Split with overlap — chunk_size=800 keeps context tight,
# overlap=200 ensures no answer falls between cracks
splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200)
chunks = splitter.split_documents(docs)

# Tag each chunk with filterable metadata
for chunk in chunks:
    chunk.metadata["doc_type"] = classify_doc(chunk.metadata["source"])
    chunk.metadata["last_updated"] = get_file_mtime(chunk.metadata["source"])

# Embed and store — text-embedding-3-small balances cost and quality
vectorstore = Chroma.from_documents(
    chunks,
    OpenAIEmbeddings(model="text-embedding-3-small"),
    collection_name="support_docs",
    persist_directory="./chroma_db"
)
print(f"Indexed {len(chunks)} chunks from {len(docs)} documents")
```

The metadata matters more than it looks. When a user asks about "v3 webhooks," the retriever can filter to `doc_type=api` and `version=v3` before doing similarity search — no more pulling deprecated v2 docs into the context window.

### Step 2: Create the LangGraph Agent with Conditional Routing

This is where the architecture diverges from basic RAG. Instead of a linear retrieve-then-generate pipeline, the agent is a state machine with five nodes. Each node reads and writes to shared state, and conditional edges decide what happens next:

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class SupportState(TypedDict):
    messages: Annotated[list, add_messages]
    question_type: str        # "simple", "multi_step", "escalate"
    sub_queries: list[str]
    retrieved_docs: list
    answer: str
    citations: list[str]
    confidence: float
    needs_human: bool

graph = StateGraph(SupportState)

# Add nodes — each is a function that takes state and returns partial state
graph.add_node("classify", classify_question)
graph.add_node("decompose", decompose_into_sub_queries)
graph.add_node("retrieve", retrieve_documents)
graph.add_node("generate", generate_answer)
graph.add_node("evaluate", evaluate_confidence)
graph.add_node("escalate", route_to_human)

# Conditional routing — this is the key difference from basic RAG
graph.add_conditional_edges("classify", lambda s: s["question_type"], {
    "simple": "retrieve",        # Direct questions go straight to retrieval
    "multi_step": "decompose",   # Complex questions get broken into sub-queries
    "escalate": "escalate",      # Ambiguous questions go to a human
})

graph.add_edge("decompose", "retrieve")  # Sub-queries feed into retrieval
graph.add_edge("retrieve", "generate")
graph.add_conditional_edges("evaluate", lambda s: s["needs_human"], {
    True: "escalate",   # Low confidence → human review
    False: END,         # High confidence → return answer
})

graph.set_entry_point("classify")
agent = graph.compile(checkpointer=SqliteSaver("./checkpoints.db"))
```

The `classify` node is the traffic cop. A question like "What's the API rate limit?" routes straight to retrieval. "How do I migrate from v2 webhooks to v3 and update my auth?" gets decomposed into two sub-queries that each retrieve their own context. "I'm having a weird issue with my account" — too vague, escalate to a human immediately rather than guessing.

### Step 3: Add Confidence Scoring and Self-Evaluation

The generate node doesn't just produce an answer — it scores its own confidence using structured output. This is what makes the difference between a chatbot that guesses and one that knows when it's guessing:

```python
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

class SupportAnswer(BaseModel):
    answer: str = Field(description="The answer to the user's question")
    citations: list[str] = Field(description="Source doc paths used")
    confidence: float = Field(description="0.0-1.0 confidence score")
    reasoning: str = Field(description="Why this confidence level")

llm = ChatOpenAI(model="gpt-4o").with_structured_output(SupportAnswer)

def generate_answer(state: SupportState) -> dict:
    context = "\n\n".join(doc.page_content for doc in state["retrieved_docs"])
    result = llm.invoke([
        {"role": "system", "content": f"""Answer the support question using ONLY the provided context.
Cite specific doc paths. If the context doesn't contain the answer, set confidence below 0.5.

Context:
{context}"""},
        {"role": "user", "content": state["messages"][-1].content}
    ])
    return {
        "answer": result.answer,
        "citations": result.citations,
        "confidence": result.confidence,
        "needs_human": result.confidence < 0.7
    }
```

The 0.7 threshold isn't arbitrary — it comes from calibrating against the evaluation dataset in the next step. Answers below 0.7 confidence are right only 40% of the time. Above 0.7, accuracy jumps to 94%.

### Step 4: Wire Up LangSmith Tracing and Evaluation

Every query that flows through the agent automatically gets traced in LangSmith — node-by-node, with inputs, outputs, latency, and token usage. But tracing alone doesn't prevent regressions. The evaluation pipeline does.

First, build a dataset from 200 real support tickets where the team already knows the right answer:

```python
from langsmith import Client

ls_client = Client()

# Create evaluation dataset from real support tickets
dataset = ls_client.create_dataset("support-eval-v1")
for ticket in labeled_tickets:
    ls_client.create_example(
        inputs={"question": ticket["question"]},
        outputs={"expected_answer": ticket["answer"],
                 "expected_sources": ticket["source_docs"]},
        dataset_id=dataset.id,
    )
```

Then define custom evaluators that check what matters — not just "is the answer similar" but "are the citations real documents that exist":

```python
from langsmith.evaluation import evaluate

def citation_accuracy(run, example):
    """Check that cited sources actually exist and are relevant."""
    cited = run.outputs.get("citations", [])
    expected = example.outputs["expected_sources"]
    if not cited:
        return {"key": "citation_accuracy", "score": 0.0}
    valid = sum(1 for c in cited if any(e in c for e in expected))
    return {"key": "citation_accuracy", "score": valid / len(cited)}

results = evaluate(
    agent.invoke,
    data="support-eval-v1",
    evaluators=[correctness_evaluator, citation_accuracy, helpfulness_evaluator],
    experiment_prefix="agent-v2.3",
)
print(f"Accuracy: {results.aggregate['correctness']:.1%}")
print(f"Citation accuracy: {results.aggregate['citation_accuracy']:.1%}")
```

### Step 5: Set Up the CI/CD Quality Gate

Evaluation runs locally during development, but the real safety net is the CI pipeline. Every pull request that touches agent code triggers a full evaluation run. If accuracy drops below 90%, the build fails:

```yaml
# .github/workflows/agent-eval.yml
name: Agent Evaluation
on:
  pull_request:
    paths: ["src/agent/**", "src/prompts/**", "docs/**"]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - name: Run evaluation suite
        env:
          LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python -m pytest tests/test_evaluation.py \
            --tb=short \
            -x  # Stop on first failure
      - name: Check accuracy threshold
        run: python scripts/check_eval_results.py --min-accuracy 0.90
```

The `check_eval_results.py` script pulls the latest evaluation run from LangSmith and fails if any metric drops below threshold. Three regressions have been caught this way before reaching production — a prompt tweak that tanked citation accuracy, a chunk size change that broke multi-step retrieval, and a model swap that hallucinated more.

### Step 6: Production Monitoring and Alerting

Once deployed, LangSmith monitors every query in production. Dashboards track latency percentiles, token usage, confidence distribution, and error rates. Alerts fire when things drift:

```python
from langsmith import traceable

@traceable(name="support_agent_query")
def handle_support_query(question: str, user_id: str) -> dict:
    """Production entry point — automatically traced in LangSmith."""
    config = {"configurable": {"thread_id": user_id}}
    result = agent.invoke({"messages": [("user", question)]}, config)

    # Log to monitoring
    track_metrics({
        "confidence": result["confidence"],
        "question_type": result["question_type"],
        "latency_ms": result.get("_latency_ms"),
        "escalated": result["needs_human"],
    })
    return result
```

The monitoring dashboard shows patterns that evaluations miss. Confidence scores trending downward across a week usually means docs have changed and embeddings are stale — time to re-index. A spike in escalation rate after a deploy means the classify node is being too conservative. These signals are visible in LangSmith within hours, not days.

## Real-World Example

Two months after launching the LangGraph agent, Dani's support metrics tell the story. Accuracy sits at 91%, up from 65% with the basic RAG chatbot. The 35% human-correction rate dropped to 12% — and those 12% are genuine edge cases that get flagged automatically by the confidence scoring, not silent failures that erode trust.

The multi-step handling is the biggest win. Questions like "How do I migrate from v2 webhooks to v3 and also update my OAuth scopes?" used to get a partial answer or a hallucination. Now they decompose into sub-queries, each pulling the right docs, and the final answer cites both the webhook migration guide and the OAuth changelog.

Monthly cost went from $2,400 in API calls with negative ROI to $1,800 serving 12,000 queries at $0.15 each — compared to $4.20 per ticket when a human handles it. The CI quality gate has blocked 3 bad deployments that would have degraded accuracy. And when something does go wrong, the team opens the LangSmith trace, sees exactly which node failed and why, and fixes it in the same afternoon. No more "the bot gave a bad answer last Tuesday and we have no idea why."
