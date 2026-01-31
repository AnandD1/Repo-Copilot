"""Main orchestration layer for the PR review workflow."""

import time
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime

from config.settings import Settings
from app.api.cleanup import CleanupManager
from app.ingest import quick_ingest_repo
from app.workflow import WorkflowState, create_review_workflow, run_workflow
from app.pr_review import PRFetcher, DiffParser, PRReviewCoordinator
from app.evaluation import Evaluator


class WorkflowOrchestrator:
    """Orchestrate the complete PR review workflow."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.cleanup_manager = CleanupManager(self.settings)
        self.current_repo_id: Optional[str] = None
        self.ingested_repos: Dict[str, Dict[str, Any]] = {}  # Track ingested repos
    
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
                
                evaluator = Evaluator(settings=self.settings)
                # Get evaluation metrics (simplified for now)
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
            'message': f'Cloning and embedding repository...',
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
        """
        Step 2: Fetch and parse PR only.
        
        Returns detailed progress for PR fetching and parsing.
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
            repo_full_name = f"{repo_owner}/{repo_name}"
            
            progress.append({
                'step': 'parse_url',
                'status': 'success',
                'message': f'Repository: {repo_owner}/{repo_name}',
                'data': {
                    'repo_owner': repo_owner,
                    'repo_name': repo_name,
                    'repo_full_name': repo_full_name
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
        
        # Step 2: Validate token
        progress.append({
            'step': 'validate_token',
            'status': 'in_progress',
            'message': 'Validating GitHub token...',
            'timestamp': datetime.now().isoformat()
        })
        
        token = github_token or self.settings.github_token
        if not token:
            progress.append({
                'step': 'validate_token',
                'status': 'error',
                'message': 'GitHub token required',
                'timestamp': datetime.now().isoformat()
            })
            return {
                'success': False,
                'error': 'GitHub token required',
                'progress': progress
            }
        
        progress.append({
            'step': 'validate_token',
            'status': 'success',
            'message': 'GitHub token validated',
            'timestamp': datetime.now().isoformat()
        })
        
        # Step 3: Fetch PR data
        progress.append({
            'step': 'fetch_pr',
            'status': 'in_progress',
            'message': f'Fetching PR #{pr_number} from GitHub...',
            'timestamp': datetime.now().isoformat()
        })
        
        try:
            coordinator = PRReviewCoordinator(github_token=token)
            
            fetch_start = time.time()
            session = coordinator.prepare_pr_review(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                strategy="per_hunk"
            )
            fetch_time = time.time() - fetch_start
            
            coordinator.close()
            
            progress.append({
                'step': 'fetch_pr',
                'status': 'success',
                'message': f'PR fetched and parsed: {session.pr_data.title}',
                'data': {
                    'pr_title': session.pr_data.title,
                    'pr_state': session.pr_data.state,
                    'pr_author': session.pr_data.author,
                    'files_changed': len(session.file_diffs),
                    'additions': session.pr_data.additions,
                    'deletions': session.pr_data.deletions,
                    'review_units': len(session.review_units),
                    'high_priority_units': len(session.high_priority_units),
                    'fetch_time': fetch_time
                },
                'timestamp': datetime.now().isoformat()
            })
            
            return {
                'success': True,
                'repo_owner': repo_owner,
                'repo_name': repo_name,
                'repo_full_name': repo_full_name,
                'pr_number': pr_number,
                'pr_title': session.pr_data.title,
                'pr_state': session.pr_data.state,
                'pr_author': session.pr_data.author,
                'files_changed': len(session.file_diffs),
                'additions': session.pr_data.additions,
                'deletions': session.pr_data.deletions,
                'review_units_count': len(session.review_units),
                'high_priority_units_count': len(session.high_priority_units),
                'fetch_time': fetch_time,
                'progress': progress,
                'duration': time.time() - start_time
            }
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            
            progress.append({
                'step': 'fetch_pr',
                'status': 'error',
                'message': f'PR fetch failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
            
            return {
                'success': False,
                'error': str(e),
                'traceback': error_trace,
                'progress': progress,
                'duration': time.time() - start_time
            }