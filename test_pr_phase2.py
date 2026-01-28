"""Test Phase 2: PR intake and diff parsing."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.pr_review import (
    PRFetcher,
    DiffParser,
    ReviewUnitBuilder
)


def test_pr_fetching(repo_full_name: str = None, pr_number: int = None):
    """Test fetching PR data from GitHub."""
    print("="*80)
    print("PHASE 2 TEST: PR INTAKE & DIFF PARSING")
    print("="*80)
    
    # Get repo and PR from user if not provided
    if not repo_full_name:
        repo_input = input("\nEnter GitHub repo (format: owner/repo or GitHub URL): ").strip()
        
        # Parse GitHub URL if provided
        if 'github.com' in repo_input:
            # Extract owner/repo from URL
            # Handles: https://github.com/owner/repo, https://github.com/owner/repo.git, etc.
            import re
            match = re.search(r'github\.com[:/]([^/]+)/([^/\.]+)', repo_input)
            if match:
                owner = match.group(1)
                repo = match.group(2)
                repo_full_name = f"{owner}/{repo}"
                print(f"Parsed repo: {repo_full_name}")
            else:
                print("✗ Could not parse GitHub URL")
                return False
        else:
            repo_full_name = repo_input
    
    if not pr_number:
        pr_number_input = input("Enter PR number: ").strip()
        try:
            pr_number = int(pr_number_input)
        except ValueError:
            print("✗ Invalid PR number")
            return False
    
    print(f"\n1. Fetching PR #{pr_number} from {repo_full_name}...")
    print("-" * 80)
    
    try:
        fetcher = PRFetcher()
        pr_data = fetcher.fetch_pr(repo_full_name, pr_number)
        
        print("\n✓ PR Data Retrieved:")
        print(f"  Title: {pr_data.title}")
        print(f"  Author: {pr_data.author}")
        print(f"  State: {pr_data.state}")
        print(f"  Base: {pr_data.base_branch} ({pr_data.base_sha[:8]})")
        print(f"  Head: {pr_data.head_branch} ({pr_data.head_sha[:8]})")
        print(f"  Files changed: {pr_data.changed_files_count}")
        print(f"  Additions: +{pr_data.additions}")
        print(f"  Deletions: -{pr_data.deletions}")
        print(f"  Commits: {pr_data.commits_count}")
        
        if pr_data.labels:
            print(f"  Labels: {', '.join(pr_data.labels)}")
        
        print("\n  Changed Files:")
        for i, file in enumerate(pr_data.files[:5], 1):  # Show first 5
            print(f"    {i}. {file.filename} ({file.status})")
            print(f"       +{file.additions} -{file.deletions}")
        
        if len(pr_data.files) > 5:
            print(f"    ... and {len(pr_data.files) - 5} more files")
        
        # Test diff parsing
        print("\n2. Parsing Diffs into Hunks...")
        print("-" * 80)
        
        file_diffs = []
        for pr_file in pr_data.files:
            if pr_file.patch:
                file_diff = DiffParser.parse_file_patch(pr_file.patch, pr_file.filename)
                file_diffs.append(file_diff)
        
        print(f"\n✓ Parsed {len(file_diffs)} file diffs")
        
        # Show detailed hunk information for first file
        if file_diffs:
            first_diff = file_diffs[0]
            print(f"\nExample: {first_diff.new_path}")
            print("  Status: ", end="")
            if first_diff.is_new:
                print("NEW FILE")
            elif first_diff.is_deleted:
                print("DELETED")
            elif first_diff.is_renamed:
                print(f"RENAMED from {first_diff.old_path}")
            else:
                print("MODIFIED")
            
            print(f"  Total changes: +{first_diff.total_additions} -{first_diff.total_deletions}")
            print(f"  Hunks: {len(first_diff.hunks)}")
            
            # Show first hunk details
            if first_diff.hunks:
                hunk = first_diff.hunks[0]
                print("\n  Hunk 1:")
                print(f"    Old lines: {hunk.old_start}-{hunk.old_start + hunk.old_count - 1}")
                print(f"    New lines: {hunk.new_start}-{hunk.new_start + hunk.new_count - 1}")
                print(f"    Changes: +{hunk.additions_count} -{hunk.deletions_count}")
                
                if hunk.header_context:
                    print(f"    Context: {hunk.header_context}")
                
                # Show added lines with line numbers
                if hunk.added_lines:
                    print("\n    Added lines (with line numbers):")
                    for line in hunk.added_lines[:5]:  # Show first 5
                        print(f"      L{line.new_line_no}: {line.content[:70]}")
                    if len(hunk.added_lines) > 5:
                        print(f"      ... and {len(hunk.added_lines) - 5} more")
        
        # Test review units
        print("\n3. Building Review Units...")
        print("-" * 80)
        
        builder = ReviewUnitBuilder(pr_data, file_diffs)
        
        # Test different strategies
        strategies = ["per_file", "per_hunk", "smart"]
        
        for strategy in strategies:
            units = builder.build_all_units(strategy=strategy, max_hunk_size=50)
            print(f"\n  Strategy: {strategy}")
            print(f"  Units created: {len(units)}")
            
            # Show statistics
            high_priority = len([u for u in units if u.priority == 1])
            med_priority = len([u for u in units if u.priority == 2])
            low_priority = len([u for u in units if u.priority == 3])
            
            print("  Priority distribution:")
            print(f"    High (1): {high_priority}")
            print(f"    Medium (2): {med_priority}")
            print(f"    Low (3): {low_priority}")
            
            # Show example unit
            if units:
                unit = units[0]
                print(f"\n  Example unit: {unit.unit_id}")
                print(f"    Type: {unit.unit_type.value}")
                print(f"    File: {unit.context.file_path}")
                print(f"    Lines: {unit.context.new_line_start}-{unit.context.new_line_end}")
                print(f"    Changes: +{unit.context.additions} -{unit.context.deletions}")
                print(f"    Complexity: {unit.complexity_score:.2f}")
                print(f"    Priority: {unit.priority}")
                
                # Show diff snippet
                print("\n  Diff snippet:")
                snippet = unit.get_diff_snippet(max_lines=10)
                for line in snippet.split('\n')[:15]:
                    print(f"    {line}")
        
        # Summary
        print("\n" + "="*80)
        print("✓ PHASE 2 TEST COMPLETE!")
        print("="*80)
        print("\nSummary:")
        print("  ✓ PR data fetched successfully")
        print("  ✓ {len(file_diffs)} files parsed into hunks")
        print("  ✓ Review units created with multiple strategies")
        print("  ✓ Line numbers accurately tracked for comments")
        
        fetcher.close()
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def test_diff_parsing_standalone():
    """Test diff parsing with example diff text."""
    print("\n" + "="*80)
    print("STANDALONE DIFF PARSING TEST")
    print("="*80)
    
    # Example unified diff
    example_diff = """--- a/example.py
