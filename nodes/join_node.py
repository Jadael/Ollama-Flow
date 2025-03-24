from nodes.base_node import OllamaBaseNode

class JoinNode(OllamaBaseNode):
    """A node that joins multiple inputs with a configurable delimiter"""
    
    # Node identifier and type
    __identifier__ = 'com.ollamaflow.nodes'
    __type__ = 'JoinNode'
    
    # Node display name
    NODE_NAME = 'Join'
    
    # Node category for menu organization
    NODE_CATEGORY = 'Basic'
    
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
        # Get all input values
        values = []
        empty_count = 0
        
        # Process inputs in order
        for i in range(8):
            input_num = i + 1
            input_port_name = f'Input {input_num}'
            prop_name = f'input_{input_num}'
            
            # Track if we've found a value for this input
            value_found = False
            
            # Check for direct input connection on this port
            for port in self.input_ports():
                if port.name() == input_port_name and port.connected_ports():
                    # Get data from connected node
                    conn_port = port.connected_ports()[0]
                    conn_node = conn_port.node()
                    
                    # Process the connected node if needed
                    if hasattr(conn_node, 'dirty') and conn_node.dirty and hasattr(conn_node, 'compute'):
                        conn_node.compute()
                    
                    # Get the value from the connected node's output
                    if hasattr(conn_node, 'output_cache'):
                        conn_port_name = conn_port.name()
                        input_value = conn_node.output_cache.get(conn_port_name)
                        
                        if input_value is not None and input_value != '':
                            value_str = str(input_value)
                            
                            # Apply trimming if enabled
                            if self.get_property('trim_whitespace').lower() == 'true':
                                value_str = value_str.strip()
                            
                            # Add to values if not skipping empty or if not empty
                            if not self.get_property('skip_empty').lower() == 'true' or value_str:
                                values.append(value_str)
                                value_found = True
                    
                    break  # Only process the first connected port
            
            # If no value from connection, check the property value
            if not value_found:
                prop_value = self.get_property(prop_name)
                
                if prop_value is None or prop_value == '':
                    empty_count += 1
                else:
                    value_str = str(prop_value)
                    
                    # Apply trimming if enabled
                    if self.get_property('trim_whitespace').lower() == 'true':
                        value_str = value_str.strip()
                    
                    # Add to values if not skipping empty or if not empty
                    if not self.get_property('skip_empty').lower() == 'true' or value_str:
                        values.append(value_str)
                        value_found = True
            
            # Update the empty count if we didn't find a value
            if not value_found:
                empty_count += 1
        
        # Join the values with the delimiter
        delimiter = self.get_property('delimiter')
        result = delimiter.join(values)
        
        # Update status based on inputs
        if empty_count == 8:
            self.set_status("All inputs empty")
        else:
            self.set_status(f"Complete: {len(values)} inputs joined")
        
        # Update preview
        preview = result[:5000] + ('...' if len(result) > 5000 else '')
        self.set_property('result_preview', preview)
        
        return {"Result": result}
