"""Visualize LangGraph workflow for Repo-Copilot."""

from app.workflow import create_review_workflow
from config.settings import Settings


def visualize_workflow():
    """Generate and save LangGraph workflow visualization."""
    
    print("Creating workflow graph...")
    
    # Initialize settings
    settings = Settings()
    
    # Create the workflow (same as used in production)
    workflow = create_review_workflow(
        github_token="dummy_token_for_visualization",
        settings=settings
    )
    
    print("Generating Mermaid diagram...")
    
    try:
        # Generate PNG using Mermaid
        png_data = workflow.get_graph().draw_mermaid_png()
        
        # Save to file
        output_file = "workflow_graph.png"
        with open(output_file, "wb") as f:
            f.write(png_data)
        
        print(f"✓ Workflow graph saved to: {output_file}")
        print("\nWorkflow nodes:")
        print("1. retriever - Retrieve relevant code context")
        print("2. reviewer - Analyze code and find issues")
        print("3. planner - Create fix plan from issues")
        print("4. guardrail - Validate review quality")
        print("5. hitl - Human-in-the-loop decision")
        print("6. publish - Post to GitHub & send notifications")
        print("7. persistence - Save workflow results")
        print("8. persistence_reject - Save rejected workflows")
        
        return output_file
        
    except Exception as e:
        print(f"Error generating diagram: {e}")
        print("\nTrying alternative ASCII representation...")
        
        try:
            # Fallback: print ASCII diagram
            ascii_diagram = workflow.get_graph().draw_ascii()
            print("\nWorkflow Graph (ASCII):")
            print("=" * 80)
            print(ascii_diagram)
            print("=" * 80)
        except Exception as e2:
            print(f"ASCII diagram also failed: {e2}")
            
        return None


def visualize_in_notebook():
    """For Jupyter Notebook usage."""
    from IPython.display import Image
    
    # Create the workflow
    settings = Settings()
    workflow = create_review_workflow(
        github_token="dummy_token_for_visualization",
        settings=settings
    )
    
    # Display in notebook
    return Image(workflow.get_graph().draw_mermaid_png())


if __name__ == "__main__":
    print("=" * 80)
    print("Repo-Copilot Workflow Visualization")
    print("=" * 80)
    print()
    
    output_file = visualize_workflow()
    
    if output_file:
        print(f"\n{'=' * 80}")
        print("To view in Jupyter Notebook, use:")
        print("  from visualize_workflow import visualize_in_notebook")
        print("  visualize_in_notebook()")
        print(f"{'=' * 80}")
