"""Streamlit UI for Repo-Copilot PR Review System."""

import streamlit as st
import requests
import json
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
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #667eea;
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
    .stButton>button {
        width: 100%;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem;
        font-size: 1rem;
        font-weight: bold;
        border-radius: 0.5rem;
    }
    .stButton>button:hover {
        background: linear-gradient(90deg, #764ba2 0%, #667eea 100%);
    }
</style>
""", unsafe_allow_html=True)

# API Configuration
API_BASE_URL = "http://localhost:8000/api/v1"

# Initialize session state
if 'review_result' not in st.session_state:
    st.session_state.review_result = None
if 'is_loading' not in st.session_state:
    st.session_state.is_loading = False


def check_api_health():
    """Check if API is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200, response.json()
    except:
        return False, None


def run_pr_review(repo_url, pr_number, github_token, run_evaluation):
    """Call API to run PR review."""
    try:
        payload = {
            "repo_url": repo_url,
            "pr_number": pr_number,
            "github_token": github_token if github_token else None,
            "run_evaluation": run_evaluation
        }
        
        response = requests.post(
            f"{API_BASE_URL}/review",
            json=payload,
            timeout=600  # 10 minutes timeout
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
        st.success("✅ API Running")
        if health_data:
            with st.expander("Service Details"):
                for service, status in health_data.get('services', {}).items():
                    st.text(f"{service}: {status}")
    else:
        st.error("❌ API Not Running")
        st.warning("Start the API server:\n```bash\nuvicorn app.main:app --reload\n```")
    
    st.divider()
    
    # Settings
    st.subheader("🔧 Settings")
    
    run_evaluation = st.checkbox(
        "Run Evaluation Metrics",
        value=False,
        help="Calculate groundedness, precision, usefulness, etc."
    )
    
    st.divider()
    
    # Cleanup
    st.subheader("🧹 Cleanup")
    if st.button("🗑️ Clear All Resources"):
        with st.spinner("Cleaning up..."):
            result = cleanup_resources()
            if result.get('status') == 'success':
                st.success("✓ Cleanup complete")
            else:
                st.error(f"Cleanup failed: {result.get('message')}")

# Main Content
tab1, tab2 = st.tabs(["📝 New Review", "📊 Results"])

with tab1:
    st.header("Start PR Review")
    
    # Input form
    col1, col2 = st.columns([2, 1])
    
    with col1:
        repo_url = st.text_input(
            "Repository URL",
            placeholder="https://github.com/owner/repo or owner/repo",
            help="GitHub repository URL or owner/repo format"
        )
    
    with col2:
        pr_number = st.number_input(
            "PR Number",
            min_value=1,
            value=1,
            step=1,
            help="Pull request number to review"
        )
    
    github_token = st.text_input(
        "GitHub Token (Optional)",
        type="password",
        placeholder="ghp_xxxxxxxxxxxx",
        help="Leave empty to use configured token from .env"
    )
    
    st.divider()
    
    # Info box
    st.markdown("""
    <div class="info-box">
        <b>ℹ️ How it works:</b>
        <ol>
            <li><b>Ingestion</b> - Clone and embed repository code</li>
            <li><b>Retrieval</b> - Find relevant context for PR changes</li>
            <li><b>Review</b> - AI agents analyze code quality, security, performance</li>
            <li><b>Guardrails</b> - Validate review output quality</li>
            <li><b>HITL</b> - Human-in-the-loop approval (auto for demo)</li>
            <li><b>Publish</b> - Post GitHub comments & Slack notifications</li>
            <li><b>Evaluation</b> - Calculate quality metrics (optional)</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)
    
    # Submit button
    if st.button("🚀 Start Review", disabled=not health_status or st.session_state.is_loading):
        if not repo_url:
            st.error("Please enter a repository URL")
        elif not pr_number:
            st.error("Please enter a PR number")
        else:
            st.session_state.is_loading = True
            
            # Progress indicators
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            stages = [
                "🔍 Parsing repository URL...",
                "📥 Ingesting repository...",
                "📋 Fetching PR data...",
                "🔄 Running workflow...",
                "✅ Finalizing..."
            ]
            
            # Simulate progress (actual progress from API would be better)
            for i, stage in enumerate(stages):
                status_text.text(stage)
                progress_bar.progress((i + 1) * 20)
                
                if i == 3:  # Actually call API during workflow stage
                    result = run_pr_review(repo_url, pr_number, github_token, run_evaluation)
                    st.session_state.review_result = result
                else:
                    time.sleep(0.5)
            
            progress_bar.progress(100)
            status_text.text("✅ Review complete!")
            
            st.session_state.is_loading = False
            
            # Auto-switch to results tab
            st.success("✅ Review complete! Check the Results tab.")

with tab2:
    st.header("Review Results")
    
    if st.session_state.review_result is None:
        st.info("👈 Start a new review to see results here")
    else:
        result = st.session_state.review_result
        
        if result.get('success'):
            data = result.get('data', {})
            
            # Success message
            st.markdown(f"""
            <div class="success-box">
                <h3>✅ Review Complete!</h3>
                <p><b>Repository:</b> {data.get('repo_owner')}/{data.get('repo_name')}</p>
                <p><b>PR #{data.get('pr_number')}:</b> {data.get('pr_title')}</p>
                <p><b>Run ID:</b> {data.get('run_id')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Metrics
            st.subheader("📊 Key Metrics")
            
            col1, col2, col3, col4 = st.columns(4)
            
            pr_data = data.get('pr_data', {})
            review = data.get('review', {})
            timings = data.get('timings', {})
            
            with col1:
                st.metric("Files Changed", pr_data.get('files_count', 0))
                st.metric("Hunks Analyzed", pr_data.get('hunks', 0))
            
            with col2:
                st.metric("Issues Found", review.get('issues_found', 0))
                st.metric("Fix Tasks", review.get('fix_tasks', 0))
            
            with col3:
                guardrails = "✅ Passed" if review.get('guardrails_passed') else "❌ Failed"
                st.metric("Guardrails", guardrails)
                st.metric("HITL Decision", review.get('hitl_decision', 'N/A'))
            
            with col4:
                published = "✅ Yes" if review.get('published') else "❌ No"
                st.metric("Published", published)
                notification = "✅ Yes" if review.get('notification_sent') else "❌ No"
                st.metric("Slack Sent", notification)
            
            st.divider()
            
            # Timing breakdown
            st.subheader("⏱️ Performance")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Ingestion Time", f"{timings.get('ingestion', 0):.2f}s")
            
            with col2:
                st.metric("Workflow Time", f"{timings.get('workflow', 0):.2f}s")
            
            with col3:
                total_time = timings.get('total', 0)
                st.metric("Total Time", f"{total_time:.2f}s")
                
                if total_time < 60:
                    st.success("✅ Within target (<60s)")
                else:
                    st.warning(f"⚠️ Above target ({total_time:.2f}s > 60s)")
            
            st.divider()
            
            # Ingestion details
            st.subheader("📥 Ingestion Details")
            ingestion = data.get('ingestion', {})
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Files Processed", ingestion.get('files_processed', 0))
            with col2:
                st.metric("Chunks Created", ingestion.get('chunks_created', 0))
            
            # Evaluation (if available)
            if data.get('evaluation'):
                st.divider()
                st.subheader("📈 Evaluation Metrics")
                
                eval_data = data.get('evaluation', {})
                
                if isinstance(eval_data, dict) and 'latency' in eval_data:
                    st.info("ℹ️ Full evaluation requires manual assessment. Only latency available for now.")
                    st.metric("Latency", f"{eval_data.get('latency', 0):.2f}s")
            
            st.divider()
            
            # Raw response
            with st.expander("🔍 View Full Response"):
                st.json(result)
        
        else:
            # Error message
            error = result.get('error', 'Unknown error')
            stage = result.get('stage', 'unknown')
            
            st.markdown(f"""
            <div class="error-box">
                <h3>❌ Review Failed</h3>
                <p><b>Stage:</b> {stage}</p>
                <p><b>Error:</b> {error}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if result.get('error_trace'):
                with st.expander("🐛 Error Trace"):
                    st.code(result['error_trace'])

# Footer
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem;">
    <p>Built with ❤️ using FastAPI, LangGraph, and Streamlit</p>
    <p>Powered by Ollama, Qdrant, and GitHub API</p>
</div>
""", unsafe_allow_html=True)
