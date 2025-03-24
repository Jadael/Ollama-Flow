from NodeGraphQt import BaseNode
import requests
import json
import time
import copy
from threading import Thread
from PySide6.QtCore import QObject, Signal, Qt, Slot, QThread, QCoreApplication, QTimer

# Create a QObject for thread-safe signal communication
class NodeSignalHandler(QObject):
    # Define signals for thread-safe operations
    property_updated = Signal(object, str, object)  # node, property_name, value
    status_updated = Signal(object, str)  # node, status_text
    widget_refresh = Signal(object)  # node to refresh widgets

    @Slot(object, str, object)
    def _update_property(self, node, prop_name, value):
        """Slot to update a node property on the main thread"""
        print(f"UI Update: Setting {prop_name} = {value[:30]}... on {node.name()}" if isinstance(value, str) else f"UI Update: Setting {prop_name} = {value} on {node.name()}")
        if hasattr(node, 'set_property'):
            try:
                # Use the NodeGraphQt's property system
                # The push_undo=False argument is important for compatibility
                node.set_property(prop_name, value, push_undo=False)
            except TypeError:
                # Fall back to simpler version if push_undo isn't supported
                node.set_property(prop_name, value)
                
            # Force widget refresh after property update
            if hasattr(node, '_NodeObject__view'):
                if hasattr(node._NodeObject__view, 'update'):
                    node._NodeObject__view.update()
    
    @Slot(object, str)
    def _update_status(self, node, status_text):
        """Slot to update a node status on the main thread"""
        print(f"UI Update: Setting status = {status_text} on {node.name()}")
        if hasattr(node, 'status'):
            node.status = status_text
            # Also update any status property if it exists
            if hasattr(node, 'set_property') and hasattr(node, 'get_property'):
                if node.get_property('status_info') is not None:
                    try:
                        node.set_property('status_info', status_text, push_undo=False)
                    except TypeError:
                        node.set_property('status_info', status_text)
                    
            # Force widget refresh after status update
            if hasattr(node, '_NodeObject__view'):
                if hasattr(node._NodeObject__view, 'update'):
                    node._NodeObject__view.update()

    @Slot(object)
    def _refresh_node_widgets(self, node):
        """Trigger a refresh of the node's property widgets"""
        try:
            # Force a property widget refresh via the node's view
            if hasattr(node, 'update'):
                node.update()
                
            if hasattr(node, 'view') and callable(node.view):
                view = node.view()
                if view and hasattr(view, 'update'):
                    view.update()
                    
            # For NodeGraphQt specifically, try to refresh the properties bin
            if hasattr(node, 'graph') and callable(node.graph):
                try:
                    graph = node.graph()
                    if graph and hasattr(graph, '_viewer'):
                        viewer = graph._viewer
                        if hasattr(viewer, 'property_bin'):
                            prop_bin = viewer.property_bin
                            if hasattr(prop_bin, 'add_node'):
                                prop_bin.add_node(node)
                except Exception as e:
                    print(f"Error accessing node graph: {e}")
        except Exception as e:
            print(f"Error refreshing node widgets: {e}")

# Create a singleton instance of the signal handler
_signal_handler = None

