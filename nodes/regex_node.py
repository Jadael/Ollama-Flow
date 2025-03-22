import re
from nodes.base_node import OllamaBaseNode

class RegexNode(OllamaBaseNode):
    """A node that applies a regex pattern to its input text"""
    
    # Node identifier and name
    __identifier__ = 'com.ollamaflow.nodes'
    __type__ = 'RegexNode'
    NODE_NAME = 'RegexNode'
    
    def __init__(self):
        super(RegexNode, self).__init__()
        
        # Set node name that will be displayed
        self.set_name('Regex')
        
        # Create input and output ports
        self.add_input('Text')
        self.add_output('Result')
        
        # Create properties
        self.add_text_input('pattern', 'Regex Pattern', r'<think>.*?</think>')
        self.add_text_input('replacement', 'Replacement', '')
        
        operations = ['replace', 'match', 'split', 'findall']
        self.add_combo_menu('operation', 'Operation', items=operations, default='replace')
        
        # Add checkbox properties
        self.add_checkbox('use_dotall', 'Dot Matches Newline', True)
        self.add_checkbox('use_multiline', 'Multiline Mode', False)
        self.add_checkbox('use_ignorecase', 'Ignore Case', False)
        
        # Add preview tab for input and output
        self.add_text_input('input_preview', 'Input Text', '')
        self.add_text_input('result_preview', 'Result', '')
        
        # Set node color
        self.set_color(156, 59, 217)
    
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
            if self.get_property('use_dotall'):
                flags |= re.DOTALL
            if self.get_property('use_multiline'):
                flags |= re.MULTILINE
            if self.get_property('use_ignorecase'):
                flags |= re.IGNORECASE
            
            # Compile the regex pattern
            pattern = re.compile(self.get_property('pattern'), flags)
            
            # Perform the selected operation
            operation = self.get_property('operation')
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
