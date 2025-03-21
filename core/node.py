import uuid
from threading import Event
import time

class Node:
    """Base class for all nodes in the workflow"""
    node_type = "Generic Node"    # Name shown in the UI
    category = "Uncategorized"    # Category for node menu grouping
    
    # Registry of registered node types
    _registry = {}
    
    # Default dimensions
    default_width = 240
    default_height = 180
    min_width = 180
    min_height = 120
    
    @classmethod
    def register_node_type(cls, module_name):
        """Register this node class with the registry"""
        from core.node_registry import register_node_type
        register_node_type(cls)
        return cls
    
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
        self.resize_handle_size = 15
        
        # Section spacing and layout
        self.section_padding = 10
        self.section_spacing = 15
        self.socket_spacing = 25
        self.property_spacing = 20
        
        # State flags
        self.selected = False
        self.dragging = False
        self.resizing = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.resize_start_width = 0
        self.resize_start_height = 0
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
        
        # Property and output visibility tracking
        self.property_visibility = {}  # property_name -> should_show_on_node
        self.output_visibility = {}    # output_name -> should_show_on_node
        
        # Initialize property visibility from class definition
        if hasattr(self.__class__, 'properties'):
            for name, config in self.__class__.properties.items():
                ui_config = config.get('ui', {})
                self.property_visibility[name] = ui_config.get('preview_on_node', False)
        
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
        # Update status to show we're working
        self.status = "Processing..."
        self.draw()
        
        # If already processing, just return cached output or empty dict
        if self.processing:
            return self.output_cache or {}
        
        # If not dirty and we have cached output, return it
        if not self.dirty and self.output_cache and not self.workflow.force_recompute:
            self.status = "Complete"
            self.draw()
            return self.output_cache
        
        # Set processing state
        self.processing = True
        self.processing_error = None
        self.processing_complete_event.clear()
        
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
                
                # Initialize visibility for any new outputs
                for output_name in result.keys():
                    if output_name not in self.output_visibility:
                        self.output_visibility[output_name] = True
                
                # Update UI with the complete status
                self.canvas.after(0, self.draw)
                
            # Mark that this node has been processed
            self.workflow.node_processed = True
                
            return result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.processing_error = str(e)
            self.status = f"Error: {str(e)[:20]}..."
            
            # Update UI with the error status
            self.canvas.after(0, self.draw)
            
            return {}
            
        finally:
            # Only set processing complete for non-async nodes
            if not getattr(self, 'is_async_node', False):
                self.processing = False
                self.processing_complete_event.set()
                
                # Final UI update
                self.canvas.after(0, self.draw)
    
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
    
    def wait_for_input_nodes(self, timeout=600, path=None):
        """Wait for all input nodes to complete processing with cycle detection
        
        Args:
            timeout: Timeout in seconds (default: 600 seconds/10 minutes)
            path: Used internally for cycle detection
        """
        if path is None:
            path = []
        
        # Check for cycles
        if self in path:
            # Extract node titles for error message
            cycle_idx = path.index(self)
            cycle_path = [node.title for node in path[cycle_idx:]] + [self.title]
            cycle_str = " -> ".join(cycle_path)
            raise ValueError(f"Cyclic dependency detected: {cycle_str}")
        
        # Add this node to the path
        path.append(self)
        
        try:
            # First, identify all input nodes that need processing
            input_nodes = []
            
            for socket in self.inputs:
                if socket.is_connected():
                    source_node = socket.connected_to.node
                    # Only wait for nodes that are actually processing or dirty
                    if source_node.processing or source_node.dirty:
                        # Process the input node if it's dirty but not currently processing
                        if source_node.dirty and not source_node.processing:
                            # Start processing the node (will handle its own inputs)
                            source_node.process()
                        
                        # Add to list of nodes to wait for
                        input_nodes.append(source_node)
            
            # Wait for all input nodes to complete - with periodic UI updates
            start_time = time.time()
            for node in input_nodes:
                # Poll instead of blocking wait to keep UI responsive
                while node.processing and time.time() - start_time < timeout:
                    # Allow the UI to update
                    if hasattr(self.canvas, 'update_idletasks'):
                        self.canvas.update_idletasks()
                    
                    # Short sleep to prevent CPU spinning
                    time.sleep(0.1)
                    
                    # Update node visuals periodically
                    if time.time() % 1 < 0.1:  # Update roughly every second
                        self.draw()
                        node.draw()
                
                # If still processing after timeout
                if node.processing:
                    print(f"Warning: Node '{node.title}' is still processing after timeout")
                    # Don't raise error, just warn and continue
                
                # Check for errors
                if node.processing_error:
                    print(f"Warning: Error in input node '{node.title}': {node.processing_error}")
                    # Don't raise error, just warn and continue
        
        finally:
            # Remove this node from the path
            if path and path[-1] == self:
                path.pop()
    
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
        """Get properties that should be visible on the node face with no truncation"""
        visible_props = {}
        
        # Add regular properties with no truncation based on visibility settings
        if hasattr(self.__class__, 'properties'):
            for name, config in self.__class__.properties.items():
                ui_config = config.get('ui', {})
                # Use instance-level visibility setting
                if self.property_visibility.get(name, ui_config.get('preview_on_node', False)):
                    value = getattr(self, name, None)
                    if value is not None:
                        # Show full value with no truncation
                        visible_props[ui_config.get('label', name)] = str(value)
        
        # Add output cache to visible properties based on visibility settings
        if hasattr(self, 'output_cache') and self.output_cache:
            for key, value in self.output_cache.items():
                # Check if this output should be shown
                if self.output_visibility.get(key, True):
                    # Show full output value with no truncation
                    visible_props[f"Output: {key}"] = str(value)
        
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
            
    def contains_point(self, x, y):
        """Check if a point is inside this node"""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.height)
    
    def contains_header(self, x, y):
        """Check if a point is inside this node's header"""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.header_height)
    
    def contains_resize_handle(self, x, y):
        """Check if a point is inside the resize handle"""
        handle_x = self.x + self.width - self.resize_handle_size
        handle_y = self.y + self.height - self.resize_handle_size
        return (handle_x <= x <= self.x + self.width and
                handle_y <= y <= self.y + self.height)
    
    def start_drag(self, x, y):
        """Start dragging the node"""
        self.dragging = True
        self.drag_start_x = x
        self.drag_start_y = y
        
    def start_resize(self, x, y):
        """Start resizing the node"""
        self.resizing = True
        self.drag_start_x = x
        self.drag_start_y = y
        self.resize_start_width = self.width
        self.resize_start_height = self.height
    
    def calculate_min_height(self):
        """Calculate minimum height based on content to prevent overflow"""
        # Base height calculation
        min_height = self.header_height + self.section_padding * 2
        
        # Add height for inputs
        if self.inputs:
            min_height += 15  # section header
            min_height += len(self.inputs) * self.socket_spacing
            min_height += self.section_spacing
        
        # Add height for outputs
        if self.outputs:
            min_height += 15  # section header
            min_height += len(self.outputs) * self.socket_spacing
            min_height += self.section_spacing
        
        # Add height for properties section header
        visible_props = self.get_visible_properties()
        if visible_props:
            min_height += 15  # Properties section header
            
            # Estimate height for each property
            for label, value in visible_props.items():
                # Space for label
                min_height += 18
                
                # Estimate number of lines for value (with a maximum)
                max_width = self.width - 20
                words = str(value).split()
                line_count = 1
                current_line_width = 0
                
                for word in words:
                    word_width = len(word) * 7  # Approximate character width
                    if current_line_width + word_width < max_width:
                        current_line_width += word_width + 7  # Add space
                    else:
                        line_count += 1
                        current_line_width = word_width
                        if line_count >= 8:  # Limit to 8 lines max
                            break
                
                # Add height for value lines plus spacing
                min_height += line_count * 18 + 5
        
        # Add space for status
        min_height += 30
        
        # Ensure at least minimum height
        return max(min_height, self.min_height)
