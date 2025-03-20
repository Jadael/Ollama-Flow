from core.node import Node
from core.socket import NodeSocket

class StaticTextNode(Node):
    """A node that outputs static text"""
    node_type = "Static Text"
    category = "Core"
    
    # Default dimensions - suitable for text content
    default_width = 260
    default_height = 200
    
    # Property definitions
    properties = {
        "text": {
            "type": "string",
            "default": "Enter text here...",
            "ui": {
                "widget": "text_area",
                "label": "Text Content",
                "preview_on_node": True,
                "preview_length": 30,
            }
        }
    }
    
    def init_sockets(self):
        """Initialize the node's input and output sockets"""
        self.outputs.append(NodeSocket(
            self, 
            name="Text", 
            data_type="string", 
            is_input=False
        ))
    
    def execute(self):
        """Process the node and return output values"""
        return {"Text": self.text}
    
    def calculate_min_height(self):
        """Calculate minimum height based on content"""
        # Start with base calculation from parent class
        min_height = super().calculate_min_height()
        
        # Add additional height for text content preview
        text_lines = len(self.text.split("\n"))
        min_preview_height = min(text_lines * 20, 100)  # Max 100px for preview
        
        return max(min_height, min_preview_height + self.header_height + 60)
