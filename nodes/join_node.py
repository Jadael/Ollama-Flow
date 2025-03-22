from nodes.base_node import OllamaBaseNode

class JoinNode(OllamaBaseNode):
    """A node that joins multiple inputs with a configurable delimiter"""
    
    # Node identifier and type
    __identifier__ = 'com.ollamaflow.nodes'
    __type__ = 'JoinNode'
    
    # Node display name
    NODE_NAME = 'Join'
    
    # Node category for menu organization
    NODE_CATEGORY = 'Text Processing'
    
    def __init__(self):
        super(JoinNode, self).__init__()
        
        # Set node name that will be displayed
        self.set_name('Join')
        
        # Create numbered input properties - these will automatically create input ports
        for i in range(8):
            self.add_text_input(f'input_{i+1}', f'Input {i+1}', '')
        
        # Create configuration properties - these will automatically create input ports
        self.add_text_input('delimiter', 'Delimiter', '\n')
        self.add_text_input('skip_empty', 'Skip Empty Inputs (true/false)', 'true')
        self.add_text_input('trim_whitespace', 'Trim Whitespace (true/false)', 'false')
        
        # Add output
        self.add_output('Result')
        
        # Add preview tab for result - exclude from auto-inputs
        self.exclude_property_from_input('result_preview')
        self.exclude_property_from_input('status_info')
        self.add_text_input('result_preview', 'Joined Result', '')
        self.add_text_input('status_info', 'Status', 'Ready')
        
        # Set node color
        self.set_color(59, 217, 147)
    
    def execute(self):
        """Process the node and return output"""
        # Get all input values using our new property input system
        values = []
        empty_count = 0
        
        for i in range(8):
            prop_name = f'input_{i+1}'
            value = self.get_property_value(prop_name)
            
            if value is None or value == '':
                empty_count += 1
            else:
                value_str = str(value)
                
                # Apply trimming if enabled
                if self.get_property_value('trim_whitespace').lower() == 'true':
                    value_str = value_str.strip()
                
                # Add to values if not skipping empty or if not empty
                if not self.get_property_value('skip_empty').lower() == 'true' or value_str:
                    values.append(value_str)
        
        # Join the values with the delimiter
        result = self.get_property_value('delimiter').join(values)
        
        # Update status based on inputs
        if empty_count == 8:
            self.set_status("All inputs empty")
        else:
            self.set_status(f"Complete: {len(values)} inputs joined")
        
        # Update preview
        preview = result[:5000] + ('...' if len(result) > 5000 else '')
        self.set_property('result_preview', preview)
        
        return {"Result": result}
