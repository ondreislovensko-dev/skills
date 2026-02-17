---
name: langchain
description: >-
  Build LLM-powered applications with LangChain. Use when a user asks to create
  AI chains, build RAG pipelines, implement agents with tools, set up document
  loaders, create vector stores, build conversational AI, implement prompt
  templates, chain LLM calls, add memory to chatbots, or orchestrate language
  model workflows. Covers LangChain v0.3+ with LCEL (LangChain Expression Language),
  structured output, tool calling, retrieval, and production deployment patterns.
license: Apache-2.0
compatibility: "Python 3.9+ or Node.js 18+ (langchain, langchain-core, langchain-community)"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: ai
  tags: ["langchain", "llm", "rag", "agents", "ai-chains", "retrieval"]
---

# LangChain

## Overview

Build production-grade LLM applications using LangChain's composable framework. This skill covers chains, agents, retrieval-augmented generation (RAG), tool integration, memory, and deployment — using modern LCEL patterns (not legacy `LLMChain`).

## Instructions

### Step 1: Project Setup

Determine the user's runtime (Python or TypeScript) and initialize the project:

**Python:**
```bash
pip install langchain langchain-core langchain-openai langchain-community
# For RAG:
pip install langchain-chroma sentence-transformers
# For document loading:
pip install unstructured pypdf docx2txt
```

**TypeScript:**
```bash
npm install langchain @langchain/core @langchain/openai @langchain/community
# For RAG:
npm install @langchain/chroma
```

Verify the LLM provider API key is set:
```bash
echo $OPENAI_API_KEY  # or ANTHROPIC_API_KEY, etc.
```

### Step 2: Understand LCEL (LangChain Expression Language)

All modern LangChain code uses LCEL — the pipe (`|`) operator for composing runnables:

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant specialized in {domain}."),
    ("human", "{question}")
])

chain = prompt | ChatOpenAI(model="gpt-4o") | StrOutputParser()

result = chain.invoke({"domain": "Python", "question": "Explain decorators"})
```

Key LCEL concepts:
- **Runnables**: Any component that implements `.invoke()`, `.stream()`, `.batch()`
- **Pipe operator**: `a | b` means output of `a` feeds into `b`
- **RunnablePassthrough**: Pass input through unchanged
- **RunnableLambda**: Wrap any function as a runnable
- **RunnableParallel**: Run multiple chains simultaneously

### Step 3: Implement Core Patterns

#### Simple Chain
```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

prompt = ChatPromptTemplate.from_template("Summarize this text in {language}: {text}")
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
chain = prompt | llm

result = chain.invoke({"language": "Spanish", "text": "..."})
```

#### Structured Output
```python
from pydantic import BaseModel, Field

class ExtractedInfo(BaseModel):
    name: str = Field(description="Person's full name")
    role: str = Field(description="Job title or role")
    sentiment: str = Field(description="Overall sentiment: positive, negative, neutral")

llm_structured = llm.with_structured_output(ExtractedInfo)
chain = prompt | llm_structured
# Returns ExtractedInfo object, not raw text
```

#### Retrieval-Augmented Generation (RAG)
```python
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.runnables import RunnablePassthrough

# Load and split documents
loader = PyPDFLoader("docs/manual.pdf")
docs = loader.load()
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
splits = splitter.split_documents(docs)

# Create vector store
vectorstore = Chroma.from_documents(splits, OpenAIEmbeddings())
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

# RAG chain
rag_prompt = ChatPromptTemplate.from_template(
    "Answer based on context:\n\n{context}\n\nQuestion: {question}"
)

def format_docs(docs):
    return "\n\n".join(d.page_content for d in docs)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | rag_prompt
    | llm
    | StrOutputParser()
)

answer = rag_chain.invoke("What is the return policy?")
```

#### Tool-Calling Agent
```python
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

@tool
def search_database(query: str) -> str:
    """Search the product database for matching items."""
    # Implementation here
    return f"Found 3 results for '{query}'"

@tool
def calculate_discount(price: float, percent: float) -> float:
    """Calculate discounted price."""
    return price * (1 - percent / 100)

tools = [search_database, calculate_discount]
llm = ChatOpenAI(model="gpt-4o")

# Modern approach uses LangGraph for agents
agent = create_react_agent(llm, tools)
result = agent.invoke({"messages": [("human", "Find laptops under $1000 and apply 15% discount")]})
```

#### Conversational Memory
```python
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

