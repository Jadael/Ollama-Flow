from NodeGraphQt import BaseNode
import requests
import json
import time

class OllamaBaseNode(BaseNode):
    """Base class for all Ollama nodes that uses minimal API features"""
    
    # Node identifier - should be overridden by subclasses
    __identifier__ = 'com.ollamaflow.nodes'
    
    # Node type - should be overridden by subclasses
    __type__ = 'BaseNode'
    
    # Node display name
    NODE_NAME = 'Base Node'
    
    # Node category for menu organization
    NODE_CATEGORY = 'Basic'
    
    def __init__(self):
        super(OllamaBaseNode, self).__init__()
        
        # Processing state
        self.processing = False
        self.dirty = True  # Needs processing
        self.output_cache = {}  # Cache for output values
        self.status = "Ready"
        self.processing_error = None
        self.is_async_node = False  # Flag for async processing nodes
        self.processing_done = True  # Flag for tracking completion
        self.processing_start_time = 0  # When processing started
        
        # Keep track of property inputs
        self._property_inputs = {}  # Maps property names to input port names
        self._input_properties = {}  # Maps input port names to property names
        self._excluded_input_props = set()  # Properties that shouldn't get auto-inputs
    
    def mark_dirty(self):
        """Mark this node as needing reprocessing"""
        if not self.dirty:
            self.dirty = True
            self.status = "Ready"
            
            # Mark downstream nodes as dirty
            for port in self.output_ports():
                for connected_port in port.connected_ports():
                    connected_node = connected_port.node()
                    if hasattr(connected_node, 'mark_dirty'):
                        connected_node.mark_dirty()
    
    def execute(self):
        """
        Override this method in subclasses to implement node-specific processing logic.
        Returns a dictionary mapping output socket names to values.
        """
        return {}
    
    def process(self):
        """Process this node, getting inputs from connected nodes and returning outputs"""
        return self.compute()
        
    def compute(self):
        """Process this node (should be called when inputs change)"""
        # Update status
        self.status = "Processing..."
        
        # If already processing, just return cached output
        if self.processing:
            return self.output_cache
        
        # If not dirty and we have cached output, return it
        if not self.dirty and self.output_cache:
            self.status = "Complete"
            return self.output_cache
        
        # Set processing state
        self.processing = True
        self.processing_done = False
        self.processing_error = None
        self.processing_start_time = time.time()
        
        try:
            # Execute the actual node-specific processing logic
            result = self.execute()
            
            # For synchronous nodes, update cache and state
            if not self.is_async_node:
                self.output_cache = result
                self.dirty = False
                self.status = "Complete"
                self.processing_done = True
            
            return result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.processing_error = str(e)
            self.status = f"Error: {str(e)[:20]}..."
            self.processing_done = True
            
            return {}
            
        finally:
            # Only set processing complete for non-async nodes
            if not self.is_async_node:
                self.processing = False
    
    def get_input_data(self, input_name):
        """Get data from an input port by name"""
        # Get the input port
        input_port = None
        for port in self.input_ports():
            if port.name() == input_name:
                input_port = port
                break
                
        if not input_port or not input_port.connected_ports():
            return None
        
        # Get the first connected port
        connected_port = input_port.connected_ports()[0]
        connected_node = connected_port.node()
        
        # Process the connected node if it's dirty
        if hasattr(connected_node, 'dirty') and connected_node.dirty:
            connected_node.compute()
        
        # Wait if the connected node is processing (for async nodes)
        if hasattr(connected_node, 'processing') and connected_node.processing:
            # Simple polling with timeout
            timeout = 120  # 2 minute timeout (120 seconds)
            start_wait = time.time()
            
            while time.time() - start_wait < timeout:
                # If the connected node finished processing, break out of the loop
                if hasattr(connected_node, 'processing_done') and connected_node.processing_done:
                    break
                    
                # Sleep briefly to avoid busy waiting
                time.sleep(0.1)
                
                # Check again if it's still processing
                if not hasattr(connected_node, 'processing') or not connected_node.processing:
                    break
            
            # If we timed out and node is still processing
            if hasattr(connected_node, 'processing') and connected_node.processing:
                if not hasattr(connected_node, 'processing_done') or not connected_node.processing_done:
                    self.status = f"Timeout waiting for {connected_node.name()}"
                    raise TimeoutError(f"Timed out waiting for input from '{connected_node.name()}'")
        
        # Check for errors in the input node
        if hasattr(connected_node, 'processing_error') and connected_node.processing_error:
            self.status = f"Input error: {connected_node.name()}"
            raise ValueError(f"Error in input node '{connected_node.name()}': {connected_node.processing_error}")
        
        # Get data from the connected port's node
        if hasattr(connected_node, 'output_cache'):
            return connected_node.output_cache.get(connected_port.name(), None)
        
        return None
    
    def set_status(self, status_text):
        """Set the status text for the node"""
        self.status = status_text
        # Also update any status property if it exists
        if hasattr(self, 'set_property') and hasattr(self, 'get_property'):
            if self.get_property('status_info') is not None:
                self.set_property('status_info', status_text)

    # ----- Enhanced property methods -----
    
    def add_text_input(self, prop_name, label, default_value="", create_input=True, tab=None):
        """
        Add a text input property with an optional corresponding input port.
        
        Args:
            prop_name: Name of the property
            label: Display label for the property
            default_value: Default value for the property
            create_input: Whether to create a corresponding input port
            tab: Optional tab name to place the property in
        """
        # Call the original method from BaseNode
        kwargs = {}
        if tab is not None:
            kwargs['tab'] = tab
            
        result = super(OllamaBaseNode, self).add_text_input(prop_name, label, default_value, **kwargs)
        
        # Create the corresponding input port if required
        if create_input and not self._should_exclude_property(prop_name):
            input_name = self._get_input_name_for_property(prop_name)
            self.add_input(input_name)
            
            # Track the property-input relationship
            self._property_inputs[prop_name] = input_name
            self._input_properties[input_name] = prop_name
            
        return result
    
    def add_combo_menu(self, prop_name, label, items, default="", create_input=True, tab=None):
        """
        Add a combo menu property with an optional corresponding input port.
        
        Args:
            prop_name: Name of the property
            label: Display label for the property
            items: List of items for the combo menu
            default: Default selected item
            create_input: Whether to create a corresponding input port
            tab: Optional tab name to place the property in
        """
        # Call the original method from BaseNode
        kwargs = {}
        if tab is not None:
            kwargs['tab'] = tab
            
        result = super(OllamaBaseNode, self).add_combo_menu(prop_name, label, items, default, **kwargs)
        
        # Create the corresponding input port if required
        if create_input and not self._should_exclude_property(prop_name):
            input_name = self._get_input_name_for_property(prop_name)
            self.add_input(input_name)
            
            # Track the property-input relationship
            self._property_inputs[prop_name] = input_name
            self._input_properties[input_name] = prop_name
            
        return result
    
    def add_checkbox(self, prop_name, label, default=False, create_input=True, tab=None):
        """
        Add a checkbox property with an optional corresponding input port.
        
        Args:
            prop_name: Name of the property
            label: Display label for the property
            default: Default state (True/False)
            create_input: Whether to create a corresponding input port
            tab: Optional tab name to place the property in
        """
        # Call the original method from BaseNode
        kwargs = {}
        if tab is not None:
            kwargs['tab'] = tab
            
        result = super(OllamaBaseNode, self).add_checkbox(prop_name, label, default, **kwargs)
        
        # Create the corresponding input port if required
        if create_input and not self._should_exclude_property(prop_name):
            input_name = self._get_input_name_for_property(prop_name)
            self.add_input(input_name)
            
            # Track the property-input relationship
            self._property_inputs[prop_name] = input_name
            self._input_properties[input_name] = prop_name
            
        return result
    
    def add_float_input(self, prop_name, label, default=0.0, create_input=True, tab=None):
        """
        Add a float input property with an optional corresponding input port.
        
        Args:
            prop_name: Name of the property
            label: Display label for the property
            default: Default value
            create_input: Whether to create a corresponding input port
            tab: Optional tab name to place the property in
        """
        # Call the original method from BaseNode
        kwargs = {}
        if tab is not None:
            kwargs['tab'] = tab
            
        result = super(OllamaBaseNode, self).add_float_input(prop_name, label, default, **kwargs)
        
        # Create the corresponding input port if required
        if create_input and not self._should_exclude_property(prop_name):
            input_name = self._get_input_name_for_property(prop_name)
            self.add_input(input_name)
            
            # Track the property-input relationship
            self._property_inputs[prop_name] = input_name
            self._input_properties[input_name] = prop_name
            
        return result
    
    def add_int_input(self, prop_name, label, default=0, create_input=True, tab=None):
        """
        Add an integer input property with an optional corresponding input port.
        
        Args:
            prop_name: Name of the property
            label: Display label for the property
            default: Default value
            create_input: Whether to create a corresponding input port
            tab: Optional tab name to place the property in
        """
        # Call the original method from BaseNode
        kwargs = {}
        if tab is not None:
            kwargs['tab'] = tab
            
        result = super(OllamaBaseNode, self).add_int_input(prop_name, label, default, **kwargs)
        
        # Create the corresponding input port if required
        if create_input and not self._should_exclude_property(prop_name):
            input_name = self._get_input_name_for_property(prop_name)
            self.add_input(input_name)
            
            # Track the property-input relationship
            self._property_inputs[prop_name] = input_name
            self._input_properties[input_name] = prop_name
            
        return result
    
    def exclude_property_from_input(self, prop_name):
        """
        Mark a property as excluded from auto-input creation.
        Use this before creating the property.
        """
        self._excluded_input_props.add(prop_name)
    
    def get_property_value(self, prop_name):
        """
        Get the value of a property, checking input connections first.
        If an input for this property is connected, use that value.
        Otherwise, fall back to the property's value.
        
        Args:
            prop_name: Name of the property
            
        Returns:
            The value from the input connection or the property value
        """
        # Check if this property has a corresponding input
        if prop_name in self._property_inputs:
            input_name = self._property_inputs[prop_name]
            input_value = self.get_input_data(input_name)
            
            # If the input is connected and has a value, use it
            if input_value is not None:
                return input_value
        
        # Otherwise use the property value
        return super(OllamaBaseNode, self).get_property(prop_name)
    
    def _get_input_name_for_property(self, prop_name):
        """Generate an input port name for a property"""
        # Convert to title case and add spaces for readability
        input_name = ' '.join(word.capitalize() for word in prop_name.split('_'))
        return f"{input_name}"
    
    def _should_exclude_property(self, prop_name):
        """Check if a property should be excluded from auto-input creation"""
        # Common properties that shouldn't get inputs
        default_excludes = {
            'status_info', 'result_preview', 'response_preview', 'input_preview'
        }
        
        if prop_name in default_excludes or prop_name in self._excluded_input_props:
            return True
            
        # Skip properties that end with common preview/status suffixes
        if prop_name.endswith(('_preview', '_info', '_status')):
            return True
            
        return False
    
    # Override the original get_property for backwards compatibility
    def get_property(self, name):
        """Override to check inputs first"""
        return self.get_property_value(name)
