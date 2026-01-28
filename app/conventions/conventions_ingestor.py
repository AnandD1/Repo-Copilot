"""Extract conventions from various sources."""

import json
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re


@dataclass
class Convention:
    """A single convention/rule."""
    source: str  # File path or linter name
    category: str  # style, architecture, testing, security, etc.
    rule_id: Optional[str]  # For linters: eslint rule ID, ruff code, etc.
    title: str
    description: str
    example_good: Optional[str] = None
    example_bad: Optional[str] = None
    severity: str = "info"  # error, warning, info
    language: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ConventionsIngestor:
    """Extract conventions from documentation and config files."""
    
    CONVENTION_FILES = {
        "CONTRIBUTING.md", "CONTRIBUTING", 
        "STYLE_GUIDE.md", "STYLEGUIDE.md",
        "CONVENTIONS.md", "BEST_PRACTICES.md",
        "CODE_STANDARDS.md", "DEVELOPMENT.md",
        "ADR", "docs/adr", "docs/architecture"
    }
    
    LINTER_CONFIGS = {
        ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml",
        ".prettierrc", ".prettierrc.js", ".prettierrc.json",
        "ruff.toml", "pyproject.toml",
        ".flake8", "setup.cfg",
        ".black", ".black.toml",
        ".pylintrc", "pylint.toml",
        "tslint.json", ".tslintrc",
        ".rubocop.yml",
        "checkstyle.xml", "pmd.xml",
        ".editorconfig"
    }
    
    def __init__(self, repo_path: Path):
        """Initialize conventions ingestor.
        
        Args:
            repo_path: Path to repository root
        """
        self.repo_path = Path(repo_path)
    
    def extract_all_conventions(self) -> List[Convention]:
        """Extract conventions from all sources.
        
        Returns:
            List of Convention objects
        """
        conventions = []
        
        # Extract from markdown docs
        conventions.extend(self._extract_from_markdown_docs())
        
        # Extract from linter configs
        conventions.extend(self._extract_from_linter_configs())
        
        # Extract from ADR (Architecture Decision Records)
        conventions.extend(self._extract_from_adr())
        
        return conventions
    
    def _extract_from_markdown_docs(self) -> List[Convention]:
        """Extract conventions from markdown documentation files."""
        conventions = []
        
        for file_pattern in self.CONVENTION_FILES:
            matching_files = list(self.repo_path.glob(f"**/{file_pattern}"))
            matching_files.extend(self.repo_path.glob(f"**/{file_pattern}.md"))
            
            for file_path in matching_files:
                if file_path.is_file():
                    conventions.extend(self._parse_markdown_file(file_path))
        
        return conventions
    
    def _parse_markdown_file(self, file_path: Path) -> List[Convention]:
        """Parse markdown file for conventions.
        
        Extracts atomic bullet-point rules and MUST/SHOULD statements.
        """
        conventions = []
        
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception:
            return conventions
        
        # Parse headers with their content
        current_header = "General"
        current_category = "general"
        
        for match in re.finditer(r'^(#{1,3})\s+(.*)$', content, re.MULTILINE):
            header_text = match.group(2).strip()
            current_header = header_text
            category = self._categorize_from_header(header_text)
            if category:
                current_category = category
        
        # Extract bullet points (-, *, 1., etc.)
        bullet_pattern = r'^\s*(?:[-*•]|\d+\.)\s+(.+?)(?=^\s*(?:[-*•]|\d+\.)|^#{1,3}\s|$)'
        for match in re.finditer(bullet_pattern, content, re.MULTILINE | re.DOTALL):
            rule_text = match.group(1).strip()
            
            # Skip if too long (probably not a rule)
            if len(rule_text) > 300:
                continue
            
            # Determine severity from keywords
            severity = "info"
            if any(word in rule_text.upper() for word in ["MUST", "REQUIRED", "SHALL"]):
                severity = "error"
            elif any(word in rule_text.upper() for word in ["SHOULD", "RECOMMENDED"]):
                severity = "warning"
            
            conventions.append(Convention(
                source=str(file_path.relative_to(self.repo_path)),
                category=current_category,
                rule_id=None,
                title=rule_text[:80],  # First 80 chars as title
                description=rule_text,
                severity=severity,
                metadata={"file_type": "markdown", "header": current_header}
            ))
        
        # Extract MUST/SHOULD/DO/DON'T statements
        imperative_pattern = r'\b(MUST|SHOULD|SHALL|DO|DON\'T|AVOID|NEVER|ALWAYS)\b[^.!?]*[.!?]'
        for match in re.finditer(imperative_pattern, content, re.IGNORECASE):
            statement = match.group(0).strip()
            
            if len(statement) > 300 or len(statement) < 10:
                continue
            
            keyword = match.group(1).upper()
            severity = "error" if keyword in ["MUST", "NEVER", "SHALL"] else "warning"
            
            conventions.append(Convention(
                source=str(file_path.relative_to(self.repo_path)),
                category=current_category,
                rule_id=None,
                title=statement[:80],
                description=statement,
                severity=severity,
                metadata={"file_type": "markdown", "type": "imperative"}
            ))
        
        return conventions
    
    def _extract_from_linter_configs(self) -> List[Convention]:
        """Extract rules from linter configuration files."""
        conventions = []
        
        for config_file in self.LINTER_CONFIGS:
            matching_files = list(self.repo_path.glob(f"**/{config_file}"))
            
            for file_path in matching_files:
                if file_path.is_file():
                    conventions.extend(self._parse_linter_config(file_path))
        
        return conventions
    
    def _parse_linter_config(self, file_path: Path) -> List[Convention]:
        """Parse linter configuration file."""
        conventions = []
        file_name = file_path.name
        
        try:
            # ESLint/Prettier JSON configs
            if file_name in ['.eslintrc.json', '.prettierrc.json', 'tslint.json', '.eslintrc', '.prettierrc']:
                conventions.extend(self._parse_json_config(file_path, 'javascript'))
            # ESLint/Prettier JS configs
            elif file_name in ['.eslintrc.js', '.prettierrc.js']:
                conventions.extend(self._parse_js_config(file_path))
            # YAML configs
            elif file_name.endswith('.yml') or file_name.endswith('.yaml'):
                conventions.extend(self._parse_yaml_config(file_path))
            # package.json
            elif file_name == 'package.json':
                conventions.extend(self._parse_package_json(file_path))
            # Python: Ruff/pyproject.toml
            elif 'ruff' in file_name or file_name == 'pyproject.toml':
                conventions.extend(self._parse_ruff_config(file_path))
            # Python: other linters
            elif file_name in ['.flake8', 'setup.cfg', '.pylintrc']:
                conventions.extend(self._parse_python_config(file_path))
            # EditorConfig
            elif file_name == '.editorconfig':
                conventions.extend(self._parse_editorconfig(file_path))
        except Exception:
            pass
        
        return conventions
    
    def _parse_json_config(self, file_path: Path, language: str) -> List[Convention]:
        """Parse JSON linter config."""
        conventions = []
        
        try:
            config = json.loads(file_path.read_text(encoding='utf-8'))
            conventions.extend(self._extract_eslint_rules(config, file_path, language))
            conventions.extend(self._extract_prettier_rules(config, file_path, language))
        except Exception:
            pass
        
        return conventions
    
    def _parse_js_config(self, file_path: Path) -> List[Convention]:
        """Parse JavaScript config files (.eslintrc.js, .prettierrc.js)."""
        conventions = []
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Extract simple key-value exports
            # This is basic - won't handle complex JS logic
            if 'module.exports' in content:
                # Try to find simple rule definitions
                rule_pattern = r'["\']([a-zA-Z0-9-/@]+)["\']\s*:\s*(["\'](?:error|warn|off)["\']|[0-2])'
                for match in re.finditer(rule_pattern, content):
                    rule_id = match.group(1)
                    severity_raw = match.group(2).strip('"\'')
                    
                    severity = self._normalize_eslint_severity(severity_raw)
                    
                    conventions.append(Convention(
                        source=str(file_path.relative_to(self.repo_path)),
                        category="linting",
                        rule_id=rule_id,
                        title=f"ESLint: {rule_id}",
                        description=f"Rule {rule_id} is set to {severity}",
                        severity=severity,
                        language="javascript",
                        metadata={"linter": "eslint"}
                    ))
        except Exception:
            pass
        
        return conventions
    
    def _parse_package_json(self, file_path: Path) -> List[Convention]:
        """Parse package.json for eslintConfig and prettier keys."""
        conventions = []
        
        try:
            config = json.loads(file_path.read_text(encoding='utf-8'))
            
            # ESLint config in package.json
            if 'eslintConfig' in config:
                conventions.extend(self._extract_eslint_rules(
                    config['eslintConfig'], file_path, 'javascript'
                ))
            
            # Prettier config in package.json
            if 'prettier' in config:
                conventions.extend(self._extract_prettier_rules(
                    config['prettier'], file_path, 'javascript'
                ))
        except Exception:
            pass
        
        return conventions
    
    def _extract_eslint_rules(self, config: dict, file_path: Path, language: str) -> List[Convention]:
        """Extract ESLint rules from config object."""
        conventions = []
        
        if 'rules' in config:
            for rule_id, rule_config in config['rules'].items():
                severity_raw = rule_config
                if isinstance(rule_config, list) and rule_config:
                    severity_raw = rule_config[0]
                
                severity = self._normalize_eslint_severity(severity_raw)
                
                conventions.append(Convention(
                    source=str(file_path.relative_to(self.repo_path)),
                    category="linting",
                    rule_id=rule_id,
                    title=f"ESLint: {rule_id}",
                    description=f"Rule {rule_id} configured",
                    severity=severity,
                    language=language,
                    metadata={"linter": "eslint", "config": rule_config}
                ))
        
        return conventions
    
    def _extract_prettier_rules(self, config: dict, file_path: Path, language: str) -> List[Convention]:
        """Extract Prettier rules from config object."""
        conventions = []
        
        prettier_keys = ['printWidth', 'tabWidth', 'semi', 'singleQuote', 'trailingComma', 'arrowParens']
        
        for key, value in config.items():
            if key in prettier_keys or key.startswith('prettier'):
                conventions.append(Convention(
                    source=str(file_path.relative_to(self.repo_path)),
                    category="formatting",
                    rule_id=key,
                    title=f"Prettier: {key}",
                    description=f"{key} = {value}",
                    severity="info",
                    language=language,
                    metadata={"linter": "prettier"}
                ))
        
        return conventions
    
    def _normalize_eslint_severity(self, severity_raw) -> str:
        """Normalize ESLint severity (0/1/2 or off/warn/error) to error/warning/info."""
        if severity_raw in [2, "error"]:
            return "error"
        elif severity_raw in [1, "warn"]:
            return "warning"
        else:  # 0, "off"
            return "info"
    
    def _parse_yaml_config(self, file_path: Path) -> List[Convention]:
        """Parse YAML linter config."""
        conventions = []
        
        try:
            config = yaml.safe_load(file_path.read_text(encoding='utf-8'))
            
            if isinstance(config, dict) and 'rules' in config:
                for rule_id, rule_config in config['rules'].items():
                    conventions.append(Convention(
                        source=str(file_path.relative_to(self.repo_path)),
                        category="linting",
                        rule_id=rule_id,
                        title=f"Linter: {rule_id}",
                        description=f"Rule {rule_id} configuration",
                        severity="warning",
                        metadata={"config": rule_config}
                    ))
        except Exception:
            pass
        
        return conventions
    
    def _parse_ruff_config(self, file_path: Path) -> List[Convention]:
        """Parse Ruff/pyproject.toml configuration using proper TOML parsing."""
        conventions = []
        
        try:
            # Try Python 3.11+ tomllib first, fallback to tomli
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib
                except ImportError:
                    # Fallback to basic regex if no TOML library
                    return self._parse_ruff_config_regex(file_path)
            
            with open(file_path, 'rb') as f:
                config = tomllib.load(f)
            
            # Navigate to tool.ruff section
            ruff_config = config.get('tool', {}).get('ruff', {})
            
            if not ruff_config:
                return conventions
            
            # Extract selected rules
            select_rules = ruff_config.get('select', [])
            for rule in select_rules:
                conventions.append(Convention(
                    source=str(file_path.relative_to(self.repo_path)),
                    category="linting",
                    rule_id=rule,
                    title=f"Ruff: {rule}",
                    description=f"Ruff rule {rule} is enabled",
                    severity="warning",
                    language="python",
                    metadata={"linter": "ruff", "status": "enabled"}
                ))
            
            # Extract ignored rules
            ignore_rules = ruff_config.get('ignore', [])
            for rule in ignore_rules:
                conventions.append(Convention(
                    source=str(file_path.relative_to(self.repo_path)),
                    category="linting",
                    rule_id=rule,
                    title=f"Ruff: {rule} (ignored)",
                    description=f"Ruff rule {rule} is ignored",
                    severity="info",
                    language="python",
                    metadata={"linter": "ruff", "status": "ignored"}
                ))
            
            # Extract line-length
            line_length = ruff_config.get('line-length')
            if line_length:
                conventions.append(Convention(
                    source=str(file_path.relative_to(self.repo_path)),
                    category="formatting",
                    rule_id="line-length",
                    title=f"Ruff: Max line length {line_length}",
                    description=f"Maximum line length: {line_length}",
                    severity="info",
                    language="python",
                    metadata={"linter": "ruff", "value": line_length}
                ))
        except Exception:
            pass
        
        return conventions
    
    def _parse_ruff_config_regex(self, file_path: Path) -> List[Convention]:
        """Fallback regex-based Ruff parsing (less reliable)."""
        conventions = []
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            if '[tool.ruff]' not in content:
                return conventions
            
            # Extract select/ignore with better regex
            select_match = re.search(r'select\s*=\s*\[((?:[^\]]*\n?)*?)\]', content, re.DOTALL)
            ignore_match = re.search(r'ignore\s*=\s*\[((?:[^\]]*\n?)*?)\]', content, re.DOTALL)
            
            if select_match:
                rules = re.findall(r'["\']([A-Z][A-Z0-9]*)["\']', select_match.group(1))
                for rule in rules:
                    conventions.append(Convention(
                        source=str(file_path.relative_to(self.repo_path)),
                        category="linting",
                        rule_id=rule,
                        title=f"Ruff: {rule}",
                        description=f"Ruff rule {rule} is enabled",
                        severity="warning",
                        language="python",
                        metadata={"linter": "ruff", "status": "enabled"}
                    ))
            
            if ignore_match:
                rules = re.findall(r'["\']([A-Z][A-Z0-9]*)["\']', ignore_match.group(1))
                for rule in rules:
                    conventions.append(Convention(
                        source=str(file_path.relative_to(self.repo_path)),
                        category="linting",
                        rule_id=rule,
                        title=f"Ruff: {rule} (ignored)",
                        description=f"Ruff rule {rule} is ignored",
                        severity="info",
                        language="python",
                        metadata={"linter": "ruff", "status": "ignored"}
                    ))
        except Exception:
            pass
        
        return conventions
    
    def _parse_python_config(self, file_path: Path) -> List[Convention]:
        """Parse Python linter configs (.flake8, setup.cfg, .pylintrc)."""
        conventions = []
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Extract max line length
            line_length_match = re.search(r'max[_-]line[_-]length\s*[=:]\s*(\d+)', content)
            if line_length_match:
                conventions.append(Convention(
                    source=str(file_path.relative_to(self.repo_path)),
                    category="formatting",
                    rule_id="line-length",
                    title="Max Line Length",
                    description=f"Maximum line length: {line_length_match.group(1)}",
                    severity="info",
                    language="python",
                    metadata={"value": int(line_length_match.group(1))}
                ))
            
            # Extract ignore/exclude rules
            ignore_match = re.search(r'ignore\s*[=:]\s*([A-Z0-9,\s]+)', content)
            if ignore_match:
                rules = [r.strip() for r in ignore_match.group(1).split(',')]
                for rule in rules:
                    if rule:
                        conventions.append(Convention(
                            source=str(file_path.relative_to(self.repo_path)),
                            category="linting",
                            rule_id=rule,
                            title=f"Ignored: {rule}",
                            description=f"Rule {rule} is ignored",
                            severity="info",
                            language="python",
                            metadata={"status": "ignored"}
                        ))
        except Exception:
            pass
        
        return conventions
    
    def _parse_editorconfig(self, file_path: Path) -> List[Convention]:
        """Parse .editorconfig file."""
        conventions = []
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Extract indent settings
            indent_style = re.search(r'indent_style\s*=\s*(\w+)', content)
            indent_size = re.search(r'indent_size\s*=\s*(\d+)', content)
            
            if indent_style:
                conventions.append(Convention(
                    source=str(file_path.relative_to(self.repo_path)),
                    category="formatting",
                    rule_id="indent-style",
                    title="Indent Style",
                    description=f"Use {indent_style.group(1)} for indentation",
                    severity="info",
                    metadata={"value": indent_style.group(1)}
                ))
            
            if indent_size:
                conventions.append(Convention(
                    source=str(file_path.relative_to(self.repo_path)),
                    category="formatting",
                    rule_id="indent-size",
                    title="Indent Size",
                    description=f"Indent size: {indent_size.group(1)}",
                    severity="info",
                    metadata={"value": int(indent_size.group(1))}
                ))
        except Exception:
            pass
        
        return conventions
    
    def _extract_from_adr(self) -> List[Convention]:
        """Extract conventions from Architecture Decision Records."""
        conventions = []
        
        adr_dirs = [
            self.repo_path / "docs" / "adr",
            self.repo_path / "docs" / "architecture",
            self.repo_path / "ADR",
            self.repo_path / "adr"
        ]
        
        for adr_dir in adr_dirs:
            if adr_dir.exists() and adr_dir.is_dir():
                for adr_file in adr_dir.glob("*.md"):
                    conventions.extend(self._parse_adr_file(adr_file))
        
        return conventions
    
    def _parse_adr_file(self, file_path: Path) -> List[Convention]:
        """Parse single ADR file."""
        conventions = []
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Extract title
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else file_path.stem
            
            # Extract decision section
            decision_match = re.search(r'##\s+Decision\s*\n+(.*?)(?=\n##|$)', content, re.DOTALL | re.IGNORECASE)
            decision = decision_match.group(1).strip() if decision_match else content[:500]
            
            conventions.append(Convention(
                source=str(file_path.relative_to(self.repo_path)),
                category="architecture",
                rule_id=file_path.stem,
                title=title,
                description=decision,
                severity="info",
                metadata={
                    "type": "adr",
                    "file": file_path.name
                }
            ))
        except Exception:
            pass
        
        return conventions
    
    def _categorize_from_header(self, header: str) -> Optional[str]:
        """Categorize convention based on header text."""
        header_lower = header.lower()
        
        if any(word in header_lower for word in ['style', 'format', 'indent', 'naming']):
            return "style"
        elif any(word in header_lower for word in ['test', 'testing', 'spec']):
            return "testing"
        elif any(word in header_lower for word in ['security', 'auth', 'credential']):
            return "security"
        elif any(word in header_lower for word in ['architecture', 'design', 'pattern']):
            return "architecture"
        elif any(word in header_lower for word in ['commit', 'pr', 'review', 'git']):
            return "workflow"
        elif any(word in header_lower for word in ['doc', 'comment', 'readme']):
            return "documentation"
        
        return None
