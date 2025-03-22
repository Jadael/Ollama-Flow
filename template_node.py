"""
Template Node for Ollama Flow

This file provides a template for creating new nodes in Ollama Flow.
It contains extensive comments to help beginners understand how nodes work.

To create a new node:
1. Copy this file to the /nodes/ directory
2. Rename it to your_node_name.py (use snake_case)
3. Rename the class to YourNodeName (use CamelCase)
4. Customize the node's attributes, ports, and functionality
5. Save the file - it will be automatically discovered!
"""

# Import the base node class - this is required for all nodes
from nodes.base_node import OllamaBaseNode

# Optional: Import any additional libraries your node needs
# import os
# import json
# import requests
# from PySide6.QtWidgets import QFileDialog, QWidget, QVBoxLayout, QPushButton


class TemplateNode(OllamaBaseNode):
    """
    Template node for Ollama Flow.
    
    This docstring will be used as the node's description in the node registry.
    It should clearly explain what the node does in 1-3 sentences.
    """
    
    # === REQUIRED NODE METADATA ===
    
    # Identifier - Usually keep this as the default namespace
    # This is like a "package name" for your nodes
    __identifier__ = 'com.ollamaflow.nodes'
    
    # Type - This must be unique for each node type!
    # By convention, use the class name, e.g., 'TemplateNode'
    __type__ = 'TemplateNode'
    
    # Node display name - This is what users will see in the UI
    # Make it concise but descriptive, e.g., 'Text Filter', 'JSON Parser'
    NODE_NAME = 'Template Node'
    
    # Node category - This determines where your node appears in the menu
    # Common categories: 'Input', 'Output', 'Text Processing', 'LLM', 'Utility'
    NODE_CATEGORY = 'Utility'
    
    def __init__(self):
        """
        Initialize the node.
        
        This method sets up the node's appearance, ports, and properties.
        It runs once when the node is created.
        """
        # Always call the parent class's __init__ first
        super(TemplateNode, self).__init__()
        
        # === NODE APPEARANCE ===
        
        # Set the node's display name (typically same as NODE_NAME)
        self.set_name('Template Node')
        
        # Set the node's color (RGB values from 0-255)
        # Choose distinctive colors for different node types
        self.set_color(120, 120, 220)  # Light blue
        
        # === INPUT PORTS ===
        # Input ports receive data from other nodes
        # Each input port has a name that will be displayed on the node
        
        # Add a standard input port
        self.add_input('Input')
        
        # You can add multiple input ports with different names
        # self.add_input('Second Input')
        
        # === OUTPUT PORTS ===
        # Output ports send data to other nodes
        # The names should describe what data is being output
        
        # Add a standard output port
        self.add_output('Output')
        
        # You can add multiple output ports
        # self.add_output('Alternative Output')
        
        # === NODE PROPERTIES ===
        # Properties are settings that appear in the Properties panel
        # They can be edited by the user and affect the node's behavior
        
        # Text input property - for single-line text entry
        self.add_text_input('text_property', 'Text Setting', 'Default value')
        
        # Checkbox property - for boolean (true/false) settings
        self.add_checkbox('bool_property', 'Enable Feature', True)
        
        # Dropdown menu property - for selecting from a list of options
        options = ['Option 1', 'Option 2', 'Option 3']
        self.add_combo_menu('dropdown', 'Select Option', items=options, default='Option 1')
        
        # Slider property - for numeric values within a range
        self.add_float_slider('value', 'Number Value', value=5.0, range=(0.0, 10.0))
        
        # Integer slider
        self.add_int_slider('int_value', 'Integer Value', value=5, range=(0, 10))
        
        # === PREVIEW AND MONITORING PROPERTIES ===
        # These properties are useful for debugging and monitoring
        
        # A property to show output preview
        self.add_text_input('output_preview', 'Output Preview', '')
        
        # === CUSTOM WIDGETS (OPTIONAL) ===
        # If your node needs custom UI elements (buttons, etc.),
        # you can add them by uncommenting and customizing this code:
        
        """
        # Create custom widget
        control_widget = QWidget()
        layout = QVBoxLayout(control_widget)
        
        # Add a button
        self.action_button = QPushButton("Perform Action")
        self.action_button.clicked.connect(self.on_button_click)
        layout.addWidget(self.action_button)
        
        # Set layout and add the widget
        control_widget.setLayout(layout)
        self.add_custom_widget(control_widget, tab='Controls')
        """
        
        # === NODE STATE ===
        # You can add any instance variables your node needs here
        self.my_internal_state = None
    
    def execute(self):
        """
        Execute the node's functionality when it needs to process data.
        
        This method is called when:
        1. The node is first added to the graph
        2. Input values change
        3. The user manually triggers the workflow to run
        
        It should:
        1. Get input data
        2. Process that data
        3. Return a dictionary mapping output port names to values
        
        Returns:
            dict: A dictionary with output port names as keys and output values as values
        """
        # === STEP 1: GET INPUT DATA ===
        # Use self.get_input_data() to get values from input ports
        # If the input port isn't connected, this will return None
        input_value = self.get_input_data('Input')
        
        # Update status to show what's happening
        self.set_status("Processing...")
        
        # === STEP 2: PROCESS THE DATA ===
        # This is where you implement your node's actual functionality
        # Below is just a simple example - replace with your own logic
        
        if input_value is None:
            # Handle case where input is not connected
            self.set_status("No input data")
            result = "No input data provided"
        else:
            # Process the input (this is a trivial example - modify for your needs)
            # For this template, we just convert to uppercase if it's a string
            if isinstance(input_value, str):
                result = input_value.upper()
                self.set_status("Converted string to uppercase")
            else:
                # If it's not a string, convert it to a string
                result = str(input_value)
                self.set_status("Converted input to string")
        
        # Update preview for debugging
        preview = result[:1000] + ('...' if len(result) > 1000 else '')
        self.set_property('output_preview', preview)
        
        # === STEP 3: RETURN OUTPUT VALUES ===
        # Return a dictionary mapping output port names to their values
        # The keys must match your output port names exactly
        return {
            'Output': result,
            # If you have multiple outputs, add them here
            # 'Alternative Output': some_other_result,
        }
    
    # === OPTIONAL METHODS ===
    # These methods are optional but can be useful for more complex nodes
    
    """
    def on_button_click(self):
        # Handle button clicks for custom widgets
        self.set_status("Button clicked!")
        # Perform any actions needed...
        
        # If the action should update the node's output,
        # mark the node as needing processing
        self.mark_dirty()
    """

# === NOTES FOR NODE CREATORS ===
"""
NODE LIFECYCLE:
1. When your node is first created, __init__ runs once
2. The execute() method runs whenever the node needs to process data
3. The node registry automatically discovers your node on application startup
4. Your node appears in the appropriate category in the Nodes menu

DATA FLOW:
- Nodes receive data through input ports
- Nodes send data through output ports
- Connections between ports pass data from one node to another
- The workflow executor determines the order of execution based on connections

BEST PRACTICES:
- Keep node functionality focused on a single task
- Use clear, descriptive names for ports and properties
- Update the status often to show what the node is doing
- Handle errors gracefully
- Provide preview properties for debugging
- Use appropriate categories for your nodes

DEBUGGING TIPS:
- Check the application console for print statements and errors
- Use self.set_status() to display status messages on the node
- Use preview properties to see intermediate data
- If your node doesn't appear in the menu, check for syntax errors

NAMING CONVENTIONS:
- File names: snake_case (lower_case_with_underscores.py)
- Class names: CamelCase (UpperCamelCase)
- Method and property names: snake_case (lower_case_with_underscores)
"""
