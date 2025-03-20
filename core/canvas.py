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
        
        # Bind events
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Motion>", self.on_motion)
        
        # Create a right-click menu - will be populated dynamically
        self.context_menu = tk.Menu(self, tearoff=0)
        self.bind("<Button-3>", self.show_context_menu)
    
    def show_context_menu(self, event):
        """Show the context menu at the cursor position"""
        self.mouse_x, self.mouse_y = event.x, event.y
        
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
            self.workflow.delete_node(self.selected_node)
    
    def on_click(self, event):
        """Handle mouse click events with resize handle check"""
        self.mouse_x, self.mouse_y = event.x, event.y
        
        # Check if we clicked on a socket
        socket = self.find_socket_at(event.x, event.y)
        if socket:
            # Start connection creation from this socket
            self.connecting_socket = socket
            self.connecting_line = self.create_line(
                socket.position[0], socket.position[1],
                event.x, event.y,
                fill=socket.color, width=2, dash=(4, 4)
            )
            return
        
        # Check if we clicked on a node
        node = self.find_node_at(event.x, event.y)
        
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
            if node.contains_resize_handle(event.x, event.y):
                node.start_resize(event.x, event.y)
            # Check if we clicked on the header (to drag)
            elif node.contains_header(event.x, event.y):
                node.start_drag(event.x, event.y)
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
        if self.connecting_socket and self.connecting_line:
            # Update the temporary connection line
            self.coords(
                self.connecting_line,
                self.connecting_socket.position[0],
                self.connecting_socket.position[1],
                event.x, event.y
            )
        elif self.selected_node:
            if self.selected_node.resizing:
                # Resize the node
                new_width = max(self.selected_node.resize_start_width + (event.x - self.selected_node.drag_start_x), 
                                self.selected_node.min_width)
                new_height = max(self.selected_node.resize_start_height + (event.y - self.selected_node.drag_start_y), 
                                self.selected_node.min_height)
                
                # Update node dimensions
                self.selected_node.width = new_width
                self.selected_node.height = new_height
                
                # Redraw the node
                self.redraw_node(self.selected_node)
                
            elif self.selected_node.dragging:
                # Drag the selected node
                dx = event.x - self.selected_node.drag_start_x
                dy = event.y - self.selected_node.drag_start_y
                self.selected_node.x += dx
                self.selected_node.y += dy
                self.selected_node.drag_start_x = event.x
                self.selected_node.drag_start_y = event.y
                
                # Redraw this node and all connected nodes to update connections properly
                self.redraw_node(self.selected_node)
    
    def on_release(self, event):
        """Handle mouse release events with resizing support"""
        if self.connecting_socket and self.connecting_line:
            # Check if we're over another socket
            target_socket = self.find_socket_at(event.x, event.y)
            
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
        socket = self.find_socket_at(event.x, event.y)
        
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
        """Find the topmost node at the given coordinates"""
        # Check all nodes in reverse order (so top nodes are found first)
        for node in reversed(self.workflow.nodes):
            if hasattr(node, 'contains_point') and node.contains_point(x, y):
                return node
        return None
    
    def find_socket_at(self, x, y):
        """Find the socket at the given coordinates"""
        # Check all nodes in reverse order
        for node in reversed(self.workflow.nodes):
            for socket in node.inputs + node.outputs:
                if socket.contains_point(x, y):
                    return socket
        return None
    
    def redraw_node(self, node):
        """Clear and redraw a node on the canvas with improved connection handling"""
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
        
        # Draw node content
        self._draw_node_content(node)
        
        # Redraw ALL connected nodes to fix all connections
        for connected_node in connected_nodes:
            # Only need to redraw connections, not the whole node
            self._draw_node_connections(connected_node)
        
        # Draw connections for this node
        self._draw_node_connections(node)
    
    def _draw_node_body(self, node):
        """Draw the main body of the node"""
        fill_color = "#2a2a2a" if not node.selected else "#3a3a3a"
        body_id = self.create_rectangle(
            node.x, node.y + node.header_height, 
            node.x + node.width, node.y + node.height,
            fill=fill_color, outline="#555", width=node.border_width,
            tags=("node", node.id)
        )
        node.canvas_items.append(body_id)
        
        # Add resize handle to bottom right corner
        handle_x = node.x + node.width - node.resize_handle_size
        handle_y = node.y + node.height - node.resize_handle_size
        
        # Draw resize handle lines
        handle_line1 = self.create_line(
            handle_x, node.y + node.height,
            node.x + node.width, handle_y,
            fill="#888", width=1,
            tags=("resize_handle", node.id)
        )
        node.canvas_items.append(handle_line1)
        
        handle_line2 = self.create_line(
            handle_x + node.resize_handle_size // 2, node.y + node.height,
            node.x + node.width, handle_y + node.resize_handle_size // 2,
            fill="#888", width=1,
            tags=("resize_handle", node.id)
        )
        node.canvas_items.append(handle_line2)

    
    def _draw_node_header(self, node):
        """Draw the node header with title"""
        header_id = self.create_rectangle(
            node.x, node.y, 
            node.x + node.width, node.y + node.header_height,
            fill="#1E90FF", outline="#555", width=node.border_width,
            tags=("node_header", node.id)
        )
        node.canvas_items.append(header_id)
        
        title_id = self.create_text(
            node.x + 10, node.y + node.header_height / 2,
            text=node.title, fill="white", anchor="w",
            tags=("node_title", node.id)
        )
        node.canvas_items.append(title_id)
    
    def _draw_node_sockets(self, node):
        """Draw input and output sockets with better organization"""
        # Calculate vertical starting position
        y_pos = node.y + node.header_height + node.section_padding
        
        # Draw "Inputs" section header if there are inputs
        if node.inputs:
            section_id = self.create_text(
                node.x + 10, y_pos,
                text="INPUTS", fill="#888", anchor="w",
                font=("Helvetica", 8),
                tags=("section_header", node.id)
            )
            node.canvas_items.append(section_id)
            y_pos += 15  # Add space after section header
            
            # Draw input sockets
            for i, socket in enumerate(node.inputs):
                socket.position = (node.x, y_pos)
                
                # Socket circle
                fill_color = socket.color if socket.hover else "#2a2a2a"
                socket_id = self.create_oval(
                    socket.position[0] - socket.radius, socket.position[1] - socket.radius,
                    socket.position[0] + socket.radius, socket.position[1] + socket.radius,
                    fill=fill_color, outline="#AAA",
                    tags=("socket", "input_socket", socket.id, node.id)
                )
                node.canvas_items.append(socket_id)
                
                # Socket label
                label_id = self.create_text(
                    socket.position[0] + socket.radius + 5, socket.position[1],
                    text=socket.name, fill="white", anchor="w",
                    tags=("socket_label", node.id)
                )
                node.canvas_items.append(label_id)
                
                y_pos += node.socket_spacing
            
            # Add section divider
            y_pos += node.section_spacing - node.socket_spacing
            divider_id = self.create_line(
                node.x + 10, y_pos - node.section_spacing // 2,
                node.x + node.width - 10, y_pos - node.section_spacing // 2,
                fill="#555", dash=(4, 4),
                tags=("section_divider", node.id)
            )
            node.canvas_items.append(divider_id)
        
        # Draw "Outputs" section if there are outputs
        if node.outputs:
            section_id = self.create_text(
                node.x + 10, y_pos,
                text="OUTPUTS", fill="#888", anchor="w",
                font=("Helvetica", 8),
                tags=("section_header", node.id)
            )
            node.canvas_items.append(section_id)
            y_pos += 15  # Add space after section header
            
            # Draw output sockets
            for i, socket in enumerate(node.outputs):
                socket.position = (node.x + node.width, y_pos)
                
                # Socket circle
                fill_color = socket.color if socket.hover else "#2a2a2a"
                socket_id = self.create_oval(
                    socket.position[0] - socket.radius, socket.position[1] - socket.radius,
                    socket.position[0] + socket.radius, socket.position[1] + socket.radius,
                    fill=fill_color, outline="#AAA",
                    tags=("socket", "output_socket", socket.id, node.id)
                )
                node.canvas_items.append(socket_id)
                
                # Socket label
                label_id = self.create_text(
                    socket.position[0] - socket.radius - 5, socket.position[1],
                    text=socket.name, fill="white", anchor="e",
                    tags=("socket_label", node.id)
                )
                node.canvas_items.append(label_id)
                
                y_pos += node.socket_spacing
            
            # Add section divider for properties
            y_pos += node.section_spacing - node.socket_spacing
            divider_id = self.create_line(
                node.x + 10, y_pos - node.section_spacing // 2,
                node.x + node.width - 10, y_pos - node.section_spacing // 2,
                fill="#555", dash=(4, 4),
                tags=("section_divider", node.id)
            )
            node.canvas_items.append(divider_id)
    
    def _draw_node_status(self, node):
        """Draw node status information"""
        status_color = "#AAA"  # Default gray
        if "Processing" in node.status or "Generating" in node.status:
            status_color = "#F0AD4E"  # Orange for active
        elif "Complete" in node.status:
            status_color = "#5CB85C"  # Green for complete
        elif "Error" in node.status:
            status_color = "#D9534F"  # Red for error
        
        status_id = self.create_text(
            node.x + 10, node.y + node.height - 20,
            text=f"Status: {node.status}", fill=status_color, anchor="w",
            tags=("node_status", node.id)
        )
        node.canvas_items.append(status_id)
    
    def _draw_node_content(self, node):
        """Draw node content with property previews without truncation"""
        # Get visible properties to show on the node
        visible_props = node.get_visible_properties()
        
        if visible_props:
            # Calculate y position after inputs and outputs
            y_pos = node.y + node.header_height + node.section_padding
            
            # Skip past inputs section if there are inputs
            if node.inputs:
                y_pos += 15  # section header
                y_pos += len(node.inputs) * node.socket_spacing
                y_pos += node.section_spacing
            
            # Skip past outputs section if there are outputs
            if node.outputs:
                y_pos += 15  # section header
                y_pos += len(node.outputs) * node.socket_spacing
                y_pos += node.section_spacing
            
            # Draw "Properties" section header
            section_id = self.create_text(
                node.x + 10, y_pos,
                text="PROPERTIES", fill="#888", anchor="w",
                font=("Helvetica", 8),
                tags=("section_header", node.id)
            )
            node.canvas_items.append(section_id)
            y_pos += 15  # Add space after section header
            
            # Calculate max width for text wrapping
            max_width = node.width - 20
            
            # Draw properties without truncation
            for label, value in visible_props.items():
                # Use different color for output properties
                fill_color = "#5CB85C" if label.startswith("Output:") else "white"
                
                # Create the property label (with bold style)
                label_id = self.create_text(
                    node.x + 10, y_pos,
                    text=f"{label}:", fill=fill_color, anchor="nw",
                    font=("Helvetica", 10, "bold"),
                    tags=("node_content", "prop_label", node.id)
                )
                node.canvas_items.append(label_id)
                y_pos += 18  # Space after label
                
                # Get the text bounds to calculate appropriate text wrapping
                # based on the node width
                text_value = str(value)
                wrapped_text = self._wrap_text(text_value, max_width)
                
                # Create text for the value - using a single text item with newlines
                value_id = self.create_text(
                    node.x + 15, y_pos,
                    text=wrapped_text, fill=fill_color, anchor="nw",
                    width=max_width,  # Enable built-in text wrapping
                    tags=("node_content", "prop_value", node.id)
                )
                node.canvas_items.append(value_id)
                
                # Calculate height of wrapped text and add spacing
                line_count = wrapped_text.count('\n') + 1
                y_pos += line_count * 18 + 10  # Add space after value based on lines
    
    def _draw_node_connections(self, node):
        """Draw connections to/from this node with improved cleanup"""
        # Draw connections from output sockets to connected inputs
        for socket in node.outputs:
            if socket.is_connected():
                target = socket.connected_to
                if target:
                    # Draw bezier curve - looks nicer than straight line
                    # Calculate control points for curve
                    cx1 = socket.position[0] + 50
                    cy1 = socket.position[1]
                    cx2 = target.position[0] - 50
                    cy2 = target.position[1]
                    
                    # Create unique tag for this specific connection
                    connection_tag = f"conn_{socket.id}_{target.id}"
                    
                    # Delete any existing connection with the same tag
                    for item_id in self.find_withtag(connection_tag):
                        self.delete(item_id)
                    
                    # Draw the connection line
                    line_id = self.create_line(
                        socket.position[0], socket.position[1],
                        cx1, cy1, cx2, cy2,
                        target.position[0], target.position[1],
                        fill=socket.color, width=2, smooth=True,
                        tags=("connection", socket.id, target.id, connection_tag, node.id)
                    )
                    node.canvas_items.append(line_id)

    def _wrap_text(self, text, width):
        """Wrap text to fit within width"""
        # Approximate character width (in pixels)
        char_width = 7
        
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            # Check if adding this word would exceed the width
            if len(test_line) * char_width <= width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        # Join with newlines
        return "\n".join(lines)


# Helper functions for the canvas
def get_node_subclasses():
    """Get all available node types for the context menu"""
    from core.node_registry import get_all_node_categories
    
    # Get all node classes from registry
    node_categories = get_all_node_categories()
    
    # Flatten the categories
    node_classes = []
    for category, classes in node_categories.items():
        node_classes.extend(classes)
    
    return node_classes