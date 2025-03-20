import customtkinter as ctk
import json
import requests
from threading import Thread, Event
import tkinter as tk
from tkinter import messagebox
import re
import time
import subprocess
import uuid
import math

class NodeSocket:
    """Represents an input or output connection point on a node"""
    def __init__(self, node, is_input=True, name="Data", socket_id=None):
        self.node = node
        self.is_input = is_input
        self.name = name
        self.id = socket_id or str(uuid.uuid4())
        self.connected_to = None  # Will store another socket if connected
        
        # Drawing properties
        self.radius = 8
        self.position = (0, 0)  # Will be calculated when drawing
        self.hover = False
    
    def is_connected(self):
        return self.connected_to is not None
    
    def disconnect(self):
        if self.connected_to:
            self.connected_to.connected_to = None
            self.connected_to = None
    
    def connect(self, other_socket):
        # Ensure one socket is input and one is output
        if self.is_input == other_socket.is_input:
            return False
        
        # Disconnect any existing connections
        self.disconnect()
        other_socket.disconnect()
        
        # Make the connection
        self.connected_to = other_socket
        other_socket.connected_to = self
        
        return True
    
    def contains_point(self, x, y):
        """Check if a point is inside this socket"""
        socket_x, socket_y = self.position
        distance = math.sqrt((socket_x - x) ** 2 + (socket_y - y) ** 2)
        return distance <= self.radius

