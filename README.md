# OpenCQL v2 — Structured Context Engineering DSL

> *"SQL gave non-experts a declarative way to ask for data. OpenCQL does the same for LLM context."*

[![Status](https://img.shields.io/badge/Status-Experimental-orange)](.)
[![License](https://img.shields.io/badge/License-GPL--3.0-blue)](LICENSE)

---

## Table of Contents

1. [What Is Context Engineering?](#1-what-is-context-engineering)
2. [The Context Window — The Most Valuable Space in AI](#2-the-context-window--the-most-valuable-space-in-ai)
3. [The Problems with How We Do It Today](#3-the-problems-with-how-we-do-it-today)
4. [Why This Is Hard to Fix with Code Alone](#4-why-this-is-hard-to-fix-with-code-alone)
5. [Enter OpenCQL](#5-enter-opencql)
6. [Installation](#6-installation)
7. [Quick Start](#7-quick-start)
8. [DSL Reference](#8-dsl-reference)
9. [Aggregation Strategies](#9-aggregation-strategies)
10. [LLM Providers](#10-llm-providers)
11. [Vector Store](#11-vector-store)
12. [Architecture](#12-architecture)
13. [Running the Demo](#13-running-the-demo)
14. [File Structure](#14-file-structure)
15. [Roadmap](#15-roadmap)

---

## 1. What Is Context Engineering?

When you talk to an LLM, it does not remember anything. Every request starts from zero. The model has no idea who you are, what your codebase looks like, what happened in previous conversations, what documents are relevant to your question, or what rules it should follow when answering you.

All of that information — everything the model needs to give you a good, accurate, grounded response — has to be physically placed inside the **context window** before the model generates its reply.

**Context engineering** is the discipline of deciding:

- *What* information to place in the context window
- *Where* that information comes from (documents, databases, conversation history, tools)
- *How much* of it to include (token budgets, ranking, filtering)
- *In what form* it should be presented (raw text, structured summaries, role-labeled turns)
- *In what order* the model should reason over it (sequentially, in parallel, hierarchically)

It sits one level above prompt engineering. Prompt engineering is about *how you phrase* the instructions. Context engineering is about *what information is present* when those instructions are executed.

The quality of your context is, in most production AI systems, the single largest determinant of output quality — more than the model choice, the temperature setting, or the system prompt wording.

---

## 2. The Context Window — The Most Valuable Space in AI

Think of the context window as a whiteboard that the LLM can see while it works. It can only see what is written on that whiteboard. Anything not on the whiteboard does not exist as far as the model is concerned.

Modern models have large whiteboards — 128k, 200k, even 1 million tokens. This sounds like a lot. But size alone does not solve the problem. The real challenge is *selection* — deciding what deserves a place on the whiteboard in the first place.

### The Context Window Is a Knapsack Problem

In computer science, the **0/1 Knapsack Problem** is a classic optimization challenge: given a knapsack with a fixed weight capacity and a collection of items each with a weight and a value, find the combination of items that maximizes total value without exceeding the capacity.

The context window is exactly this problem, played out on every single LLM request.

| Knapsack Concept | Context Window Equivalent |
|---|---|
| Knapsack capacity (weight limit) | Token limit of the context window |
| Item weight | Token count of a document chunk, history turn, or instruction |
| Item value | How much that piece of information improves the model's response |
| Selected items | The final context sent to the LLM |
| Left-behind items | Documents retrieved but not included due to budget |
| Optimal packing | The context assembly that maximizes response quality within the token budget |

The analogy holds in its most important dimension: **you cannot put everything in**. You have a finite budget, a large candidate pool, and items of unequal value and size. The question is never "should I include more information?" — it is always "which information, at what cost, produces the best outcome?"

### Why the Knapsack Framing Matters

The classic knapsack problem is NP-hard in its general form. There is no polynomial-time algorithm guaranteed to find the perfect packing. In practice, people use approximations — greedy heuristics, dynamic programming over discretized weights, or branch-and-bound search. These work well enough most of the time.

Context engineering faces the exact same situation, with additional complications that make it strictly *harder* than the textbook knapsack:

**Item value is not known in advance.** In the classic problem, each item has a clearly labeled value. In context engineering, you do not know how valuable a document chunk is until after the model has read it and generated a response. You are estimating relevance — via semantic similarity, recency, metadata filters — but these are proxies for value, not value itself. A chunk with 0.95 cosine similarity to the query might be a near-duplicate of something already in the context and thus add almost nothing. A chunk with 0.61 similarity might contain the one fact that prevents a hallucination. You do not know until it is too late.

**Item value is not independent.** In the standard knapsack, each item's value is fixed regardless of what else is in the bag. In context engineering, the value of a document chunk depends heavily on what other chunks surround it. A policy document that says "exceptions apply when the customer is on the Enterprise plan" is worthless if the customer's account tier is not also in the context. Information is relational. Its value is conditional.

**The knapsack has positional effects.** In the standard problem, item order does not matter — the bag holds what it holds. In the context window, order matters significantly. Items placed at the beginning (system prompt, key instructions) and at the end (the user's most recent message) receive disproportionately more attention than items in the middle. So the problem is not just *which items* to select — it is also *in what order* to place them. This turns a packing problem into a packing-and-ordering problem simultaneously.

**The capacity itself is not uniform.** A token budget of 8,000 tokens with 10 dense technical paragraphs is a different problem than 8,000 tokens with 40 short conversational exchanges. The model's effective comprehension of the context degrades in different ways depending on content density, topic coherence, and how many distinct information sources are represented. Capacity is nominally fixed but practically variable.

**There is a cost for every packing attempt.** In the classic problem, you can try different combinations without penalty. In context engineering, every request costs money — in API tokens, in latency, in compute. A poor packing decision is not just suboptimal; it is expensive and potentially irreversible if it leads to a hallucinated response that a user acts on.

### The Naive Solution and Why It Fails

Most RAG systems today use a greedy approximation that is equivalent to the simplest possible knapsack heuristic: **take the highest-value items first until the bag is full**.

```
Sort chunks by cosine similarity (descending)
Add chunks one by one until token limit is reached
Stop
```

This is the greedy fractional knapsack algorithm. It is optimal when item values are independent and the value-to-weight ratio is the right sorting criterion. Neither condition holds for context assembly. Items are interdependent, similarity is an imperfect value proxy, and the position of each item in the final window matters as much as whether it was included at all.

The greedy approach produces adequate results for simple queries with coherent, non-overlapping retrieval results. It produces poor results — and hallucinations — for complex, multi-source, multi-domain queries where the interaction effects between items dominate.

### What Good Context Packing Looks Like

A well-engineered context packing strategy has to address each dimension of the problem:

**Selection** — Which chunks to include, based not just on individual similarity scores but on marginal information gain. The second chunk about the same topic adds less value than the first. Diversity of information matters, not just relevance.

**Deduplication** — Near-duplicate chunks are dead weight. They consume tokens without adding value and can confuse the model by presenting slightly different phrasings of the same fact.

**Ordering** — High-signal items belong at the top (right after the system prompt) and at the bottom (right before the user's question). Low-signal background context belongs in the middle where attention naturally falls off.

**Domain separation** — Chunks from different domains should not be interleaved when they represent distinct reasoning contexts. A legal analysis paragraph sandwiched between technical infrastructure notes forces the model to context-switch mid-thought.

**Budget allocation** — The token budget is not a single pool to be filled greedily. It is a resource to be allocated across categories: some tokens for system instructions, some for retrieved knowledge, some for conversation history, some for the user's current query. Over-allocating to retrieved documents can crowd out history that the model needs to maintain conversational coherence.

**Explicit limits** — The packing algorithm should be explicit and auditable. Silent truncation is the context engineering equivalent of a knapsack that secretly throws out items without telling you. You need to know what got left out and why.

### The Broader Constraints

Beyond the knapsack dynamics, the context window has several additional properties that compound the difficulty.

**It is expensive.** Every token in the context window costs money on every single request. A 100k-token context sent 10,000 times per day at typical API pricing costs thousands of dollars monthly. A poorly packed knapsack does not just degrade quality — it directly inflates your inference bill.

**It is not uniform.** Research consistently shows that LLMs pay more attention to information at the beginning and end of the context window. Information buried in the middle gets significantly less attention — the so-called *lost in the middle* problem. A 200k context stuffed with marginally relevant documents is often worse than a carefully curated 4k context. In knapsack terms: the bag has a gradient, not a flat interior.

**It is a shared resource.** The window holds everything at once: system instructions, conversation history, retrieved documents, tool results, user input. These all compete for the same space and the same model attention. Poor allocation means important information gets crowded out by less important information that was simply easier to retrieve.

**It has no structure the model enforces.** You can put anything in any order. The model has no concept of "this part is background, this part is authoritative policy." It is all just tokens, and the model has to figure out what to trust, what to prioritize, and what to ignore. A well-packed knapsack with no labeling is still a pile of unlabeled items.

---

## 3. The Problems with How We Do It Today

Despite how central context assembly is to AI quality, the tooling for it is remarkably primitive. Here is what the state of the art actually looks like in most production codebases today.

### Problem 1: The Bag of Words Approach

The standard retrieval pattern is this:

```python
docs = vector_db.similarity_search(query, k=5)
context = "\n".join([d.page_content for d in docs])
prompt = f"{context}\n\nQuestion: {query}"
response = llm.invoke(prompt)
```

This is the **bag of words** approach. You grab the top-k semantically similar chunks and concatenate them. It ignores:

- Whether those chunks actually answer the question or just share vocabulary with it
- Whether they come from authoritative sources or low-quality ones
- Whether they contradict each other
- Whether they are recent or stale
- Whether the combined token count fits the model's sweet spot
- Whether they are relevant to each *part* of a multi-part question

This approach works acceptably for simple, single-domain, single-question queries. It breaks down on everything more complex.

### Problem 2: No Cross-Source Reasoning

Real-world questions often require information from multiple sources simultaneously. A customer support question might need:

- The product documentation (what does the feature do?)
- The customer's account history (what plan are they on, have they hit this before?)
- Internal policy documents (what is the refund policy?)
- The current conversation (what exactly did they say?)

The bag of words approach treats all of this as one undifferentiated pile of text. There is no concept of "join these two sources" or "prioritize this source over that one when they conflict." The model has to figure out provenance from the raw text, which it frequently gets wrong.

### Problem 3: Context Overflow and Silent Truncation

When the retrieved context exceeds the model's context window, most frameworks silently truncate. The last chunks in the list get dropped. Because retrieval usually returns results in descending similarity order, truncation preferentially drops the *least similar* results — which sounds fine until you realize those might contain crucial nuance the top results don't cover.

Worse, developers often don't know this is happening. There is no error, no warning, just a quietly degraded response.

```python
# This silently drops anything past the token limit.
# You have no idea what got cut.
context = "\n".join([d.page_content for d in docs])
```

### Problem 4: Hallucination Under Context Conflict

LLMs hallucinate most aggressively when the context is ambiguous, conflicting, or under-specified. When you dump five retrieved chunks that partially contradict each other into the context with no structure, the model has to reconcile them. Often it invents a synthesis that isn't supported by any of the individual sources. It sounds confident because it is drawing on its training distribution to fill the gaps, not because it is reasoning carefully about what the evidence actually says.

This is not a model quality problem. It is a context quality problem. The same model with a well-structured, non-contradictory context produces far fewer hallucinations.

### Problem 5: The Logic Is Buried in Python

Consider what a production RAG pipeline actually looks like:

```python
def build_context(query, user_id, session_id):
    # Retrieve product docs
    product_results = product_index.similarity_search(query, k=5)
    product_chunks = [r.page_content for r in product_results
                      if r.metadata.get("similarity", 0) > 0.75]

    # Get customer history
    customer_history = history_db.query(
        f"SELECT content FROM history WHERE user_id = '{user_id}' "
        f"ORDER BY timestamp DESC LIMIT 10"
    )

    # Get relevant policies
    policy_results = policy_index.similarity_search(query, k=3)

    # Combine, respect token limit
    all_chunks = product_chunks + customer_history + policy_results
    token_count = 0
    trimmed = []
    for chunk in all_chunks:
        tokens = len(chunk.split()) * 1.3  # rough estimate
        if token_count + tokens > 3000:
            break
        trimmed.append(chunk)
        token_count += tokens

    # Inject history
    history = session_store.get(session_id, [])[-5:]
    history_text = "\n".join([f"{r}: {m}" for r, m in history])

    return {
        "system": "You are a helpful support agent.",
        "context": "\n\n".join(trimmed),
        "history": history_text
    }
```

This is 30 lines of Python that embeds critical business logic — what sources to query, how to rank them, what the token budget is, how many history turns to include — inside imperative code. It is hard to read, hard to modify, impossible to inspect at runtime, and completely invisible to anyone who isn't a developer.

When this pipeline produces a bad response, you have no DSL-level trace of what happened. You have to add logging manually, re-run the query, parse the logs, and try to reconstruct what the model actually saw.

### Problem 6: Multi-Domain Queries Collapse Into Noise

When a query touches multiple distinct domains — say, a compliance question that is simultaneously a legal question, a financial question, and a technical infrastructure question — the bag-of-words approach retrieves a mixed pile of chunks from all three domains and presents them together. The model has to simultaneously be a lawyer, a CFO, and a systems engineer in a single inference pass.

Domain experts know this does not produce good answers. The better approach is to reason about each domain separately with appropriate framing, then synthesize. But this requires orchestration logic that is painful to write and maintain in plain code.

### Problem 7: No Reusability or Composability

The context assembly logic for "customer support question" is written once, inline, in one service. When the billing team builds their own assistant, they rewrite it from scratch. When the onboarding team builds theirs, same thing. There is no mechanism to define a context pattern once and reuse it — no equivalent of a SQL `VIEW` or a stored procedure for context assembly.

The result is that every team implements its own slightly different, slightly wrong version of the same retrieval patterns, with no shared vocabulary for discussing them and no way to systematically improve them across the organization.

---

## 4. Why This Is Hard to Fix with Code Alone

You might reasonably ask: why not just write better Python? Clean up the retrieval logic, add proper token counting, build utility functions for common patterns.

The problem is that context assembly logic is inherently **declarative** in nature. What you want to express is: "give me the most relevant product documentation, joined with this customer's history, filtered by recency, capped at 2000 tokens, with a system prompt appropriate for billing questions." That is a *description of what you want* — not a procedure for how to get it.

Python is an imperative language. It is excellent at expressing *how* to do things step by step. It is poor at expressing *what* you want at a high level of abstraction without specifying implementation details. Every time you want to change "recency threshold from 30 days to 60 days," you are modifying a data retrieval policy decision inside procedural code. Every time you want to add a new source to a context, you are changing control flow.

This is exactly the problem SQL solved for databases forty years ago. Before SQL, querying a database meant writing low-level navigation code — follow this pointer, iterate over these records, apply this filter manually. SQL introduced a declarative layer: you describe the shape of the data you want, and the query engine figures out how to retrieve it. The separation between *what* (the query) and *how* (the execution plan) was transformative.

Context engineering for LLMs is at the same pre-SQL moment right now.

---

## 5. Enter OpenCQL

OpenCQL is a Domain-Specific Language for context engineering. It gives you a declarative syntax for expressing the *what* of context assembly, while the runtime handles the *how*.

The same 30-line Python pipeline from Problem 5 becomes:

```sql
CONTEXT customer_support AS (
    WITH SYSTEM "You are a helpful support agent."

    RETRIEVE FROM docs.product
        WHERE similarity > 0.75
        TOP 5

    JOIN history.customer SEMANTIC ON customer_id

    RETRIEVE FROM docs.policy
        TOP 3

    INJECT HISTORY LAST 5 TURNS

    LIMIT TOKENS 3000
)

INFER
    WITH MODEL = "claude-3-5-sonnet-20241022"
    USING CONTEXT customer_support
    GOAL "Resolve the customer's question accurately"
```

This is readable by a non-engineer. It is inspectable. It can be versioned, reviewed in a pull request, and discussed in plain language. The what is completely separated from the how.

**OpenCQL directly addresses each problem outlined above:**

| Problem | OpenCQL Solution |
|---|---|
| Bag of words retrieval | `RETRIEVE FROM <source> WHERE similarity > 0.8` — explicit thresholds and ranking |
| No cross-source reasoning | `JOIN <source> SEMANTIC ON <key>` — first-class cross-source joins |
| Silent truncation | `LIMIT TOKENS 2000` — explicit, visible, enforced budget |
| Hallucination under conflict | `PARTITION BY domain` — separate inference chains per domain reduce cross-domain noise |
| Logic buried in Python | CQL is the logic — declarative, inspectable, versionable |
| Multi-domain collapse | `PARTITION BY domain AUTO` — MapReduce across domains, then synthesis |
| No reusability | `CONTEXT <n> AS (...)` — named, reusable context definitions like SQL VIEWs |

### The MapReduce Pattern in Practice

For multi-domain queries, OpenCQL's `PARTITION BY` clause is particularly powerful. Instead of dumping all domains into one context, it runs parallel inference chains:

```sql
CONTEXT compliance_check AS (
    RETRIEVE FROM docs.governance TOP 10
    PARTITION BY domain ("Legal", "Financial", "Technical")
)

INFER
    WITH MODEL = "claude-3-5-sonnet-20241022"
    USING CONTEXT compliance_check
    GOAL "Assess our compliance posture across all domains"
    AGGREGATE BY "synthesis"
```

Execution:

1. **Map phase**: Three parallel LLM calls, each with only their domain's documents and a domain-specific system prompt. The Legal agent sees only legal docs. The Financial agent sees only financial docs.
2. **Reduce phase**: A final synthesis call combines the three expert analyses into one coherent response.

This is categorically less prone to hallucination than presenting all 30 governance documents to a single LLM call and asking it to reason across all three domains simultaneously.

### Context as a First-Class Abstraction

The `CONTEXT ... AS (...)` construct is deliberately analogous to a SQL `VIEW`. It separates the *definition* of how to assemble context from the *use* of that context in inference. You can define `CONTEXT customer_support` once and reuse it across dozens of `INFER` statements with different goals, models, and parameters. Teams can share context definitions. Context patterns can be reviewed, tested, and iterated on independently of the inference logic that uses them.

This is the missing abstraction layer in production AI systems today.

---

## 6. Installation

```bash
pip install lark
# Optional: real semantic embeddings (otherwise falls back to TF-IDF)
pip install sentence-transformers
# Optional: LLM provider SDKs
pip install anthropic openai
```

---

## 7. Quick Start

```python
from opencql import CQLRuntime

rt = CQLRuntime(default_model="mock")

# Register your data sources
store = rt.registry.get_or_create("docs.product")
store.add_documents([
    {"text": "OpenCQL uses SQL-style syntax to control LLM context.", "topic": "overview"},
    {"text": "RETRIEVE performs semantic search over vector stores.", "topic": "retrieval"},
    {"text": "PARTITION BY enables parallel MapReduce inference chains.", "topic": "partitioning"},
])

result = rt.execute("""
    CONTEXT overview AS (
        WITH SYSTEM "You are a helpful assistant."
        RETRIEVE FROM docs.product
            WHERE similarity > 0.1
            TOP 3
        LIMIT TOKENS 1500
    )

    INFER
        WITH MODEL = "mock"
        USING CONTEXT overview
        GOAL "Explain what OpenCQL is and why it matters"
""", query="what is opencql")

print(result)
```

---

## 8. DSL Reference

### `CONTEXT` — Define a reusable context block

```sql
CONTEXT <n> AS (
    <clauses>
)
```

Analogous to a SQL `VIEW`. Defines *how* to assemble context, not the context itself. Reusable across any number of `INFER` statements.

---

### `RETRIEVE` — Semantic search

```sql
RETRIEVE FROM <source>
    WHERE similarity > 0.8     -- minimum cosine similarity threshold
    TOP 10                      -- max results to retrieve
    LIMIT TOKENS 1500           -- trim retrieved chunks to token budget
```

`<source>` maps to a named `VectorStore` in the registry (e.g. `docs.product`, `history.customer`). Multiple `RETRIEVE` clauses accumulate chunks in order.

---

### `JOIN` — Cross-source retrieval

```sql
JOIN history.customer SEMANTIC ON customer_id    -- semantic similarity join
JOIN taxonomy.labels  EXACT    ON category_id    -- exact metadata match join
```

Brings in documents from a second source — like a SQL `JOIN` but over embeddings or metadata fields.

---

### `PARTITION BY` — MapReduce inference

```sql
-- Explicit partitions
PARTITION BY domain ("Legal", "Financial", "Technical")

-- Auto-discover partition values from document metadata
PARTITION BY domain AUTO
```

Splits context into groups, runs a parallel inference chain on each group (Map), then combines (Reduce). Eliminates cross-domain noise. Powered by `concurrent.futures` for real parallelism.

---

### `INJECT HISTORY` — Conversation memory

```sql
INJECT HISTORY LAST 5 TURNS                                        -- from runtime params
INJECT HISTORY ( ("user", "hello"), ("assistant", "hi there") )   -- explicit turns
```

---

### `LIMIT` — Token budget control

```sql
LIMIT TOKENS 2000    -- trim context chunks to stay within token budget
LIMIT CHUNKS 5       -- keep only the top N retrieved chunks
```

Explicit and visible. No more silent truncation.

---

### `WITH SYSTEM` — System prompt

```sql
WITH SYSTEM "You are an expert in compliance and legal risk."
```

Scoped to the context block. Different contexts can have different system prompts.

---

### `INFER` — Run inference

```sql
INFER
    WITH MODEL = "claude-3-5-sonnet-20241022"   -- or "gpt-4o", "llama3", "mock"
    USING CONTEXT <context_name>
    GOAL "your natural language goal"
    AGGREGATE BY "synthesis"                     -- synthesis | vote | concat
    TEMPERATURE = 0.7
    MAX TOKENS = 1024
    FORMAT = "json"
```

---

## 9. Aggregation Strategies

Used when `PARTITION BY` is active — controls how parallel inference results are combined.

| Strategy | Behavior |
|---|---|
| `synthesis` | A final LLM call synthesizes all partition outputs into one cohesive response |
| `concat` | Partition outputs are concatenated with domain labels — good for audit trails |
| `vote` | Returns the most common response across partitions — good for factual consistency checks |

---

## 10. LLM Providers

Provider is auto-detected from the model name. No configuration object needed.

| Model prefix | Provider | Requires |
|---|---|---|
| `claude-*` | Anthropic | `ANTHROPIC_API_KEY` env var |
| `gpt-*`, `o1-*`, `o3-*` | OpenAI | `OPENAI_API_KEY` env var |
| `llama3`, `mistral`, `phi3`, etc. | Ollama (local) | Running Ollama instance |
| `mock` | Built-in mock | Nothing |

```python
import os
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."
rt = CQLRuntime(default_model="claude-3-5-sonnet-20241022")
```

---

## 11. Vector Store

The built-in `VectorStore` uses cosine similarity. With `sentence-transformers` installed it uses `all-MiniLM-L6-v2` for real semantic embeddings. Without it, a lightweight TF-IDF approximation is used — sufficient for development.

```python
store = VectorStore()
store.add_documents([
    {"text": "GDPR requires encryption of all PII at rest.", "domain": "Legal"},
    {"text": "Budget for compliance tooling is $120k.", "domain": "Financial"},
])
results = store.search("encryption requirements", top_k=3, threshold=0.2)
```

To plug in Chroma, Pinecone, Weaviate, or pgvector: subclass `VectorStore` and override `search()`. The registry and runtime have no opinion about the backing store implementation.

---

## 12. Architecture

```
.cql source code
       │
       ▼
  grammar.lark          Lark Earley/LALR parser
       │
       ▼
   compiler.py          Lark Transformer → execution plan (dict)
       │
       ▼
   runtime.py
   ┌──────────────────────────────────────────┐
   │  ContextAssembler                         │
   │  ├── RETRIEVE   →  vectors.py (search)    │
   │  ├── JOIN       →  vectors.py (join)      │
   │  ├── PARTITION  →  PartitionExecutor      │
   │  │   ├── Map:  parallel LLM calls         │
   │  │   └── Reduce: synthesis / vote / concat│
   │  └── HISTORY / SYSTEM / LIMIT             │
   └──────────────────────────────────────────┘
       │
       ▼
    llm.py              Anthropic / OpenAI / Ollama / Mock
       │
       ▼
   Final response string
```

---

## 13. Running the Demo

```bash
python demo_full.py
```

Five demos, no API key needed (uses mock LLM by default):

- **Demo A**: Simple `CONTEXT` + `INFER` with similarity filtering
- **Demo B**: `JOIN` across two named sources
- **Demo C**: MapReduce with explicit `PARTITION BY domain`
- **Demo D**: Conversation history injection via `INJECT HISTORY`
- **Demo E**: `PARTITION BY domain AUTO` — dynamic domain discovery

To run against a real model, set your API key and change `"mock"` to `"claude-3-5-sonnet-20241022"` or `"gpt-4o"` in the demo file.

---

## 14. File Structure

```
opencql/
├── grammar.lark       DSL grammar definition (Lark)
├── compiler.py        Parse tree → execution plan (Transformer)
├── runtime.py         Execution engine (ContextAssembler, PartitionExecutor)
├── vectors.py         VectorStore + SourceRegistry
├── llm.py             Multi-provider LLM layer
├── demo_full.py       End-to-end demos
└── __init__.py        Package exports
```

---

## 15. Roadmap

- [ ] `WHERE recency < 30 DAYS` — time-based metadata filters
- [ ] `CACHE` clause — memoize expensive retrievals across requests
- [ ] `EXPLAIN` statement — show exactly what ended up in the context and why
- [ ] `SCORE BY` — custom ranking functions beyond cosine similarity
- [ ] CLI: `opencql run query.cql --params params.json`
- [ ] PyPI package: `pip install opencql`
- [ ] Chroma / Pinecone / Weaviate / pgvector adapter classes
- [ ] Hallucination benchmarks vs naive retrieval
- [ ] `CONTEXT` import/export for cross-team sharing

---

## License

GPL-3.0 — see [LICENSE](LICENSE)
