"""Generate synthetic PRs for evaluation."""

from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import random


@dataclass
class SyntheticPR:
    """A synthetic PR for evaluation."""
    pr_id: str
    title: str
    description: str
    file_path: str
    code_before: str
    code_after: str
    expected_issues: List[Dict[str, Any]]
    expected_severity: str
    ground_truth_evidence: List[str]
    category: str
    
    def to_hunk(self) -> Dict[str, Any]:
        """Convert to hunk format for workflow."""
        return {
            'hunk_id': f'hunk_{self.pr_id}',
            'file_path': self.file_path,
            'old_start': 1,
            'new_start': 1,
            'old_lines': len(self.code_before.split('\n')),
            'new_lines': len(self.code_after.split('\n')),
            'changes': f"--- {self.file_path}\n+++ {self.file_path}\n{self._generate_diff()}"
        }
    
    def _generate_diff(self) -> str:
        """Generate diff from before/after code."""
        lines = []
        before_lines = self.code_before.split('\n')
        after_lines = self.code_after.split('\n')
        
        for line in before_lines:
            if line.strip():
                lines.append(f"- {line}")
        
        for line in after_lines:
            if line.strip():
                lines.append(f"+ {line}")
        
        return '\n'.join(lines)


class SyntheticPRGenerator:
    """Generate synthetic PRs for evaluation."""
    
    @staticmethod
    def generate_evaluation_set() -> List[SyntheticPR]:
        """Generate 10 synthetic PRs covering different scenarios."""
        
        prs = [
            # 1. SQL Injection vulnerability
            SyntheticPR(
                pr_id="eval_001",
                title="Add user authentication",
                description="Added login functionality",
                file_path="src/auth/login.py",
                code_before="def login(username, password):\n    return True",
                code_after="def login(username, password):\n    query = f\"SELECT * FROM users WHERE username='{username}' AND password='{password}'\"\n    result = db.execute(query)\n    return result is not None",
                expected_issues=[
                    {
                        "severity": "blocker",
                        "category": "security",
                        "description": "SQL injection vulnerability"
                    }
                ],
                expected_severity="blocker",
                ground_truth_evidence=["OWASP Top 10 - A03:2021 Injection", "CWE-89: SQL Injection"],
                category="security"
            ),
            
            # 2. Missing error handling
            SyntheticPR(
                pr_id="eval_002",
                title="Add file upload feature",
                description="Users can now upload files",
                file_path="src/api/upload.py",
                code_before="def upload_file(file):\n    pass",
                code_after="def upload_file(file):\n    with open(f'/uploads/{file.name}', 'wb') as f:\n        f.write(file.read())\n    return {'status': 'success'}",
                expected_issues=[
                    {
                        "severity": "major",
                        "category": "correctness",
                        "description": "Missing error handling for file operations"
                    }
                ],
                expected_severity="major",
                ground_truth_evidence=["Python Best Practices - Exception Handling"],
                category="correctness"
            ),
            
            # 3. Performance issue - N+1 query
            SyntheticPR(
                pr_id="eval_003",
                title="Display user posts",
                description="Show all user posts on profile page",
                file_path="src/views/profile.py",
                code_before="def get_user_profile(user_id):\n    user = User.query.get(user_id)\n    return user",
                code_after="def get_user_profile(user_id):\n    user = User.query.get(user_id)\n    posts = []\n    for post_id in user.post_ids:\n        post = Post.query.get(post_id)\n        posts.append(post)\n    return {'user': user, 'posts': posts}",
                expected_issues=[
                    {
                        "severity": "major",
                        "category": "performance",
                        "description": "N+1 query problem"
                    }
                ],
                expected_severity="major",
                ground_truth_evidence=["Database Query Optimization", "N+1 Query Problem"],
                category="performance"
            ),
            
            # 4. Style guide violation
            SyntheticPR(
                pr_id="eval_004",
                title="Add utility functions",
                description="Helper functions for data processing",
                file_path="src/utils/helpers.py",
                code_before="",
                code_after="def ProcessData(InputData):\n    result=[]\n    for x in InputData:\n        result.append(x*2)\n    return result",
                expected_issues=[
                    {
                        "severity": "minor",
                        "category": "style",
                        "description": "PEP 8 violations: function naming, variable naming"
                    }
                ],
                expected_severity="minor",
                ground_truth_evidence=["PEP 8 - Python Style Guide"],
                category="style"
            ),
            
            # 5. Missing test coverage
            SyntheticPR(
                pr_id="eval_005",
                title="Add payment processing",
                description="Integrate payment gateway",
                file_path="src/payments/processor.py",
                code_before="",
                code_after="def process_payment(amount, card_number):\n    response = gateway.charge(amount, card_number)\n    if response.success:\n        return {'status': 'charged'}\n    return {'status': 'failed'}",
                expected_issues=[
                    {
                        "severity": "major",
                        "category": "test",
                        "description": "Critical payment logic without tests"
                    }
                ],
                expected_severity="major",
                ground_truth_evidence=["Testing Best Practices", "Test Coverage Requirements"],
                category="test"
            ),
            
            # 6. Hardcoded credentials
            SyntheticPR(
                pr_id="eval_006",
                title="Add database connection",
                description="Connect to production database",
                file_path="src/db/connection.py",
                code_before="",
                code_after="DB_HOST = 'prod-db.example.com'\nDB_USER = 'admin'\nDB_PASS = 'SuperSecret123!'\n\ndef connect():\n    return psycopg2.connect(host=DB_HOST, user=DB_USER, password=DB_PASS)",
                expected_issues=[
                    {
                        "severity": "blocker",
                        "category": "security",
                        "description": "Hardcoded credentials"
                    }
                ],
                expected_severity="blocker",
                ground_truth_evidence=["OWASP - Hardcoded Credentials", "Security Best Practices"],
                category="security"
            ),
            
            # 7. Memory leak potential
            SyntheticPR(
                pr_id="eval_007",
                title="Add caching layer",
                description="Cache user sessions",
                file_path="src/cache/session_cache.py",
                code_before="",
                code_after="cache = {}\n\ndef store_session(user_id, data):\n    cache[user_id] = data\n\ndef get_session(user_id):\n    return cache.get(user_id)",
                expected_issues=[
                    {
                        "severity": "major",
                        "category": "performance",
                        "description": "Unbounded cache can cause memory leak"
                    }
                ],
                expected_severity="major",
                ground_truth_evidence=["Memory Management Best Practices", "Cache Eviction Policies"],
                category="performance"
            ),
            
            # 8. Missing input validation
            SyntheticPR(
                pr_id="eval_008",
                title="Add user registration",
                description="New user signup endpoint",
                file_path="src/api/register.py",
                code_before="",
                code_after="def register_user(email, password):\n    user = User(email=email, password=password)\n    user.save()\n    return {'user_id': user.id}",
                expected_issues=[
                    {
                        "severity": "major",
                        "category": "security",
                        "description": "Missing input validation and password hashing"
                    }
                ],
                expected_severity="major",
                ground_truth_evidence=["Input Validation Best Practices", "Password Hashing Standards"],
                category="security"
            ),
            
            # 9. Clean code (no issues)
            SyntheticPR(
                pr_id="eval_009",
                title="Add logging utility",
                description="Helper for structured logging",
                file_path="src/utils/logger.py",
                code_before="",
                code_after="import logging\n\ndef get_logger(name: str) -> logging.Logger:\n    \"\"\"Get a configured logger instance.\"\"\"\n    logger = logging.getLogger(name)\n    logger.setLevel(logging.INFO)\n    return logger",
                expected_issues=[],
                expected_severity="none",
                ground_truth_evidence=[],
                category="clean"
            ),
            
            # 10. Documentation issue
            SyntheticPR(
                pr_id="eval_010",
                title="Add data export function",
                description="Export data to CSV",
                file_path="src/export/csv_export.py",
                code_before="",
                code_after="def export_to_csv(data, filename):\n    with open(filename, 'w') as f:\n        for row in data:\n            f.write(','.join(map(str, row)) + '\\n')",
                expected_issues=[
                    {
                        "severity": "minor",
                        "category": "docs",
                        "description": "Missing docstring and type hints"
                    }
                ],
                expected_severity="minor",
                ground_truth_evidence=["Python Documentation Standards", "Type Hinting Best Practices"],
                category="docs"
            ),
        ]
        
        return prs
    
    @staticmethod
    def get_pr_by_id(pr_id: str) -> SyntheticPR:
        """Get a specific synthetic PR by ID."""
        prs = SyntheticPRGenerator.generate_evaluation_set()
        for pr in prs:
            if pr.pr_id == pr_id:
                return pr
        raise ValueError(f"PR {pr_id} not found")
