from nodes.base_node import OllamaBaseNode
import re

class SplitNode(OllamaBaseNode):
    """A node that splits input text into multiple outputs based on a delimiter"""
    
    # Node identifier and type
    __identifier__ = 'com.ollamaflow.nodes'
    __type__ = 'SplitNode'
    
    # Node display name
    NODE_NAME = 'Split'
    
    # Node category for menu organization
    NODE_CATEGORY = 'Text Processing'
    
    def __init__(self):
        super(SplitNode, self).__init__()
        
        # Set node name that will be displayed
        self.set_name('Split')
        
        # Create properties - these will automatically create input ports
        self.add_text_input('input_text', 'Input Text', '')
        self.add_text_input('delimiter', 'Delimiter', '\n')
        self.add_text_input('trim_whitespace', 'Trim Whitespace (true/false)', 'false')
        self.add_text_input('max_splits', 'Max Splits (-1 for all)', '-1')
        self.add_text_input('use_regex', 'Use Regex (true/false)', 'false')
        
        # Create output ports - 8 numbered outputs plus an overflow
        for i in range(8):
            self.add_output(f'Output {i+1}')
        self.add_output('Overflow')  # For parts beyond the 8 outputs
        
        # Add preview tab for input and output - exclude from auto-inputs
        self.exclude_property_from_input('input_preview')
        self.exclude_property_from_input('output_preview')
        self.exclude_property_from_input('status_info')
        self.add_text_input('input_preview', 'Input Text', '')
        self.add_text_input('output_preview', 'Split Results', '')
        self.add_text_input('status_info', 'Status', 'Ready')
        
        # Set node color (complementary to JoinNode)
        self.set_color(59, 180, 200)
    
    def execute(self):
        """Process the node and return output"""
        # Get input text using our property input system
        input_text = self.get_property_value('input_text')
        
        # Update input preview
        if input_text:
            preview = input_text[:5000] + ('...' if len(input_text) > 5000 else '')
            self.set_property('input_preview', preview)
        
        if not input_text:
            self.set_status("No input text")
            self.set_property('output_preview', '')
            return {f"Output {i+1}": "" for i in range(8)} | {"Overflow": ""}
        
        try:
            # Get configuration options
            delimiter = self.get_property_value('delimiter')
            use_regex = self.get_property_value('use_regex').lower() == 'true'
            trim_whitespace = self.get_property_value('trim_whitespace').lower() == 'true'
            
            try:
                max_splits = int(self.get_property_value('max_splits'))
            except (ValueError, TypeError):
                max_splits = -1  # Default to all splits
            
            # Split the text
            if use_regex:
                # Use regex pattern as delimiter
                parts = re.split(delimiter, input_text, maxsplit=max_splits if max_splits >= 0 else 0)
            else:
                # Use literal delimiter string
                parts = input_text.split(delimiter, maxsplit=max_splits if max_splits >= 0 else -1)
            
            # Trim whitespace if requested
            if trim_whitespace:
                parts = [part.strip() for part in parts]
            
            # Prepare output dictionary
            output_data = {}
            
            # Assign parts to output ports
            for i in range(min(8, len(parts))):
                output_data[f"Output {i+1}"] = parts[i]
            
            # Fill any unused outputs with empty strings
            for i in range(len(parts), 8):
                output_data[f"Output {i+1}"] = ""
            
            # Handle overflow - join any remaining parts with the delimiter
            if len(parts) > 8:
                overflow_parts = parts[8:]
                if use_regex:
                    # For regex, we don't have the original delimiters, so use a space
                    overflow_text = " ".join(overflow_parts)
                else:
                    overflow_text = delimiter.join(overflow_parts)
                output_data["Overflow"] = overflow_text
            else:
                output_data["Overflow"] = ""
            
            # Update output preview
            preview_text = []
            for i in range(min(8, len(parts))):
                part_preview = parts[i][:500] + ('...' if len(parts[i]) > 500 else '')
                preview_text.append(f"Output {i+1}: {part_preview}")
            
            if len(parts) > 8:
                overflow_count = len(parts) - 8
                preview_text.append(f"Overflow: {overflow_count} more part(s)")
            
            self.set_property('output_preview', '\n\n'.join(preview_text))
            
            # Update status
            if len(parts) <= 8:
                self.set_status(f"Split into {len(parts)} part(s)")
            else:
                self.set_status(f"Split into {len(parts)} part(s) (8 outputs + overflow)")
            
            return output_data
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.set_status(f"Error: {str(e)[:20]}...")
            self.set_property('output_preview', f"Error: {str(e)}")
            return {f"Output {i+1}": "" for i in range(8)} | {"Overflow": ""}
