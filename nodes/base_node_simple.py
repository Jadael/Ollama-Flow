from NodeGraphQt import BaseNode
import time
from threading import Event

class OllamaBaseNodeSimple(BaseNode):
    """Simplified base class for all Ollama nodes that uses minimal API features"""
    
    # Node identifier - should be overridden by subclasses
    __identifier__ = 'com.ollamaflow.nodes'
    
    # Node type - should be overridden by subclasses
    __type__ = 'OllamaBaseNodeSimple'
    
    # Node name - should be overridden by subclasses
    NODE_NAME = 'Base Node'
    
    def __init__(self):
        super(OllamaBaseNodeSimple, self).__init__()
        
        # Processing state
        self.processing = False
        self.dirty = True  # Needs processing
        self.output_cache = {}  # Cache for output values
        self.status = "Ready"
        self.processing_error = None
        self.is_async_node = False  # Flag for async processing nodes
        self.processing_complete_event = Event()
        self.processing_complete_event.set()  # Initially not processing
    
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
        
        # If already processing, just return
        if self.processing:
            return
        
        # If not dirty and we have cached output, return it
        if not self.dirty and self.output_cache:
            self.status = "Complete"
            return
        
        # Set processing state
        self.processing = True
        self.processing_error = None
        self.processing_complete_event.clear()
        
        try:
            # Execute the actual node-specific processing logic
            result = self.execute()
            
            # For synchronous nodes, update cache and state
            if not self.is_async_node:
                self.output_cache = result
                self.dirty = False
                self.status = "Complete"
            
            return result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.processing_error = str(e)
            self.status = f"Error: {str(e)[:20]}..."
            
            return {}
            
        finally:
            # Only set processing complete for non-async nodes
            if not self.is_async_node:
                self.processing = False
                self.processing_complete_event.set()
    
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
            if hasattr(connected_node, 'processing_complete_event'):
                timeout = 60  # 1 minute timeout
                if not connected_node.processing_complete_event.wait(timeout):
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
