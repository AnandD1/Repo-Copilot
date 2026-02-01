"""Streamlit UI for Repo-Copilot PR Review System - Step by Step."""

import streamlit as st
import requests
from datetime import datetime
import time

# Configure page
st.set_page_config(
    page_title="Repo-Copilot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    .step-container {
        background: white;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 5px solid #e0e0e0;
    }
    .step-success {
        border-left-color: #28a745 !important;
        background: #f0fff4 !important;
    }
    .step-in-progress {
        border-left-color: #ffc107 !important;
        background: #fffbf0 !important;
    }
    .step-error {
        border-left-color: #dc3545 !important;
        background: #fff5f5 !important;
    }
    .step-pending {
        border-left-color: #6c757d !important;
        background: #f8f9fa !important;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .error-box {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .info-box {
        background: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# API Configuration
API_BASE_URL = "http://localhost:8000/api/v1"

# Initialize session state
if 'ingestion_result' not in st.session_state:
    st.session_state.ingestion_result = None
if 'pr_fetch_result' not in st.session_state:
    st.session_state.pr_fetch_result = None
if 'workflow_result' not in st.session_state:
    st.session_state.workflow_result = None
if 'is_loading' not in st.session_state:
    st.session_state.is_loading = False
if 'current_repo' not in st.session_state:
    st.session_state.current_repo = None
if 'current_phase' not in st.session_state:
    st.session_state.current_phase = 1
if 'hitl_paused' not in st.session_state:
    st.session_state.hitl_paused = False
if 'hitl_data' not in st.session_state:
    st.session_state.hitl_data = None
if 'run_id' not in st.session_state:
    st.session_state.run_id = None
if 'editing_review' not in st.session_state:
    st.session_state.editing_review = False


def check_api_health():
    """Check if API is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200, response.json()
    except:
        return False, None


def ingest_repository(repo_url):
    """Call API to ingest repository."""
    try:
        payload = {"repo_url": repo_url}
        response = requests.post(
            f"{API_BASE_URL}/ingest",
            json=payload,
            timeout=600
        )
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def fetch_pr(repo_url, pr_number, github_token=None):
    """Call API to fetch and parse PR."""
    try:
        payload = {
            "repo_url": repo_url,
            "pr_number": pr_number,
            "github_token": github_token if github_token else None
        }
        response = requests.post(
            f"{API_BASE_URL}/fetch-pr",
            json=payload,
            timeout=300
        )
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def cleanup_resources():
    """Call API to cleanup resources."""
    try:
        response = requests.post(f"{API_BASE_URL}/cleanup", timeout=30)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}


def render_progress_step(step_info):
    """Render a single progress step."""
    status = step_info.get('status', 'pending')
    step_name = step_info.get('step', 'unknown')
    message = step_info.get('message', '')
    
    # Map step names to display names
    step_display = {
        'parse_url': '🔗 Parse Repository URL',
        'check_repo': '🔍 Check Repository Status',
        'cleanup': '🧹 Cleanup Old Data',
        'ingestion': '📥 Clone & Embed Repository',
        'validate_token': '🔑 Validate GitHub Token',
        'fetch_pr': '📋 Fetch & Parse PR'
    }
    
    # Status icons
    status_icon = {
        'success': '✅',
        'in_progress': '⏳',
        'error': '❌',
        'warning': '⚠️',
        'pending': '⭕'
    }
    
    # CSS class based on status
    css_class = f"step-container step-{status.replace('_', '-')}"
    
    display_name = step_display.get(step_name, step_name)
    icon = status_icon.get(status, '⭕')
    
    st.markdown(f"""
    <div class="{css_class}">
        <div style="display: flex; align-items: center; gap: 10px;">
            <div style="font-size: 1.5rem;">{icon}</div>
            <div style="flex: 1;">
                <div style="font-weight: bold; font-size: 1.1rem;">{display_name}</div>
                <div style="color: #666; margin-top: 0.25rem;">{message}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show additional data if available
    if 'data' in step_info and step_info['data']:
        with st.expander("📊 Details", expanded=False):
            st.json(step_info['data'])


# Header
st.markdown('<div class="main-header">🤖 Repo-Copilot</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-Powered Pull Request Review System</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # API Health Check
    st.subheader("🏥 System Status")
    health_status, health_data = check_api_health()
    
    if health_status:
        st.success("✅ API Connected")
        if health_data and 'services' in health_data:
            for service, status in health_data['services'].items():
                if 'healthy' in status or 'configured' in status:
                    st.text(f"✓ {service}: {status}")
                else:
                    st.text(f"✗ {service}: {status}")
    else:
        st.error("❌ API Offline")
        st.info("Please start the backend:\n```\npython run_backend.py\n```")
    
    st.divider()
    
    # Current Repo Info
    st.subheader("📚 Current Repository")
    if st.session_state.current_repo:
        st.success(f"✅ {st.session_state.current_repo}")
    else:
        st.info("No repository ingested yet")
    
    st.divider()
    
    # Cleanup
    st.subheader("🧹 Cleanup")
    if st.button("🗑️ Clear All Resources"):
        with st.spinner("Cleaning up..."):
            result = cleanup_resources()
            if result.get('status') == 'success':
                st.success("✅ Cleanup complete")
                st.session_state.ingestion_result = None
                st.session_state.pr_fetch_result = None
                st.session_state.workflow_result = None
                st.session_state.current_repo = None
                st.session_state.current_phase = 1
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"❌ {result.get('message', 'Cleanup failed')}")


# Main Content - Show current phase
if st.session_state.current_phase == 1:
    st.header("📥 Phase 1: Repository Ingestion")

# Main Content - Show current phase
if st.session_state.current_phase == 1:
    st.header("📥 Phase 1: Repository Ingestion")
    
    st.markdown("""
    <div class="info-box">
        <b>ℹ️ Repository Ingestion</b><br>
        This step will:
        <ul>
            <li>Parse the GitHub repository URL</li>
            <li>Check if the repository is already ingested</li>
            <li>Clean up old data if switching repositories</li>
            <li>Clone and embed the repository code</li>
        </ul>
        <br>
        <b>Note:</b> If you switch repositories, all previous data will be cleaned up automatically.
    </div>
    """, unsafe_allow_html=True)
    
    # Input form
    col1, col2 = st.columns([3, 1])
    
    with col1:
        repo_url = st.text_input(
            "GitHub Repository URL",
            placeholder="https://github.com/owner/repo",
            help="Enter the full GitHub repository URL",
            key="phase1_repo_url"
        )
    
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        ingest_btn = st.button(
            "🚀 Start Ingestion",
            disabled=not health_status or st.session_state.is_loading or not repo_url,
            use_container_width=True
        )
    
    # Handle ingestion
    if ingest_btn and repo_url:
        st.session_state.is_loading = True
        st.session_state.ingestion_result = None
        
        # Progress container
        progress_container = st.container()
        
        with progress_container:
            st.subheader("📊 Ingestion Progress")
            
            with st.spinner("Processing..."):
                result = ingest_repository(repo_url)
                
                st.session_state.ingestion_result = result
                st.session_state.is_loading = False
                
                # Display progress steps
                if 'progress' in result:
                    for step in result['progress']:
                        render_progress_step(step)
                
                # Display final result
                st.divider()
                
                if result.get('success'):
                    if result.get('already_ingested'):
                        st.success(f"✅ Repository already ingested! Ready to proceed with PR review.")
                        st.info(f"📦 Chunks: {result.get('chunks_created', 'N/A')}")
                    else:
                        st.success(f"✅ Repository ingestion complete! Ready to proceed with PR review.")
                        st.info(f"📦 Chunks created: {result.get('chunks_created', 'N/A')} | "
                               f"⏱️ Time: {result.get('ingestion_time', 0):.2f}s")
                    
                    # Update current repo
                    st.session_state.current_repo = result.get('repo_id', repo_url)
                    
                    # Next steps button
                    if st.button("➡️ Proceed to Phase 2: PR Fetch", type="primary"):
                        st.session_state.current_phase = 2
                        st.rerun()
                    
                else:
                    st.error(f"❌ Ingestion failed: {result.get('error', 'Unknown error')}")
                    
                    # Show traceback in expander
                    if 'traceback' in result:
                        with st.expander("🔍 Error Details"):
                            st.code(result['traceback'], language='python')
    
    # Show previous result if available
    elif st.session_state.ingestion_result:
        st.subheader("📊 Previous Ingestion Result")
        
        result = st.session_state.ingestion_result
        
        # Display progress steps
        if 'progress' in result:
            for step in result['progress']:
                render_progress_step(step)
        
        # Display final result
        st.divider()
        
        if result.get('success'):
            if result.get('already_ingested'):
                st.success(f"✅ Repository already ingested! Ready to proceed with PR review.")
                st.info(f"📦 Chunks: {result.get('chunks_created', 'N/A')}")
            else:
                st.success(f"✅ Repository ingestion complete! Ready to proceed with PR review.")
                st.info(f"📦 Chunks created: {result.get('chunks_created', 'N/A')} | "
                       f"⏱️ Time: {result.get('ingestion_time', 0):.2f}s")
            
            # Next steps button
            if st.button("➡️ Proceed to Phase 2: PR Fetch", type="primary", key="phase1_next"):
                st.session_state.current_phase = 2
                st.rerun()
        else:
            st.error(f"❌ Ingestion failed: {result.get('error', 'Unknown error')}")

elif st.session_state.current_phase == 2:
    st.header("📋 Phase 2: PR Fetch & Parse")
    
    st.markdown("""
    <div class="info-box">
        <b>ℹ️ PR Fetch & Parse</b><br>
        This step will:
        <ul>
            <li>Fetch pull request data from GitHub</li>
            <li>Parse diffs into structured hunks</li>
            <li>Build review units for analysis</li>
            <li>Extract metadata and statistics</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # Input form
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        pr_repo_url = st.text_input(
            "GitHub Repository URL",
            value=st.session_state.ingestion_result.get('repo_owner', '') + '/' + st.session_state.ingestion_result.get('repo_name', '') if st.session_state.ingestion_result and st.session_state.ingestion_result.get('success') else "",
            placeholder="https://github.com/owner/repo",
            help="Repository URL (auto-filled from Phase 1)",
            key="phase2_repo_url"
        )
    
    with col2:
        pr_number = st.number_input(
            "PR Number",
            min_value=1,
            step=1,
            help="Pull request number to review",
            key="phase2_pr_number"
        )
    
    with col3:
        st.write("")  # Spacing
        st.write("")  # Spacing
        fetch_btn = st.button(
            "🚀 Fetch PR",
            disabled=not health_status or st.session_state.is_loading or not pr_repo_url or not pr_number,
            use_container_width=True
        )
    
    github_token = st.text_input(
        "GitHub Token (Optional)",
        type="password",
        placeholder="ghp_xxxxxxxxxxxx",
        help="Leave empty to use configured token from .env",
        key="phase2_token"
    )
    
    # Handle PR fetch
    if fetch_btn and pr_repo_url and pr_number:
        st.session_state.is_loading = True
        st.session_state.pr_fetch_result = None
        
        with st.container():
            st.subheader("📊 PR Fetch Progress")
            
            with st.spinner("Fetching PR data..."):
                result = fetch_pr(pr_repo_url, pr_number, github_token)
                
                st.session_state.pr_fetch_result = result
                st.session_state.is_loading = False
                
                # Display progress steps
                if 'progress' in result:
                    for step in result['progress']:
                        render_progress_step(step)
                
                # Display final result
                st.divider()
                
                if result.get('success'):
                    st.success(f"✅ PR fetched successfully!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Files Changed", result.get('files_changed', 0))
                    with col2:
                        st.metric("Additions", f"+{result.get('additions', 0)}")
                    with col3:
                        st.metric("Deletions", f"-{result.get('deletions', 0)}")
                    
                    st.info(f"**PR Title:** {result.get('pr_title', 'N/A')}")
                    st.info(f"**Author:** {result.get('pr_author', 'N/A')} | **State:** {result.get('pr_state', 'N/A')}")
                    st.info(f"**Review Units:** {result.get('review_units_count', 0)} | **High Priority:** {result.get('high_priority_units_count', 0)}")
                    
                    # Next phase button
                    if st.button("➡️ Proceed to Phase 3-6: Workflow Execution", type="primary", key="phase2_next"):
                        st.session_state.current_phase = 3
                        st.rerun()
                    
                else:
                    st.error(f"❌ PR fetch failed: {result.get('error', 'Unknown error')}")
                    
                    if 'traceback' in result:
                        with st.expander("🔍 Error Details"):
                            st.code(result['traceback'], language='python')
    
    # Show previous result if available
    elif st.session_state.pr_fetch_result:
        st.subheader("📊 Previous PR Fetch Result")
        
        result = st.session_state.pr_fetch_result
        
        if 'progress' in result:
            for step in result['progress']:
                render_progress_step(step)
        
        st.divider()
        
        if result.get('success'):
            st.success(f"✅ PR fetched successfully!")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Files Changed", result.get('files_changed', 0))
            with col2:
                st.metric("Additions", f"+{result.get('additions', 0)}")
            with col3:
                st.metric("Deletions", f"-{result.get('deletions', 0)}")
            
            st.info(f"**PR Title:** {result.get('pr_title', 'N/A')}")
            st.info(f"**Author:** {result.get('pr_author', 'N/A')} | **State:** {result.get('pr_state', 'N/A')}")
            
            # Next phase button
            if st.button("➡️ Proceed to Phase 3-6: Workflow Execution", type="primary", key="phase2_prev_next"):
                st.session_state.current_phase = 3
                st.rerun()
        else:
            st.error(f"❌ PR fetch failed: {result.get('error', 'Unknown error')}")
    
    # Back button
    st.divider()
    if st.button("⬅️ Back to Phase 1"):
        st.session_state.current_phase = 1
        st.rerun()

elif st.session_state.current_phase == 3:
    st.header("⚡ Phase 3-6: Workflow Execution")
    
    st.markdown("""
    <div class="info-box">
        <b>ℹ️ Workflow Execution</b><br>
        This step will run the complete review workflow:
        <ul>
            <li><b>Phase 3:</b> Retrieval - Fetch relevant code context from vector store</li>
            <li><b>Phase 4:</b> Review - Analyze hunks and generate review issues</li>
            <li><b>Phase 4:</b> Planning - Create fix plan from issues</li>
            <li><b>Phase 5:</b> Guardrails - Validate review quality and run safety checks</li>
            <li><b>Phase 5:</b> HITL - Human-in-the-loop approval decision</li>
            <li><b>Phase 6:</b> Publish - Post review to GitHub</li>
            <li><b>Phase 6:</b> Notify - Send Slack notifications</li>
            <li><b>Phase 6:</b> Persist - Save workflow results to disk</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # Show previous phases summary
    if st.session_state.ingestion_result and st.session_state.pr_fetch_result:
        with st.expander("✅ Phase 1-2 Complete", expanded=False):
            ing_result = st.session_state.ingestion_result
            pr_result = st.session_state.pr_fetch_result
            st.write(f"**Repository:** {ing_result.get('repo_id', 'N/A')}")
            st.write(f"**Chunks:** {ing_result.get('chunks_created', 'N/A')}")
            st.write(f"**PR #{pr_result.get('pr_number', 'N/A')}:** {pr_result.get('pr_title', 'N/A')}")
            st.write(f"**Review Units:** {pr_result.get('review_units_count', 0)}")
    
    # Execute button
    execute_btn = st.button(
        "🚀 Execute Workflow",
        disabled=not health_status or st.session_state.is_loading or not st.session_state.pr_fetch_result,
        use_container_width=True,
        type="primary"
    )
    
    # Handle workflow execution
    if execute_btn and st.session_state.pr_fetch_result:
        st.session_state.is_loading = True
        st.session_state.workflow_result = None
        st.session_state.hitl_paused = False
        
        with st.container():
            st.subheader("📊 Workflow Execution Progress")
            
            with st.spinner("Running workflow agents (this may take 2-3 minutes)..."):
                try:
                    pr_result = st.session_state.pr_fetch_result
                    
                    response = requests.post(
                        f"{API_BASE_URL}/execute-workflow",
                        json={
                            "repo_url": pr_result.get("repo_id", ""),
                            "pr_number": pr_result.get("pr_number", 0),
                            "pr_data": pr_result.get("pr_data", {}),
                            "review_units": pr_result.get("review_units", []),
                            "github_token": None,
                            "run_evaluation": False
                        },
                        timeout=300
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        # Check if workflow paused at HITL
                        if result.get('paused_at_hitl'):
                            st.session_state.hitl_paused = True
                            st.session_state.hitl_data = result.get('hitl_data', {})
                            st.session_state.run_id = result.get('run_id')
                            st.session_state.workflow_result = result
                            st.session_state.is_loading = False
                            st.rerun()
                        else:
                            # Workflow completed normally (shouldn't happen with new HITL)
                            st.session_state.workflow_result = result
                            st.session_state.is_loading = False
                        
                        # Display progress steps
                        if 'steps' in result:
                            for step in result['steps']:
                                render_progress_step(step)
                        
                        # Display final result
                        st.divider()
                        
                        if result.get('success'):
                            st.success("✅ Workflow execution complete!")
                            
                            # Metrics
                            final_state = result.get('final_state', {})
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Issues Found", len(final_state.get('review_issues', [])))
                            with col2:
                                st.metric("Fix Tasks", len(final_state.get('fix_tasks', [])))
                            with col3:
                                guardrail = final_state.get('guardrail_result', {})
                                st.metric("Guardrail", "✅ Passed" if guardrail.get('passed') else "❌ Failed")
                            with col4:
                                hitl = final_state.get('hitl_decision')
                                hitl_action = hitl.get('action', 'N/A').upper() if hitl else 'N/A'
                                st.metric("Decision", hitl_action)
                            
                            # Review Issues
                            with st.expander("📋 Review Issues", expanded=True):
                                issues = final_state.get('review_issues', [])
                                if issues:
                                    for i, issue in enumerate(issues):
                                        severity_colors = {
                                            "blocker": "🔴",
                                            "major": "🟠",
                                            "minor": "🟡",
                                            "nit": "⚪"
                                        }
                                        severity_icon = severity_colors.get(issue.get('severity', 'nit'), "⚪")
                                        st.markdown(f"{severity_icon} **{issue.get('category', 'Unknown').upper()}** - {issue.get('file_path', 'Unknown')}:{issue.get('line_number', 0)}")
                                        st.write(f"*{issue.get('explanation', '')}*")
                                        st.code(issue.get('suggestion', ''), language="text")
                                        st.divider()
                                else:
                                    st.info("No issues found!")
                            
                            # Fix Tasks
                            with st.expander("🔧 Fix Plan", expanded=True):
                                tasks = final_state.get('fix_tasks', [])
                                if tasks:
                                    for task in tasks:
                                        effort_colors = {"S": "🟢", "M": "🟡", "L": "🔴"}
                                        effort_icon = effort_colors.get(task.get('effort_estimate', 'M'), "🟡")
                                        st.markdown(f"{effort_icon} **{task.get('title', 'Unknown')}** ({task.get('effort_estimate', 'M')})")
                                        st.write(f"*{task.get('why_it_matters', '')}*")
                                        st.write(f"**Approach:** {task.get('suggested_approach', '')}")
                                        st.write(f"**Files:** {', '.join(task.get('affected_files', []))}")
                                        st.divider()
                                else:
                                    st.info("No fix tasks generated.")
                            
                            # Publish Result
                            if result.get('posted_comment_url'):
                                with st.expander("📢 Publish Result", expanded=False):
                                    st.write(f"**Comment URL:** {result['posted_comment_url']}")
                                    st.write(f"**Notifications Sent:** {'✅ Yes' if result.get('notification_sent') else '❌ No'}")
                                    if result.get('persistence_path'):
                                        st.write(f"**Saved to:** {result['persistence_path']}")
                        else:
                            st.error(f"❌ Workflow execution failed: {result.get('error', 'Unknown error')}")
                            
                            if 'traceback' in result:
                                with st.expander("🔍 Error Details"):
                                    st.code(result['traceback'], language='python')
                    else:
                        st.session_state.is_loading = False
                        st.error(f"❌ Request failed: {response.text}")
                        
                except Exception as e:
                    st.session_state.is_loading = False
                    st.error(f"❌ Error: {str(e)}")
    
    # HITL Decision UI (when workflow paused)
    if st.session_state.hitl_paused and st.session_state.hitl_data:
        st.divider()
        st.subheader("👤 Human-in-the-Loop: Review Decision Required")
        
        result = st.session_state.workflow_result
        hitl_data = st.session_state.hitl_data
        
        # Display progress steps up to HITL
        with st.expander("✅ Workflow Progress (Paused at HITL)", expanded=False):
            if 'steps' in result:
                for step in result['steps']:
                    render_progress_step(step)
        
        # Display review summary
        st.markdown("""
        <div class="info-box">
            <b>⏸️ Workflow Paused</b><br>
            The workflow has completed the review and is waiting for your decision.
            Please review the findings below and choose an action.
        </div>
        """, unsafe_allow_html=True)
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Issues Found", hitl_data.get('issues_count', 0))
        with col2:
            st.metric("Fix Tasks", hitl_data.get('tasks_count', 0))
        with col3:
            guardrails_passed = hitl_data.get('guardrails_passed', True)
            st.metric("Guardrails", "✅ Passed" if guardrails_passed else "❌ Failed")
        
        # Show guardrail warnings if failed
        if not guardrails_passed and hitl_data.get('blocked_reasons'):
            st.warning("**Guardrails Failed:**")
            for reason in hitl_data['blocked_reasons']:
                st.write(f"- {reason}")
        
        # Review Summary (from formatted text)
        with st.expander("📋 Detailed Review Summary", expanded=True):
            summary_text = hitl_data.get('summary', '')
            st.text(summary_text)
        
        # Review Issues
        with st.expander("🐛 Review Issues", expanded=True):
            issues = result.get('review_issues', [])
            if issues:
                for i, issue in enumerate(issues):
                    severity_colors = {"blocker": "🔴", "major": "🟠", "minor": "🟡", "nit": "⚪"}
                    severity_icon = severity_colors.get(issue.get('severity', 'nit'), "⚪")
                    st.markdown(f"{severity_icon} **{issue.get('category', 'Unknown').upper()}** - {issue.get('file_path', 'Unknown')}:{issue.get('line_number', 0)}")
                    st.write(f"*{issue.get('explanation', '')}*")
                    st.code(issue.get('suggestion', ''), language="text")
                    st.divider()
            else:
                st.info("No issues found!")
        
        # Fix Plan
        with st.expander("🔧 Suggested Fix Plan", expanded=True):
            tasks = result.get('fix_tasks', [])
            if tasks:
                for task in tasks:
                    effort_colors = {"S": "🟢", "M": "🟡", "L": "🔴"}
                    effort_icon = effort_colors.get(task.get('effort_estimate', 'M'), "🟡")
                    st.markdown(f"{effort_icon} **{task.get('title', 'Unknown')}** ({task.get('effort_estimate', 'M')})")
                    st.write(f"*{task.get('why_it_matters', '')}*")
                    st.write(f"**Approach:** {task.get('suggested_approach', '')}")
                    st.write(f"**Files:** {', '.join(task.get('affected_files', []))}")
                    st.divider()
            else:
                st.info("No fix tasks generated.")
        
        # Decision Buttons
        st.divider()
        st.subheader("Make Your Decision")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("✅ Approve & Publish", use_container_width=True, type="primary"):
                # Submit decision
                with st.spinner("Resuming workflow with approval..."):
                    response = requests.post(
                        f"{API_BASE_URL}/hitl-decision",
                        json={
                            "run_id": st.session_state.run_id,
                            "action": "approve",
                            "feedback": "Approved by user via web UI"
                        },
                        timeout=120
                    )
                    
                    if response.status_code == 200:
                        final_result = response.json()
                        st.session_state.workflow_result = final_result
                        st.session_state.hitl_paused = False
                        st.session_state.hitl_data = None
                        st.rerun()
                    else:
                        st.error(f"Failed to resume workflow: {response.text}")
        
        with col2:
            if st.button("📝 Edit & Publish", use_container_width=True):
                st.session_state.editing_review = True
        
        with col3:
            if st.button("📄 Summary Only", use_container_width=True):
                with st.spinner("Resuming workflow with summary only..."):
                    response = requests.post(
                        f"{API_BASE_URL}/hitl-decision",
                        json={
                            "run_id": st.session_state.run_id,
                            "action": "post_summary_only",
                            "feedback": "Post summary only"
                        },
                        timeout=120
                    )
                    
                    if response.status_code == 200:
                        final_result = response.json()
                        st.session_state.workflow_result = final_result
                        st.session_state.hitl_paused = False
                        st.session_state.hitl_data = None
                        st.rerun()
                    else:
                        st.error(f"Failed to resume workflow: {response.text}")
        
        with col4:
            if st.button("❌ Reject", use_container_width=True, type="secondary"):
                with st.spinner("Stopping workflow..."):
                    response = requests.post(
                        f"{API_BASE_URL}/hitl-decision",
                        json={
                            "run_id": st.session_state.run_id,
                            "action": "reject",
                            "feedback": "Rejected by user via web UI"
                        },
                        timeout=120
                    )
                    
                    if response.status_code == 200:
                        final_result = response.json()
                        st.session_state.workflow_result = final_result
                        st.session_state.hitl_paused = False
                        st.session_state.hitl_data = None
                        st.info("Workflow rejected and stopped.")
                        st.rerun()
                    else:
                        st.error(f"Failed to resume workflow: {response.text}")
        
        # Edit mode
        if st.session_state.get('editing_review', False):
            st.divider()
            st.subheader("✍️ Edit Review Content")
            
            edited_content = st.text_area(
                "Edit the review content:",
                value=hitl_data.get('summary', ''),
                height=400
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save & Publish", use_container_width=True, type="primary"):
                    with st.spinner("Saving edits and resuming workflow..."):
                        response = requests.post(
                            f"{API_BASE_URL}/hitl-decision",
                            json={
                                "run_id": st.session_state.run_id,
                                "action": "edit",
                                "edited_content": edited_content,
                                "feedback": "User edited the review content"
                            },
                            timeout=120
                        )
                        
                        if response.status_code == 200:
                            final_result = response.json()
                            st.session_state.workflow_result = final_result
                            st.session_state.hitl_paused = False
                            st.session_state.hitl_data = None
                            st.session_state.editing_review = False
                            st.rerun()
                        else:
                            st.error(f"Failed to resume workflow: {response.text}")
            
            with col2:
                if st.button("🚫 Cancel", use_container_width=True):
                    st.session_state.editing_review = False
                    st.rerun()
    
    # Show previous result if available (completed workflow)
    elif st.session_state.workflow_result and not st.session_state.hitl_paused:
        st.subheader("📊 Previous Workflow Result")
        
        result = st.session_state.workflow_result
        
        if 'steps' in result:
            for step in result['steps']:
                render_progress_step(step)
        
        st.divider()
        
        if result.get('success'):
            st.success("✅ Workflow execution complete!")
            
            # Metrics
            final_state = result.get('final_state', {})
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Issues Found", len(final_state.get('review_issues', [])))
            with col2:
                st.metric("Fix Tasks", len(final_state.get('fix_tasks', [])))
            with col3:
                guardrail = final_state.get('guardrail_result', {})
                st.metric("Guardrail", "✅ Passed" if guardrail.get('passed') else "❌ Failed")
            with col4:
                hitl = final_state.get('hitl_decision')
                hitl_action = hitl.get('action', 'N/A').upper() if hitl else 'N/A'
                st.metric("Decision", hitl_action)
            
            # Review Issues
            with st.expander("📋 Review Issues", expanded=True):
                issues = final_state.get('review_issues', [])
                if issues:
                    for i, issue in enumerate(issues):
                        severity_colors = {
                            "blocker": "🔴",
                            "major": "🟠",
                            "minor": "🟡",
                            "nit": "⚪"
                        }
                        severity_icon = severity_colors.get(issue.get('severity', 'nit'), "⚪")
                        st.markdown(f"{severity_icon} **{issue.get('category', 'Unknown').upper()}** - {issue.get('file_path', 'Unknown')}:{issue.get('line_number', 0)}")
                        st.write(f"*{issue.get('explanation', '')}*")
                        st.code(issue.get('suggestion', ''), language="text")
                        st.divider()
                else:
                    st.info("No issues found!")
            
            # Fix Tasks
            with st.expander("🔧 Fix Plan", expanded=True):
                tasks = final_state.get('fix_tasks', [])
                if tasks:
                    for task in tasks:
                        effort_colors = {"S": "🟢", "M": "🟡", "L": "🔴"}
                        effort_icon = effort_colors.get(task.get('effort_estimate', 'M'), "🟡")
                        st.markdown(f"{effort_icon} **{task.get('title', 'Unknown')}** ({task.get('effort_estimate', 'M')})")
                        st.write(f"*{task.get('why_it_matters', '')}*")
                        st.write(f"**Approach:** {task.get('suggested_approach', '')}")
                        st.write(f"**Files:** {', '.join(task.get('affected_files', []))}")
                        st.divider()
                else:
                    st.info("No fix tasks generated.")
            
            # Publish Result
            if result.get('posted_comment_url'):
                with st.expander("📢 Publish Result", expanded=False):
                    st.write(f"**Comment URL:** {result['posted_comment_url']}")
                    st.write(f"**Notifications Sent:** {'✅ Yes' if result.get('notification_sent') else '❌ No'}")
                    if result.get('persistence_path'):
                        st.write(f"**Saved to:** {result['persistence_path']}")
        else:
            st.error(f"❌ Workflow execution failed: {result.get('error', 'Unknown error')}")
    
    # Back button
    st.divider()
    if st.button("⬅️ Back to Phase 2"):
        st.session_state.current_phase = 2
        st.rerun()

else:
    st.header("Invalid Phase")
    st.error("Unknown phase selected")
    if st.button("Reset to Phase 1"):
        st.session_state.current_phase = 1
        st.rerun()

# Footer
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem;">
    <p><b>Repo-Copilot v1.0</b> - Step-by-Step Workflow</p>
    <p>Built with ❤️ using FastAPI, LangGraph, and Streamlit</p>
    <p>Powered by Ollama, Qdrant, and GitHub API</p>
</div>
""", unsafe_allow_html=True)
