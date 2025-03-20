from core.node import Node
from core.socket import NodeSocket
import re

class RegexNode(Node):
    """A node that applies a regex pattern to its input text"""
    node_type = "Regex Processor"
    category = "Core"
    
    # Node dimensions
    default_width = 260
    default_height = 220
    
    # Property definitions
    properties = {
        "pattern": {
            "type": "string",
            "default": r"<think>.*?</think>",
            "ui": {
                "widget": "text_area",
                "label": "Regex Pattern",
                "preview_on_node": True,
                "preview_length": 30,
            }
        },
        "replacement": {
            "type": "string",
            "default": "",
            "ui": {
                "widget": "text_area",
                "label": "Replacement",
                "preview_on_node": True,
                "preview_length": 30,
            }
        },
        "operation": {
            "type": "choice",
            "default": "replace",
            "options": ["replace", "match", "split", "findall"],
            "ui": {
                "widget": "dropdown",
                "label": "Operation",
                "preview_on_node": True,
            }
        },
        "use_dotall": {
            "type": "boolean",
            "default": True,
            "ui": {
                "widget": "checkbox",
                "label": "Dot Matches Newline",
                "preview_on_node": True,
            }
        },
        "use_multiline": {
            "type": "boolean",
            "default": False,
            "ui": {
                "widget": "checkbox",
                "label": "Multiline Mode",
                "preview_on_node": True,
            }
        },
        "use_ignorecase": {
            "type": "boolean",
            "default": False,
            "ui": {
                "widget": "checkbox",
                "label": "Ignore Case",
                "preview_on_node": True,
            }
        }
    }
    
    def init_sockets(self):
        """Initialize the node's input and output sockets"""
        self.inputs.append(NodeSocket(
            self, 
            name="Text", 
            data_type="string", 
            is_input=True
        ))
        self.outputs.append(NodeSocket(
            self, 
            name="Result", 
            data_type="string", 
            is_input=False
        ))
    
    def execute(self):
        """Process the node and return output values"""
        # Get input text
        input_text = self.get_input_value("Text")
        
        if not input_text:
            self.status = "No input text"
            return {"Result": ""}
        
        try:
            # Compile regex flags
            flags = 0
            if self.use_dotall:
                flags |= re.DOTALL
            if self.use_multiline:
                flags |= re.MULTILINE
            if self.use_ignorecase:
                flags |= re.IGNORECASE
            
            # Compile the regex pattern
            pattern = re.compile(self.pattern, flags)
            
            # Perform the selected operation
            if self.operation == "replace":
                result = pattern.sub(self.replacement, input_text)
            elif self.operation == "match":
                match = pattern.search(input_text)
                result = match.group(0) if match else ""
            elif self.operation == "split":
                result = "\n".join(pattern.split(input_text))
            elif self.operation == "findall":
                matches = pattern.findall(input_text)
                # Handle tuple results from capturing groups
                processed_matches = []
                for match in matches:
                    if isinstance(match, tuple):
                        processed_matches.append(" | ".join(match))
                    else:
                        processed_matches.append(match)
                result = "\n".join(processed_matches)
            else:
                result = input_text
                
            self.status = "Complete"
            return {"Result": result}
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status = f"Error: {str(e)[:20]}..."
            return {"Result": ""}
