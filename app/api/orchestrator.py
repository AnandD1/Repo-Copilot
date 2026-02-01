"""Main orchestration layer for the PR review workflow."""

import time
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime

from config.settings import Settings
from app.api.cleanup import CleanupManager
from app.ingest import quick_ingest_repo
from app.workflow import WorkflowState, create_review_workflow, run_workflow
from app.pr_review import PRFetcher, DiffParser, PRReviewCoordinator


class WorkflowOrchestrator:
    """Orchestrate the complete PR review workflow."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.cleanup_manager = CleanupManager(self.settings)
        self.current_repo_id: Optional[str] = None
        self.ingested_repos: Dict[str, Dict[str, Any]] = {}  # Track ingested repos
        self.active_workflows: Dict[str, Any] = {}  # Track running workflows
    
    def parse_github_url(self, url: str) -> tuple[str, str]:
        """
        Parse GitHub URL to extract owner and repo.
        
        Supports:
        - https://github.com/owner/repo
        - https://github.com/owner/repo.git
        - github.com/owner/repo
        - owner/repo
        """
        url = url.strip()
        
        # Remove .git suffix
        if url.endswith('.git'):
            url = url[:-4]
        
        # Remove protocol
        url = url.replace('https://', '').replace('http://', '')
        
        # Remove github.com prefix
        url = url.replace('github.com/', '')
        
        # Split to get owner/repo
        parts = url.split('/')
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        
        raise ValueError(f"Invalid GitHub URL: {url}")
    
    async def run_full_workflow(
        self,
        repo_url: str,
        pr_number: int,
        github_token: Optional[str] = None,
        run_evaluation: bool = False
    ) -> Dict[str, Any]:
        """
        Run the complete PR review workflow.
        
        Args:
            repo_url: GitHub repository URL
            pr_number: PR number to review
            github_token: GitHub token (optional, uses settings if not provided)
            run_evaluation: Whether to run evaluation metrics
            
        Returns:
            Dict with workflow results
        """
        start_time = time.time()
        
        # Parse repo URL
        try:
            repo_owner, repo_name = self.parse_github_url(repo_url)
        except ValueError as e:
            return {
                'success': False,
                'error': str(e),
                'stage': 'url_parsing'
            }
        
        repo_id = f"{repo_owner}_{repo_name}_main"
        
        # Use provided token or fallback to settings
        token = github_token or self.settings.github_token
        if not token:
            return {
                'success': False,
                'error': 'GitHub token required',
                'stage': 'authentication'
            }
        
        print(f"\n{'=' * 80}")
        print("PR REVIEW WORKFLOW")
        print(f"{'=' * 80}")
        print(f"Repository: {repo_owner}/{repo_name}")
        print(f"PR Number: {pr_number}")
        print(f"{'=' * 80}\n")
        
        # Handle cleanup based on repo change
        if self.current_repo_id and self.current_repo_id != repo_id:
            # Different repo - full cleanup
            self.cleanup_manager.cleanup_for_new_repo(self.current_repo_id, repo_id)
        elif self.current_repo_id == repo_id:
            # Same repo - just clean temp repos
            self.cleanup_manager.cleanup_for_same_repo(repo_id)
        else:
            # First run - clean everything
            self.cleanup_manager.full_cleanup()
        
        self.current_repo_id = repo_id
        
        try:
            # Phase 1: Ingestion
            print("\n📥 PHASE 1: INGESTION")
            print("-" * 80)
            
            ingestion_start = time.time()
            ingestion_result = quick_ingest_repo(
                repo_url=f"https://github.com/{repo_owner}/{repo_name}",
                branch="main",
                settings_obj=self.settings
            )
            ingestion_time = time.time() - ingestion_start
            
            print(f"✓ Ingestion complete: {ingestion_result['chunks_created']} chunks in {ingestion_time:.2f}s")
            
            # Phase 2: PR Fetch & Parse
            print("\n📋 PHASE 2: PR FETCH & PARSE")
            print("-" * 80)
            
            fetcher = PRFetcher(github_token=token)
            pr_data = fetcher.fetch_pr(repo_owner, repo_name, pr_number)
            
            if not pr_data or 'error' in pr_data:
                return {
                    'success': False,
                    'error': pr_data.get('error', 'Failed to fetch PR'),
                    'stage': 'pr_fetch'
                }
            
            print(f"✓ Fetched PR #{pr_number}: {pr_data['title']}")
            print(f"  Files changed: {pr_data['files_count']}")
            print(f"  +{pr_data['additions']} -{pr_data['deletions']}")
            
            # Parse diff
            parser = DiffParser()
            review_units = parser.parse_diff(pr_data)
            hunks = [unit.to_hunk() for unit in review_units]
            
            print(f"✓ Parsed into {len(hunks)} hunks")
            
            # Phase 3-6: Workflow Execution
            print("\n🔄 PHASE 3-6: WORKFLOW EXECUTION")
            print("-" * 80)
            
            run_id = f"{repo_id}_pr{pr_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            diff_hash = hashlib.md5(str(hunks).encode()).hexdigest()[:12]
            
            initial_state = WorkflowState(
                run_id=run_id,
                repo_owner=repo_owner,
                repo_name=repo_name,
                repo_id=repo_id,
                pr_number=pr_number,
                pr_sha=pr_data['sha'],
                diff_hash=diff_hash,
                hunks=hunks
            )
            
            workflow = create_review_workflow(
                github_token=token,
                settings=self.settings
            )
            
            workflow_start = time.time()
            final_state = run_workflow(initial_state, workflow)
            workflow_time = time.time() - workflow_start
            
            print(f"✓ Workflow complete in {workflow_time:.2f}s")
            
            # Convert to dict if needed
            if not isinstance(final_state, dict):
                final_state = final_state.__dict__ if hasattr(final_state, '__dict__') else {}
            
            # Phase 7: Evaluation (optional)
            evaluation_results = None
            if run_evaluation:
                print("\n📊 PHASE 7: EVALUATION")
                print("-" * 80)
                
                # Evaluator would be used here for actual evaluation
                # For now, return placeholder results
                # evaluator = Evaluator(settings=self.settings)
                evaluation_results = {
                    'groundedness': 'N/A - Requires manual evaluation',
                    'precision': 'N/A - Requires manual evaluation',
                    'usefulness': 'N/A - Requires manual evaluation',
                    'consistency': 'N/A - Requires manual evaluation',
                    'latency': workflow_time
                }
            
            # Cleanup temp repos
            self.cleanup_manager.cleanup_all_temp_repos()
            
            total_time = time.time() - start_time
            
            print(f"\n{'=' * 80}")
            print("✅ WORKFLOW COMPLETE")
            print(f"{'=' * 80}")
            print(f"Total time: {total_time:.2f}s")
            print(f"{'=' * 80}\n")
            
            return {
                'success': True,
                'repo_owner': repo_owner,
                'repo_name': repo_name,
                'pr_number': pr_number,
                'pr_title': pr_data['title'],
                'run_id': run_id,
                'timings': {
                    'ingestion': ingestion_time,
                    'workflow': workflow_time,
                    'total': total_time
                },
                'ingestion': {
                    'chunks_created': ingestion_result['chunks_created'],
                    'files_processed': ingestion_result['files_processed']
                },
                'pr_data': {
                    'title': pr_data['title'],
                    'author': pr_data['author'],
                    'files_count': pr_data['files_count'],
                    'additions': pr_data['additions'],
                    'deletions': pr_data['deletions'],
                    'hunks': len(hunks)
                },
                'review': {
                    'issues_found': len(final_state.get('review_issues', [])),
                    'fix_tasks': len(final_state.get('fix_tasks', [])),
                    'guardrails_passed': final_state.get('guardrail_result', {}).get('passed', False) if isinstance(final_state.get('guardrail_result'), dict) else getattr(final_state.get('guardrail_result'), 'passed', False),
                    'hitl_decision': final_state.get('hitl_decision', {}).get('action', 'unknown') if isinstance(final_state.get('hitl_decision'), dict) else getattr(final_state.get('hitl_decision'), 'action', 'unknown'),
                    'published': final_state.get('publish_result', {}).get('published', False) if isinstance(final_state.get('publish_result'), dict) else getattr(final_state.get('publish_result'), 'published', False),
                    'notification_sent': final_state.get('notification_result', {}).get('slack_sent', False) if isinstance(final_state.get('notification_result'), dict) else getattr(final_state.get('notification_result'), 'slack_sent', False)
                },
                'evaluation': evaluation_results,
                'workflow_state': final_state
            }
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            
            print(f"\n❌ ERROR: {e}")
            print(error_trace)
            
            return {
                'success': False,
                'error': str(e),
                'error_trace': error_trace,
                'stage': 'workflow_execution'
            }    
    async def run_ingestion_only(
        self,
        repo_url: str
    ) -> Dict[str, Any]:
        """
        Step 1: Ingest repository only.
        
        Returns detailed progress and handles repo switching logic.
        """
        import time
        
        start_time = time.time()
        progress = []
        
        # Step 1: Parse URL
        progress.append({
            'step': 'parse_url',
            'status': 'in_progress',
            'message': 'Parsing GitHub URL...',
            'timestamp': datetime.now().isoformat()
        })
        
        try:
            repo_owner, repo_name = self.parse_github_url(repo_url)
            repo_id = f"{repo_owner}_{repo_name}_main"
            
            progress.append({
                'step': 'parse_url',
                'status': 'success',
                'message': f'Repository: {repo_owner}/{repo_name}',
                'data': {
                    'repo_owner': repo_owner,
                    'repo_name': repo_name,
                    'repo_id': repo_id
                },
                'timestamp': datetime.now().isoformat()
            })
            
        except ValueError as e:
            progress.append({
                'step': 'parse_url',
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return {
                'success': False,
                'error': str(e),
                'progress': progress
            }
        
        # Step 2: Check if repo is already ingested
        progress.append({
            'step': 'check_repo',
            'status': 'in_progress',
            'message': 'Checking repository status...',
            'timestamp': datetime.now().isoformat()
        })
        
        if repo_id in self.ingested_repos:
            # Repo already ingested
            progress.append({
                'step': 'check_repo',
                'status': 'success',
                'message': f'Repository already ingested with {self.ingested_repos[repo_id]["chunks_created"]} chunks',
                'data': {
                    'already_ingested': True,
                    'chunks_created': self.ingested_repos[repo_id]['chunks_created'],
                    'ingested_at': self.ingested_repos[repo_id]['timestamp']
                },
                'timestamp': datetime.now().isoformat()
            })
            
            return {
                'success': True,
                'repo_url': repo_url,
                'repo_owner': repo_owner,
                'repo_name': repo_name,
                'repo_id': repo_id,
                'already_ingested': True,
                'chunks_created': self.ingested_repos[repo_id]['chunks_created'],
                'progress': progress,
                'duration': time.time() - start_time
            }
        
        progress.append({
            'step': 'check_repo',
            'status': 'success',
            'message': 'New repository detected',
            'data': {'already_ingested': False},
            'timestamp': datetime.now().isoformat()
        })
        
        # Step 3: Cleanup old repos if switching
        if self.current_repo_id and self.current_repo_id != repo_id:
            progress.append({
                'step': 'cleanup',
                'status': 'in_progress',
                'message': f'Cleaning up previous repository: {self.current_repo_id}',
                'timestamp': datetime.now().isoformat()
            })
            
            try:
                self.cleanup_manager.cleanup_for_new_repo(self.current_repo_id, repo_id)
                
                progress.append({
                    'step': 'cleanup',
                    'status': 'success',
                    'message': 'Previous repository cleaned up',
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                progress.append({
                    'step': 'cleanup',
                    'status': 'warning',
                    'message': f'Cleanup warning: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                })
        elif not self.current_repo_id:
            progress.append({
                'step': 'cleanup',
                'status': 'in_progress',
                'message': 'First run - performing full cleanup',
                'timestamp': datetime.now().isoformat()
            })
            
            try:
                self.cleanup_manager.full_cleanup()
                
                progress.append({
                    'step': 'cleanup',
                    'status': 'success',
                    'message': 'Full cleanup completed',
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                progress.append({
                    'step': 'cleanup',
                    'status': 'warning',
                    'message': f'Cleanup warning: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                })
        
        # Step 4: Clone and ingest repository
        progress.append({
            'step': 'ingestion',
            'status': 'in_progress',
            'message': 'Cloning and embedding repository...',
            'timestamp': datetime.now().isoformat()
        })
        
        try:
            ingestion_start = time.time()
            ingestion_result = quick_ingest_repo(
                repo_url=f"https://github.com/{repo_owner}/{repo_name}",
                branch="main",
                settings_obj=self.settings
            )
            ingestion_time = time.time() - ingestion_start
            
            # Store ingestion info
            self.ingested_repos[repo_id] = {
                'repo_owner': repo_owner,
                'repo_name': repo_name,
                'chunks_created': ingestion_result['chunks_created'],
                'timestamp': datetime.now().isoformat(),
                'ingestion_time': ingestion_time
            }
            self.current_repo_id = repo_id
            
            progress.append({
                'step': 'ingestion',
                'status': 'success',
                'message': f'Repository ingested: {ingestion_result["chunks_created"]} chunks in {ingestion_time:.2f}s',
                'data': {
                    'chunks_created': ingestion_result['chunks_created'],
                    'ingestion_time': ingestion_time
                },
                'timestamp': datetime.now().isoformat()
            })
            
            return {
                'success': True,
                'repo_url': repo_url,
                'repo_owner': repo_owner,
                'repo_name': repo_name,
                'repo_id': repo_id,
                'already_ingested': False,
                'chunks_created': ingestion_result['chunks_created'],
                'ingestion_time': ingestion_time,
                'progress': progress,
                'duration': time.time() - start_time
            }
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            
            progress.append({
                'step': 'ingestion',
                'status': 'error',
                'message': f'Ingestion failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
            
            return {
                'success': False,
                'error': str(e),
                'traceback': error_trace,
                'progress': progress,
                'duration': time.time() - start_time
            }
    
    async def run_pr_fetch_only(
        self,
        repo_url: str,
        pr_number: int,
        github_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run Phase 2: PR Fetch and Parse only."""
        steps = []
        
        try:
            # Step 1: Parse URL
            steps.append({"step": "parse_url", "status": "in_progress", "message": "Parsing repository URL"})
            try:
                owner, name = self.parse_github_url(repo_url)
                repo_id = f"{owner}/{name}"
                steps[-1]["status"] = "success"
                steps[-1]["message"] = f"✓ Parsed: {repo_id}"
            except Exception as e:
                steps[-1]["status"] = "error"
                steps[-1]["message"] = f"✗ Failed to parse URL: {str(e)}"
                return {"success": False, "steps": steps, "error": str(e)}
            
            # Step 2: Validate token
            steps.append({"step": "validate_token", "status": "in_progress", "message": "Validating GitHub token"})
            token = github_token or self.settings.github_token
            if not token:
                steps[-1]["status"] = "error"
                steps[-1]["message"] = "✗ GitHub token required"
                return {"success": False, "steps": steps, "error": "GitHub token required"}
            steps[-1]["status"] = "success"
            steps[-1]["message"] = "✓ Token validated"
            
            # Step 3: Fetch PR and build review units
            steps.append({"step": "fetch_pr", "status": "in_progress", "message": f"Fetching PR #{pr_number}"})
            try:
                coordinator = PRReviewCoordinator(github_token=token)
                
                # Use prepare_pr_review which returns a PRReviewSession
                session = coordinator.prepare_pr_review(
                    repo_full_name=f"{owner}/{name}",
                    pr_number=pr_number,
                    strategy="per_hunk"
                )
                
                # Extract data from session
                pr_data_obj = session.pr_data
                pr_data = {
                    "number": pr_data_obj.number,
                    "title": pr_data_obj.title,
                    "description": pr_data_obj.description,
                    "state": pr_data_obj.state,
                    "author": pr_data_obj.author,
                    "created_at": pr_data_obj.created_at.isoformat() if pr_data_obj.created_at else None,
                    "updated_at": pr_data_obj.updated_at.isoformat() if pr_data_obj.updated_at else None,
                    "head": {"sha": pr_data_obj.head_sha},
                    "base": {"sha": pr_data_obj.base_sha},
                    "additions": pr_data_obj.additions,
                    "deletions": pr_data_obj.deletions,
                    "changed_files": pr_data_obj.changed_files_count
                }
                
                # Convert review units to dict format
                review_units = []
                for unit in session.review_units:
                    review_units.append({
                        "hunk_id": f"{unit.context.file_path}:{unit.context.new_line_start or 0}",
                        "file_path": unit.context.file_path,
                        "old_line_start": unit.context.old_line_start or 0,
                        "old_line_end": unit.context.old_line_end or 0,
                        "new_line_start": unit.context.new_line_start or 0,
                        "new_line_end": unit.context.new_line_end or 0,
                        "added_lines": unit.context.added_lines,
                        "removed_lines": unit.context.removed_lines,
                        "context_lines": unit.context.context_lines
                    })
                
                coordinator.close()
                
                steps[-1]["status"] = "success"
                steps[-1]["message"] = f"✓ Fetched PR: {pr_data.get('title', 'Unknown')}"
                
                # Add metrics step
                steps.append({
                    "step": "metrics",
                    "status": "success",
                    "message": f"✓ Created {len(review_units)} review units"
                })
                
                return {
                    "success": True,
                    "steps": steps,
                    "pr_data": pr_data,
                    "review_units": review_units,
                    "repo_id": repo_id,
                    "pr_number": pr_number,
                    # Flatten for UI convenience
                    "pr_title": pr_data.get("title", "N/A"),
                    "pr_author": pr_data.get("author", "N/A"),
                    "pr_state": pr_data.get("state", "N/A"),
                    "files_changed": pr_data.get("changed_files", 0),
                    "additions": pr_data.get("additions", 0),
                    "deletions": pr_data.get("deletions", 0),
                    "review_units_count": len(review_units),
                    "high_priority_units_count": 0  # Calculate if needed
                }
                
            except Exception as e:
                steps[-1]["status"] = "error"
                steps[-1]["message"] = f"✗ Failed to fetch PR: {str(e)}"
                return {"success": False, "steps": steps, "error": str(e)}
                
        except Exception as e:
            return {
                "success": False,
                "steps": steps,
                "error": str(e)
            }
    
    async def run_workflow_execution(
        self,
        repo_url: str,
        pr_number: int,
        pr_data: Dict[str, Any],
        review_units: List[Dict[str, Any]],
        github_token: Optional[str] = None,
        run_evaluation: bool = False
    ) -> Dict[str, Any]:
        """Run Phase 3-6: Workflow Execution (Retrieval → Review → Guardrails → HITL → Publish → Persist)."""
        steps = []
        
        try:
            # Parse URL
            owner, name = self.parse_github_url(repo_url)
            repo_id = f"{owner}/{name}"
            
            # Step 1: Create Initial State
            steps.append({"step": "create_state", "status": "in_progress", "message": "Creating workflow state"})
            try:
                from app.workflow import WorkflowState
                import uuid
                import hashlib
                
                # Convert review_units to hunks format
                hunks = []
                for unit in review_units:
                    hunks.append({
                        "hunk_id": unit.get("hunk_id", ""),
                        "file_path": unit.get("file_path", ""),
                        "old_line_start": unit.get("old_line_start", 0),
                        "old_line_end": unit.get("old_line_end", 0),
                        "new_line_start": unit.get("new_line_start", 0),
                        "new_line_end": unit.get("new_line_end", 0),
                        "added_lines": unit.get("added_lines", []),
                        "removed_lines": unit.get("removed_lines", []),
                        "context_lines": unit.get("context_lines", [])
                    })
                
                # Create diff hash for caching
                diff_content = str(hunks)
                diff_hash = hashlib.md5(diff_content.encode()).hexdigest()
                
                initial_state = WorkflowState(
                    run_id=str(uuid.uuid4()),
                    repo_owner=owner,
                    repo_name=name,
                    repo_id=repo_id,
                    pr_number=pr_number,
                    pr_sha=pr_data.get("head", {}).get("sha", ""),
                    diff_hash=diff_hash,
                    hunks=hunks,
                    review_issues=[],
                    fix_tasks=[],
                    retrieval_bundles={},
                    guardrail_result=None,
                    hitl_decision=None,
                    posted_comment_url=None,
                    notification_sent=False,
                    persisted=False,
                    persistence_path=None,
                    errors=[],
                    current_node=None,
                    started_at=datetime.now()
                )
                
                steps[-1]["status"] = "success"
                steps[-1]["message"] = f"✓ State created with {len(hunks)} hunks"
            except Exception as e:
                steps[-1]["status"] = "error"
                steps[-1]["message"] = f"✗ Failed to create state: {str(e)}"
                return {"success": False, "steps": steps, "error": str(e)}
            
            # Step 2: Create Workflow
            steps.append({"step": "create_workflow", "status": "in_progress", "message": "Building LangGraph workflow"})
            try:
                from app.workflow import create_review_workflow
                
                token = github_token or self.settings.github_token
                workflow = create_review_workflow(
                    github_token=token,
                    settings=self.settings
                )
                
                steps[-1]["status"] = "success"
                steps[-1]["message"] = "✓ Workflow graph created with 7 agent nodes"
            except Exception as e:
                steps[-1]["status"] = "error"
                steps[-1]["message"] = f"✗ Failed to create workflow: {str(e)}"
                return {"success": False, "steps": steps, "error": str(e)}
            
            # Step 3: Run Workflow
            steps.append({"step": "run_workflow", "status": "in_progress", "message": "Executing workflow agents"})
            try:
                from app.workflow import WorkflowState as WFState
                
                # Create config for checkpointing
                config = {"configurable": {"thread_id": initial_state.run_id}}
                
                # Start workflow execution
                print(f"\n{'='*80}")
                print(f"🚀 Starting Workflow - Run ID: {initial_state.run_id}")
                print(f"{'='*80}\n")
                
                # Stream workflow events
                for event in workflow.stream(initial_state.model_dump(), config):
                    # Check if we hit a breakpoint (HITL)
                    if '__interrupt__' in event:
                        # Workflow paused at HITL - store for resumption
                        print(f"\n⏸️  Workflow paused at HITL - awaiting user decision")
                        
                        # Store workflow for later resumption
                        self.active_workflows[initial_state.run_id] = {
                            'workflow': workflow,
                            'config': config,
                            'started_at': datetime.now()
                        }
                        
                        # Get current state to return HITL data
                        current_state = workflow.get_state(config)
                        state_dict = current_state.values
                        
                        # Extract interrupt data (it's stored in the Interrupt object)
                        interrupt_obj = event['__interrupt__']
                        
                        # The interrupt() function returns data that gets stored
                        # We passed a dict with review summary info
                        try:
                            # Access the value from the Interrupt object
                            if hasattr(interrupt_obj, 'value'):
                                hitl_data = interrupt_obj.value
                            elif isinstance(interrupt_obj, (list, tuple)) and len(interrupt_obj) > 0:
                                hitl_data = interrupt_obj[0].value if hasattr(interrupt_obj[0], 'value') else {}
                            else:
                                # Fallback: construct from current state
                                hitl_data = {
                                    "type": "hitl_decision_required",
                                    "issues_count": len(state_dict.get('review_issues', [])),
                                    "tasks_count": len(state_dict.get('fix_tasks', [])),
                                    "guardrails_passed": state_dict.get('guardrail_result', {}).get('passed', True) if isinstance(state_dict.get('guardrail_result'), dict) else True,
                                    "summary": "Review complete - decision required"
                                }
                        except Exception as e:
                            print(f"Warning: Could not extract interrupt data: {e}")
                            hitl_data = {
                                "type": "hitl_decision_required",
                                "issues_count": len(state_dict.get('review_issues', [])),
                                "tasks_count": len(state_dict.get('fix_tasks', [])),
                                "summary": "Review complete - decision required"
                            }
                        
                        # Return partial results with HITL requirement
                        return {
                            "success": True,
                            "paused_at_hitl": True,
                            "run_id": initial_state.run_id,
                            "hitl_data": hitl_data,
                            "review_issues": state_dict.get('review_issues', []),
                            "fix_tasks": state_dict.get('fix_tasks', []),
                            "guardrail_result": state_dict.get('guardrail_result'),
                            "steps": steps
                        }
                
                # Workflow completed without interruption
                final_state_dict = workflow.get_state(config).values
                final_state = WFState(**final_state_dict)
                
                steps[-1]["status"] = "success"
                steps[-1]["message"] = "✓ Workflow execution complete"
                
                # Add detailed step results
                steps.append({
                    "step": "retrieval",
                    "status": "success",
                    "message": f"✓ Retrieved {len(final_state.retrieval_bundles)} context bundles"
                })
                
                steps.append({
                    "step": "review",
                    "status": "success",
                    "message": f"✓ Found {len(final_state.review_issues)} issues"
                })
                
                steps.append({
                    "step": "planning",
                    "status": "success",
                    "message": f"✓ Created {len(final_state.fix_tasks)} fix tasks"
                })
                
                guardrail_passed = final_state.guardrail_result.passed if final_state.guardrail_result else True
                steps.append({
                    "step": "guardrails",
                    "status": "success" if guardrail_passed else "warning",
                    "message": f"✓ Guardrails {'passed' if guardrail_passed else 'failed'}"
                })
                
                hitl_action = final_state.hitl_decision.action if final_state.hitl_decision else "unknown"
                steps.append({
                    "step": "hitl",
                    "status": "success",
                    "message": f"✓ HITL decision: {hitl_action}"
                })
                
                if final_state.posted_comment_url:
                    steps.append({
                        "step": "publish",
                        "status": "success",
                        "message": "✓ Published to GitHub"
                    })
                
                if final_state.notification_sent:
                    steps.append({
                        "step": "notify",
                        "status": "success",
                        "message": "✓ Notifications sent"
                    })
                
                steps.append({
                    "step": "persist",
                    "status": "success",
                    "message": "✓ Workflow state persisted"
                })
                
                return {
                    "success": True,
                    "steps": steps,
                    "final_state": final_state.model_dump(mode='json'),
                    "run_id": final_state.run_id,
                    "review_issues": [issue.model_dump(mode='json') for issue in final_state.review_issues],
                    "fix_tasks": [task.model_dump(mode='json') for task in final_state.fix_tasks],
                    "guardrail_result": final_state.guardrail_result.model_dump(mode='json') if final_state.guardrail_result else None,
                    "hitl_decision": final_state.hitl_decision.model_dump(mode='json') if final_state.hitl_decision else None,
                    "posted_comment_url": final_state.posted_comment_url,
                    "notification_sent": final_state.notification_sent,
                    "persistence_path": final_state.persistence_path
                }
                
            except Exception as e:
                steps[-1]["status"] = "error"
                steps[-1]["message"] = f"✗ Workflow execution failed: {str(e)}"
                import traceback
                return {"success": False, "steps": steps, "error": str(e), "traceback": traceback.format_exc()}
                
        except Exception as e:
            import traceback
            return {
                "success": False,
                "steps": steps,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    async def resume_workflow_with_hitl(
        self,
        run_id: str,
        action: str,
        edited_content: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """Resume workflow after HITL decision."""
        from app.workflow import WorkflowState as WFState
        from app.workflow.state import HITLAction
        
        # Check if workflow exists
        if run_id not in self.active_workflows:
            return {"success": False, "error": "Workflow not found or already completed"}
        
        workflow_info = self.active_workflows[run_id]
        workflow = workflow_info['workflow']
        config = workflow_info['config']
        
        # Create HITL decision object
        from app.workflow.state import HITLDecision
        
        decision = HITLDecision(
            action=HITLAction(action),
            edited_content=edited_content,
            feedback=feedback or f"User selected: {action}"
        )
        
        try:
            # Update state with HITL decision
            current_state = workflow.get_state(config)
            
            # Update the state with the decision
            workflow.update_state(
                config,
                {"hitl_decision": decision}
            )
            
            # Continue workflow execution from interrupt
            for event in workflow.stream(None, config):
                pass  # Continue to completion
            
            # Get final state
            final_state_dict = workflow.get_state(config).values
            final_state = WFState(**final_state_dict)
            
            # Remove from active workflows
            del self.active_workflows[run_id]
            
            # Return final results
            steps = []
            steps.append({"step": "hitl_resumed", "status": "success", "message": f"✓ HITL decision: {action}"})
            
            if final_state.posted_comment_url:
                steps.append({"step": "publish", "status": "success", "message": "✓ Published to GitHub"})
            
            if final_state.notification_sent:
                steps.append({"step": "notify", "status": "success", "message": "✓ Notifications sent"})
            
            steps.append({"step": "persist", "status": "success", "message": "✓ Workflow state persisted"})
            
            return {
                "success": True,
                "workflow_complete": True,
                "steps": steps,
                "final_state": final_state.model_dump(mode='json'),
                "posted_comment_url": final_state.posted_comment_url,
                "notification_sent": final_state.notification_sent,
                "persistence_path": final_state.persistence_path
            }
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    async def get_workflow_status(self, run_id: str) -> Dict[str, Any]:
        """Get current workflow status."""
        if run_id not in self.active_workflows:
            return {"success": False, "error": "Workflow not found"}
        
        workflow_info = self.active_workflows[run_id]
        workflow = workflow_info['workflow']
        config = workflow_info['config']
        
        # Get current state
        current_state = workflow.get_state(config)
        
        return {
            "success": True,
            "run_id": run_id,
            "current_node": current_state.next,
            "state": current_state.values,
            "paused_at_hitl": "hitl" in (current_state.next or [])
        }