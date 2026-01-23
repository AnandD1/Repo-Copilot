"""Tests for language detector."""

import pytest
from pathlib import Path
from app.ingest.language_detector import LanguageDetector


class TestLanguageDetector:
    """Tests for LanguageDetector class."""
    
    def test_detect_python(self):
        """Test Python file detection."""
        detector = LanguageDetector()
        assert detector.detect_language(Path("main.py")) == "python"
        assert detector.detect_language(Path("script.pyw")) == "python"
        assert detector.detect_language(Path("types.pyi")) == "python"
    
    def test_detect_javascript(self):
        """Test JavaScript file detection."""
        detector = LanguageDetector()
        assert detector.detect_language(Path("app.js")) == "javascript"
        assert detector.detect_language(Path("module.mjs")) == "javascript"
        assert detector.detect_language(Path("Component.jsx")) == "javascript"
    
    def test_detect_typescript(self):
        """Test TypeScript file detection."""
        detector = LanguageDetector()
        assert detector.detect_language(Path("app.ts")) == "typescript"
        assert detector.detect_language(Path("Component.tsx")) == "typescript"
    
    def test_detect_unknown(self):
        """Test unknown file detection."""
        detector = LanguageDetector()
        assert detector.detect_language(Path("unknown.xyz")) is None
    
    def test_get_language_info(self):
        """Test getting language information."""
        detector = LanguageDetector()
        lang_info = detector.get_language_info("python")
        
        assert lang_info is not None
        assert lang_info.name == "Python"
        assert lang_info.category == "programming"
        assert ".py" in lang_info.extensions
    
    def test_is_code_file(self):
        """Test code file detection."""
        detector = LanguageDetector()
        
        assert detector.is_code_file(Path("main.py")) is True
        assert detector.is_code_file(Path("app.js")) is True
        assert detector.is_code_file(Path("README.md")) is False
        assert detector.is_code_file(Path("config.json")) is False
    
    def test_get_language_statistics(self):
        """Test language statistics."""
        detector = LanguageDetector()
        
        files = [
            Path("main.py"),
            Path("utils.py"),
            Path("app.js"),
            Path("types.ts"),
            Path("README.md"),
        ]
        
        stats = detector.get_language_statistics(files)
        
        assert stats["Python"] == 2
        assert stats["JavaScript"] == 1
        assert stats["TypeScript"] == 1
        assert stats["Markdown"] == 1
    
    def test_get_supported_languages(self):
        """Test getting supported languages."""
        detector = LanguageDetector()
        
        all_langs = detector.get_supported_languages()
        assert len(all_langs) > 0
        assert "Python" in all_langs
        
        prog_langs = detector.get_supported_languages(category="programming")
        assert "Python" in prog_langs
        assert "HTML" not in prog_langs  # HTML is markup, not programming
    
    def test_case_insensitive(self):
        """Test case-insensitive extension matching."""
        detector = LanguageDetector()
        
        assert detector.detect_language(Path("Main.PY")) == "python"
        assert detector.detect_language(Path("App.JS")) == "javascript"
