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
        
        # Create the output port
        self.add_output('Text')
        
        # Create property for text content - this should be supported in all NodeGraphQt versions
        self.add_text_input('text', 'Text Content', 'Enter text here...')
        self.add_text_input('status_info', 'Status', 'Ready')
        
        # Set node color
        self.set_color(59, 156, 217)
    
    def set_status(self, status_text):
        """Update status by setting a property that's visible to the user"""
        self.set_property('status_info', status_text)
        # Also call base implementation if it exists
        if hasattr(super(), 'set_status'):
            super().set_status(status_text)
    
    def execute(self):
        """Process the node and return output"""
        text = self.get_property('text')
        self.set_status(f"Outputting {len(text)} characters")
        return {'Text': text}
