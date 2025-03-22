import os
from nodes.base_node import OllamaBaseNode

class TextFileNode(OllamaBaseNode):
    """A node that loads and saves text files"""
    
    # Node identifier and type
    __identifier__ = 'com.ollamaflow.nodes'
    __type__ = 'TextFileNode'
    
    # Node display name
    NODE_NAME = 'Text File'
    
    # Node category for menu organization
    NODE_CATEGORY = 'I/O'
    
    def __init__(self):
        super(TextFileNode, self).__init__()
        
        # Set node name that will be displayed
        self.set_name('Text File')
        
        # Create input and output ports
        self.add_input('Text In')
        self.add_output('Text Out')
        
        # Create properties
        self.add_text_input('filepath', 'File Path', '')
        self.add_text_input('mode', 'Mode (Load or Save)', 'Load')
        self.add_text_input('auto_reload', 'Auto Reload on Compute (true/false)', 'true')
        self.add_text_input('preview', 'Content Preview', '')
        self.add_text_input('status_info', 'Status', 'Ready')
        self.add_text_input('help_text', 'Instructions', 'Enter a file path and set mode to Load or Save.\nClick Execute in the workflow to process the file.')
        
        # Set node color
        self.set_color(86, 147, 217)
        
        # Track last modified time
        self.last_modified = 0
    
    def set_status(self, status_text):
        """Update status by setting a property that's visible to the user"""
        self.set_property('status_info', status_text)
        # Also call base implementation if it exists
        if hasattr(super(), 'set_status'):
            super().set_status(status_text)
    
    def execute(self):
        """Process the node based on its mode"""
        mode = self.get_property('mode').lower()
        
        if mode.startswith('l'):  # 'load' or 'Load'
            # Check if file exists and needs reload
            file_path = self.get_property('filepath')
            
            if not file_path or not os.path.exists(file_path):
                self.set_status("No file path specified or file doesn't exist")
                return {'Text Out': ""}
            
            # Check if file has been modified since last load
            current_mtime = os.path.getmtime(file_path)
            auto_reload = self.get_property('auto_reload').lower() == 'true'
            
            if auto_reload or current_mtime > self.last_modified or 'Text Out' not in self.output_cache:
                try:
                    # Read the file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Update last modified time
                    self.last_modified = current_mtime
                    
                    # Update preview
                    preview = content[:1000] + ('...' if len(content) > 1000 else '')
                    self.set_property('preview', preview)
                    
                    self.set_status(f"Loaded {len(content)} characters from file")
                    return {'Text Out': content}
                except Exception as e:
                    self.set_status(f"Error loading file: {str(e)[:20]}...")
                    return {'Text Out': ""}
            else:
                self.set_status("Using cached file content")
                return self.output_cache
                
        else:  # 'save' or 'Save'
            # Get input data
            content = self.get_input_data('Text In')
            
            if content is None:
                self.set_status("No input data to save")
                return {'Text Out': ""}
            
            file_path = self.get_property('filepath')
            
            if not file_path:
                self.set_status("No file path specified")
                return {'Text Out': content}  # Pass through content anyway
            
            try:
                # Write to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(str(content))
                
                # Update preview
                preview = str(content)[:1000] + ('...' if len(str(content)) > 1000 else '')
                self.set_property('preview', preview)
                
                self.set_status(f"Saved {len(str(content))} characters to file")
                return {'Text Out': content}  # Pass through the input
            except Exception as e:
                self.set_status(f"Error saving file: {str(e)[:20]}...")
                return {'Text Out': content}  # Pass through the input even if save fails
