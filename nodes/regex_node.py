import re
from nodes.base_node import OllamaBaseNode

class RegexNode(OllamaBaseNode):
    """A node that applies a regex pattern to its input text"""
    
    # Node identifier and type
    __identifier__ = 'com.ollamaflow.nodes'
    __type__ = 'RegexNode'
    
    # Node display name
    NODE_NAME = 'Regex'
    
    # Node category for menu organization
    NODE_CATEGORY = 'Text Processing'
    
    def __init__(self):
        super(RegexNode, self).__init__()
        
        # Set node name that will be displayed
        self.set_name('Regex')
        
        # Create input and output ports
        self.add_input('Text')
        self.add_output('Result')
        
        # Create properties - all as simple text inputs to avoid compatibility issues
        self.add_text_input('pattern', 'Regex Pattern', r'<think>.*?</think>')
        self.add_text_input('replacement', 'Replacement', '')
        
        # Use text input for operation instead of combo menu
        self.add_text_input('operation', 'Operation (replace, match, split, or findall)', 'replace')
        
        # Add flags as text inputs with "true" or "false" values
        self.add_text_input('use_dotall', 'Dot Matches Newline (true/false)', 'true')
        self.add_text_input('use_multiline', 'Multiline Mode (true/false)', 'false')
        self.add_text_input('use_ignorecase', 'Ignore Case (true/false)', 'false')
        
        # Add preview tab for input and output
        self.add_text_input('input_preview', 'Input Text', '')
        self.add_text_input('result_preview', 'Result', '')
        self.add_text_input('status_info', 'Status', 'Ready')
        
        # Set node color
        self.set_color(156, 59, 217)
    
    def set_status(self, status_text):
        """Update status by setting a property that's visible to the user"""
        self.set_property('status_info', status_text)
        # Also call base implementation if it exists
        if hasattr(super(), 'set_status'):
            super().set_status(status_text)
    
    def execute(self):
        """Process the node and return output"""
        # Get input text
        input_text = self.get_input_data('Text')
        
        # Update input preview
        if input_text:
            preview = input_text[:5000] + ('...' if len(input_text) > 5000 else '')
            self.set_property('input_preview', preview)
        
        if not input_text:
            self.set_status("No input text")
            self.set_property('result_preview', '')
            return {"Result": ""}
        
        try:
            # Compile regex flags
            flags = 0
            if self.get_property('use_dotall').lower() == 'true':
                flags |= re.DOTALL
            if self.get_property('use_multiline').lower() == 'true':
                flags |= re.MULTILINE
            if self.get_property('use_ignorecase').lower() == 'true':
                flags |= re.IGNORECASE
            
            # Compile the regex pattern
            pattern = re.compile(self.get_property('pattern'), flags)
            
            # Perform the selected operation
            operation = self.get_property('operation').lower()
            replacement = self.get_property('replacement')
            
            if operation == 'replace':
                result = pattern.sub(replacement, input_text)
            elif operation == 'match':
                match = pattern.search(input_text)
                result = match.group(0) if match else ""
            elif operation == 'split':
                result = "\n".join(pattern.split(input_text))
            elif operation == 'findall':
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
                
            # Update result preview
            if result:
                preview = result[:5000] + ('...' if len(result) > 5000 else '')
                self.set_property('result_preview', preview)
                
            self.set_status("Complete")
            return {"Result": result}
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.set_status(f"Error: {str(e)[:20]}...")
            self.set_property('result_preview', f"Error: {str(e)}")
            return {"Result": ""}
