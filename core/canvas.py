import customtkinter as ctk
import tkinter as tk
import math
from core.node_registry import get_all_node_categories, get_node_class

class NodeCanvas(ctk.CTkCanvas):
    """Canvas widget for drawing and interacting with nodes"""
    def __init__(self, master, workflow, **kwargs):
        super().__init__(master, **kwargs)
        self.workflow = workflow
        
        # State variables
        self.selected_node = None
        self.connecting_socket = None
        self.connecting_line = None
        self.mouse_x = 0
        self.mouse_y = 0
        
        # Pan and zoom state variables
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.panning = False
        self.last_pan_x = 0
        self.last_pan_y = 0
        
        # Store text widgets to avoid garbage collection
        self.textbox_widgets = {}
        
        # Bind events
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Motion>", self.on_motion)
        
        # Bind zoom and pan events
        self.bind("<Button-2>", self.start_pan)         # Middle mouse button to start panning
        self.bind("<B2-Motion>", self.pan_canvas)       # Middle mouse drag to pan
        self.bind("<ButtonRelease-2>", self.end_pan)    # Middle mouse release to end panning
        
        # Mouse wheel for zooming (platform-specific)
        self.bind("<MouseWheel>", self.zoom_canvas)     # Windows
        self.bind("<Button-4>", self.zoom_in)           # Linux (scroll up)
        self.bind("<Button-5>", self.zoom_out)          # Linux (scroll down)
        
        # Keyboard shortcuts
        self.bind("<Control-equal>", self.zoom_in)      # Ctrl + "+" to zoom in
        self.bind("<Control-minus>", self.zoom_out)     # Ctrl + "-" to zoom out
        self.bind("<Control-0>", self.reset_zoom)       # Ctrl + "0" to reset zoom
        
        # Create a right-click menu - will be populated dynamically
        self.context_menu = tk.Menu(self, tearoff=0)
        self.bind("<Button-3>", self.show_context_menu)
        
        # Add information text
        self.status_text_id = self.create_text(
            10, 10, 
            text="Zoom: 100% | Pan: 0, 0",
            anchor="nw",
            fill="#AAA", 
            tags=("status_text")
        )
    
    def world_to_canvas(self, world_x, world_y):
        """Convert world coordinates to canvas coordinates"""
        canvas_x = world_x * self.zoom + self.pan_x
        canvas_y = world_y * self.zoom + self.pan_y
        return canvas_x, canvas_y
    
    def canvas_to_world(self, canvas_x, canvas_y):
        """Convert canvas coordinates to world coordinates"""
        world_x = (canvas_x - self.pan_x) / self.zoom
        world_y = (canvas_y - self.pan_y) / self.zoom
        return world_x, world_y
    
    def start_pan(self, event):
        """Start panning the canvas"""
        self.panning = True
        self.last_pan_x = event.x
        self.last_pan_y = event.y
        self.config(cursor="fleur")  # Change cursor to indicate panning
    
    def pan_canvas(self, event):
        """Pan the canvas"""
        if not self.panning:
            return
        
        # Calculate how much to move
        dx = event.x - self.last_pan_x
        dy = event.y - self.last_pan_y
        
        # Update pan position
        self.pan_x += dx
        self.pan_y += dy
        
        # Update last position
        self.last_pan_x = event.x
        self.last_pan_y = event.y
        
        # Redraw everything
        self.redraw_all()
    
    def end_pan(self, event):
        """End panning operation"""
        self.panning = False
        self.config(cursor="")  # Reset cursor
    
    def zoom_canvas(self, event):
        """Zoom the canvas (Windows/macOS)"""
        # Get the current mouse position in world coordinates 
        world_x, world_y = self.canvas_to_world(event.x, event.y)
        
        # Determine zoom direction
        if event.delta > 0:
            self.zoom *= 1.1  # Zoom in
        else:
            self.zoom *= 0.9  # Zoom out
        
        # Limit zoom level
        self.zoom = max(0.1, min(self.zoom, 5.0))
        
        # Adjust pan to zoom toward mouse position
        new_canvas_x, new_canvas_y = self.world_to_canvas(world_x, world_y)
        self.pan_x += event.x - new_canvas_x
        self.pan_y += event.y - new_canvas_y
        
        # Redraw everything
        self.redraw_all()
    
    def zoom_in(self, event=None):
        """Zoom in on the canvas"""
        # Get center of view if no event provided
        if event:
            x, y = event.x, event.y
        else:
            x = self.winfo_width() // 2
            y = self.winfo_height() // 2
            
        # Get world coordinates of center
        world_x, world_y = self.canvas_to_world(x, y)
        
        # Zoom in
        self.zoom *= 1.1
        
        # Limit zoom level
        self.zoom = min(self.zoom, 5.0)
        
        # Adjust pan to zoom toward center point
        new_canvas_x, new_canvas_y = self.world_to_canvas(world_x, world_y)
        self.pan_x += x - new_canvas_x
        self.pan_y += y - new_canvas_y
        
        # Redraw everything
        self.redraw_all()
    
    def zoom_out(self, event=None):
        """Zoom out on the canvas"""
        # Get center of view if no event provided
        if event:
            x, y = event.x, event.y
        else:
            x = self.winfo_width() // 2
            y = self.winfo_height() // 2
            
        # Get world coordinates of center
        world_x, world_y = self.canvas_to_world(x, y)
        
        # Zoom out
        self.zoom *= 0.9
        
        # Limit zoom level
        self.zoom = max(0.1, self.zoom)
        
        # Adjust pan to zoom toward center point
        new_canvas_x, new_canvas_y = self.world_to_canvas(world_x, world_y)
        self.pan_x += x - new_canvas_x
        self.pan_y += y - new_canvas_y
        
        # Redraw everything
        self.redraw_all()
    
    def reset_zoom(self, event=None):
        """Reset zoom to 100% and center view"""
        center_x = self.winfo_width() // 2
        center_y = self.winfo_height() // 2
        
        # Get world coordinates of center
        world_x, world_y = self.canvas_to_world(center_x, center_y)
        
        # Reset zoom
        self.zoom = 1.0
        
        # Center view on nodes or just reset pan
        if self.workflow.nodes:
            # Calculate bounding box of all nodes
            min_x = min(node.x for node in self.workflow.nodes)
            min_y = min(node.y for node in self.workflow.nodes)
            max_x = max(node.x + node.width for node in self.workflow.nodes)
            max_y = max(node.y + node.height for node in self.workflow.nodes)
            
            # Calculate center of the bounding box
            center_world_x = (min_x + max_x) / 2
            center_world_y = (min_y + max_y) / 2
            
            # Set pan to center the view on the nodes
            self.pan_x = center_x - center_world_x
            self.pan_y = center_y - center_world_y
        else:
            # Just reset pan
            self.pan_x = 0
            self.pan_y = 0
        
        # Redraw everything
        self.redraw_all()
    
    def redraw_all(self):
        """Redraw all nodes and update status text"""
        # Cleanup any orphaned textbox widgets
        self._cleanup_textbox_widgets()
        
        # Update status text
        zoom_percent = int(self.zoom * 100)
        status_text = f"Zoom: {zoom_percent}% | Pan: {int(self.pan_x)}, {int(self.pan_y)}"
        self.itemconfig(self.status_text_id, text=status_text)
        
        # Redraw each node
        for node in self.workflow.nodes:
            self.redraw_node(node)
    
    def _cleanup_textbox_widgets(self):
        """Clean up textbox widgets that are no longer needed"""
        # Get all current node IDs
        current_nodes = {node.id for node in self.workflow.nodes}
        
        # Clean up widgets for nodes that no longer exist
        for node_id in list(self.textbox_widgets.keys()):
            if node_id not in current_nodes:
                # Destroy all textboxes for this node
                for textbox in self.textbox_widgets[node_id].values():
                    textbox.destroy()
                # Remove from storage
                del self.textbox_widgets[node_id]
    
    def show_context_menu(self, event):
        """Show the context menu at the cursor position"""
        self.mouse_x, self.mouse_y = self.canvas_to_world(event.x, event.y)
        
        # Clear the existing menu
        self.context_menu.delete(0, tk.END)
        
        # Get all node categories
        node_categories = get_all_node_categories()
        
        # Add categories as cascading menus
        for category, node_classes in node_categories.items():
            # Skip empty categories
            if not node_classes:
                continue
                
            # Create submenu for this category
            category_menu = tk.Menu(self.context_menu, tearoff=0)
            
            # Add nodes in this category
            for node_class in sorted(node_classes, key=lambda cls: cls.node_type):
                category_menu.add_command(
                    label=f"Add {node_class.node_type}", 
                    command=lambda cls=node_class: self.add_node_at_cursor(cls)
                )
            
            # Add submenu to main context menu
            self.context_menu.add_cascade(label=category, menu=category_menu)
        
        # Add a separator and Delete option
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete Selected Node", command=self.delete_selected_node)
        
        # Add zoom controls
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Zoom In", command=self.zoom_in)
        self.context_menu.add_command(label="Zoom Out", command=self.zoom_out)
        self.context_menu.add_command(label="Reset View", command=self.reset_zoom)
        
        # Show the menu
        self.context_menu.post(event.x_root, event.y_root)
    
    def add_node_at_cursor(self, node_class):
        """Add a new node at the cursor position"""
        node = node_class(self, x=self.mouse_x, y=self.mouse_y)
        self.workflow.add_node(node)
        self.redraw_node(node)
    
    def delete_selected_node(self):
        """Delete the currently selected node"""
        if self.selected_node:
            # Clean up any textbox widgets for this node
            if self.selected_node.id in self.textbox_widgets:
                for textbox in self.textbox_widgets[self.selected_node.id].values():
                    textbox.destroy()
                del self.textbox_widgets[self.selected_node.id]
            
            # Delete the node from the workflow
            self.workflow.delete_node(self.selected_node)
    
    def on_click(self, event):
        """Handle mouse click events with resize handle check"""
        # Convert canvas coordinates to world coordinates
        world_x, world_y = self.canvas_to_world(event.x, event.y)
        self.mouse_x, self.mouse_y = world_x, world_y
        
        # Check if we clicked on a socket
        socket = self.find_socket_at(world_x, world_y)
        if socket:
            # Start connection creation from this socket
            self.connecting_socket = socket
            # Create line in canvas coordinates
            canvas_x, canvas_y = self.world_to_canvas(*socket.position)
            self.connecting_line = self.create_line(
                canvas_x, canvas_y,
                event.x, event.y,
                fill=socket.color, width=2, dash=(4, 4)
            )
            return
        
        # Check if we clicked on a node
        node = self.find_node_at(world_x, world_y)
        
        # Deselect previous node
        if self.selected_node and (not node or node != self.selected_node):
            # Clean up any canvas items that might be lingering
            if hasattr(self.selected_node, 'canvas_items'):
                for item_id in list(self.selected_node.canvas_items):
                    if not self.type(item_id):  # Check if item still exists
                        self.selected_node.canvas_items.remove(item_id)
                        
            self.selected_node.on_deselect()
        
        # Select and handle the clicked node
        if node:
            self.selected_node = node
            node.on_select()
            
            # Check if we clicked on the resize handle
            if node.contains_resize_handle(world_x, world_y):
                node.start_resize(world_x, world_y)
            # Check if we clicked on the header (to drag)
            elif node.contains_header(world_x, world_y):
                node.start_drag(world_x, world_y)
        else:
            # Clicked on empty space
            self.selected_node = None
            # Clear properties panel
            self.workflow.show_node_properties(None)
            
        # Clean up any stale canvas items (ghost nodes)
        self.cleanup_canvas_items()
    
    def cleanup_canvas_items(self):
        """Clean up any stale canvas items"""
        # Get all canvas items
        all_items = self.find_all()
        
        # Check each item
        for item_id in all_items:
            # Skip items with no tags
            if not self.gettags(item_id):
                continue
                
            # Get the tags for this item
            tags = self.gettags(item_id)
            
            # Check if this item belongs to a node
            node_id = None
            for tag in tags:
                # Look for node IDs (UUID format)
                if len(tag) > 30 and "-" in tag:
                    node_id = tag
                    break
            
            if node_id:
                # Check if this node ID still exists in our workflow
                node_exists = False
                for node in self.workflow.nodes:
                    if node.id == node_id:
                        node_exists = True
                        # Check if this item is in the node's canvas_items list
                        if item_id not in node.canvas_items:
                            node.canvas_items.append(item_id)
                        break
                
                # If no node with this ID exists, delete the item
                if not node_exists:
                    self.delete(item_id)

    def on_drag(self, event):
        """Handle mouse drag events with improved connection handling"""
        # Convert canvas coordinates to world coordinates for node operations
        world_x, world_y = self.canvas_to_world(event.x, event.y)
        
        if self.connecting_socket and self.connecting_line:
            # Update the temporary connection line (in canvas coordinates)
            canvas_socket_x, canvas_socket_y = self.world_to_canvas(*self.connecting_socket.position)
            self.coords(
                self.connecting_line,
                canvas_socket_x, canvas_socket_y,
                event.x, event.y
            )
        elif self.selected_node:
            if self.selected_node.resizing:
                # Resize the node (in world coordinates)
                new_width = max(self.selected_node.resize_start_width + (world_x - self.selected_node.drag_start_x), 
                                self.selected_node.min_width)
                new_height = max(self.selected_node.resize_start_height + (world_y - self.selected_node.drag_start_y), 
                                self.selected_node.min_height)
                
                # Update node dimensions
                self.selected_node.width = new_width
                self.selected_node.height = new_height
                
                # Redraw the node
                self.redraw_node(self.selected_node)
                
            elif self.selected_node.dragging:
                # Drag the selected node (in world coordinates)
                dx = world_x - self.selected_node.drag_start_x
                dy = world_y - self.selected_node.drag_start_y
                self.selected_node.x += dx
                self.selected_node.y += dy
                self.selected_node.drag_start_x = world_x
                self.selected_node.drag_start_y = world_y
                
                # Redraw this node and all connected nodes to update connections properly
                self.redraw_node(self.selected_node)
    
    def on_release(self, event):
        """Handle mouse release events with resizing support"""
        # Convert canvas coordinates to world coordinates
        world_x, world_y = self.canvas_to_world(event.x, event.y)
        
        if self.connecting_socket and self.connecting_line:
            # Check if we're over another socket (using world coordinates)
            target_socket = self.find_socket_at(world_x, world_y)
            
            if target_socket and target_socket != self.connecting_socket:
                # Try to create a connection
                if self.connecting_socket.is_input != target_socket.is_input:
                    # Determine input and output sockets
                    if self.connecting_socket.is_input:
                        input_socket, output_socket = self.connecting_socket, target_socket
                    else:
                        input_socket, output_socket = target_socket, self.connecting_socket
                    
                    # Make the connection
                    if input_socket.connect(output_socket):
                        # Redraw the nodes to show the connection
                        self.redraw_node(input_socket.node)
                        if output_socket.node != input_socket.node:
                            self.redraw_node(output_socket.node)
            
            # Remove the temporary line
            self.delete(self.connecting_line)
            self.connecting_line = None
            self.connecting_socket = None
        
        # End any node dragging or resizing
        if self.selected_node:
            self.selected_node.dragging = False
            self.selected_node.resizing = False
    
    def on_motion(self, event):
        """Handle mouse motion events (hover effects)"""
        # Convert canvas coordinates to world coordinates
        world_x, world_y = self.canvas_to_world(event.x, event.y)
        
        socket = self.find_socket_at(world_x, world_y)
        
        # Reset hover state for all sockets
        for node in self.workflow.nodes:
            for s in node.inputs + node.outputs:
                if s.hover:
                    s.hover = False
                    # Find and update the socket display
                    for item_id in self.find_withtag(s.id):
                        if "socket" in self.gettags(item_id):
                            self.itemconfig(item_id, fill="#2a2a2a")
        
        # Set hover state for the socket under cursor
        if socket:
            socket.hover = True
            # Highlight the socket
            for item_id in self.find_withtag(socket.id):
                if "socket" in self.gettags(item_id):
                    self.itemconfig(item_id, fill=socket.color)
    
    def find_node_at(self, x, y):
        """Find the topmost node at the given coordinates (in world space)"""
        # Check all nodes in reverse order (so top nodes are found first)
        for node in reversed(self.workflow.nodes):
            if hasattr(node, 'contains_point') and node.contains_point(x, y):
                return node
        return None
    
    def find_socket_at(self, x, y):
        """Find the socket at the given coordinates (in world space)"""
        # Check all nodes in reverse order
        for node in reversed(self.workflow.nodes):
            for socket in node.inputs + node.outputs:
                if socket.contains_point(x, y):
                    return socket
        return None
    
    def redraw_node(self, node):
        """Clear and redraw a node on the canvas with embedded textboxes for properties"""
        # Track connected nodes so we can redraw them later
        connected_nodes = set()
        
        # Find connected nodes before deletion
        for socket in node.inputs + node.outputs:
            if socket.is_connected():
                connected_socket = socket.connected_to
                if connected_socket and connected_socket.node:
                    connected_nodes.add(connected_socket.node)
        
        # Delete all items associated with THIS node (not connections yet)
        for item_id in node.canvas_items:
            self.delete(item_id)
        node.canvas_items = []
        
        # Delete all connection lines connected to this node
        for item_id in self.find_withtag("connection"):
            tags = self.gettags(item_id)
            for socket in node.inputs + node.outputs:
                if socket.id in tags:
                    self.delete(item_id)
        
        # Draw node body
        self._draw_node_body(node)
        
        # Draw node header
        self._draw_node_header(node)
        
        # Draw sockets
        self._draw_node_sockets(node)
        
        # Draw node status
        self._draw_node_status(node)
        
        # Draw node content with embedded text widgets
        self._draw_node_content(node)
        
        # Redraw ALL connected nodes to fix all connections
        for connected_node in connected_nodes:
            # Only need to redraw connections, not the whole node
            self._draw_node_connections(connected_node)
        
        # Draw connections for this node
        self._draw_node_connections(node)
    
    def _draw_node_body(self, node):
        """Draw the main body of the node"""
        # Apply zoom and pan to node coordinates
        canvas_x, canvas_y = self.world_to_canvas(node.x, node.y)
        canvas_width = node.width * self.zoom
        canvas_height = node.height * self.zoom
        canvas_header_height = node.header_height * self.zoom
        
        fill_color = "#2a2a2a" if not node.selected else "#3a3a3a"
        body_width = max(1, node.border_width * self.zoom)  # Scale border width but ensure at least 1px
        body_id = self.create_rectangle(
            canvas_x, canvas_y + canvas_header_height, 
            canvas_x + canvas_width, canvas_y + canvas_height,
            fill=fill_color, outline="#555", width=body_width,
            tags=("node", node.id)
        )
        node.canvas_items.append(body_id)
        
        # Add resize handle to bottom right corner
        handle_size = node.resize_handle_size * self.zoom
        handle_x = canvas_x + canvas_width - handle_size
        handle_y = canvas_y + canvas_height - handle_size
        
        # Draw resize handle lines
        handle_line1 = self.create_line(
            handle_x, canvas_y + canvas_height,
            canvas_x + canvas_width, handle_y,
            fill="#888", width=max(1, self.zoom),
            tags=("resize_handle", node.id)
        )
        node.canvas_items.append(handle_line1)
        
        handle_line2 = self.create_line(
            handle_x + handle_size // 2, canvas_y + canvas_height,
            canvas_x + canvas_width, handle_y + handle_size // 2,
            fill="#888", width=max(1, self.zoom),
            tags=("resize_handle", node.id)
        )
        node.canvas_items.append(handle_line2)
    
    def _draw_node_header(self, node):
        """Draw the node header with title"""
        # Apply zoom and pan to coordinates
        canvas_x, canvas_y = self.world_to_canvas(node.x, node.y)
        canvas_width = node.width * self.zoom
        canvas_header_height = node.header_height * self.zoom
        body_width = max(1, node.border_width * self.zoom)
        
        header_id = self.create_rectangle(
            canvas_x, canvas_y, 
            canvas_x + canvas_width, canvas_y + canvas_header_height,
            fill="#1E90FF", outline="#555", width=body_width,
            tags=("node_header", node.id)
        )
        node.canvas_items.append(header_id)
        
        # Scale font size proportionally with zoom
        font_size = int(10 * self.zoom)
        
        title_id = self.create_text(
            canvas_x + 10 * self.zoom, canvas_y + canvas_header_height / 2,
            text=node.title, fill="white", anchor="w",
            font=("Helvetica", font_size),
            tags=("node_title", node.id)
        )
        node.canvas_items.append(title_id)
    
    def _draw_node_sockets(self, node):
        """Draw input and output sockets with better organization"""
        # Apply zoom and pan to coordinates
        canvas_x, canvas_y = self.world_to_canvas(node.x, node.y)
        canvas_header_height = node.header_height * self.zoom
        canvas_section_padding = node.section_padding * self.zoom
        canvas_socket_spacing = node.socket_spacing * self.zoom
        canvas_section_spacing = node.section_spacing * self.zoom
        
        # Calculate vertical starting position
        y_pos = canvas_y + canvas_header_height + canvas_section_padding
        
        # Scale font size based on zoom
        section_font_size = int(8 * self.zoom)
        label_font_size = int(9 * self.zoom)
        
        # Draw "Inputs" section header if there are inputs
        if node.inputs:
            section_id = self.create_text(
                canvas_x + 10 * self.zoom, y_pos,
                text="INPUTS", fill="#888", anchor="w",
                font=("Helvetica", section_font_size),
                tags=("section_header", node.id)
            )
            node.canvas_items.append(section_id)
            y_pos += 15 * self.zoom  # Add space after section header
            
            # Draw input sockets
            for i, socket in enumerate(node.inputs):
                # Store socket position in world coordinates
                socket_world_x = node.x
                socket_world_y = (y_pos - canvas_y) / self.zoom + node.y
                socket.position = (socket_world_x, socket_world_y)
                
                # Calculate socket position in canvas coordinates
                socket_canvas_x, socket_canvas_y = canvas_x, y_pos
                
                # Adjust socket radius based on zoom
                socket_radius = socket.radius * self.zoom
                
                # Socket circle
                fill_color = socket.color if socket.hover else "#2a2a2a"
                socket_id = self.create_oval(
                    socket_canvas_x - socket_radius, socket_canvas_y - socket_radius,
                    socket_canvas_x + socket_radius, socket_canvas_y + socket_radius,
                    fill=fill_color, outline="#AAA",
                    tags=("socket", "input_socket", socket.id, node.id)
                )
                node.canvas_items.append(socket_id)
                
                # Socket label
                label_id = self.create_text(
                    socket_canvas_x + socket_radius + 5 * self.zoom, socket_canvas_y,
                    text=socket.name, fill="white", anchor="w",
                    font=("Helvetica", label_font_size),
                    tags=("socket_label", node.id)
                )
                node.canvas_items.append(label_id)
                
                y_pos += canvas_socket_spacing
            
            # Add section divider
            y_pos += canvas_section_spacing - canvas_socket_spacing
            divider_id = self.create_line(
                canvas_x + 10 * self.zoom, y_pos - canvas_section_spacing // 2,
                canvas_x + node.width * self.zoom - 10 * self.zoom, y_pos - canvas_section_spacing // 2,
                fill="#555", dash=(4, 4),
                tags=("section_divider", node.id)
            )
            node.canvas_items.append(divider_id)
        
        # Draw "Outputs" section if there are outputs
        if node.outputs:
            section_id = self.create_text(
                canvas_x + 10 * self.zoom, y_pos,
                text="OUTPUTS", fill="#888", anchor="w",
                font=("Helvetica", section_font_size),
                tags=("section_header", node.id)
            )
            node.canvas_items.append(section_id)
            y_pos += 15 * self.zoom  # Add space after section header
            
            # Draw output sockets
            for i, socket in enumerate(node.outputs):
                # Store socket position in world coordinates
                socket_world_x = node.x + node.width
                socket_world_y = (y_pos - canvas_y) / self.zoom + node.y
                socket.position = (socket_world_x, socket_world_y)
                
                # Calculate socket position in canvas coordinates
                socket_canvas_x, socket_canvas_y = canvas_x + node.width * self.zoom, y_pos
                
                # Adjust socket radius based on zoom
                socket_radius = socket.radius * self.zoom
                
                # Socket circle
                fill_color = socket.color if socket.hover else "#2a2a2a"
                socket_id = self.create_oval(
                    socket_canvas_x - socket_radius, socket_canvas_y - socket_radius,
                    socket_canvas_x + socket_radius, socket_canvas_y + socket_radius,
                    fill=fill_color, outline="#AAA",
                    tags=("socket", "output_socket", socket.id, node.id)
                )
                node.canvas_items.append(socket_id)
                
                # Socket label
                label_id = self.create_text(
                    socket_canvas_x - socket_radius - 5 * self.zoom, socket_canvas_y,
                    text=socket.name, fill="white", anchor="e",
                    font=("Helvetica", label_font_size),
                    tags=("socket_label", node.id)
                )
                node.canvas_items.append(label_id)
                
                y_pos += canvas_socket_spacing
            
            # Add section divider for properties
            y_pos += canvas_section_spacing - canvas_socket_spacing
            divider_id = self.create_line(
                canvas_x + 10 * self.zoom, y_pos - canvas_section_spacing // 2,
                canvas_x + node.width * self.zoom - 10 * self.zoom, y_pos - canvas_section_spacing // 2,
                fill="#555", dash=(4, 4),
                tags=("section_divider", node.id)
            )
            node.canvas_items.append(divider_id)
    
    def _draw_node_status(self, node):
        """Draw node status information"""
        # Apply zoom and pan to coordinates
        canvas_x, canvas_y = self.world_to_canvas(node.x, node.y)
        canvas_height = node.height * self.zoom
        
        # Scale font size with zoom
        font_size = int(9 * self.zoom)
        
        status_color = "#AAA"  # Default gray
        if "Processing" in node.status or "Generating" in node.status:
            status_color = "#F0AD4E"  # Orange for active
        elif "Complete" in node.status:
            status_color = "#5CB85C"  # Green for complete
        elif "Error" in node.status:
            status_color = "#D9534F"  # Red for error
        
        status_id = self.create_text(
            canvas_x + 10 * self.zoom, canvas_y + canvas_height - 20 * self.zoom,
            text=f"Status: {node.status}", fill=status_color, anchor="w",
            font=("Helvetica", font_size),
            tags=("node_status", node.id)
        )
        node.canvas_items.append(status_id)
    
    def _draw_node_content(self, node):
        """Draw node content using a combination of text and embedded CTkTextbox widgets"""
        # Apply zoom and pan to coordinates
        canvas_x, canvas_y = self.world_to_canvas(node.x, node.y)
        canvas_width = node.width * self.zoom
        canvas_height = node.height * self.zoom
        canvas_header_height = node.header_height * self.zoom
        canvas_section_padding = node.section_padding * self.zoom
        canvas_section_spacing = node.section_spacing * self.zoom
        
        # Scale font size with zoom
        section_font_size = int(8 * self.zoom)
        label_font_size = int(9 * self.zoom)
        
        # Get visible properties to show on the node
        visible_props = node.get_visible_properties()
        
        # Initialize storage for this node if not exists
        if node.id not in self.textbox_widgets:
            self.textbox_widgets[node.id] = {}
        
        # Clean up existing widgets that might not be needed anymore
        for key in list(self.textbox_widgets[node.id].keys()):
            if key not in [f"{label}" for label in visible_props.keys()]:
                # This property is no longer visible, destroy its widget
                self.textbox_widgets[node.id][key].destroy()
                del self.textbox_widgets[node.id][key]
        
        if visible_props:
            # Calculate y position after inputs and outputs
            y_pos = canvas_y + canvas_header_height + canvas_section_padding
            
            # Skip past inputs section if there are inputs
            if node.inputs:
                y_pos += 15 * self.zoom  # section header
                y_pos += len(node.inputs) * node.socket_spacing * self.zoom
                y_pos += canvas_section_spacing
            
            # Skip past outputs section if there are outputs
            if node.outputs:
                y_pos += 15 * self.zoom  # section header
                y_pos += len(node.outputs) * node.socket_spacing * self.zoom
                y_pos += canvas_section_spacing
            
            # Draw "Properties" section header
            section_id = self.create_text(
                canvas_x + 10 * self.zoom, y_pos,
                text="PROPERTIES", fill="#888", anchor="w",
                font=("Helvetica", section_font_size),
                tags=("section_header", node.id)
            )
            node.canvas_items.append(section_id)
            y_pos += 15 * self.zoom  # Add space after section header
            
            # Calculate available height for properties
            status_bar_height = 30 * self.zoom
            max_y_pos = canvas_y + canvas_height - status_bar_height
            remaining_height = max_y_pos - y_pos
            
            # Analyze properties to determine optimal layout
            prop_count = len(visible_props)
            
            # Categorize properties by size
            single_line_props = {}
            multi_line_props = {}
            
            for label, value in visible_props.items():
                value_str = str(value)
                lines = value_str.split('\n')
                if len(lines) == 1 and len(value_str) < 30:
                    # Short single-line property
                    single_line_props[label] = value_str
                else:
                    # Multi-line or long property
                    multi_line_props[label] = value_str
            
            # Calculate heights
            single_line_height = 26 * self.zoom  # Compact height for single line
            
            # If remaining space is limited, make multi-line items smaller
            available_per_multi = 0
            if len(multi_line_props) > 0:
                # Calculate space after accounting for single-line props
                space_for_multi = remaining_height - (len(single_line_props) * (single_line_height + 5 * self.zoom))
                available_per_multi = max(60 * self.zoom, space_for_multi / len(multi_line_props))
            
            # Draw all properties
            for label, value in visible_props.items():
                value_str = str(value)
                
                # Use different color for output properties
                is_output = label.startswith("Output:")
                bg_color = "#2d4a2d" if is_output else "#2d3a4a"  # Dark green for outputs, dark blue for properties
                
                # Check if this is a single-line or multi-line property
                is_single_line = label in single_line_props
                
                # Set frame height based on property type
                if is_single_line:
                    frame_height = single_line_height
                    textbox_height = int(single_line_height - 6 * self.zoom)
                else:
                    frame_height = min(available_per_multi, 120 * self.zoom)
                    textbox_height = int(frame_height - 6 * self.zoom)
                
                # Check if we'll overflow past max_y_pos
                if y_pos + frame_height > max_y_pos:
                    # We don't have enough space, adjust height
                    frame_height = max(single_line_height, max_y_pos - y_pos - 5 * self.zoom)
                    textbox_height = int(frame_height - 6 * self.zoom)
                
                # Create a frame for this property
                frame_width = canvas_width - 20 * self.zoom
                
                # For single-line properties, create a more compact display
                if is_single_line:
                    # Create background rectangle
                    frame_id = self.create_rectangle(
                        canvas_x + 10 * self.zoom,
                        y_pos,
                        canvas_x + 10 * self.zoom + frame_width,
                        y_pos + frame_height,
                        fill=bg_color,
                        outline="#555",
                        tags=("property_frame", node.id)
                    )
                    node.canvas_items.append(frame_id)
                    
                    # Draw label and value side by side
                    label_id = self.create_text(
                        canvas_x + 15 * self.zoom,
                        y_pos + frame_height/2,
                        text=f"{label}:",
                        fill="#DDD",
                        anchor="w",
                        font=("Helvetica", label_font_size, "bold"),
                        tags=("property_label", node.id)
                    )
                    node.canvas_items.append(label_id)
                    
                    # Add value text directly on canvas for single-line properties
                    value_id = self.create_text(
                        canvas_x + frame_width - 10 * self.zoom,
                        y_pos + frame_height/2,
                        text=value_str,
                        fill="#FFF",
                        anchor="e",
                        font=("Helvetica", label_font_size),
                        tags=("property_value", node.id)
                    )
                    node.canvas_items.append(value_id)
                    
                    # Remove any existing textbox for this property
                    if label in self.textbox_widgets[node.id]:
                        self.textbox_widgets[node.id][label].destroy()
                        del self.textbox_widgets[node.id][label]
                    
                else:
                    # Multi-line property - use textbox widget
                    # Create frame
                    frame_id = self.create_rectangle(
                        canvas_x + 10 * self.zoom,
                        y_pos,
                        canvas_x + 10 * self.zoom + frame_width,
                        y_pos + frame_height,
                        fill=bg_color,
                        outline="#555",
                        tags=("property_frame", node.id)
                    )
                    node.canvas_items.append(frame_id)
                    
                    # Create label
                    label_id = self.create_text(
                        canvas_x + 15 * self.zoom,
                        y_pos + 3 * self.zoom,
                        text=label,
                        fill="#DDD",
                        anchor="nw",
                        font=("Helvetica", label_font_size, "bold"),
                        tags=("property_label", node.id)
                    )
                    node.canvas_items.append(label_id)
                    
                    # Check if we need to create a new textbox or update an existing one
                    if label not in self.textbox_widgets[node.id]:
                        # Create textbox
                        textbox = ctk.CTkTextbox(
                            self,
                            width=int(frame_width - 10 * self.zoom),
                            height=textbox_height,
                            fg_color=bg_color,
                            text_color="#FFF",
                            corner_radius=0,
                            border_width=0,
                            font=("Helvetica", max(8, int(8 * self.zoom)))
                        )
                        self.textbox_widgets[node.id][label] = textbox
                        
                        # Set text
                        textbox.insert("1.0", value_str)
                        textbox.configure(state="disabled")
                    else:
                        # Update existing textbox
                        textbox = self.textbox_widgets[node.id][label]
                        textbox.configure(
                            width=int(frame_width - 10 * self.zoom),
                            height=textbox_height,
                            font=("Helvetica", max(8, int(8 * self.zoom)))
                        )
                        
                        # Update text
                        textbox.configure(state="normal")
                        textbox.delete("1.0", "end")
                        textbox.insert("1.0", value_str)
                        textbox.configure(state="disabled")
                    
                    # Create window for textbox
                    window_id = self.create_window(
                        canvas_x + 15 * self.zoom,
                        y_pos + 20 * self.zoom,  # Below the label
                        window=textbox,
                        anchor="nw",
                        tags=("property_textbox", node.id)
                    )
                    node.canvas_items.append(window_id)
                
                # Move down for next property
                y_pos += frame_height + 3 * self.zoom  # Small gap between properties
    
    def _draw_node_connections(self, node):
        """Draw connections to/from this node"""
        # Draw connections from output sockets to connected inputs
        for socket in node.outputs:
            if socket.is_connected():
                target = socket.connected_to
                if target:
                    # Convert socket positions to canvas coordinates
                    source_x, source_y = self.world_to_canvas(*socket.position)
                    target_x, target_y = self.world_to_canvas(*target.position)
                    
                    # Draw bezier curve - looks nicer than straight line
                    # Calculate control points for curve - scale with zoom
                    cx1 = source_x + 50 * self.zoom
                    cy1 = source_y
                    cx2 = target_x - 50 * self.zoom
                    cy2 = target_y
                    
                    # Create unique tag for this specific connection
                    connection_tag = f"conn_{socket.id}_{target.id}"
                    
                    # Delete any existing connection with the same tag
                    for item_id in self.find_withtag(connection_tag):
                        self.delete(item_id)
                    
                    # Draw the connection line - width scales with zoom
                    line_width = max(1, 2 * self.zoom)
                    line_id = self.create_line(
                        source_x, source_y,
                        cx1, cy1, cx2, cy2,
                        target_x, target_y,
                        fill=socket.color, width=line_width, smooth=True,
                        tags=("connection", socket.id, target.id, connection_tag, node.id)
                    )
                    node.canvas_items.append(line_id)
