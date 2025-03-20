from core.node import Node
from core.socket import NodeSocket

class StaticTextNode(Node):
    """A node that outputs static text"""
    node_type = "Static Text"
    category = "Core"
    
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
    
    # Additional methods
    def contains_point(self, x, y):
        """Check if a point is inside this node"""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.height)
    
    def contains_header(self, x, y):
        """Check if a point is inside this node's header"""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.header_height)
    
    def start_drag(self, x, y):
        """Start dragging the node"""
        self.dragging = True
        self.drag_start_x = x
        self.drag_start_y = y