def get_signal_handler():
    """Get or create the signal handler singleton"""
    global _signal_handler
    if _signal_handler is not None:
        return _signal_handler
        
    if QCoreApplication.instance() is not None:
        print("Creating NodeSignalHandler for thread-safe UI updates")
        _signal_handler = NodeSignalHandler()
        
        # Connect the signals to slots
        _signal_handler.property_updated.connect(
            _signal_handler._update_property, 
            Qt.QueuedConnection
        )
        _signal_handler.status_updated.connect(
            _signal_handler._update_status, 
            Qt.QueuedConnection
        )
        _signal_handler.widget_refresh.connect(
            _signal_handler._refresh_node_widgets,
            Qt.QueuedConnection
        )
    
    return _signal_handler

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
        
        # IMPORTANT: Initialize these FIRST to avoid errors in subclasses
        self._property_inputs = {}  # Maps property names to input port names
        self._input_properties = {}  # Maps input port names to property names
        self._excluded_input_props = set()  # Properties that shouldn't get auto-inputs
        self._property_values = {}  # Cache of property values to detect changes
        
        # Processing state
        self.processing = False
        self.dirty = True  # Needs processing
        self.output_cache = {}  # Cache for output values
        self.status = "Ready"
        self.processing_error = None
        self.is_async_node = False  # Flag for async processing nodes
        self.processing_done = True  # Flag for tracking completion
        self.processing_start_time = 0  # When processing started
        
        # Add recalculation mode property - this is a node configuration option
        # Renamed for clarity on behavior
        self.exclude_property_from_input('recalculation_mode')
        self.add_combo_menu('recalculation_mode', 'Recalculation Mode', 
                           ['Dirty if inputs change', 'Always dirty', 'Never dirty'], 
                           'Dirty if inputs change', tab='Configuration')
        
        # Initialize the signal handler
        get_signal_handler()
    
    def exclude_property_from_input(self, prop_name):
        """
        Mark a property as excluded from auto-input creation.
        Use this before creating the property.
        """
        # Defensive initialization - ensure the set exists
        if not hasattr(self, '_excluded_input_props'):
            self._excluded_input_props = set()
            
        self._excluded_input_props.add(prop_name)
        
    def mark_dirty(self):
        """Mark this node as needing reprocessing"""
        # Don't mark as dirty if recalculation mode is "Never dirty" and we have output_cache
        try:
            recalc_mode = self.get_property('recalculation_mode')
            if recalc_mode == 'Never dirty' and hasattr(self, 'output_cache') and self.output_cache:
                print(f"Node {self.name()}: Not marking as dirty due to 'Never dirty' mode")
                return
        except Exception as e:
            # If we can't get the mode, proceed with normal marking
            print(f"Node {self.name()}: Error checking recalculation mode: {e}, proceeding with normal marking")

        # Only proceed if not already dirty
        if not self.dirty:
            self.dirty = True
            self.status = "Ready"
            
            # Mark downstream nodes as dirty
            for port in self.output_ports():
                for connected_port in port.connected_ports():
                    connected_node = connected_port.node()
                    if hasattr(connected_node, 'mark_dirty'):
                        connected_node.mark_dirty()
    
    def _mark_downstream_dirty(self):
        """Mark downstream nodes as dirty if appropriate"""
        for port in self.output_ports():
            for connected_port in port.connected_ports():
                connected_node = connected_port.node()
                if hasattr(connected_node, 'mark_dirty'):
                    recalc_mode = connected_node.get_property('recalculation_mode')
                    if recalc_mode != 'Never dirty':  # Only propagate if not 'Never dirty'
                        connected_node.mark_dirty()
    
    def serialize(self):
        """
        Serialize the node data for saving.
        With our simplified approach using properties, we can remove most of the custom 
        serialization logic. The properties will be automatically saved by NodeGraphQt.
        
        We'll still need to keep track of our processing state flags.
        """
        # Create a dictionary for any custom data we still need to track
        node_dict = {
            'ollama_dirty': self.dirty if hasattr(self, 'dirty') else True,
            'ollama_processing_done': self.processing_done if hasattr(self, 'processing_done') else True
        }
        
        return node_dict

    def has_valid_cache(self):
        """
        Check if the node has a valid output cache.
        Override in subclasses for node-specific validation.
        """
        return hasattr(self, 'output_cache') and bool(self.output_cache)

    def deserialize(self, node_dict, namespace=None, context=None):
        """
        Deserialize the node data when loading.
        We're only handling our custom fields here.
        """
        # Only restore our custom fields
        if 'ollama_output_cache' in node_dict:
            self.output_cache = node_dict['ollama_output_cache']
            print(f"Node {self.name()}: Restored output cache with {len(self.output_cache)} entries")
        
        # Restore processing state flags
        if 'ollama_dirty' in node_dict:
            self.dirty = node_dict['ollama_dirty']
        
        if 'ollama_processing_done' in node_dict:
            self.processing_done = node_dict['ollama_processing_done']
        
        # If in "Never dirty" mode and we have a valid cache, ensure it stays not dirty
        try:
            recalc_mode = self.get_property('recalculation_mode')
            if recalc_mode == 'Never dirty' and self.has_valid_cache():
                self.dirty = False
                print(f"Node {self.name()}: Set to not dirty based on 'Never dirty' mode and valid cache")
            elif recalc_mode == 'Always dirty':
                self.dirty = True
                print(f"Node {self.name()}: Set to dirty based on 'Always dirty' mode")
        except Exception as e:
            print(f"Node {self.name()}: Error checking recalculation mode during deserialization: {e}")

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
        """
        Process this node (should be called when inputs change).
        Enhanced with improved dependency handling and output change detection.
        """
        # Update status
        self.status = "Processing..."
        self.set_property('status_info', "Processing...")
        node_name = self.name() if hasattr(self, 'name') and callable(getattr(self, 'name')) else "Unknown"
        print(f"Node {node_name}: Status set to Processing...")
        
        # Get the current recalculation mode
        recalculation_mode = self.get_property('recalculation_mode')
        
        # If already processing, just return cached output to prevent cycles
        if self.processing:
            print(f"Node {node_name}: Already processing, returning cached output to avoid cycle")
            return self.output_cache or {}
        
        # Handle caching based on recalculation mode
        if recalculation_mode == 'Never dirty' and hasattr(self, 'output_cache') and self.output_cache:
            self.status = "Complete (cached)"
            self.set_property('status_info', "Complete (cached)")
            print(f"Node {node_name}: Using cached output (Never dirty mode)")
            return self.output_cache
            
        # Default behavior: if not dirty and we have cached output, return it
        if recalculation_mode == 'Always dirty':
            # Always recalculate for this mode, even if not dirty
            print(f"Node {node_name}: Always dirty mode - forcing recalculation")
        elif not self.dirty and hasattr(self, 'output_cache') and self.output_cache:
            self.status = "Complete (cached)"
            self.set_property('status_info', "Complete (cached)")
            print(f"Node {node_name}: Using cached output (not dirty)")
            return self.output_cache
        
        # Process all input dependencies first
        # This ensures all inputs are up-to-date before we execute
        try:
            # Only process dependencies if we're being called directly (not from workflow executor)
            # We can detect this by checking if there's a calling method on the stack
            import inspect
            caller_frames = inspect.stack()
            if len(caller_frames) > 1:
                caller_name = caller_frames[1].function if hasattr(caller_frames[1], 'function') else ""
                if caller_name != '_execute_workflow_thread':
                    # If we're not being called from the workflow executor's main processing method,
                    # we need to ensure dependencies are processed
                    print(f"Node {node_name}: Processing dependencies (called from {caller_name})")
                    self._process_input_dependencies()
                else:
                    print(f"Node {node_name}: Skipping dependency processing (called from workflow executor)")
            else:
                # No caller frame means we're being called directly
                print(f"Node {node_name}: Processing dependencies (direct call)")
                self._process_input_dependencies()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.processing_error = str(e)
            error_msg = f"Error in dependencies: {str(e)[:30]}..."
            self.status = error_msg
            self.set_property('status_info', error_msg)
            return {}
        
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
                # Check if output has changed
                output_changed = self._has_output_changed(result)
                
                # Update the cache - use deep copy to avoid reference issues
                if result:
                    import copy
                    self.output_cache = copy.deepcopy(result)
                
                # Clear dirty flag
                self.dirty = False
                
                # If output changed and mode isn't 'Never dirty', mark downstream nodes dirty
                if output_changed and recalculation_mode != 'Never dirty':
                    self._mark_downstream_dirty()
                
                self.status = "Complete"
                self.set_property('status_info', "Complete")
                print(f"Node {node_name}: Execution complete, status set to Complete")
                self.processing_done = True
                self.processing = False
            else:
                # For async nodes, the thread will handle the output cache update
                # But we need to make sure the node is properly marked as processing
                print(f"Node {node_name}: Async execution started")
            
            return result or {}
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.processing_error = str(e)
            error_msg = f"Error: {str(e)[:30]}..."
            self.status = error_msg
            self.set_property('status_info', error_msg)
            print(f"Node {node_name}: Execution error: {error_msg}")
            self.processing_done = True
            self.processing = False
            
            return {}
    
    def async_processing_complete(self, result_dict=None):
        """
        Call this method from async nodes when background processing is complete.
        This ensures proper dirty state management for async nodes.
        
        Args:
            result_dict: Optional dictionary of output values to set in output_cache
        """
        node_name = self.name() if hasattr(self, 'name') and callable(getattr(self, 'name')) else "Unknown"
        print(f"Node {node_name}: Async processing complete")
        
        # If result_dict provided, update output_cache
        if result_dict:
            # Check if output has changed
            output_changed = self._has_output_changed(result_dict)
            
            # Update the cache with a deep copy to avoid reference issues
            import copy
            self.output_cache = copy.deepcopy(result_dict)
            
            # If output changed and not in Never dirty mode, mark downstream nodes dirty
            recalculation_mode = self.get_property('recalculation_mode')
            if output_changed and recalculation_mode != 'Never dirty':
                print(f"Node {node_name}: Output changed, marking downstream nodes as dirty")
                self._mark_downstream_dirty()
            
            print(f"Node {node_name}: Updated output cache with {len(result_dict)} entries")
        
        # Clear dirty flag - async processing is now complete
        self.dirty = False
        self.processing = False
        self.processing_done = True
        
        # Make sure status is updated
        if not self.processing_error:
            self.status = "Complete"
            self.set_property('status_info', "Complete")

    def _has_output_changed(self, new_output):
        """Check if the output has changed compared to the cached output"""
        if not hasattr(self, 'output_cache') or not self.output_cache:
            return True  # No previous output, so it has changed
            
        if set(new_output.keys()) != set(self.output_cache.keys()):
            return True  # Different output keys
            
        # Compare values for each output
        for key, value in new_output.items():
            if key not in self.output_cache:
                return True  # New output key
                
            # Special handling for strings (most common case)
            if isinstance(value, str) and isinstance(self.output_cache[key], str):
                if value != self.output_cache[key]:
                    return True  # String content changed
            else:
                # For non-string values, do a simple comparison
                # This is not perfect for complex objects but a reasonable compromise
                if value != self.output_cache[key]:
                    return True
                    
        return False  # No changes detected
    
    def _process_input_dependencies(self):
        """
        Processes all input dependencies to ensure they're computed before this node.
        """
        # Get all input ports
        if callable(getattr(self, 'input_ports', None)):
            input_ports = self.input_ports()
        elif hasattr(self, 'inputs'):
            input_ports = self.inputs
        else:
            input_ports = []
        
        # Process each connected input
        for input_port in input_ports:
            # Get connected ports
            if callable(getattr(input_port, 'connected_ports', None)):
                connected_ports = input_port.connected_ports()
            elif hasattr(input_port, 'connections'):
                connected_ports = input_port.connections
            else:
                connected_ports = []
            
            # Process each connected node
            for connected_port in connected_ports:
                connected_node = connected_port.node()
                
                # Skip if the node is already processing (cycle detection)
                if hasattr(connected_node, 'processing') and connected_node.processing:
                    print(f"Warning: Detected execution cycle between {self.name()} and {connected_node.name()}")
                    continue
                
                # Process connected node if it's dirty
                if hasattr(connected_node, 'dirty') and connected_node.dirty and hasattr(connected_node, 'compute'):
                    print(f"Node {self.name()}: Processing dependency {connected_node.name()}")
                    connected_node.compute()
                
                # Wait if the node is asynchronous and still processing
                if hasattr(connected_node, 'processing') and connected_node.processing:
                    # Get the timeout value - default to 120 seconds (2 minutes)
                    timeout = 120
                    start_wait = time.time()
                    
                    print(f"Node {self.name()}: Waiting for async dependency {connected_node.name()}")
                    
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
                            wait_time = time.time() - start_wait
                            timeout_msg = f"Timeout waiting for {connected_node.name()} after {wait_time:.1f}s"
                            self.status = timeout_msg
                            print(f"Node {self.name()}: {timeout_msg}")
                            raise TimeoutError(f"Timed out waiting for input from '{connected_node.name()}'")
                
                # Check for errors in the dependency
                if hasattr(connected_node, 'processing_error') and connected_node.processing_error:
                    error_msg = f"Error in dependency {connected_node.name()}: {connected_node.processing_error}"
                    print(f"Node {self.name()}: {error_msg}")
                    raise ValueError(error_msg)

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
    
    def thread_safe_set_property(self, prop_name, value):
        """
        Thread-safe method to set a property value.
        This will ensure the property is set on the main (GUI) thread.
        
        Args:
            prop_name: Name of the property to set
            value: Value to set the property to
        """
        # Get the signal handler
        signal_handler = get_signal_handler()
        if signal_handler:
            # Use the signal-slot mechanism to update the property on the main thread
            signal_handler.property_updated.emit(self, prop_name, value)
        else:
            print(f"Warning: No signal handler available for thread-safe property update")
            # Fall back to direct update if no signal handler is available
            if hasattr(self, 'set_property'):
                # Use super's set_property to avoid recursion
                super(OllamaBaseNode, self).set_property(prop_name, value)
    
    def thread_safe_set_status(self, status_text):
        """
        Thread-safe method to set the status text for the node.
        This will ensure the status is updated on the main (GUI) thread.
        
        Args:
            status_text: Status text to set
        """
        # Get the signal handler
        signal_handler = get_signal_handler()
        if signal_handler:
            # Use the signal-slot mechanism to update the status on the main thread
            signal_handler.status_updated.emit(self, status_text)
        else:
            print(f"Warning: No signal handler available for thread-safe status update")
            # Fall back to direct update if no signal handler is available
            self.status = status_text
            # Also update any status property if it exists
            if hasattr(self, 'set_property') and hasattr(self, 'get_property'):
                if self.get_property('status_info') is not None:
                    # Use super's set_property to avoid recursion
                    super(OllamaBaseNode, self).set_property('status_info', status_text)
    
    def set_status(self, status_text):
        """Set the status text for the node"""
        # If called from a non-main thread, use the thread-safe version
        current_thread = QThread.currentThread()
        app_thread = None
        if QCoreApplication.instance():
            app_thread = QCoreApplication.instance().thread()
            
        if current_thread != app_thread:
            self.thread_safe_set_status(status_text)
            return
            
        # Otherwise, update directly
        self.status = status_text
        # Also update any status property if it exists
        if hasattr(self, 'set_property') and hasattr(self, 'get_property'):
            if self.get_property('status_info') is not None:
                self.set_property('status_info', status_text)

    # ----- Enhanced property methods -----
    
    def add_text_input(self, prop_name, label, default_value="", tab=None):
        """
        Add a text input property with an optional corresponding input port.
        
        Args:
            prop_name: Name of the property
            label: Display label for the property
            default_value: Default value for the property
            tab: Optional tab name to place the property in
        """
        # Ensure the excluded properties set exists
        if not hasattr(self, '_excluded_input_props'):
            self._excluded_input_props = set()
            
        # Ensure the property inputs map exists
        if not hasattr(self, '_property_inputs'):
            self._property_inputs = {}
            
        # Ensure the input properties map exists
        if not hasattr(self, '_input_properties'):
            self._input_properties = {}
            
        # Call the original method from BaseNode
        kwargs = {}
        if tab is not None:
            kwargs['tab'] = tab
            
        result = super(OllamaBaseNode, self).add_text_input(prop_name, label, default_value, **kwargs)
        
        # Store the initial property value for change detection
        if not hasattr(self, '_property_values'):
            self._property_values = {}
        self._property_values[prop_name] = default_value
        
        # Create the corresponding input port if not excluded
        should_create_input = not self._should_exclude_property(prop_name)
        
        if should_create_input:
            input_name = self._get_input_name_for_property(prop_name)
            self.add_input(input_name)
            
            # Track the property-input relationship
            self._property_inputs[prop_name] = input_name
            self._input_properties[input_name] = prop_name
            
        return result
    
    def add_combo_menu(self, prop_name, label, items, default="", tab=None):
        """
        Add a combo menu property with an optional corresponding input port.
        
        Args:
            prop_name: Name of the property
            label: Display label for the property
            items: List of items for the combo menu
            default: Default selected item
            tab: Optional tab name to place the property in
        """
        # Ensure the excluded properties set exists
        if not hasattr(self, '_excluded_input_props'):
            self._excluded_input_props = set()
            
        # Ensure the property inputs map exists
        if not hasattr(self, '_property_inputs'):
            self._property_inputs = {}
            
        # Ensure the input properties map exists
        if not hasattr(self, '_input_properties'):
            self._input_properties = {}
            
        # Call the original method from BaseNode
        kwargs = {}
        if tab is not None:
            kwargs['tab'] = tab
            
        result = super(OllamaBaseNode, self).add_combo_menu(prop_name, label, items, default, **kwargs)
        
        # Store the initial property value for change detection
        if not hasattr(self, '_property_values'):
            self._property_values = {}
        self._property_values[prop_name] = default
        
        # Create the corresponding input port if not excluded
        should_create_input = not self._should_exclude_property(prop_name)
        
        if should_create_input:
            input_name = self._get_input_name_for_property(prop_name)
            self.add_input(input_name)
            
            # Track the property-input relationship
            self._property_inputs[prop_name] = input_name
            self._input_properties[input_name] = prop_name
            
        return result
    
    def add_checkbox(self, prop_name, label, default=False, tab=None):
        """
        Add a checkbox property with an optional corresponding input port.
        
        Args:
            prop_name: Name of the property
            label: Display label for the property
            default: Default state (True/False)
            tab: Optional tab name to place the property in
        """
        # Ensure the excluded properties set exists
        if not hasattr(self, '_excluded_input_props'):
            self._excluded_input_props = set()
            
        # Ensure the property inputs map exists
        if not hasattr(self, '_property_inputs'):
            self._property_inputs = {}
            
        # Ensure the input properties map exists
        if not hasattr(self, '_input_properties'):
            self._input_properties = {}
            
        # Call the original method from BaseNode
        kwargs = {}
        if tab is not None:
            kwargs['tab'] = tab
            
        result = super(OllamaBaseNode, self).add_checkbox(prop_name, label, default, **kwargs)
        
        # Store the initial property value for change detection
        if not hasattr(self, '_property_values'):
            self._property_values = {}
        self._property_values[prop_name] = default
        
        # Create the corresponding input port if not excluded
        should_create_input = not self._should_exclude_property(prop_name)
        
        if should_create_input:
            input_name = self._get_input_name_for_property(prop_name)
            self.add_input(input_name)
            
            # Track the property-input relationship
            self._property_inputs[prop_name] = input_name
            self._input_properties[input_name] = prop_name
            
        return result
    
    def add_float_input(self, prop_name, label, default=0.0, tab=None):
        """
        Add a float input property with an optional corresponding input port.
        
        Args:
            prop_name: Name of the property
            label: Display label for the property
            default: Default value
            tab: Optional tab name to place the property in
        """
        # Ensure the excluded properties set exists
        if not hasattr(self, '_excluded_input_props'):
            self._excluded_input_props = set()
            
        # Ensure the property inputs map exists
        if not hasattr(self, '_property_inputs'):
            self._property_inputs = {}
            
        # Ensure the input properties map exists
        if not hasattr(self, '_input_properties'):
            self._input_properties = {}
            
        # Call the original method from BaseNode
        kwargs = {}
        if tab is not None:
            kwargs['tab'] = tab
            
        result = super(OllamaBaseNode, self).add_float_input(prop_name, label, default, **kwargs)
        
        # Store the initial property value for change detection
        if not hasattr(self, '_property_values'):
            self._property_values = {}
        self._property_values[prop_name] = default
        
        # Create the corresponding input port if not excluded
        should_create_input = not self._should_exclude_property(prop_name)
        
        if should_create_input:
            input_name = self._get_input_name_for_property(prop_name)
            self.add_input(input_name)
            
            # Track the property-input relationship
            self._property_inputs[prop_name] = input_name
            self._input_properties[input_name] = prop_name
            
        return result
    
    def add_int_input(self, prop_name, label, default=0, tab=None):
        """
        Add an integer input property with an optional corresponding input port.
        
        Args:
            prop_name: Name of the property
            label: Display label for the property
            default: Default value
            tab: Optional tab name to place the property in
        """
        # Ensure the excluded properties set exists
        if not hasattr(self, '_excluded_input_props'):
            self._excluded_input_props = set()
            
        # Ensure the property inputs map exists
        if not hasattr(self, '_property_inputs'):
            self._property_inputs = {}
            
        # Ensure the input properties map exists
        if not hasattr(self, '_input_properties'):
            self._input_properties = {}
            
        # Call the original method from BaseNode
        kwargs = {}
        if tab is not None:
            kwargs['tab'] = tab
            
        result = super(OllamaBaseNode, self).add_int_input(prop_name, label, default, **kwargs)
        
        # Store the initial property value for change detection
        if not hasattr(self, '_property_values'):
            self._property_values = {}
        self._property_values[prop_name] = default
        
        # Create the corresponding input port if not excluded
        should_create_input = not self._should_exclude_property(prop_name)
        
        if should_create_input:
            input_name = self._get_input_name_for_property(prop_name)
            self.add_input(input_name)
            
            # Track the property-input relationship
            self._property_inputs[prop_name] = input_name
            self._input_properties[input_name] = prop_name
            
        return result
    
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
        if hasattr(self, '_property_inputs') and prop_name in self._property_inputs:
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
        # Ensure the excluded properties set exists
        if not hasattr(self, '_excluded_input_props'):
            self._excluded_input_props = set()
        
        # Common properties that shouldn't get inputs
        default_excludes = {
            'status_info', 'result_preview', 'response_preview', 'input_preview', 'recalculation_mode'
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
    
    # Override set_property to detect changes and mark node as dirty
    def set_property(self, name, value, **kwargs):
        """
        Override set_property to use thread-safe version when needed
        and to track property changes to mark the node as dirty.
        
        Args:
            name: Name of the property to set
            value: Value to set the property to
            **kwargs: Additional keyword arguments (like push_undo)
        """
        # If called from a non-main thread, use the thread-safe version
        current_thread = QThread.currentThread()
        app_thread = None
        if QCoreApplication.instance():
            app_thread = QCoreApplication.instance().thread()
            
        if current_thread != app_thread:
            self.thread_safe_set_property(name, value)
            return

        # Get old value for change detection
        old_value = None
        if hasattr(self, '_property_values'):
            old_value = self._property_values.get(name)
        
        # Call the original method
        result = super(OllamaBaseNode, self).set_property(name, value, **kwargs)
        
        # Store the new value
        if not hasattr(self, '_property_values'):
            self._property_values = {}
        self._property_values[name] = value
        
        # Check if this property change should mark the node as dirty
        if self._should_mark_dirty_on_property_change(name, old_value, value):
            print(f"Node {self.name()}: Property '{name}' changed, marking as dirty")
            self.mark_dirty()
            
        return result
    
    def _should_mark_dirty_on_property_change(self, prop_name, old_value, new_value):
        """
        Determine if a property change should mark the node as dirty.
        
        Args:
            prop_name: Name of the property
            old_value: Previous property value
            new_value: New property value
            
        Returns:
            True if the node should be marked as dirty, False otherwise
        """
        # Get recalculation mode
        recalc_mode = self.get_property('recalculation_mode')
        
        # Always dirty mode: property changes don't need to mark it dirty
        if recalc_mode == 'Always dirty':
            return False
            
        # Never dirty mode: property changes should not mark it dirty
        if recalc_mode == 'Never dirty':
            return False
            
        # Don't mark dirty for these property types
        if prop_name in {'status_info', 'result_preview', 'response_preview', 'input_preview', 
                        'output_preview', 'raw_response_preview'} or \
           prop_name.endswith(('_preview', '_info', '_status')):
            return False
            
        # Don't mark dirty if recalculation mode is being changed
        if prop_name == 'recalculation_mode':
            return False
            
        # Mark dirty if values are different
        return old_value != new_value
