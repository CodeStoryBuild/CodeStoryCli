from dataclasses import dataclass
from tree_sitter import Node
from tree_sitter_language_pack import get_parser
from pygments.lexers import guess_lexer_for_filename, get_lexer_for_filename
from pygments.util import ClassNotFound
from typing import Optional


@dataclass(frozen=True)
class ParsedFile:
    """Contains the parsed AST root and detected language for a file."""
    root_node: Node
    detected_language: str


class FileParser:
    """Parses files using Tree-sitter after detecting language with Pygments."""
    
    # Mapping from Pygments lexer names to Tree-sitter language names
    LANGUAGE_MAPPING = {
        'python': 'python',
        'python3': 'python',
        'javascript': 'javascript',
        'typescript': 'typescript',
        'java': 'java',
        'c': 'c',
        'cpp': 'cpp',
        'c++': 'cpp',
        'csharp': 'c_sharp',
        'c#': 'c_sharp',
        'go': 'go',
        'rust': 'rust',
        'ruby': 'ruby',
        'php': 'php',
        'swift': 'swift',
        'kotlin': 'kotlin',
        'scala': 'scala',
        'html': 'html',
        'css': 'css',
        'json': 'json',
        'yaml': 'yaml',
        'toml': 'toml',
        'xml': 'xml',
        'bash': 'bash',
        'shell': 'bash',
        'sh': 'bash',
    }
    
    @classmethod
    def parse_file(cls, file_name: str, file_content: str) -> Optional[ParsedFile]:
        """
        Parse a file by detecting its language and creating an AST.
        
        Args:
            file_name: Name of the file (used for language detection)
            file_content: Content of the file to parse
            
        Returns:
            ParsedFile containing the root node and detected language, or None if parsing failed
        """
        # Detect language using Pygments
        detected_language = cls._detect_language(file_name, file_content)
        if not detected_language:
            return None
        
        # Get Tree-sitter parser for the detected language
        try:
            parser = get_parser(detected_language)
        except Exception:
            # If we can't get a parser for this language, return None
            return None
        
        # Parse the content
        try:
            content_bytes = file_content.encode("utf8")
            tree = parser.parse(content_bytes)
            root_node = tree.root_node
            
            return ParsedFile(root_node=root_node, detected_language=detected_language)
        except Exception:
            # If parsing fails, return None
            return None
    
    @classmethod
    def _detect_language(cls, file_name: str, file_content: str) -> Optional[str]:
        """
        Detect the programming language using Pygments.
        
        Args:
            file_name: Name of the file (used for extension-based detection)
            file_content: Content of the file (used as fallback)
            
        Returns:
            Tree-sitter compatible language name, or None if detection failed
        """
        #TODO mix using file_content and file_name
        try:
            # Try to guess lexer based on filename 

            lexer = get_lexer_for_filename(file_name)
            # TODO handle composite lexers | eg language1+language2
            # Map Pygments lexer name to Tree-sitter language name
            return cls._map_lexer_to_language(lexer.name)
        except ClassNotFound:
            # If Pygments can't detect the language, return None
            return None
        
        except Exception:
            # For any other errors, return None
            return None
    
    @classmethod
    def _map_lexer_to_language(cls, lexer_name: str) -> Optional[str]:
        """
        Map a Pygments lexer name to a Tree-sitter language name.
        
        Args:
            lexer_name: The lexer name from Pygments
            
        Returns:
            Tree-sitter compatible language name, or None if no mapping exists
        """
        # Normalize the lexer name
        normalized_name = lexer_name.lower().strip()
        
        # Direct mapping
        if normalized_name in cls.LANGUAGE_MAPPING:
            return cls.LANGUAGE_MAPPING[normalized_name]
        
        # Try some common variations
        if 'python' in normalized_name:
            return 'python'
        elif 'javascript' in normalized_name or 'js' in normalized_name:
            return 'javascript'
        elif 'typescript' in normalized_name or 'ts' in normalized_name:
            return 'typescript'
        elif 'java' in normalized_name and 'javascript' not in normalized_name:
            return 'java'
        elif any(cpp_name in normalized_name for cpp_name in ['c++', 'cpp', 'cxx']):
            return 'cpp'
        elif normalized_name == 'c':
            return 'c'
        
        # If no mapping found, return None
        return None