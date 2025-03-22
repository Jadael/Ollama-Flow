"""Node package for Ollama Flow"""

# Import base node
from nodes.base_node import OllamaBaseNode

# Try to import node classes if they exist
try:
    from nodes.static_text_node import StaticTextNode
except ImportError:
    pass
    
# Add other node imports as needed
try:
    from nodes.prompt_node import PromptNode
except ImportError:
    pass
    
try:
    from nodes.regex_node import RegexNode
except ImportError:
    pass
    
try:
    from nodes.join_node import JoinNode
except ImportError:
    pass

# Export appropriate classes
__all__ = [
    'OllamaBaseNode',
    'StaticTextNode',
    'PromptNode',
    'RegexNode',
    'JoinNode'
]
