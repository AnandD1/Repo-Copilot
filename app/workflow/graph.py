"""LangGraph workflow assembly with control flow."""

from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import WorkflowState, HITLAction
from .retriever_agent import RetrieverAgent
from .reviewer_agent import ReviewerAgent
from .planner_agent import PatchPlannerAgent
from .guardrail_agent import GuardrailAgent
from .hitl_gate import HITLGate
from .publisher_notifier import PublisherNotifier
from .persistence_agent import PersistenceAgent
from config.settings import Settings


def should_proceed_to_hitl(state: WorkflowState) -> str:
    """
    Routing function: decide if we go to HITL or stop.
    
    If guardrails fail, we still go to HITL to show blocked reasons.
    """
    return "hitl"


def should_publish(state: WorkflowState) -> str:
    """
    Routing function: after HITL, decide whether to publish or stop.
    
    Routes based on HITL decision:
    - approve → publish
    - edit → publish (with edits)
    - reject → stop
    - post_summary_only → publish (summary only)
    """
    if not state.hitl_decision:
        # No decision, stop
        return "persistence_reject"
    
    action = state.hitl_decision.action
    
    if action == HITLAction.APPROVE:
        return "publish"
    elif action == HITLAction.EDIT:
        return "publish"
    elif action == HITLAction.POST_SUMMARY_ONLY:
        return "publish"
    elif action == HITLAction.REJECT:
        return "persistence_reject"
    else:
        # Unknown action, stop
        return "persistence_reject"


def create_review_workflow(
    github_token: Optional[str] = None,
    settings: Optional[Settings] = None
) -> StateGraph:
    """
    Create the LangGraph workflow for PR review.
    
    Args:
        github_token: GitHub API token for posting comments
        settings: Application settings (includes Slack config for Phase 6)
    
    Returns:
        Compiled StateGraph
    """
    # Load settings if not provided
    if settings is None:
        settings = Settings()
    
    # Initialize agents (pass settings to publisher for Slack integration)
    retriever = RetrieverAgent()
    reviewer = ReviewerAgent()
    planner = PatchPlannerAgent()
    guardrail = GuardrailAgent()
    hitl = HITLGate()
    publisher = PublisherNotifier(github_token=github_token, settings=settings)
    persistence = PersistenceAgent()
    
    # Create workflow graph
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("retriever", retriever)
    workflow.add_node("reviewer", reviewer)
    workflow.add_node("planner", planner)
    workflow.add_node("guardrail", guardrail)
    workflow.add_node("hitl", hitl)
    workflow.add_node("publish", publisher)
    workflow.add_node("persistence", persistence)
    workflow.add_node("persistence_reject", persistence)
    
    # Define edges (flow)
    # Start → Retriever
    workflow.set_entry_point("retriever")
    
    # Retriever → Reviewer
    workflow.add_edge("retriever", "reviewer")
    
    # Reviewer → Planner
    workflow.add_edge("reviewer", "planner")
    
    # Planner → Guardrail
    workflow.add_edge("planner", "guardrail")
    
    # Guardrail → HITL (always, even if failed - to show blocked reasons)
    workflow.add_conditional_edges(
        "guardrail",
        should_proceed_to_hitl,
        {
            "hitl": "hitl",
        }
    )
    
    # HITL → conditional routing
    workflow.add_conditional_edges(
        "hitl",
        should_publish,
        {
            "publish": "publish",
            "persistence_reject": "persistence_reject",
        }
    )
    
    # Publish → Persistence → END
    workflow.add_edge("publish", "persistence")
    workflow.add_edge("persistence", END)
    
    # Persistence (reject path) → END
    workflow.add_edge("persistence_reject", END)
    
    # Compile with memory
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    return app


def run_workflow(
    initial_state: WorkflowState,
    workflow: Optional[StateGraph] = None
) -> Dict[str, Any]:
    """
    Run the workflow with initial state.
    
    Args:
        initial_state: Initial workflow state
        workflow: Pre-compiled workflow (creates new if None)
        
    Returns:
        Final state dictionary
    """
    if workflow is None:
        workflow = create_review_workflow()
    
    # Create config for checkpointing
    config = {"configurable": {"thread_id": initial_state.run_id}}
    
    # Run workflow
    print(f"\n{'='*80}")
    print(f"🚀 Starting Workflow - Run ID: {initial_state.run_id}")
    print(f"{'='*80}\n")
    
    final_state = None
    
    try:
        # Stream events for visibility
        for event in workflow.stream(initial_state.model_dump(), config):
            # Each event is a dict with node name as key
            for node_name, node_output in event.items():
                if node_name != "__end__":
                    # Update is already printed by node functions
                    pass
        
        # Get final state
        final_state = workflow.get_state(config)
        
        print(f"\n{'='*80}")
        print(f"✅ Workflow Complete - Run ID: {initial_state.run_id}")
        print(f"{'='*80}\n")
        
        return final_state.values if final_state else {}
        
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ Workflow Failed - Run ID: {initial_state.run_id}")
        print(f"Error: {e}")
        print(f"{'='*80}\n")
        raise
