import uuid
from threading import Event
import time

class Node:
    """Base class for all nodes in the workflow"""
    node_type = "Generic Node"    # Name shown in the UI
    category = "Uncategorized"    # Category for node menu grouping
    
    # Default dimensions
    default_width = 220
    default_height = 150
    
    def __init__(self, canvas, x=100, y=100, title=None, width=None, height=None):
        self.canvas = canvas
        self.workflow = canvas.workflow
        self.x = x
        self.y = y
        self.width = width or self.default_width
        self.height = height or self.default_height
        self.title = title or self.node_type
        self.id = str(uuid.uuid4())
        
        # Styling properties
        self.border_width = 2
        self.header_height = 30
        self.socket_margin = 20
        
        # State flags
        self.selected = False
        self.dragging = False
        self.resizing = False
        self.dirty = True
        self.processing = False
        
        # Canvas item references
        self.canvas_items = []
        
        # Processing state
        self.output_cache = {}
        self.output_timestamp = None
        self.processing_complete_event = Event()
        self.processing_complete_event.set()  # Initially not processing
        self.processing_error = None
        self.status = "Ready"
        
        # Initialize properties from class definition
        self._init_properties()
        
        # Initialize sockets
        self.inputs = []
        self.outputs = []
        self.init_sockets()
    
    def _init_properties(self):
        """Initialize properties from class definition"""
        if hasattr(self.__class__, 'properties'):
            for name, config in self.__class__.properties.items():
                # Set default value on instance
                setattr(self, name, config.get('default', None))
    
    def init_sockets(self):
        """Initialize input and output sockets. Override in subclasses."""
        pass
    
    def process(self):
        """
        Process this node, getting inputs from connected nodes,
        and returning outputs.
        """
        # If already processing, don't start again
        if self.processing:
            return self.output_cache or {}
        
        # If not dirty and we have cached output, return it
        if not self.dirty and self.output_cache and not self.workflow.force_recompute:
            return self.output_cache
        
        # Set processing state
        self.processing = True
        self.processing_error = None
        self.processing_complete_event.clear()
        self.status = "Processing..."
        self.draw()
        
        try:
            # Wait for all input nodes to complete processing
            self.wait_for_input_nodes()
            
            # Execute the actual node-specific processing logic
            result = self.execute()
            
            # For nodes that don't process asynchronously, mark as complete
            if not getattr(self, 'is_async_node', False):
                # Store results in cache
                self.output_cache = result
                self.output_timestamp = time.time()
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
            if not getattr(self, 'is_async_node', False):
                self.processing = False
                self.processing_complete_event.set()
                self.draw()
    
    def execute(self):
        """
        Override this method in subclasses to implement node-specific processing logic.
        Returns a dictionary mapping output socket names to values.
        """
        return {}
    
    def draw(self):
        """Request the canvas to redraw this node"""
        if hasattr(self.canvas, 'redraw_node'):
            self.canvas.redraw_node(self)
    
    def wait_for_input_nodes(self, timeout=60):
        """Wait for all input nodes to complete processing"""
        input_nodes = []
        
        # Collect all connected input nodes
        for socket in self.inputs:
            if socket.is_connected():
                source_node = socket.connected_to.node
                if source_node.processing:
                    input_nodes.append(source_node)
        
        # Wait for all input nodes to complete
        start_time = time.time()
        for node in input_nodes:
            remaining_timeout = max(0, timeout - (time.time() - start_time))
            if not node.processing_complete_event.wait(timeout=remaining_timeout):
                raise TimeoutError(f"Timed out waiting for input node '{node.title}' to complete")
    
    def get_input_value(self, input_name):
        """Get the value from a connected input socket, waiting if necessary"""
        for socket in self.inputs:
            if socket.name == input_name and socket.is_connected():
                # Get the connected output socket
                output_socket = socket.connected_to
                output_node = output_socket.node
                
                # Wait for the node to complete if it's processing
                if output_node.processing:
                    if not output_node.processing_complete_event.wait(timeout=60):
                        self.status = f"Timeout waiting for {output_node.title}"
                        raise TimeoutError(f"Timed out waiting for input from '{output_node.title}'")
                
                # If there was an error processing the input node, propagate it
                if output_node.processing_error:
                    self.status = f"Input error: {output_node.title}"
                    raise ValueError(f"Error in input node '{output_node.title}': {output_node.processing_error}")
                
                # Get the value from the output node
                output_values = output_node.output_cache
                if output_socket.name in output_values:
                    return output_values[output_socket.name]
        
        return None
    
    def mark_dirty(self):
        """Mark this node and all downstream nodes as needing recalculation"""
        if self.dirty:
            return  # Already marked
            
        self.dirty = True
        
        # Propagate to downstream nodes
        for output_socket in self.outputs:
            if output_socket.is_connected():
                output_socket.connected_to.node.mark_dirty()
    
    def clear_output(self):
        """Clear the cached output and mark node as dirty"""
        self.output_cache = {}
        self.output_timestamp = None
        self.dirty = True
        self.draw()
    
    def create_properties_ui(self, parent):
        """Create properties UI for this node"""
        from core.ui.properties import create_properties_panel
        return create_properties_panel(parent, self)
    
    def get_visible_properties(self):
        """Get properties that should be visible on the node face"""
        visible_props = {}
        
        if hasattr(self.__class__, 'properties'):
            for name, config in self.__class__.properties.items():
                ui_config = config.get('ui', {})
                if ui_config.get('preview_on_node', False):
                    value = getattr(self, name, None)
                    if value is not None:
                        preview_length = ui_config.get('preview_length', 20)
                        preview = str(value)
                        if len(preview) > preview_length:
                            preview = preview[:preview_length] + "..."
                        
                        visible_props[ui_config.get('label', name)] = preview
        
        return visible_props
    
    def on_select(self):
        """Called when the node is selected"""
        self.selected = True
        self.draw()
        self.show_properties()
    
    def on_deselect(self):
        """Called when the node is deselected"""
        self.selected = False
        self.draw()
    
    def show_properties(self):
        """Show property panel for this node"""
        if self.workflow and hasattr(self.workflow, 'show_node_properties'):
            self.workflow.show_node_properties(self)
