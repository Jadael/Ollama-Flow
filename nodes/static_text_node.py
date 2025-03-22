# ============= Modified static_text_node.py file ==============
from nodes.base_node import OllamaBaseNode

class StaticTextNode(OllamaBaseNode):
    """A node that outputs static text"""
    
    # Node identifier and type
    __identifier__ = 'com.ollamaflow.nodes'
    __type__ = 'StaticTextNode'
    
    # Node display name
    NODE_NAME = 'Static Text'
    
    # Node category for menu organization
    NODE_CATEGORY = 'Input'
    
    def __init__(self):
        super(StaticTextNode, self).__init__()
        
        # Set node name that will be displayed
        self.set_name('Static Text')
        
        # Initialize these properties first to avoid errors
        self._excluded_input_props = set()
        self.exclude_property_from_input('status_info')
        
        # Create property for text content - this will automatically create an input
        self.add_text_input('text', 'Text Content', 'Enter text here...')
        
        # Add status property
        self.add_text_input('status_info', 'Status', 'Ready')
        
        # Create the output port
        self.add_output('Text')
        
        # Set node color
        self.set_color(59, 156, 217)
    
    def execute(self):
        """Process the node and return output"""
        # Get the text using the new property input system
        text = self.get_property_value('text')
        self.set_status(f"Outputting {len(text)} characters")
        return {'Text': text}
