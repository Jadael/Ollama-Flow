from nodes.base_node_simple import OllamaBaseNodeSimple

class StaticTextNode(OllamaBaseNodeSimple):
    """A node that outputs static text"""
    
    # Node identifier and name
    __identifier__ = 'com.ollamaflow.nodes'
    __type__ = 'StaticTextNode'
    NODE_NAME = 'StaticTextNode'
    
    def __init__(self):
        super(StaticTextNode, self).__init__()
        
        # Set node name that will be displayed
        self.set_name('Static Text')
        
        # Create the output port
        self.add_output('Text')
        
        # Create property for text content
        self.add_text_input('text', 'Text Content', 'Enter text here...')
        
        # Set node color
        self.set_color(59, 156, 217)
    
    def execute(self):
        """Process the node and return output"""
        text = self.get_property('text')
        return {'Text': text}
