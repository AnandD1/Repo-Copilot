"""LangGraph chain for PR review with conventions."""

from typing import TypedDict, List, Annotated, Sequence
from operator import add

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .retriever import HybridRetriever


class PRReviewState(TypedDict):
    """State for PR review chain."""
    messages: Annotated[Sequence[BaseMessage], add]
    changed_files: List[str]
    repo: str
    branch: str
    language: str
    retrieved_context: List[str]
    conventions: List[str]
    review_comments: List[str]


class PRReviewChain:
    """LangGraph chain for PR review with conventions memory."""
    
    def __init__(
        self,
        retriever: HybridRetriever,
        model_name: str = "gemini-2.0-flash-exp"
    ):
        """Initialize PR review chain.
        
        Args:
            retriever: Hybrid retriever for code + conventions
            model_name: Google Gemini model name
        """
        self.retriever = retriever
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.3)
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow."""
        workflow = StateGraph(PRReviewState)
        
        # Add nodes
        workflow.add_node("retrieve_context", self._retrieve_context)
        workflow.add_node("retrieve_conventions", self._retrieve_conventions)
        workflow.add_node("analyze_changes", self._analyze_changes)
        workflow.add_node("generate_review", self._generate_review)
        
        # Define edges
        workflow.set_entry_point("retrieve_context")
        workflow.add_edge("retrieve_context", "retrieve_conventions")
        workflow.add_edge("retrieve_conventions", "analyze_changes")
        workflow.add_edge("analyze_changes", "generate_review")
        workflow.add_edge("generate_review", END)
        
        return workflow.compile()
    
    def _retrieve_context(self, state: PRReviewState) -> PRReviewState:
        """Retrieve relevant code context."""
        # Get code for each changed file
        context_docs = []
        
        for file_path in state["changed_files"]:
            docs = self.retriever.get_code_context(
                file_path=file_path,
                repo=state["repo"],
                branch=state["branch"],
                limit=3
            )
            context_docs.extend(docs)
        
        # Also do semantic search on the changes
        if state["messages"]:
            last_message = state["messages"][-1].content
            semantic_docs = self.retriever._get_relevant_documents(
                query=last_message,
                repo=state["repo"],
                branch=state["branch"],
                code_k=5
            )
            context_docs.extend([d for d in semantic_docs if d.metadata['source'] == 'code'])
        
        state["retrieved_context"] = [
            f"File: {doc.metadata['file_path']} (lines {doc.metadata['start_line']}-{doc.metadata['end_line']})\n{doc.page_content}"
            for doc in context_docs[:10]  # Limit context
        ]
        
        return state
    
    def _retrieve_conventions(self, state: PRReviewState) -> PRReviewState:
        """Retrieve relevant conventions."""
        # Build query from changes
        if state["messages"]:
            query = state["messages"][-1].content
        else:
            query = f"Code review for {', '.join(state['changed_files'])}"
        
        # Get conventions
        convention_docs = self.retriever._get_relevant_documents(
            query=query,
            language=state.get("language"),
            repo=state["repo"],
            conventions_k=8,
            code_k=0  # Only conventions
        )
        
        state["conventions"] = [
            doc.page_content 
            for doc in convention_docs 
            if doc.metadata['source'] == 'convention'
        ]
        
        return state
    
    def _analyze_changes(self, state: PRReviewState) -> PRReviewState:
        """Analyze changes against conventions."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a code reviewer. Analyze the code changes against the project's conventions.

Project Conventions:
{conventions}

Code Context:
{context}

Changed Files:
{files}

Identify:
1. Convention violations
2. Best practice issues
3. Potential bugs
4. Security concerns
5. Performance issues

Be specific and reference the relevant conventions."""),
            ("human", "{input}")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        analysis = chain.invoke({
            "conventions": "\n\n".join(state.get("conventions", [])),
            "context": "\n\n".join(state.get("retrieved_context", [])),
            "files": ", ".join(state["changed_files"]),
            "input": state["messages"][-1].content if state["messages"] else "Review these changes"
        })
        
        state["messages"] = state.get("messages", []) + [AIMessage(content=analysis)]
        
        return state
    
    def _generate_review(self, state: PRReviewState) -> PRReviewState:
        """Generate final review comments."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful code reviewer. Based on the analysis, generate actionable review comments.

Format each comment as:
**File: [file_path]**
- [Line X]: [Issue description]
- Severity: [High/Medium/Low]
- Convention: [Reference to violated convention if applicable]
- Suggestion: [How to fix]

Be constructive and specific."""),
            ("human", "Generate review comments based on this analysis:\n\n{analysis}")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        review = chain.invoke({
            "analysis": state["messages"][-1].content
        })
        
        state["review_comments"] = review.split("\n\n")
        state["messages"] = state.get("messages", []) + [AIMessage(content=review)]
        
        return state
    
    def review_pr(
        self,
        changed_files: List[str],
        repo: str,
        branch: str = "main",
        language: str = "python",
        pr_description: str = ""
    ) -> dict:
        """Run PR review.
        
        Args:
            changed_files: List of changed file paths
            repo: Repository name
            branch: Branch name
            language: Primary language
            pr_description: PR description
        
        Returns:
            Review result with comments
        """
        initial_state = PRReviewState(
            messages=[HumanMessage(content=pr_description or f"Review changes in {', '.join(changed_files)}")],
            changed_files=changed_files,
            repo=repo,
            branch=branch,
            language=language,
            retrieved_context=[],
            conventions=[],
            review_comments=[]
        )
        
        final_state = self.graph.invoke(initial_state)
        
        return {
            "review_comments": final_state["review_comments"],
            "conventions_used": final_state["conventions"],
            "context_retrieved": len(final_state["retrieved_context"]),
            "full_conversation": [m.content for m in final_state["messages"]]
        }
