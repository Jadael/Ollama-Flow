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
import copy

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
        
        # Mark the target node as dirty when a new connection is made
        if self.is_input:
            self.node.mark_dirty()
        else:
            other_socket.node.mark_dirty()

        return True
    
    def contains_point(self, x, y):
        """Check if a point is inside this socket"""
        socket_x, socket_y = self.position
        distance = math.sqrt((socket_x - x) ** 2 + (socket_y - y) ** 2)
        return distance <= self.radius

class Node:
    """Base class for all nodes in the workflow"""
    node_type = "Generic Node"  # Class attribute for node type name in the UI
    
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
        
        # Processing state
        self.output_cache = {}
        self.output_timestamp = None
        self.dirty = True
        self.processing = False
        self.processing_complete_event = Event()
        self.processing_complete_event.set()  # Initially not processing
        self.processing_error = None
        self.status = "Ready"
        
        # Initialize sockets
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
        
        # Draw status text with color coding
        status_color = "#AAA"  # Default gray
        if "Processing" in self.status or "Generating" in self.status:
            status_color = "#F0AD4E"  # Orange for active
        elif "Complete" in self.status:
            status_color = "#5CB85C"  # Green for complete
        elif "Error" in self.status:
            status_color = "#D9534F"  # Red for error
        
        status_id = self.canvas.create_text(
            self.x + 10, self.y + self.height - 20,
            text=f"Status: {self.status}", fill=status_color, anchor="w",
            tags=("node_status", self.id)
        )
        self.items.append(status_id)
        
        # Draw cached output preview if available
        if self.output_cache:
            # Display the cached output summary
            preview_y = self.y + self.height - 40
            for i, (key, value) in enumerate(self.output_cache.items()):
                if i >= 1:  # Only show first output to save space
                    break
                    
                preview = str(value)
                if len(preview) > 30:
                    preview = preview[:27] + "..."
                    
                out_id = self.canvas.create_text(
                    self.x + 10, preview_y,
                    text=f"{key}: {preview}", fill="#5CB85C", anchor="w",
                    width=self.width - 20,
                    tags=("node_output", self.id)
                )
                self.items.append(out_id)
                preview_y -= 20
        
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
        and returning outputs.
        """
        # If not dirty and we have cached output, return it
        if not self.dirty and self.output_cache:
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
            self.processing = False
            self.processing_complete_event.set()
            self.draw()
    
    def execute(self):
        """
        Override this method in subclasses to implement the specific processing logic.
        This is called by process() after managing the dirty state and waiting for inputs.
        """
        # Default implementation returns empty dict
        return {}
    
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
            if output_socket.connected_to:
                output_socket.connected_to.node.mark_dirty()
    
    def clear_output(self):
        """Clear the cached output and mark node as dirty"""
        self.output_cache = {}
        self.output_timestamp = None
        self.dirty = True
        self.draw()
    
    def show_properties(self):
        """Show property panel for this node. Override in subclasses."""
        # Clear existing properties panel
        for widget in self.workflow.properties_frame.winfo_children():
            widget.destroy()
            
        # Add a basic properties panel with node info
        frame = ctk.CTkFrame(self.workflow.properties_frame)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Node title
        ctk.CTkLabel(frame, text=f"{self.title} Properties", font=("Arial", 14, "bold")).pack(pady=10)
        
        # Node ID
        ctk.CTkLabel(frame, text=f"ID: {self.id[:8]}...").pack(anchor="w", padx=10)
        
        # Node position
        pos_frame = ctk.CTkFrame(frame)
        pos_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(pos_frame, text="Position:").grid(row=0, column=0, padx=5, pady=5)
        
        x_var = ctk.StringVar(value=str(self.x))
        y_var = ctk.StringVar(value=str(self.y))
        
        x_entry = ctk.CTkEntry(pos_frame, textvariable=x_var, width=60)
        x_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ctk.CTkLabel(pos_frame, text="X").grid(row=0, column=2, padx=2, pady=5)
        
        y_entry = ctk.CTkEntry(pos_frame, textvariable=y_var, width=60)
        y_entry.grid(row=0, column=3, padx=5, pady=5)
        
        ctk.CTkLabel(pos_frame, text="Y").grid(row=0, column=4, padx=2, pady=5)
        
        # Apply position button
        def apply_position():
            try:
                new_x = int(x_var.get())
                new_y = int(y_var.get())
                dx = new_x - self.x
                dy = new_y - self.y
                self.move(dx, dy)
            except ValueError:
                pass
        
        apply_btn = ctk.CTkButton(pos_frame, text="Apply", command=apply_position, width=60)
        apply_btn.grid(row=0, column=5, padx=5, pady=5)
        
        # Status display
        ctk.CTkLabel(frame, text=f"Status: {self.status}").pack(anchor="w", padx=10, pady=5)
        
        # Add clear cache button
        clear_btn = ctk.CTkButton(frame, text="Clear Output Cache", command=self.clear_output)
        clear_btn.pack(pady=10)
        
        # Add process button
        process_btn = ctk.CTkButton(frame, text="Process Node", command=lambda: self.process())
        process_btn.pack(pady=5)

class StaticTextNode(Node):
    """A node that outputs static text"""
    node_type = "Static Text"
    
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
    
    def execute(self):
        # Simple synchronous execution
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
        
        # Preview button
        def preview_text():
            preview_window = ctk.CTkToplevel(self.workflow.root)
            preview_window.title("Text Preview")
            preview_window.geometry("600x400")
            
            preview_text = ctk.CTkTextbox(preview_window, wrap="word")
            preview_text.pack(fill="both", expand=True, padx=10, pady=10)
            preview_text.insert("1.0", self.text)
            preview_text.configure(state="disabled")
            
            copy_btn = ctk.CTkButton(
                preview_window, 
                text="Copy to Clipboard",
                command=lambda: self.workflow.root.clipboard_append(self.text)
            )
            copy_btn.pack(pady=10)
        
        preview_btn = ctk.CTkButton(frame, text="Preview", command=preview_text)
        preview_btn.pack(pady=10)

class PromptNode(Node):
    """A node that sends prompts to an LLM and outputs the response"""
    node_type = "LLM Prompt"
    
    def __init__(self, canvas, x=100, y=100):
        super().__init__(canvas, x, y, "LLM Prompt", width=240, height=220)
        
        # Prompt settings
        self.system_prompt = ""
        self.model = "deepseek-r1:14b"
        self.temperature = 0.7
        self.status = "Ready"
        self.response = ""
        self.stop_event = Event()
        self.current_response = None
        self.token_count = 0
        self.start_time = None
        self.stream_window = None
        self.stream_text = None
        self.progress_bar = None
    
    def init_sockets(self):
        self.inputs.append(NodeSocket(self, is_input=True, name="System Prompt"))
        self.inputs.append(NodeSocket(self, is_input=True, name="User Prompt"))
        self.outputs.append(NodeSocket(self, is_input=False, name="Response"))
    
    def draw(self):
        super().draw()
        
        # Draw token counter
        token_id = self.canvas.create_text(
            self.x + self.width / 2, self.y + self.height - 40,
            text=f"Tokens: {self.token_count}", fill="#AAA", anchor="center",
            tags=("node_tokens", self.id)
        )
        self.items.append(token_id)
        
        # Draw status text with some color coding
        status_color = "#AAA"  # Default gray
        if "Generating" in self.status:
            status_color = "#F0AD4E"  # Orange for active
        elif "Complete" in self.status:
            status_color = "#5CB85C"  # Green for complete
        elif "Error" in self.status:
            status_color = "#D9534F"  # Red for error
        
        status_id = self.canvas.create_text(
            self.x + self.width / 2, self.y + self.height - 20,
            text=f"Status: {self.status}", fill=status_color, anchor="center",
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
    
    def execute(self):
        # This will be called by the base class process() method
        # Get the input text - will wait for any upstream nodes
        system_input = self.get_input_value("System Prompt")
        input_text = self.get_input_value("User Prompt")
        
        if not input_text:
            self.status = "No input"
            return {"Response": ""}
        
        # Use system prompt from input if provided, otherwise use the node's system prompt
        system_prompt = system_input if system_input else self.system_prompt
        
        # Clear previous response data
        self.response = ""
        self.token_count = 0
        self.stop_event.clear()
        
        # Create a new event for this specific execution
        execution_complete = Event()
        
        # Start generation in a separate thread
        def generation_thread():
            try:
                self.generate_response(system_prompt, input_text)
            finally:
                execution_complete.set()
        
        Thread(target=generation_thread, daemon=True).start()
        
        # Wait for the generation to complete
        if not execution_complete.wait(timeout=120):
            raise TimeoutError("LLM generation timed out")
        
        # Return the final response
        return {"Response": self.response}
    
    def stop_generation(self):
        """Stop the current generation process"""
        self.stop_event.set()
        if self.current_response:
            try:
                self.current_response.close()
            except:
                pass
        self.status = "Stopped"
        self.draw()
        
        # Update the debug panel
        self.workflow.root.update_debug_panel(None, None, self.response, "Stopped", self.token_count)
    
    def generate_response(self, system_prompt, user_prompt):
        """Generate a response from the LLM"""
        try:
            print(f"Starting generation for node {self.id} with prompt: {user_prompt[:50]}...")
            
            # Prepare API call parameters
            model = self.model
            
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
            
            # Reset counters and start time
            self.token_count = 0
            self.start_time = time.time()
            
            # Make the API call
            self.current_response = requests.post(
                "http://localhost:11434/api/generate",
                json=payload,
                stream=True
            )
            
            if self.current_response.status_code != 200:
                self.status = f"Error: {self.current_response.status_code}"
                self.workflow.root.after(0, self.draw)
                
                # Update the debug panel
                self.workflow.root.after(0, lambda: self.workflow.root.update_debug_panel(
                    system_prompt, user_prompt, "", f"Error: {self.current_response.status_code}", 0
                ))
                
                print(f"Error from Ollama API: {self.current_response.text}")
                return
            
            # Process the streaming response
            for line in self.current_response.iter_lines():
                if self.stop_event.is_set():
                    print("Generation stopped by user")
                    break
                
                if line:
                    try:
                        data = json.loads(line)
                        if 'response' in data:
                            response_text = data['response']
                            self.response += response_text
                            self.token_count += 1
                            
                            # Update status every few tokens
                            if self.token_count % 5 == 0:
                                elapsed = time.time() - self.start_time
                                tps = self.token_count / elapsed if elapsed > 0 else 0
                                self.status = f"Generating: {self.token_count} tokens ({tps:.1f}/s)"
                                self.workflow.root.after(0, self.draw)
                                
                                # Update the debug panel
                                self.workflow.root.after(0, lambda: self.workflow.root.update_debug_panel(
                                    system_prompt, user_prompt, self.response, self.status, self.token_count
                                ))
                        
                        # Check for completion
                        if data.get('done', False):
                            elapsed = time.time() - self.start_time
                            tps = self.token_count / elapsed if elapsed > 0 else 0
                            self.status = f"Complete: {self.token_count} tokens ({tps:.1f}/s)"
                            self.workflow.root.after(0, self.draw)
                            
                            # Final update to the debug panel
                            self.workflow.root.after(0, lambda: self.workflow.root.update_debug_panel(
                                system_prompt, user_prompt, self.response, self.status, self.token_count
                            ))
                            
                            print(f"Generation complete: {self.token_count} tokens in {elapsed:.2f}s ({tps:.1f}/s)")
                    
                    except json.JSONDecodeError:
                        print(f"Error decoding JSON from Ollama API: {line}")
                        self.status = "Error: JSON decode failed"
                        self.workflow.root.after(0, self.draw)
            
            print(f"Finished processing response stream for node {self.id}")
            
        except Exception as e:
            print(f"Exception in generate_response: {str(e)}")
            import traceback
            traceback.print_exc()
            self.status = f"Error: {str(e)[:20]}..."
            self.workflow.root.after(0, self.draw)
            
            # Update the debug panel with the error
            self.workflow.root.after(0, lambda: self.workflow.root.update_debug_panel(
                system_prompt, user_prompt, self.response, f"Error: {str(e)}", self.token_count
            ))
        
        finally:
            self.current_response = None
            # Clear the active Ollama node reference
            if self.workflow.active_ollama_node == self:
                self.workflow.active_ollama_node = None
    
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
        stop_btn = ctk.CTkButton(frame, text="Stop Generation", command=self.stop_generation, fg_color="#D9534F")
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

class RegexProcessorNode(Node):
    """A node that processes text with regex patterns"""
    node_type = "Regex Processor"
    
    def __init__(self, canvas, x=100, y=100):
        super().__init__(canvas, x, y, "Regex Processor", width=220, height=180)
        
        # Default regex patterns
        self.patterns = [
            {"name": "Remove <think> tags", "pattern": r"<think>.*?</think>", "replace": "", "active": True},
            {"name": "Fix double spaces", "pattern": r"\s{2,}", "replace": " ", "active": True},
            {"name": "Trim whitespace", "pattern": r"^\s+|\s+$", "replace": "", "active": True}
        ]
        
        # Process stats
        self.last_input = ""
        self.last_output = ""
        self.status = "Ready"
    
    def init_sockets(self):
        self.inputs.append(NodeSocket(self, is_input=True, name="Input"))
        self.outputs.append(NodeSocket(self, is_input=False, name="Output"))
    
    def draw(self):
        super().draw()
        
        # Draw pattern count
        active_count = sum(1 for p in self.patterns if p["active"])
        total_count = len(self.patterns)
        
        patterns_id = self.canvas.create_text(
            self.x + 10, self.y + self.header_height + 35,
            text=f"Patterns: {active_count}/{total_count} active", 
            fill="white", anchor="w",
            tags=("node_content", self.id)
        )
        self.items.append(patterns_id)
        
        # Draw status
        status_id = self.canvas.create_text(
            self.x + 10, self.y + self.header_height + 60,
            text=f"Status: {self.status}", 
            fill="#AAA", anchor="w",
            tags=("node_status", self.id)
        )
        self.items.append(status_id)
        
        # Add a preview of the last operation if available
        if self.last_input and self.last_output:
            preview_id = self.canvas.create_text(
                self.x + 10, self.y + self.header_height + 85,
                text="Last run: Processed text",
                fill="#5CB85C", anchor="w",
                tags=("node_preview", self.id)
            )
            self.items.append(preview_id)
    
    def execute(self):
        # Get the input text - this will automatically wait for any processing nodes
        input_text = self.get_input_value("Input")
        
        if not input_text:
            self.status = "No input"
            return {"Output": ""}
        
        # Apply regex patterns
        output_text = input_text
        for pattern in self.patterns:
            if pattern["active"]:
                try:
                    output_text = re.sub(pattern["pattern"], pattern["replace"], output_text, flags=re.DOTALL)
                except Exception as e:
                    raise ValueError(f"Regex error: {str(e)}")
        
        # Store processing info
        self.last_input = input_text
        self.last_output = output_text
        
        return {"Output": output_text}
    
    def show_properties(self):
        super().show_properties()
        
        # Create a frame for the regex properties
        frame = ctk.CTkFrame(self.workflow.properties_frame)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create a scrollable frame for the patterns
        patterns_label = ctk.CTkLabel(frame, text="Regex Patterns:", font=("Arial", 12, "bold"))
        patterns_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        patterns_frame = ctk.CTkScrollableFrame(frame, height=200)
        patterns_frame.pack(fill="x", expand=True, padx=10, pady=5)
        
        # Add pattern entries
        pattern_entries = []
        for i, pattern in enumerate(self.patterns):
            pattern_frame = ctk.CTkFrame(patterns_frame)
            pattern_frame.pack(fill="x", padx=5, pady=5)
            
            # Pattern active checkbox
            active_var = ctk.BooleanVar(value=pattern["active"])
            active_check = ctk.CTkCheckBox(pattern_frame, text="", variable=active_var)
            active_check.grid(row=0, column=0, padx=5, pady=5)
            
            # Pattern name
            name_var = ctk.StringVar(value=pattern["name"])
            name_entry = ctk.CTkEntry(pattern_frame, textvariable=name_var, width=150)
            name_entry.grid(row=0, column=1, padx=5, pady=5)
            
            # Pattern entry
            pattern_var = ctk.StringVar(value=pattern["pattern"])
            pattern_label = ctk.CTkLabel(pattern_frame, text="Pattern:")
            pattern_label.grid(row=1, column=0, padx=5, pady=2, sticky="w")
            pattern_entry = ctk.CTkEntry(pattern_frame, textvariable=pattern_var, width=250)
            pattern_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=2, sticky="ew")
            
            # Replacement entry
            replace_var = ctk.StringVar(value=pattern["replace"])
            replace_label = ctk.CTkLabel(pattern_frame, text="Replace:")
            replace_label.grid(row=2, column=0, padx=5, pady=2, sticky="w")
            replace_entry = ctk.CTkEntry(pattern_frame, textvariable=replace_var, width=250)
            replace_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=2, sticky="ew")
            
            # Delete button
            delete_btn = ctk.CTkButton(
                pattern_frame, 
                text="×", 
                width=30, 
                fg_color="#D9534F",
                command=lambda idx=i: self.delete_pattern(idx, pattern_entries)
            )
            delete_btn.grid(row=0, column=2, padx=5, pady=5)
            
            # Store references to entries and variables
            pattern_entries.append({
                "frame": pattern_frame,
                "active_var": active_var,
                "name_var": name_var,
                "pattern_var": pattern_var,
                "replace_var": replace_var,
                "index": i
            })
        
        # Add a button to add new patterns
        def add_new_pattern():
            new_pattern = {
                "name": "New Pattern", 
                "pattern": r"", 
                "replace": "", 
                "active": True
            }
            self.patterns.append(new_pattern)
            self.show_properties()  # Refresh the panel
        
        add_btn = ctk.CTkButton(frame, text="Add Pattern", command=add_new_pattern)
        add_btn.pack(pady=5)
        
        # Add test section
        test_frame = ctk.CTkFrame(frame)
        test_frame.pack(fill="x", padx=10, pady=(15, 5))
        
        ctk.CTkLabel(test_frame, text="Test Patterns", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=5)
        
        test_input = ctk.CTkTextbox(test_frame, height=80, wrap="word")
        test_input.pack(fill="x", padx=10, pady=5)
        if self.last_input:
            test_input.insert("1.0", self.last_input)
        else:
            test_input.insert("1.0", "Test text with <think>hidden content</think> and  double  spaces.")
        
        # Add test output
        ctk.CTkLabel(test_frame, text="Result:").pack(anchor="w", padx=10, pady=(5, 0))
        test_output = ctk.CTkTextbox(test_frame, height=80, wrap="word")
        test_output.pack(fill="x", padx=10, pady=5)
        if self.last_output:
            test_output.insert("1.0", self.last_output)
        
        # Test button
        def test_patterns():
            input_text = test_input.get("1.0", "end-1c")
            
            # Apply active patterns from the current UI state
            output_text = input_text
            for entry in pattern_entries:
                if entry["active_var"].get():
                    try:
                        pattern = entry["pattern_var"].get()
                        replace = entry["replace_var"].get()
                        output_text = re.sub(pattern, replace, output_text, flags=re.DOTALL)
                    except Exception as e:
                        messagebox.showerror("Regex Error", f"Error in pattern '{pattern}': {str(e)}")
            
            # Update the output display
            test_output.delete("1.0", "end")
            test_output.insert("1.0", output_text)
        
        test_btn = ctk.CTkButton(test_frame, text="Test", command=test_patterns)
        test_btn.pack(pady=5)
        
        # Apply button for all changes
        def apply_changes():
            # Update patterns from UI
            new_patterns = []
            for entry in pattern_entries:
                if entry["index"] < len(self.patterns):  # Make sure the index is valid
                    new_patterns.append({
                        "name": entry["name_var"].get(),
                        "pattern": entry["pattern_var"].get(),
                        "replace": entry["replace_var"].get(),
                        "active": entry["active_var"].get()
                    })
            
            # Update if we have valid patterns
            if new_patterns:
                self.patterns = new_patterns
                self.draw()
        
        apply_btn = ctk.CTkButton(frame, text="Apply Changes", command=apply_changes)
        apply_btn.pack(pady=10)
    
    def delete_pattern(self, idx, entries):
        """Delete a pattern from the list"""
        if 0 <= idx < len(self.patterns):
            # Remove from the model
            self.patterns.pop(idx)
            
            # Remove from the UI
            for entry in entries:
                if entry["index"] == idx:
                    entry["frame"].destroy()
            
            # Refresh the UI
            self.show_properties()

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
        self.active_ollama_node = None  # Track the active Ollama node
        self.force_recompute = False
    
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
    
    def execute_workflow(self):
        """Execute the entire workflow"""
        # Find terminal nodes (nodes with no outgoing connections)
        terminal_nodes = self.get_terminal_nodes()
        
        if not terminal_nodes:
            return False, "No terminal nodes found"
        
        # Track visited nodes to prevent duplicate processing
        processed = set()
        
        # Process each terminal node (which will recursively process dependencies)
        for node in terminal_nodes:
            self.process_node(node, processed)
        
        return True, "Workflow executed successfully"
    
    def process_node(self, node, processed=None):
        """Process a node and its dependencies"""
        if processed is None:
            processed = set()
            
        # Skip if already processed
        if node.id in processed:
            return
        
        # Process the node (which handles waiting for inputs)
        result = node.process()
        processed.add(node.id)
        
        return result
    
    def get_terminal_nodes(self):
        """Find nodes with no outgoing connections"""
        terminal_nodes = []
        
        for node in self.nodes:
            has_outgoing = False
            for output in node.outputs:
                if output.is_connected():
                    has_outgoing = True
                    break
            
            # It's a terminal node if it has outputs but none are connected
            if not has_outgoing and node.outputs:
                terminal_nodes.append(node)
        
        return terminal_nodes
    
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
            return
        
        # Let the node show its properties
        node.show_properties()
    
    def mark_all_dirty(self):
        """Mark all nodes as dirty (needing recalculation)"""
        for node in self.nodes:
            node.dirty = True
            node.draw()

def get_node_subclasses():
    """Get all concrete subclasses of Node that can be instantiated"""
    node_classes = []
    
    # Helper function to recursively find all subclasses
    def find_subclasses(cls):
        direct_subclasses = cls.__subclasses__()
        all_subclasses = []
        for subclass in direct_subclasses:
            all_subclasses.append(subclass)
            all_subclasses.extend(find_subclasses(subclass))
        return all_subclasses
    
    # Get all subclasses of Node
    all_node_classes = find_subclasses(Node)
    
    # Filter out abstract classes and the base Node class itself
    for cls in all_node_classes:
        # Only include non-abstract classes
        if cls.__module__ == '__main__':  # Only include classes from this module
            node_classes.append(cls)
    
    return node_classes

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
        # Configure grid layout
        self.grid_columnconfigure(0, weight=4)  # Canvas area
        self.grid_columnconfigure(1, weight=1)  # Properties panel
        self.grid_rowconfigure(0, weight=4)     # Main workflow area
        self.grid_rowconfigure(1, weight=1)     # Debug panel
        
        # Create main frames
        canvas_frame = ctk.CTkFrame(self)
        canvas_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        properties_frame = ctk.CTkFrame(self)
        properties_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        # Create debug panel (always visible)
        debug_frame = ctk.CTkFrame(self)
        debug_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        
        # Store reference to properties frame
        self.workflow.properties_frame = properties_frame
        
        # Setup canvas area
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.grid_rowconfigure(1, weight=1)
        
        # Toolbar
        toolbar = ctk.CTkFrame(canvas_frame)
        toolbar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        # Dynamically add node buttons based on available Node subclasses
        for node_class in get_node_subclasses():
            node_type_name = getattr(node_class, "node_type", node_class.__name__)
            button = ctk.CTkButton(
                toolbar,
                text=f"Add {node_type_name}",
                command=lambda cls=node_class: self.add_node(cls)
            )
            button.pack(side="left", padx=5, pady=5)

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
        
        # Setup debug panel
        debug_frame.grid_columnconfigure(0, weight=1)
        debug_frame.grid_rowconfigure(1, weight=1)
        
        # Debug header
        debug_header = ctk.CTkFrame(debug_frame)
        debug_header.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        ctk.CTkLabel(debug_header, text="Ollama Debug Panel", font=("Verdana", 14, "bold")).pack(side="left", padx=10, pady=5)
        
        self.debug_status_var = ctk.StringVar(value="Ready")
        self.debug_token_var = ctk.StringVar(value="Tokens: 0")
        
        status_label = ctk.CTkLabel(debug_header, textvariable=self.debug_status_var, font=("Verdana", 11))
        status_label.pack(side="right", padx=10, pady=5)
        
        token_label = ctk.CTkLabel(debug_header, textvariable=self.debug_token_var, font=("Verdana", 11))
        token_label.pack(side="right", padx=10, pady=5)
        
        # Debug content
        debug_content = ctk.CTkFrame(debug_frame)
        debug_content.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        debug_content.grid_columnconfigure(0, weight=3)
        debug_content.grid_columnconfigure(1, weight=4)
        debug_content.grid_rowconfigure(0, weight=1)
        
        # Left panel - input area
        input_frame = ctk.CTkFrame(debug_content)
        input_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        input_frame.grid_columnconfigure(0, weight=1)
        input_frame.grid_rowconfigure(0, weight=0)
        input_frame.grid_rowconfigure(1, weight=1)
        input_frame.grid_rowconfigure(2, weight=0)
        input_frame.grid_rowconfigure(3, weight=1)
        
        # System prompt area
        ctk.CTkLabel(input_frame, text="System Prompt:", font=("Verdana", 12, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.debug_system_text = ctk.CTkTextbox(input_frame, height=80, wrap="word")
        self.debug_system_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # User prompt area
        ctk.CTkLabel(input_frame, text="User Prompt:", font=("Verdana", 12, "bold")).grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.debug_user_text = ctk.CTkTextbox(input_frame, wrap="word")
        self.debug_user_text.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
        
        # Right panel - response area
        response_frame = ctk.CTkFrame(debug_content)
        response_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        response_frame.grid_columnconfigure(0, weight=1)
        response_frame.grid_rowconfigure(0, weight=0)
        response_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(response_frame, text="Response:", font=("Verdana", 12, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.debug_response_text = ctk.CTkTextbox(response_frame, wrap="word")
        self.debug_response_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # Control buttons
        debug_controls = ctk.CTkFrame(debug_frame)
        debug_controls.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        
        # Stop button only active when generation is in progress
        self.stop_debug_btn = ctk.CTkButton(
            debug_controls,
            text="Stop Generation",
            command=self.stop_debug_generation,
            fg_color="#D9534F",
            state="disabled"
        )
        self.stop_debug_btn.pack(side="left", padx=10, pady=5)
        
        # Copy button
        self.copy_debug_btn = ctk.CTkButton(
            debug_controls,
            text="Copy Response",
            command=self.copy_debug_response
        )
        self.copy_debug_btn.pack(side="right", padx=10, pady=5)
    
    def update_debug_panel(self, system_prompt, user_prompt, response, status, token_count):
        """Update the debug panel with the latest information"""
        # Update the system prompt area if provided
        if system_prompt is not None:
            self.debug_system_text.delete("1.0", "end")
            self.debug_system_text.insert("1.0", system_prompt)
        
        # Update the user prompt area if provided
        if user_prompt is not None:
            self.debug_user_text.delete("1.0", "end")
            self.debug_user_text.insert("1.0", user_prompt)
        
        # Update the response area
        if response is not None:
            self.debug_response_text.delete("1.0", "end")
            self.debug_response_text.insert("1.0", response)
            self.debug_response_text.see("end")  # Auto-scroll to the bottom
        
        # Update status and token count
        if status is not None:
            self.debug_status_var.set(status)
        
        self.debug_token_var.set(f"Tokens: {token_count}")
        
        # Update stop button state based on whether generation is active
        if "Generating" in status:
            self.stop_debug_btn.configure(state="normal")
        else:
            self.stop_debug_btn.configure(state="disabled")
    
    def stop_debug_generation(self):
        """Stop the active Ollama generation"""
        if self.workflow.active_ollama_node:
            self.workflow.active_ollama_node.stop_generation()
    
    def copy_debug_response(self):
        """Copy the debug panel response to clipboard"""
        response_text = self.debug_response_text.get("1.0", "end-1c")
        if response_text:
            self.clipboard_clear()
            self.clipboard_append(response_text)
            # Show a brief confirmation
            original_text = self.copy_debug_btn.cget("text")
            self.copy_debug_btn.configure(text="Copied!")
            self.after(1000, lambda: self.copy_debug_btn.configure(text=original_text))
    
    def add_node(self, node_class, x=100, y=100):
        """Add a new node to the workflow"""
        node = node_class(self.node_canvas, x=x, y=y)
        self.workflow.add_node(node)
        node.draw()
    
    def add_example_nodes(self):
        """Add some example nodes to demonstrate the workflow"""
        # Add a static text node
        static_node = StaticTextNode(self.node_canvas, x=100, y=100)
        static_node.text = "Tell me a joke."
        self.workflow.add_node(static_node)
        
        # Add a regex processor node
        regex_node = RegexProcessorNode(self.node_canvas, x=400, y=100)
        self.workflow.add_node(regex_node)
        
        # Add a prompt node
        prompt_node = PromptNode(self.node_canvas, x=700, y=200)
        prompt_node.system_prompt = "You are a helpful assistant."
        self.workflow.add_node(prompt_node)
        
        # Draw the nodes
        static_node.draw()
        regex_node.draw()
        prompt_node.draw()
        
        # Connect the static node to the regex node
        static_output = static_node.outputs[0]
        regex_input = regex_node.inputs[0]
        static_output.connect(regex_input)
        
        # Connect the regex node to the prompt node
        regex_output = regex_node.outputs[0]
        prompt_input = prompt_node.inputs[1]  # User prompt input
        regex_output.connect(prompt_input)
        
        # Redraw the nodes to show the connections
        static_node.draw()
        regex_node.draw()
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
        
        # Create a results window that will update during processing
        results_window = ctk.CTkToplevel(self)
        results_window.title("Workflow Execution")
        results_window.geometry("700x500")
        
        results_text = ctk.CTkTextbox(results_window, wrap="word")
        results_text.pack(fill="both", expand=True, padx=10, pady=10)
        results_text.insert("1.0", "Starting workflow execution...\n\n")
        
        progress_frame = ctk.CTkFrame(results_window)
        progress_frame.pack(fill="x", padx=10, pady=5)
        
        progress_bar = ctk.CTkProgressBar(progress_frame)
        progress_bar.pack(fill="x", padx=10, pady=5, side="left", expand=True)
        progress_bar.set(0)
        
        status_label = ctk.CTkLabel(progress_frame, text="Initializing...")
        status_label.pack(side="right", padx=10)
        
        # Function to update the results window
        def update_results(text, progress=None, status=None):
            if not results_window.winfo_exists():
                return
                
            results_text.insert("end", text + "\n")
            results_text.see("end")
            
            if progress is not None:
                progress_bar.set(progress)
                
            if status is not None:
                status_label.configure(text=status)
                
            # Force UI update
            results_window.update_idletasks()
        
        # Run each end node in a separate thread
        def execute_workflow(self, end_nodes=None):
                """Execute the workflow from end nodes, resolving all dependencies first"""
                if not end_nodes:
                    # Find terminal nodes if not specified
                    end_nodes = self.get_terminal_nodes()
                    
                if not end_nodes:
                    return False, "No end nodes found in workflow"
                    
                # Track visited nodes to prevent cycles
                visited = set()
                processing = set()
                execution_order = []
                
                def visit_node(node):
                    """Depth-first traversal with cycle detection"""
                    if node.id in visited:
                        return True
                        
                    if node.id in processing:
                        return False  # Cycle detected
                        
                    processing.add(node.id)
                    
                    # Visit all input dependencies first
                    for socket in node.inputs:
                        if socket.connected_to:
                            source_node = socket.connected_to.node
                            if not visit_node(source_node):
                                return False
                    
                    # All dependencies resolved
                    processing.remove(node.id)
                    visited.add(node.id)
                    execution_order.append(node)
                    return True
                
                # Visit all end nodes
                for node in end_nodes:
                    if not visit_node(node):
                        return False, "Circular dependency detected in workflow"
                
                # Now process in dependency order
                for node in execution_order:
                    try:
                        node.process()
                    except Exception as e:
                        node.status = f"Error: {str(e)[:20]}..."
                        node.dirty = False
                        node.draw()
                        return False, f"Error processing {node.title}: {str(e)}"
                
                return True, "Workflow executed successfully"
        
        # Start the workflow execution in a background thread
        Thread(target=execute_workflow, daemon=True).start()
    
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


def process_node_async(node, callback=None):
    """Process a node asynchronously and call the callback with the result"""
    def process_thread():
        try:
            # Process the node
            result = node.process()
            
            # Format the result
            result_text = "\n\n".join([f"{key}: {value}" for key, value in result.items()])
            
            # Call the callback with the result
            if callback and result_text.strip():
                node.workflow.root.after(0, lambda: callback(result_text))
        except Exception as e:
            print(f"Error processing node {node.title}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Start processing in a background thread
    thread = Thread(target=process_thread, daemon=True)
    thread.start()
    
    # Return the thread in case we want to monitor it
    return thread

def main():
    app = OllamaFlow()
    app.mainloop()

if __name__ == "__main__":
    main()
