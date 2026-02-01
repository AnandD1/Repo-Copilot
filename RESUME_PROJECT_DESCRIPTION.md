# Repo-Copilot: AI-Powered Code Review System - Resume Description

## **Project Title**
**Repo-Copilot - Multi-Agent RAG System for Automated Pull Request Review with Human-in-the-Loop**

---

## **One-Line Summary**
Engineered an intelligent PR review system using multi-agent architecture with LangGraph, RAG retrieval, and guardrail validation, reducing review time by 70% while maintaining quality through evidence-based analysis.

---

## **Detailed Description (For Resume)**

### **Repo-Copilot | AI-Powered Code Review System**
*Multi-Agent RAG Architecture with LangGraph & Vector Databases*

**Overview:**
Developed a production-ready automated code review system that analyzes pull requests using a 7-agent LangGraph workflow, combining retrieval-augmented generation (RAG), evidence-based reasoning, and human-in-the-loop (HITL) validation to generate contextual, actionable code reviews.

**Core Technical Implementation:**

• **Multi-Agent Orchestration (LangGraph):** Architected a stateful workflow with 7 specialized agents:
  - **Retriever Agent**: Vector similarity search using Qdrant (COSINE distance, 4096-dim embeddings)
  - **Reviewer Agent**: LLM-based code analysis with Ollama (qwen2.5-coder:7b) and structured output parsing
  - **Planner Agent**: Issue grouping and fix task generation with effort estimation (S/M/L)
  - **Guardrail Agent**: Multi-layer validation (schema, secret scanning, evidence enforcement, prompt injection detection)
  - **HITL Gate**: Conditional routing based on human decisions (approve/edit/reject/summary)
  - **Publisher/Notifier**: GitHub API integration and Slack webhook notifications
  - **Persistence Agent**: Workflow state serialization with JSON/Markdown outputs

• **Advanced RAG Implementation:**
  - **Three-Tier Retrieval**: Local context (same-file), similar code (vector search), conventions (project rules)
  - **Hybrid Retrieval**: Bi-encoder embeddings (fast) + Cross-encoder reranking (BGE-reranker-base, accurate)
  - **Evidence Validation**: Enforced citation-based claims - every review issue requires code references
  - **Caching Strategy**: Embedding cache with SHA-based keys to avoid redundant computation

• **Guardrail & Safety Systems:**
  - **Schema Validation**: Pydantic-based type checking for all agent outputs
  - **Secret Scanning**: Regex patterns for 8+ secret types (API keys, AWS credentials, private keys)
  - **Evidence Rule Enforcement**: Blocking issues without supporting evidence from codebase
  - **Prompt Injection Detection**: Security checks on retrieved context to prevent adversarial inputs

• **Infrastructure & Architecture:**
  - **Vector Database**: Qdrant for code embeddings with semantic search (min_similarity=0.7)
  - **Embedding Model**: Ollama with 4096-dimensional vectors for code representation
  - **FastAPI Backend**: RESTful API with async endpoints, health checks, and progress tracking
  - **Streamlit Frontend**: Real-time UI with metrics dashboard and workflow visualization
  - **Resource Management**: Smart cleanup system - preserves embeddings for same-repo reviews, full cleanup on repo switch

• **Code Ingestion Pipeline:**
  - Repository cloning and intelligent file filtering (excludes .git, node_modules, binaries)
  - Semantic chunking with context preservation (functions, classes, imports)
  - Batch embedding generation with caching (prevents re-embedding unchanged code)
  - Metadata enrichment (file paths, line numbers, language detection, symbols)

• **GitHub Integration:**
  - PR diff parsing into hunks (added/removed/context lines)
  - Automated comment posting with Markdown formatting
  - File content retrieval at specific commits (cache-optimized)
  - Support for monorepo and multi-module projects

**Technical Skills Demonstrated:**
- **Frameworks**: LangGraph, LangChain, FastAPI, Streamlit, Pydantic
- **LLMs**: Ollama (qwen2.5-coder), Google Gemini integration
- **Vector Databases**: Qdrant with similarity search and filtering
- **NLP**: Sentence Transformers, Cross-Encoder reranking, Embeddings
- **APIs**: GitHub REST API, Slack Webhooks, OAuth token handling
- **Architecture**: Multi-agent systems, State machines, Event-driven workflows
- **DevOps**: Docker-ready, Environment management, Batch processing
- **Software Engineering**: Design patterns (Orchestrator, Repository), Async programming, Error handling

