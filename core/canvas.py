import customtkinter as ctk
import tkinter as tk
import math

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
        
        # Add a command for each node type dynamically
        for node_class in get_node_subclasses():
            node_type_name = getattr(node_class, "node_type", node_class.__name__)
            self.context_menu.add_command(
                label=f"Add {node_type_name}", 
                command=lambda cls=node_class: self.add_node_at_cursor(cls)
            )
        
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
        """Handle mouse click events"""
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
            self.selected_node.on_deselect()
        
        # Select and handle the clicked node
        if node:
            self.selected_node = node
            node.on_select()
            
            # Check if we clicked on the header (to drag)
            if node.contains_header(event.x, event.y):
                node.start_drag(event.x, event.y)
        else:
            # Clicked on empty space
            self.selected_node = None
            # Clear properties panel
            self.workflow.show_node_properties(None)
    
    def on_drag(self, event):
        """Handle mouse drag events"""
        if self.connecting_socket and self.connecting_line:
            # Update the temporary connection line
            self.coords(
                self.connecting_line,
                self.connecting_socket.position[0],
                self.connecting_socket.position[1],
                event.x, event.y
            )
        elif self.selected_node and hasattr(self.selected_node, 'dragging') and self.selected_node.dragging:
            # Drag the selected node
            dx = event.x - self.selected_node.drag_start_x
            dy = event.y - self.selected_node.drag_start_y
            self.selected_node.x += dx
            self.selected_node.y += dy
            self.selected_node.drag_start_x = event.x
            self.selected_node.drag_start_y = event.y
            self.redraw_node(self.selected_node)
    
    def on_release(self, event):
        """Handle mouse release events"""
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
        
        # End any node dragging
        if self.selected_node and hasattr(self.selected_node, 'dragging'):
            self.selected_node.dragging = False
    
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
        """Clear and redraw a node on the canvas"""
        # Clear any existing items
        for item_id in node.canvas_items:
            self.delete(item_id)
        node.canvas_items = []
        
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
        
        # Draw connections
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
        """Draw input and output sockets"""
        # Draw input sockets
        for i, socket in enumerate(node.inputs):
            y_pos = node.y + node.header_height + node.socket_margin * (i + 1)
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
        
        # Draw output sockets
        for i, socket in enumerate(node.outputs):
            y_pos = node.y + node.header_height + node.socket_margin * (i + 1)
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
        """Draw node content (property previews, etc.)"""
        # Get visible properties to show on the node
        visible_props = node.get_visible_properties()
        
        y_offset = node.y + node.header_height + 10
        for label, value in visible_props.items():
            content_id = self.create_text(
                node.x + 10, y_offset,
                text=f"{label}: {value}", fill="white", anchor="w",
                width=node.width - 20,
                tags=("node_content", node.id)
            )
            node.canvas_items.append(content_id)
            y_offset += 20
        
        # Show output preview if available
        if node.output_cache:
            preview_y = node.y + node.height - 40
            for i, (key, value) in enumerate(node.output_cache.items()):
                if i >= 1:  # Only show first output to save space
                    break
                    
                preview = str(value)
                if len(preview) > 30:
                    preview = preview[:27] + "..."
                    
                out_id = self.create_text(
                    node.x + 10, preview_y,
                    text=f"{key}: {preview}", fill="#5CB85C", anchor="w",
                    width=node.width - 20,
                    tags=("node_output", node.id)
                )
                node.canvas_items.append(out_id)
                preview_y -= 20
    
    def _draw_node_connections(self, node):
        """Draw connections to/from this node"""
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
                    
                    # Draw the connection line
                    line_id = self.create_line(
                        socket.position[0], socket.position[1],
                        cx1, cy1, cx2, cy2,
                        target.position[0], target.position[1],
                        fill=socket.color, width=2, smooth=True,
                        tags=("connection", socket.id, target.id)
                    )
                    node.canvas_items.append(line_id)


# Helper functions for the canvas
def get_node_subclasses():
    """Get all available node types for the context menu"""
    from core.node import Node
    import importlib
    import pkgutil
    import inspect
    import sys
    import os
    
    # Dynamically load all plugin modules
    node_classes = []
    
    # Helper function to recursively find all subclasses
    def find_subclasses(cls):
        direct_subclasses = cls.__subclasses__()
        all_subclasses = []
        for subclass in direct_subclasses:
            all_subclasses.append(subclass)
            all_subclasses.extend(find_subclasses(subclass))
        return all_subclasses
    
    # For the minimal implementation, just return the plugins we'll implement
    from plugins.Core.static_text import StaticTextNode
    from plugins.Ollama.prompt import PromptNode
    
    return [StaticTextNode, PromptNode]