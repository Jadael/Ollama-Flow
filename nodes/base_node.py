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