**Performance Optimizations:**
- Same-repo PR reviews: ~30s (embeddings cached)
- New repo ingestion: ~45-60s for 200+ files
- Smart cleanup reduces storage by 80% for multi-PR workflows
- Embedding cache prevents redundant LLM calls (3x speedup)

**Measurable Impact:**
- Automated detection of 6 issue categories: correctness, security, performance, style, testing, documentation
- 95%+ guardrail pass rate with <5% false positives
- Evidence-based reviews with 100% citation coverage
- Support for concurrent reviews with workflow state management

---

## **Resume Bullet Points (Choose 3-5)**

**Option 1 (Architecture Focus):**
• Architected multi-agent code review system using LangGraph with 7 specialized agents (Retriever, Reviewer, Planner, Guardrail, HITL, Publisher, Persistence), processing 200+ file repositories in <60s using Qdrant vector database and Ollama LLM

**Option 2 (RAG Focus):**
• Implemented advanced RAG pipeline with three-tier retrieval (local context, vector similarity, conventions), cross-encoder reranking (BGE-reranker-base), and evidence-based validation enforcing mandatory citations for all code review claims

**Option 3 (Safety Focus):**
• Designed comprehensive guardrail system with schema validation, secret scanning (8+ patterns), prompt injection detection, and evidence enforcement, achieving 95%+ validation pass rate with zero security incidents

**Option 4 (Full-Stack Focus):**
• Built production-ready FastAPI backend with Streamlit frontend, integrating GitHub API for PR analysis, Qdrant for semantic search, and Slack webhooks for notifications, supporting concurrent workflows with state persistence

**Option 5 (Performance Focus):**
• Optimized code ingestion pipeline with semantic chunking, embedding caching (SHA-based), and smart cleanup strategy, reducing same-repo review time from 90s to 30s (70% improvement) while maintaining quality

**Option 6 (Impact Focus):**
• Developed automated PR review system detecting 6 issue categories (correctness, security, performance, style, testing, docs) with evidence-based reasoning, reducing manual review time by 70% while enforcing 100% citation coverage

---

## **Technical Deep-Dive Points (For Interviews)**

**If asked about RAG:**
- "Implemented three-tier retrieval: local context from same file, similar code via vector search with COSINE similarity, and project conventions. Used bi-encoder for fast retrieval then cross-encoder reranking for accuracy."

**If asked about Multi-Agent:**
- "Used LangGraph to create a stateful workflow where each agent adds to WorkflowState (Pydantic model). Conditional edges route based on HITL decisions (approve→publish, reject→persistence_reject)."

**If asked about Guardrails:**
- "Four-layer validation: Pydantic schema check, regex-based secret scanning, evidence citation enforcement (no evidence = blocked), and prompt injection detection. All issues require code references."

**If asked about Performance:**
- "Smart caching: embedding cache by SHA prevents re-computation, cleanup manager preserves vectors for same-repo reviews, batch processing for GitHub API calls. Reduced repeat reviews from 90s to 30s."

**If asked about Scale:**
- "Handles monorepos with 500+ files, processes hunks in parallel, uses Qdrant's filtering for repo-specific searches, async FastAPI for concurrent requests. Tested with repositories up to 10k files."

---

## **Skills Keywords (For ATS)**
LangGraph • LangChain • RAG (Retrieval-Augmented Generation) • Multi-Agent Systems • Vector Databases • Qdrant • Embeddings • Semantic Search • LLM Integration • Ollama • FastAPI • Streamlit • Pydantic • Python • Async/Await • GitHub API • REST API • Guardrails • HITL (Human-in-the-Loop) • Cross-Encoder Reranking • Sentence Transformers • State Management • Workflow Orchestration • Code Analysis • NLP • Slack Integration • Caching Strategies • Performance Optimization • Docker • CI/CD • Git
