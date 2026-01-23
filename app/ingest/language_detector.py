"""Language detection from file extensions."""

from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class LanguageInfo:
    """Information about a programming language."""
    name: str
    extensions: List[str]
    category: str  # 'programming', 'markup', 'config', 'documentation'


class LanguageDetector:
    """
    Detects programming language from file extensions.
    
    Supports a wide range of programming languages, markup languages,
    and configuration files.
    """
    
    # Language database mapping extensions to language info
    LANGUAGES: Dict[str, LanguageInfo] = {
        # Python
        'python': LanguageInfo(
            name='Python',
            extensions=['.py', '.pyw', '.pyx', '.pyi'],
            category='programming'
        ),
        
        # JavaScript/TypeScript
        'javascript': LanguageInfo(
            name='JavaScript',
            extensions=['.js', '.mjs', '.cjs', '.jsx'],
            category='programming'
        ),
        'typescript': LanguageInfo(
            name='TypeScript',
            extensions=['.ts', '.tsx', '.mts', '.cts'],
            category='programming'
        ),
        
        # Java
        'java': LanguageInfo(
            name='Java',
            extensions=['.java'],
            category='programming'
        ),
        'kotlin': LanguageInfo(
            name='Kotlin',
            extensions=['.kt', '.kts'],
            category='programming'
        ),
        
        # C/C++
        'c': LanguageInfo(
            name='C',
            extensions=['.c', '.h'],
            category='programming'
        ),
        'cpp': LanguageInfo(
            name='C++',
            extensions=['.cpp', '.cc', '.cxx', '.hpp', '.hh', '.hxx'],
            category='programming'
        ),
        
        # C#
        'csharp': LanguageInfo(
            name='C#',
            extensions=['.cs', '.csx'],
            category='programming'
        ),
        
        # Go
        'go': LanguageInfo(
            name='Go',
            extensions=['.go'],
            category='programming'
        ),
        
        # Rust
        'rust': LanguageInfo(
            name='Rust',
            extensions=['.rs'],
            category='programming'
        ),
        
        # Ruby
        'ruby': LanguageInfo(
            name='Ruby',
            extensions=['.rb', '.rake', '.gemspec'],
            category='programming'
        ),
        
        # PHP
        'php': LanguageInfo(
            name='PHP',
            extensions=['.php', '.phtml', '.php3', '.php4', '.php5', '.phps'],
            category='programming'
        ),
        
        # Swift
        'swift': LanguageInfo(
            name='Swift',
            extensions=['.swift'],
            category='programming'
        ),
        
        # Objective-C
        'objective-c': LanguageInfo(
            name='Objective-C',
            extensions=['.m', '.mm'],
            category='programming'
        ),
        
        # Scala
        'scala': LanguageInfo(
            name='Scala',
            extensions=['.scala', '.sc'],
            category='programming'
        ),
        
        # R
        'r': LanguageInfo(
            name='R',
            extensions=['.r', '.R', '.rmd'],
            category='programming'
        ),
        
        # Shell
        'shell': LanguageInfo(
            name='Shell',
            extensions=['.sh', '.bash', '.zsh', '.fish'],
            category='programming'
        ),
        
        # PowerShell
        'powershell': LanguageInfo(
            name='PowerShell',
            extensions=['.ps1', '.psm1', '.psd1'],
            category='programming'
        ),
        
        # Markup Languages
        'html': LanguageInfo(
            name='HTML',
            extensions=['.html', '.htm', '.xhtml'],
            category='markup'
        ),
        'css': LanguageInfo(
            name='CSS',
            extensions=['.css', '.scss', '.sass', '.less'],
            category='markup'
        ),
        'xml': LanguageInfo(
            name='XML',
            extensions=['.xml', '.xsd', '.xsl', '.xslt'],
            category='markup'
        ),
        'markdown': LanguageInfo(
            name='Markdown',
            extensions=['.md', '.markdown', '.mdown', '.mkd'],
            category='documentation'
        ),
        
        # Data/Config
        'json': LanguageInfo(
            name='JSON',
            extensions=['.json', '.jsonc', '.json5'],
            category='config'
        ),
        'yaml': LanguageInfo(
            name='YAML',
            extensions=['.yaml', '.yml'],
            category='config'
        ),
        'toml': LanguageInfo(
            name='TOML',
            extensions=['.toml'],
            category='config'
        ),
        'ini': LanguageInfo(
            name='INI',
            extensions=['.ini', '.cfg', '.conf'],
            category='config'
        ),
        
        # SQL
        'sql': LanguageInfo(
            name='SQL',
            extensions=['.sql'],
            category='programming'
        ),
        
        # GraphQL
        'graphql': LanguageInfo(
            name='GraphQL',
            extensions=['.graphql', '.gql'],
            category='programming'
        ),
        
        # Solidity
        'solidity': LanguageInfo(
            name='Solidity',
            extensions=['.sol'],
            category='programming'
        ),
        
        # Dart
        'dart': LanguageInfo(
            name='Dart',
            extensions=['.dart'],
            category='programming'
        ),
        
        # Lua
        'lua': LanguageInfo(
            name='Lua',
            extensions=['.lua'],
            category='programming'
        ),
        
        # Perl
        'perl': LanguageInfo(
            name='Perl',
            extensions=['.pl', '.pm', '.perl'],
            category='programming'
        ),
        
        # Haskell
        'haskell': LanguageInfo(
            name='Haskell',
            extensions=['.hs', '.lhs'],
            category='programming'
        ),
        
        # Elixir
        'elixir': LanguageInfo(
            name='Elixir',
            extensions=['.ex', '.exs'],
            category='programming'
        ),
        
        # Clojure
        'clojure': LanguageInfo(
            name='Clojure',
            extensions=['.clj', '.cljs', '.cljc', '.edn'],
            category='programming'
        ),
        
        # Vue
        'vue': LanguageInfo(
            name='Vue',
            extensions=['.vue'],
            category='programming'
        ),
        
        # Svelte
        'svelte': LanguageInfo(
            name='Svelte',
            extensions=['.svelte'],
            category='programming'
        ),
    }
    
    def __init__(self):
        """Initialize the language detector."""
        # Build reverse mapping: extension -> language
        self._ext_to_lang: Dict[str, str] = {}
        for lang_id, lang_info in self.LANGUAGES.items():
            for ext in lang_info.extensions:
                self._ext_to_lang[ext.lower()] = lang_id
    
    def detect_language(self, file_path: Path) -> Optional[str]:
        """
        Detect language from file extension.
        
        Args:
            file_path: Path to the file
        
        Returns:
            Language identifier (e.g., 'python', 'javascript') or None if unknown
        """
        extension = file_path.suffix.lower()
        return self._ext_to_lang.get(extension)
    
    def get_language_info(self, language_id: str) -> Optional[LanguageInfo]:
        """
        Get detailed information about a language.
        
        Args:
            language_id: Language identifier
        
        Returns:
            LanguageInfo object or None if language not found
        """
        return self.LANGUAGES.get(language_id)
    
    def is_code_file(self, file_path: Path) -> bool:
        """
        Check if a file is a code file (programming language).
        
        Args:
            file_path: Path to the file
        
        Returns:
            True if file is a programming language file
        """
        lang_id = self.detect_language(file_path)
        if lang_id:
            lang_info = self.get_language_info(lang_id)
            return lang_info.category == 'programming' if lang_info else False
        return False
    
    def get_language_statistics(self, file_paths: List[Path]) -> Dict[str, int]:
        """
        Get statistics about languages in a list of files.
        
        Args:
            file_paths: List of file paths
        
        Returns:
            Dictionary mapping language names to file counts
        """
        stats: Dict[str, int] = {}
        
        for file_path in file_paths:
            lang_id = self.detect_language(file_path)
            if lang_id:
                lang_info = self.get_language_info(lang_id)
                if lang_info:
                    lang_name = lang_info.name
                    stats[lang_name] = stats.get(lang_name, 0) + 1
            else:
                stats['Unknown'] = stats.get('Unknown', 0) + 1
        
        return dict(sorted(stats.items(), key=lambda x: x[1], reverse=True))
    
    def get_supported_languages(self, category: Optional[str] = None) -> List[str]:
        """
        Get list of supported languages.
        
        Args:
            category: Optional category filter ('programming', 'markup', 'config', 'documentation')
        
        Returns:
            List of language names
        """
        languages = []
        for lang_info in self.LANGUAGES.values():
            if category is None or lang_info.category == category:
                languages.append(lang_info.name)
        return sorted(languages)


def main():
    """Example usage of LanguageDetector."""
    detector = LanguageDetector()
    
    # Example files
    test_files = [
        Path("app/main.py"),
        Path("src/index.ts"),
        Path("lib/utils.js"),
        Path("README.md"),
        Path("config.yaml"),
        Path("styles.css"),
    ]
    
    print("\n✓ Language Detection Examples:")
    for file_path in test_files:
        lang_id = detector.detect_language(file_path)
        if lang_id:
            lang_info = detector.get_language_info(lang_id)
            print(f"  {file_path}: {lang_info.name} ({lang_info.category})")
        else:
            print(f"  {file_path}: Unknown")
    
    # Statistics
    stats = detector.get_language_statistics(test_files)
    print(f"\n✓ Language Statistics:")
    for lang, count in stats.items():
        print(f"  {lang}: {count} file(s)")
    
    # Supported languages
    print(f"\n✓ Supported Programming Languages:")
    prog_langs = detector.get_supported_languages(category='programming')
    print(f"  {', '.join(prog_langs[:15])}...")
    print(f"  Total: {len(prog_langs)} languages")


if __name__ == "__main__":
    main()
