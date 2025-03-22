"""Node package for Ollama Flow"""

# Import simplified base node instead
from nodes.base_node_simple import OllamaBaseNodeSimple

# For backward compatibility
OllamaBaseNode = OllamaBaseNodeSimple

# Try to import node classes if they exist
try:
    from nodes.static_text_node_simple import StaticTextNode
except ImportError:
    pass

# Export appropriate classes
__all__ = [
    'OllamaBaseNodeSimple',
    'OllamaBaseNode',  # Alias for backward compatibility
    'StaticTextNode'
]