class Node:
    """Base class for all nodes in the workflow"""
    def __init__(self, canvas, x=100, y=100, title="Node", width=200, height=150):
        self.canvas = canvas
        self.workflow = canvas.workflow
        self.x = x
        self.y = y
        self.title = title
        self.width = width
        self.height = height
        self.id = str(uuid.uuid4())
        
        # Drawing properties
        self.border_width = 2
        self.header_height = 30
        self.socket_margin = 20
        self.selected = False
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        # Canvas items IDs
        self.body_id = None
        self.header_id = None
        self.title_id = None
        self.items = []  # All canvas items belonging to this node
        
        # Sockets
        self.inputs = []
        self.outputs = []
        self.init_sockets()
    
    def init_sockets(self):
        """Override this in subclasses to define inputs and outputs"""
        pass
    
    def draw(self):
        """Draw the node on the canvas"""
        # Clear any existing items
        for item_id in self.items:
            self.canvas.delete(item_id)
        self.items = []
        
        # Draw body
        fill_color = "#2a2a2a" if not self.selected else "#3a3a3a"
        self.body_id = self.canvas.create_rectangle(
            self.x, self.y + self.header_height, 
            self.x + self.width, self.y + self.height,
            fill=fill_color, outline="#555", width=self.border_width,
            tags=("node", self.id)
        )
        self.items.append(self.body_id)
        
        # Draw header
        self.header_id = self.canvas.create_rectangle(
            self.x, self.y, 
            self.x + self.width, self.y + self.header_height,
            fill="#1E90FF", outline="#555", width=self.border_width,
            tags=("node_header", self.id)
        )
        self.items.append(self.header_id)
        
        # Draw title
        self.title_id = self.canvas.create_text(
            self.x + 10, self.y + self.header_height / 2,
            text=self.title, fill="white", anchor="w",
            tags=("node_title", self.id)
        )
        self.items.append(self.title_id)
        
        # Draw input sockets
        for i, socket in enumerate(self.inputs):
            y_pos = self.y + self.header_height + self.socket_margin * (i + 1)
            socket.position = (self.x, y_pos)
            
            # Socket circle
            fill_color = "#4CAF50" if socket.hover else "#2a2a2a"
            socket_id = self.canvas.create_oval(
                socket.position[0] - socket.radius, socket.position[1] - socket.radius,
                socket.position[0] + socket.radius, socket.position[1] + socket.radius,
                fill=fill_color, outline="#AAA",
                tags=("socket", "input_socket", socket.id, self.id)
            )
            self.items.append(socket_id)
            
            # Socket label
            label_id = self.canvas.create_text(
                socket.position[0] + socket.radius + 5, socket.position[1],
                text=socket.name, fill="white", anchor="w",
                tags=("socket_label", self.id)
            )
            self.items.append(label_id)
        
        # Draw output sockets
        for i, socket in enumerate(self.outputs):
            y_pos = self.y + self.header_height + self.socket_margin * (i + 1)
            socket.position = (self.x + self.width, y_pos)
            
            # Socket circle
            fill_color = "#1E90FF" if socket.hover else "#2a2a2a"
            socket_id = self.canvas.create_oval(
                socket.position[0] - socket.radius, socket.position[1] - socket.radius,
                socket.position[0] + socket.radius, socket.position[1] + socket.radius,
                fill=fill_color, outline="#AAA",
                tags=("socket", "output_socket", socket.id, self.id)
            )
            self.items.append(socket_id)
            
            # Socket label
            label_id = self.canvas.create_text(
                socket.position[0] - socket.radius - 5, socket.position[1],
                text=socket.name, fill="white", anchor="e",
                tags=("socket_label", self.id)
            )
            self.items.append(label_id)
        
        # Draw connection lines
        self.draw_connections()
    
    def draw_connections(self):
        """Draw connection lines for this node's sockets"""
        # Draw lines from outputs to connected inputs
        for socket in self.outputs:
            if socket.is_connected():
                target = socket.connected_to
                if target:
                    conn_id = self.canvas.create_line(
                        socket.position[0], socket.position[1],
                        target.position[0], target.position[1],
                        fill="#1E90FF", width=2, smooth=True,
                        tags=("connection", socket.id, target.id)
                    )
                    self.items.append(conn_id)
    
    def contains_point(self, x, y):
        """Check if a point is inside this node's body"""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.height)
    
    def contains_header(self, x, y):
        """Check if a point is inside this node's header"""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.header_height)
    
    def get_socket_at(self, x, y):
        """Get the socket at the given coordinates, or None"""
        for socket in self.inputs + self.outputs:
            if socket.contains_point(x, y):
                return socket
        return None
    
    def move(self, dx, dy):
        """Move the node by the given delta"""
        self.x += dx
        self.y += dy
        self.draw()
    
    def on_select(self):
        """Called when the node is selected"""
        self.selected = True
        self.draw()
        self.show_properties()
    
    def on_deselect(self):
        """Called when the node is deselected"""
        self.selected = False
        self.draw()
    
    def start_drag(self, x, y):
        """Start dragging the node"""
        self.dragging = True
        self.drag_start_x = x
        self.drag_start_y = y
    
    def drag(self, x, y):
        """Drag the node to a new position"""
        if self.dragging:
            dx = x - self.drag_start_x
            dy = y - self.drag_start_y
            self.move(dx, dy)
            self.drag_start_x = x
            self.drag_start_y = y
    
    def end_drag(self):
        """End dragging the node"""
        self.dragging = False
    
    def process(self):
        """
        Process this node, getting inputs from connected nodes,
        and returning outputs. Override in subclasses.
        """
        return {}
    
    def get_input_value(self, input_name):
        """Get the value from a connected input socket"""
        for socket in self.inputs:
            if socket.name == input_name and socket.is_connected():
                # Find the connected output socket
                output_socket = socket.connected_to
                # Get the value from the output node
                if output_socket and output_socket.node:
                    output_values = output_socket.node.process()
                    if output_socket.name in output_values:
                        return output_values[output_socket.name]
        return None
    
    def show_properties(self):
        """Show property panel for this node. Override in subclasses."""
        # Default implementation shows nothing
        self.workflow.show_node_properties(self)

class StaticTextNode(Node):
    """A node that outputs static text"""
    def __init__(self, canvas, x=100, y=100):
        super().__init__(canvas, x, y, "Static Text", width=220, height=120)
        self.text = "Enter text here..."
    
    def init_sockets(self):
        self.outputs.append(NodeSocket(self, is_input=False, name="Text"))
    
    def draw(self):
        super().draw()
        
        # Draw a preview of the text
        preview_text = self.text[:20] + "..." if len(self.text) > 20 else self.text
        text_id = self.canvas.create_text(
            self.x + 10, self.y + self.header_height + 35,
            text=preview_text, fill="white", anchor="w",
            width=self.width - 20,
            tags=("node_content", self.id)
        )
        self.items.append(text_id)
    
    def process(self):
        return {"Text": self.text}
    
    def show_properties(self):
        super().show_properties()
        
        # Create a frame for the static text properties
        frame = ctk.CTkFrame(self.workflow.properties_frame)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Text input
        ctk.CTkLabel(frame, text="Text Content:").pack(anchor="w", padx=10, pady=(10, 0))
        text_area = ctk.CTkTextbox(frame, height=200)
        text_area.pack(fill="both", expand=True, padx=10, pady=10)
        text_area.insert("1.0", self.text)
        
        # Apply button
        def apply_text():
            self.text = text_area.get("1.0", "end-1c")
            self.draw()
        
        apply_btn = ctk.CTkButton(frame, text="Apply", command=apply_text)
        apply_btn.pack(pady=10)