store = {}

def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("placeholder", "{history}"),
    ("human", "{input}")
])

chain = prompt | llm | StrOutputParser()

chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

# Each call remembers previous messages
response = chain_with_history.invoke(
    {"input": "My name is Alice"},
    config={"configurable": {"session_id": "user-123"}}
)
```

### Step 4: Document Loaders and Text Splitters

Common loaders:
```python
from langchain_community.document_loaders import (
    PyPDFLoader,           # PDF files
    TextLoader,            # Plain text
    CSVLoader,             # CSV files
    DirectoryLoader,       # Entire directories
    WebBaseLoader,         # Web pages
    UnstructuredHTMLLoader,# HTML files
    Docx2txtLoader,        # Word documents
    JSONLoader,            # JSON files
)
```

Splitting strategies:
```python
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,  # General purpose (recommended)
    TokenTextSplitter,               # Token-aware splitting
    MarkdownHeaderTextSplitter,      # Split by markdown headers
    HTMLHeaderTextSplitter,          # Split by HTML headers
)

# Best default:
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""]
)
```

### Step 5: Vector Stores

```python
# Chroma (local, good for development)
from langchain_chroma import Chroma
vectorstore = Chroma.from_documents(docs, embeddings, persist_directory="./chroma_db")

# FAISS (fast, in-memory)
from langchain_community.vectorstores import FAISS
vectorstore = FAISS.from_documents(docs, embeddings)
vectorstore.save_local("faiss_index")

# Pinecone (managed, production)
from langchain_pinecone import PineconeVectorStore
vectorstore = PineconeVectorStore.from_documents(docs, embeddings, index_name="my-index")

# Retriever with filters
retriever = vectorstore.as_retriever(
    search_type="mmr",  # Maximum Marginal Relevance for diversity
    search_kwargs={"k": 5, "fetch_k": 20}
)
```

### Step 6: Streaming and Async

```python
# Streaming
async for chunk in chain.astream({"question": "Explain quantum computing"}):
    print(chunk, end="", flush=True)

# Batch processing
results = chain.batch([
    {"question": "What is Python?"},
    {"question": "What is Rust?"},
    {"question": "What is Go?"},
], config={"max_concurrency": 3})

# Stream events (for complex chains)
async for event in chain.astream_events(input, version="v2"):
    if event["event"] == "on_chat_model_stream":
        print(event["data"]["chunk"].content, end="")
```

### Step 7: Production Patterns

#### Error Handling with Fallbacks
```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

primary = ChatOpenAI(model="gpt-4o")
fallback = ChatAnthropic(model="claude-sonnet-4-20250514")

llm_with_fallback = primary.with_fallback([fallback])
chain = prompt | llm_with_fallback | StrOutputParser()
```

#### Caching
```python
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache

set_llm_cache(SQLiteCache(database_path=".langchain_cache.db"))
```

#### Rate Limiting
```python
llm = ChatOpenAI(model="gpt-4o", max_retries=3, request_timeout=30)
# For batch: use max_concurrency
results = chain.batch(inputs, config={"max_concurrency": 5})
```

## Best Practices

1. **Use LCEL, not legacy chains** — `LLMChain`, `SequentialChain` are deprecated
2. **Use `langchain-{provider}` packages** — not monolithic `langchain` imports
3. **Structured output over output parsers** — `.with_structured_output()` is more reliable
4. **LangGraph for agents** — `AgentExecutor` is legacy; use `create_react_agent` from langgraph
5. **Chunk size matters** — too small loses context, too large dilutes relevance; test with 500-1500
6. **Always add overlap** — 10-20% overlap prevents splitting mid-sentence
7. **Use MMR retrieval** — better diversity than pure similarity search
8. **Stream in production** — reduces perceived latency significantly
9. **Cache LLM calls** — identical prompts hit cache instead of API
10. **Test chains with `.invoke()` first** — before adding streaming or async

## Common Pitfalls

- **Importing from wrong package**: Use `from langchain_openai import ChatOpenAI`, not `from langchain.chat_models import ChatOpenAI`
- **Mixing sync/async**: Don't call `.invoke()` inside an async function; use `.ainvoke()`
- **Ignoring token limits**: Large documents need splitting before embedding
- **No error handling**: LLM calls fail — always add fallbacks or retries
- **Embedding model mismatch**: Use the same embedding model for indexing and querying
