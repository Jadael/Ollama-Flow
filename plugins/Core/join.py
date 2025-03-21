from core.node import Node
from core.socket import NodeSocket

class JoinNode(Node):
    """A node that joins multiple inputs with a configurable delimiter"""
    node_type = "Join"
    category = "Core"
    
    # Default dimensions
    default_width = 280
    default_height = 300
    
    # Property definitions
    properties = {
        "delimiter": {
            "type": "string",
            "default": "\n",
            "ui": {
                "widget": "entry",
                "label": "Delimiter",
                "preview_on_node": True,
            }
        },
        "skip_empty": {
            "type": "boolean",
            "default": True,
            "ui": {
                "widget": "checkbox",
                "label": "Skip Empty Inputs",
                "preview_on_node": True,
            }
        },
        "trim_whitespace": {
            "type": "boolean",
            "default": False,
            "ui": {
                "widget": "checkbox",
                "label": "Trim Whitespace",
                "preview_on_node": True,
            }
        }
    }
    
    def init_sockets(self):
        """Initialize input and output sockets"""
        # Create 8 input sockets
        for i in range(8):
            self.inputs.append(NodeSocket(
                self, 
                name=f"Input {i+1}", 
                data_type="string",  # Use string type for compatibility
                is_input=True
            ))
        
        # Create output socket
        self.outputs.append(NodeSocket(
            self, 
            name="Result", 
            data_type="string", 
            is_input=False
        ))
    
    def execute(self):
        """Join all inputs with the delimiter"""
        # Get all input values
        values = []
        for i, socket in enumerate(self.inputs):
            value = self.get_input_value(f"Input {i+1}")
            
            # Convert to string if not None
            if value is not None:
                value_str = str(value)
                
                # Apply trimming if enabled
                if self.trim_whitespace:
                    value_str = value_str.strip()
                
                # Add to values if not skipping empty or if not empty
                if not self.skip_empty or value_str:
                    values.append(value_str)
        
        # Join the values with the delimiter
        result = self.delimiter.join(values)
        
        return {"Result": result}

# Register this as a plugin node
Node.register_node_type(__name__)