class PromptNode(Node):
    """A node that sends prompts to an LLM and outputs the response"""
    def __init__(self, canvas, x=100, y=100):
        super().__init__(canvas, x, y, "LLM Prompt", width=240, height=200)
        
        # Prompt settings
        self.system_prompt = ""
        self.model = "deepseek-r1:14b"
        self.temperature = 0.7
        self.status = "Ready"
        self.response = ""
        self.stop_event = Event()
        self.current_response = None
    
    def init_sockets(self):
        self.inputs.append(NodeSocket(self, is_input=True, name="Input"))
        self.outputs.append(NodeSocket(self, is_input=False, name="Response"))
    
    def draw(self):
        super().draw()
        
        # Draw status text
        status_id = self.canvas.create_text(
            self.x + self.width / 2, self.y + self.height - 20,
            text=f"Status: {self.status}", fill="#AAA", anchor="center",
            tags=("node_status", self.id)
        )
        self.items.append(status_id)
        
        # Draw model text
        model_id = self.canvas.create_text(
            self.x + 10, self.y + self.header_height + 35,
            text=f"Model: {self.model}", fill="white", anchor="w",
            tags=("node_content", self.id)
        )
        self.items.append(model_id)
        
        # Draw a preview of the system prompt
        if self.system_prompt:
            preview = self.system_prompt[:20] + "..." if len(self.system_prompt) > 20 else self.system_prompt
            sys_id = self.canvas.create_text(
                self.x + 10, self.y + self.header_height + 60,
                text=f"System: {preview}", fill="#AAA", anchor="w",
                width=self.width - 20,
                tags=("node_content", self.id)
            )
            self.items.append(sys_id)
    
    def process(self):
        # Get the input text
        input_text = self.get_input_value("Input")
        
        if not input_text:
            self.status = "No input"
            self.draw()
            return {"Response": ""}
        
        # Clear existing response
        self.response = ""
        self.status = "Generating..."
        self.stop_event.clear()
        self.draw()
        
        # Run in a thread to avoid blocking
        thread = Thread(target=self.generate_response, args=(input_text,), daemon=True)
        thread.start()
        
        # Wait for the thread to complete (for synchronous processing)
        thread.join()
        
        return {"Response": self.response}
    
    def generate_response(self, user_prompt):
        """Generate a response from the LLM"""
        try:
            # Prepare API call parameters
            model = self.model
            system_prompt = self.system_prompt
            
            # Options dictionary
            options = {
                "temperature": self.temperature,
                "top_p": 0.9,
                "top_k": 40
            }
            
            # Prepare payload
            payload = {
                "model": model,
                "prompt": user_prompt,
                "stream": True,
                "options": options
            }
            
            # Add system prompt if provided
            if system_prompt:
                payload["system"] = system_prompt
            
            # Make the API call
            self.current_response = requests.post(
                "http://localhost:11434/api/generate",
                json=payload,
                stream=True
            )
            
            if self.current_response.status_code != 200:
                self.status = f"Error: {self.current_response.status_code}"
                self.draw()
                return
            
            # Process the streaming response
            for line in self.current_response.iter_lines():
                if self.stop_event.is_set():
                    break
                
                if line:
                    try:
                        data = json.loads(line)
                        if 'response' in data:
                            response_text = data['response']
                            self.response += response_text
                            
                            # Update status periodically (not on every token)
                            if len(self.response) % 50 == 0:
                                self.status = f"Generated: {len(self.response)} chars"
                                self.draw()
                        
                        # Check for completion
                        if data.get('done', False):
                            self.status = "Complete"
                            self.draw()
                    
                    except json.JSONDecodeError:
                        self.status = "Error: JSON decode failed"
                        self.draw()
            
        except Exception as e:
            self.status = f"Error: {str(e)[:20]}..."
            self.draw()
        
        finally:
            self.current_response = None
    
    def show_properties(self):
        super().show_properties()
        
        # Create a frame for the prompt properties
        frame = ctk.CTkFrame(self.workflow.properties_frame)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Model selection
        ctk.CTkLabel(frame, text="Model:").pack(anchor="w", padx=10, pady=(10, 0))
        model_var = ctk.StringVar(value=self.model)
        model_entry = ctk.CTkEntry(frame, textvariable=model_var)
        model_entry.pack(fill="x", padx=10, pady=5)
        
        # Temperature slider
        ctk.CTkLabel(frame, text=f"Temperature: {self.temperature:.1f}").pack(anchor="w", padx=10, pady=(10, 0))
        
        def update_temp(value):
            self.temperature = float(value)
            temp_label.configure(text=f"Temperature: {self.temperature:.1f}")
        
        temp_slider = ctk.CTkSlider(frame, from_=0.0, to=1.5, number_of_steps=15, command=update_temp)
        temp_slider.set(self.temperature)
        temp_slider.pack(fill="x", padx=10, pady=5)
        temp_label = ctk.CTkLabel(frame, text=f"Temperature: {self.temperature:.1f}")
        temp_label.pack(anchor="w", padx=10)
        
        # System prompt
        ctk.CTkLabel(frame, text="System Prompt:").pack(anchor="w", padx=10, pady=(10, 0))
        system_text = ctk.CTkTextbox(frame, height=100)
        system_text.pack(fill="both", expand=True, padx=10, pady=5)
        system_text.insert("1.0", self.system_prompt)
        
        # Apply button
        def apply_settings():
            self.model = model_var.get()
            self.system_prompt = system_text.get("1.0", "end-1c")
            self.draw()
        
        apply_btn = ctk.CTkButton(frame, text="Apply", command=apply_settings)
        apply_btn.pack(pady=10)
        
        # Stop button (only relevant if generation is in progress)
        def stop_generation():
            self.stop_event.set()
            if self.current_response:
                try:
                    self.current_response.close()
                except:
                    pass
            self.status = "Stopped"
            self.draw()
        
        stop_btn = ctk.CTkButton(frame, text="Stop Generation", command=stop_generation, fg_color="#8B0000")
        stop_btn.pack(pady=5)
        
        # View Response button
        def view_response():
            response_window = ctk.CTkToplevel(self.workflow.root)
            response_window.title("Node Response")
            response_window.geometry("600x400")
            
            response_text = ctk.CTkTextbox(response_window, wrap="word")
            response_text.pack(fill="both", expand=True, padx=10, pady=10)
            response_text.insert("1.0", self.response)
            
            copy_btn = ctk.CTkButton(
                response_window, 
                text="Copy to Clipboard",
                command=lambda: self.workflow.root.clipboard_append(self.response)
            )
            copy_btn.pack(pady=10)
        
        view_btn = ctk.CTkButton(frame, text="View Response", command=view_response)
        view_btn.pack(pady=5)

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
        
        # Create a right-click menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Add Static Text Node", command=lambda: self.add_node_at_cursor("static_text"))
        self.context_menu.add_command(label="Add Prompt Node", command=lambda: self.add_node_at_cursor("prompt"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete Selected Node", command=self.delete_selected_node)
        
        self.bind("<Button-3>", self.show_context_menu)
    
    def show_context_menu(self, event):
        """Show the context menu at the cursor position"""
        self.mouse_x, self.mouse_y = event.x, event.y
        self.context_menu.post(event.x_root, event.y_root)
    
    def add_node_at_cursor(self, node_type):
        """Add a new node at the cursor position"""
        if node_type == "static_text":
            node = StaticTextNode(self, x=self.mouse_x, y=self.mouse_y)
        elif node_type == "prompt":
            node = PromptNode(self, x=self.mouse_x, y=self.mouse_y)
        else:
            return
        
        self.workflow.add_node(node)
        node.draw()
    
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
                fill="#1E90FF", width=2, dash=(4, 4)
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
        elif self.selected_node and self.selected_node.dragging:
            # Drag the selected node
            self.selected_node.drag(event.x, event.y)
    
    def on_release(self, event):
        """Handle mouse release events"""
        if self.connecting_socket and self.connecting_line:
            # Check if we're over another socket
            target_socket = self.find_socket_at(event.x, event.y)
            
            if target_socket and target_socket != self.connecting_socket:
                # Try to create a connection
                if self.connecting_socket.is_input != target_socket.is_input:
                    # Connect input to output
                    if self.connecting_socket.is_input:
                        input_socket, output_socket = self.connecting_socket, target_socket
                    else:
                        input_socket, output_socket = target_socket, self.connecting_socket
                    
                    # Make the connection
                    input_socket.connect(output_socket)
                    
                    # Redraw the nodes to show the connection
                    input_socket.node.draw()
                    if output_socket.node != input_socket.node:
                        output_socket.node.draw()
            
            # Remove the temporary line
            self.delete(self.connecting_line)
            self.connecting_line = None
            self.connecting_socket = None
        
        # End any node dragging
        if self.selected_node and self.selected_node.dragging:
            self.selected_node.end_drag()
    
    def on_motion(self, event):
        """Handle mouse motion events (hover effects)"""
        socket = self.find_socket_at(event.x, event.y)
        
        # Reset hover state for all sockets
        for node in self.workflow.nodes:
            for s in node.inputs + node.outputs:
                if s.hover:
                    s.hover = False
                    # Redraw the socket
                    for item_id in self.find_withtag(s.id):
                        if "socket" in self.gettags(item_id):
                            fill_color = "#4CAF50" if s.is_input else "#1E90FF"
                            self.itemconfig(item_id, fill="#2a2a2a")
        
        # Set hover state for the socket under cursor
        if socket:
            socket.hover = True
            # Highlight the socket
            for item_id in self.find_withtag(socket.id):
                if "socket" in self.gettags(item_id):
                    fill_color = "#4CAF50" if socket.is_input else "#1E90FF"
                    self.itemconfig(item_id, fill=fill_color)
    
    def find_node_at(self, x, y):
        """Find the topmost node at the given coordinates"""
        # Check all nodes in reverse order (so top nodes are found first)
        for node in reversed(self.workflow.nodes):
            if node.contains_point(x, y):
                return node
        return None
    
    def find_socket_at(self, x, y):
        """Find the socket at the given coordinates"""
        # Check all nodes in reverse order
        for node in reversed(self.workflow.nodes):
            socket = node.get_socket_at(x, y)
            if socket:
                return socket
        return None

class NodeWorkflow:
    """Manages the collection of nodes and their execution"""
    def __init__(self, root):
        self.root = root
        self.nodes = []
        self.properties_frame = None
    
    def add_node(self, node):
        """Add a node to the workflow"""
        self.nodes.append(node)
    
    def delete_node(self, node):
        """Remove a node from the workflow"""
        if node in self.nodes:
            # Disconnect all sockets
            for socket in node.inputs + node.outputs:
                socket.disconnect()
            
            # Remove from canvas
            for item_id in node.items:
                node.canvas.delete(item_id)
            
            # Remove from nodes list
            self.nodes.remove(node)
            
            # Clear properties if this was the selected node
            if node.canvas.selected_node == node:
                node.canvas.selected_node = None
                self.show_node_properties(None)
    
    def execute_node(self, node_id):
        """Execute a specific node and its dependencies"""
        for node in self.nodes:
            if node.id == node_id:
                return node.process()
        return {}
    
    def show_node_properties(self, node):
        """Show properties for the selected node"""
        # Clear existing properties
        if self.properties_frame:
            for widget in self.properties_frame.winfo_children():
                widget.destroy()
        
        # If no node is selected, show a message
        if not node:
            if self.properties_frame:
                ctk.CTkLabel(
                    self.properties_frame,
                    text="No node selected",
                    font=("Verdana", 16)
                ).pack(padx=20, pady=20)

class OllamaFlow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Ollama Flow - Node Workflow")
        self.geometry("1600x900")
        
        # Configure dark theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Create the workflow
        self.workflow = NodeWorkflow(self)
        
        # Create main layout
        self.create_layout()
        
        # Add some example nodes
        self.add_example_nodes()
    
    def create_layout(self):
        # Configure grid layout with 2 columns
        self.grid_columnconfigure(0, weight=4)  # Canvas area
        self.grid_columnconfigure(1, weight=1)  # Properties panel
        self.grid_rowconfigure(0, weight=1)
        
        # Create main frames
        canvas_frame = ctk.CTkFrame(self)
        canvas_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        properties_frame = ctk.CTkFrame(self)
        properties_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        # Store reference to properties frame
        self.workflow.properties_frame = properties_frame
        
        # Setup canvas area
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.grid_rowconfigure(1, weight=1)
        
        # Toolbar
        toolbar = ctk.CTkFrame(canvas_frame)
        toolbar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        # Add toolbar buttons
        add_static_btn = ctk.CTkButton(
            toolbar,
            text="Add Static Text",
            command=lambda: self.add_node("static_text")
        )
        add_static_btn.pack(side="left", padx=5, pady=5)
        
        add_prompt_btn = ctk.CTkButton(
            toolbar,
            text="Add Prompt Node",
            command=lambda: self.add_node("prompt")
        )
        add_prompt_btn.pack(side="left", padx=5, pady=5)
        
        run_btn = ctk.CTkButton(
            toolbar,
            text="Run Workflow",
            command=self.run_workflow,
            fg_color="#4CAF50"
        )
        run_btn.pack(side="right", padx=5, pady=5)
        
        # Create node canvas
        self.node_canvas = NodeCanvas(
            canvas_frame,
            self.workflow,
            bg="#1e1e1e",
            highlightthickness=0
        )
        self.node_canvas.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Properties panel
        ctk.CTkLabel(
            properties_frame,
            text="Node Properties",
            font=("Verdana", 16, "bold")
        ).pack(pady=10)
        
        # Initially show "no node selected"
        self.workflow.show_node_properties(None)
    
    def add_node(self, node_type, x=100, y=100):
        """Add a new node to the workflow"""
        if node_type == "static_text":
            node = StaticTextNode(self.node_canvas, x=x, y=y)
        elif node_type == "prompt":
            node = PromptNode(self.node_canvas, x=x, y=y)
        else:
            return
        
        self.workflow.add_node(node)
        node.draw()
    
    def add_example_nodes(self):
        """Add some example nodes to demonstrate the workflow"""
        # Add a static text node
        static_node = StaticTextNode(self.node_canvas, x=100, y=100)
        static_node.text = "This is a sample text to test the workflow. It will be sent to the LLM for processing."
        self.workflow.add_node(static_node)
        
        # Add a prompt node
        prompt_node = PromptNode(self.node_canvas, x=400, y=200)
        prompt_node.system_prompt = "You are a helpful AI assistant. Summarize the input text in a concise way."
        self.workflow.add_node(prompt_node)
        
        # Draw the nodes
        static_node.draw()
        prompt_node.draw()
        
        # Connect the static node to the prompt node
        static_output = static_node.outputs[0]
        prompt_input = prompt_node.inputs[0]
        static_output.connect(prompt_input)
        
        # Redraw the nodes to show the connection
        static_node.draw()
        prompt_node.draw()
    
    def run_workflow(self):
        """Run all output nodes in the workflow"""
        # Find nodes with no outgoing connections (end nodes)
        end_nodes = []
        for node in self.workflow.nodes:
            has_outgoing = False
            for output in node.outputs:
                if output.is_connected():
                    has_outgoing = True
                    break
            if not has_outgoing and node.outputs:  # It has outputs but none are connected
                end_nodes.append(node)
        
        if not end_nodes:
            messagebox.showinfo("Run Workflow", "No end nodes found. Connect nodes to create a workflow.")
            return
        
        # Run each end node
        for node in end_nodes:
            result = node.process()
            
            # Show results in a simple popup for demonstration
            result_text = "\n\n".join([f"{key}: {value}" for key, value in result.items()])
            if result_text.strip():
                self.show_result(node.title, result_text)
    
    def show_result(self, title, result):
        """Show the result of a workflow execution"""
        result_window = ctk.CTkToplevel(self)
        result_window.title(f"Result: {title}")
        result_window.geometry("600x400")
        
        result_text = ctk.CTkTextbox(result_window, wrap="word")
        result_text.pack(fill="both", expand=True, padx=10, pady=10)
        result_text.insert("1.0", result)
        
        copy_btn = ctk.CTkButton(
            result_window, 
            text="Copy to Clipboard",
            command=lambda: self.clipboard_append(result)
        )
        copy_btn.pack(pady=10)

def main():
    app = OllamaFlow()
    app.mainloop()

if __name__ == "__main__":
    main()
