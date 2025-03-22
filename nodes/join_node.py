from nodes.base_node import OllamaBaseNode

class JoinNode(OllamaBaseNode):
    """A node that joins multiple inputs with a configurable delimiter"""
    
    # Node identifier and name
    __identifier__ = 'com.ollamaflow.nodes'
    __type__ = 'JoinNode'
    NODE_NAME = 'JoinNode'
    
    def __init__(self):
        super(JoinNode, self).__init__()
        
        # Set node name that will be displayed
        self.set_name('Join')
        
        # Create input and output ports
        for i in range(8):
            self.add_input(f'Input {i+1}')
        
        self.add_output('Result')
        
        # Create properties
        self.add_text_input('delimiter', 'Delimiter', '\n')
        self.add_checkbox('skip_empty', 'Skip Empty Inputs', True)
        self.add_checkbox('trim_whitespace', 'Trim Whitespace', False)
        
        # Add preview tab for result
        self.add_text_input('result_preview', 'Joined Result', '')
        
        # Create an input status property for each input to show on the node
        for i in range(8):
            self.add_text_input(f'input_{i+1}_status', f'Input {i+1}', 'Empty')
        
        # Set node color
        self.set_color(59, 217, 147)
    
    def execute(self):
        """Process the node and return output"""
        # Get all input values
        values = []
        empty_count = 0
        
        for i in range(8):
            port_name = f'Input {i+1}'
            value = self.get_input_data(port_name)
            
            # Update input status
            status_prop = f'input_{i+1}_status'
            if value is None:
                self.set_property(status_prop, 'Empty')
                empty_count += 1
            else:
                preview = str(value)[:20]
                if len(str(value)) > 20:
                    preview += "..."
                self.set_property(status_prop, f'Has data: {preview}')
            
            # Convert to string if not None
            if value is not None:
                value_str = str(value)
                
                # Apply trimming if enabled
                if self.get_property('trim_whitespace'):
                    value_str = value_str.strip()
                
                # Add to values if not skipping empty or if not empty
                if not self.get_property('skip_empty') or value_str:
                    values.append(value_str)
        
        # Join the values with the delimiter
        result = self.get_property('delimiter').join(values)
        
        # Update status based on inputs
        if empty_count == 8:
            self.set_status("All inputs empty")
        else:
            self.set_status(f"Complete: {len(values)} inputs joined")
        
        # Update preview
        preview = result[:5000] + ('...' if len(result) > 5000 else '')
        self.set_property('result_preview', preview)
        
        return {"Result": result}