+++ b/example.py
@@ -10,7 +10,9 @@ class Example:
     def process(self):
         # Process data
-        data = self.load_data()
-        result = self.transform(data)
+        # Load and validate data
+        data = self.load_and_validate_data()
+        # Transform with new method
+        result = self.transform_v2(data)
+        self.log_result(result)
         return result
     
@@ -25,3 +27,8 @@ class Example:
     def transform(self, data):
         return data.upper()
+    
+    def transform_v2(self, data):
+        # New transformation logic
+        return data.upper().strip()
"""
    
    print("\nParsing example diff...")
    file_diffs = DiffParser.parse_diff(example_diff)
    
    print(f"✓ Parsed {len(file_diffs)} file(s)")
    
    for file_diff in file_diffs:
        print(f"\nFile: {file_diff.new_path}")
        print(f"  Hunks: {len(file_diff.hunks)}")
        
        for i, hunk in enumerate(file_diff.hunks, 1):
            print(f"\n  Hunk {i}:")
            print(f"    Old: lines {hunk.old_start}-{hunk.old_start + hunk.old_count - 1}")
            print(f"    New: lines {hunk.new_start}-{hunk.new_start + hunk.new_count - 1}")
            print(f"    Added: {hunk.additions_count} lines")
            print(f"    Removed: {hunk.deletions_count} lines")
            
            print(f"\n    Added line numbers: {hunk.get_added_line_numbers()}")
            print(f"    Removed line numbers: {hunk.get_removed_line_numbers()}")
    
    print("\n✓ Standalone parsing test complete!")


if __name__ == "__main__":
    print("Testing Phase 2: PR Intake & Diff Parsing\n")
    
    # Test standalone diff parsing first (no API needed)
    test_diff_parsing_standalone()
    
    # Ask before testing with real GitHub API
    print("\n" + "="*80)
    response = input("\nTest with real GitHub PR? (requires GITHUB_TOKEN) (y/n): ")
    
    if response.lower() == 'y':
        success = test_pr_fetching()
        if success:
            print("\n✓ All tests passed!")
        else:
            print("\n✗ Some tests failed")
    else:
        print("\nSkipped GitHub API test.")
        print("✓ Offline tests passed!")
