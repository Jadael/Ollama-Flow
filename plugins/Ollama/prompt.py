from core.node import Node
from core.socket import NodeSocket
import requests
import json
from threading import Thread, Event
import time
import customtkinter as ctk

class PromptNode(Node):
    """A node that sends prompts to an LLM and outputs the response"""
    node_type = "LLM Prompt"
    category = "Ollama"
    
    # Node dimensions - increased to accommodate multiple inputs and properties
    default_width = 280
    default_height = 260
    min_width = 240
    min_height = 200
    
    # Property definitions
    properties = {
        "model": {
            "type": "string",
            "default": "deepseek-r1:14b",
            "ui": {
                "widget": "entry",
                "label": "Model",
                "preview_on_node": True,
                "preview_length": 20,
            }
        },
        "system_prompt": {
            "type": "string",
            "default": "You are a helpful assistant.",
            "ui": {
                "widget": "text_area",
                "label": "System Prompt",
                "preview_on_node": True,
                "preview_length": 30,
            }
        },
        "temperature": {
            "type": "number",
            "default": 0.7,
            "ui": {
                "widget": "slider",
                "label": "Temperature",
                "min": 0.0,
                "max": 1.5,
                "preview_on_node": True,
            }
        }
    }
    
    def __init__(self, canvas, x=100, y=100, title=None, width=None, height=None):
        super().__init__(canvas, x, y, title, width, height)
        
        # Flag this as an async node
        self.is_async_node = True
        
        # Additional prompt node state
        self.stop_event = Event()
        self.current_response = None
        self.response = ""
        self.token_count = 0
        self.start_time = None
    
    def init_sockets(self):
        """Initialize the node's input and output sockets"""
        self.inputs.append(NodeSocket(
            self, 
            name="System Prompt", 
            data_type="string", 
            is_input=True
        ))
        self.inputs.append(NodeSocket(
            self, 
            name="User Prompt", 
            data_type="string", 
            is_input=True
        ))
        self.outputs.append(NodeSocket(
            self, 
            name="Response", 
            data_type="string", 
            is_input=False
        ))
    
    def execute(self):
        """Process the node and return output values"""
        # Get input values from connected nodes
        system_input = self.get_input_value("System Prompt")
        user_input = self.get_input_value("User Prompt")
        
        if not user_input:
            self.status = "No user prompt input"
            self.processing = False
            self.processing_complete_event.set()
            return {"Response": ""}
        
        # Use system prompt from input if provided, otherwise use the node's system prompt
        system_prompt = system_input if system_input else self.system_prompt
        
        # Clear previous response data
        self.response = ""
        self.token_count = 0
        self.stop_event.clear()
        
        # Start time tracking
        self.start_time = time.time()
        self.status = "Generating..."
        self.draw()
        
        # Start generation in a separate thread without waiting
        def generation_thread():
            try:
                self.generate_response(system_prompt, user_input)
                # Once complete, update output_cache and mark node as not dirty
                self.output_cache = {"Response": self.response}
                self.dirty = False
                self.status = "Complete"
                self.processing = False
                self.processing_complete_event.set()
                
                # Mark node as processed in workflow
                self.workflow.node_processed = True
                
                # Update UI
                if hasattr(self.canvas, 'after'):
                    self.canvas.after(0, self.draw)
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.status = f"Error: {str(e)}"
                self.processing = False
                self.processing_complete_event.set()
                
                # Update UI
                if hasattr(self.canvas, 'after'):
                    self.canvas.after(0, self.draw)
        
        Thread(target=generation_thread, daemon=True).start()
        
        # Return a placeholder result
        # The real result will be updated asynchronously
        return {"Response": "Processing..."}
    
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
    
    def generate_response(self, system_prompt, user_prompt):
        """Generate a response from the LLM"""
        try:
            # Prepare API call parameters
            options = {
                "temperature": self.temperature,
                "top_p": 0.9,
                "top_k": 40
            }
            
            # Prepare payload
            payload = {
                "model": self.model,
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
                self.canvas.after(0, self.draw)
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
                                self.canvas.after(0, self.draw)
                        
                        # Check for completion
                        if data.get('done', False):
                            elapsed = time.time() - self.start_time
                            tps = self.token_count / elapsed if elapsed > 0 else 0
                            self.status = f"Complete: {self.token_count} tokens ({tps:.1f}/s)"
                            self.canvas.after(0, self.draw)
                            print(f"Generation complete: {self.token_count} tokens in {elapsed:.2f}s ({tps:.1f}/s)")
                    
                    except json.JSONDecodeError:
                        print(f"Error decoding JSON from Ollama API: {line}")
                        self.status = "Error: JSON decode failed"
                        self.canvas.after(0, self.draw)
            
        except Exception as e:
            print(f"Exception in generate_response: {str(e)}")
            import traceback
            traceback.print_exc()
            self.status = f"Error: {str(e)[:20]}..."
            self.canvas.after(0, self.draw)
        
        finally:
            self.current_response = None
    
    def create_properties_ui(self, parent):
        """Create node-specific property UI"""
        # Use the default properties panel and add custom controls
        properties_frame = super().create_properties_ui(parent)
        
        # Add specific control buttons
        controls_frame = ctk.CTkFrame(parent)
        controls_frame.pack(fill="x", padx=10, pady=10)
        
        # Stop button
        stop_btn = ctk.CTkButton(
            controls_frame, 
            text="Stop Generation", 
            command=self.stop_generation, 
            fg_color="#D9534F"
        )
        stop_btn.pack(pady=5, fill="x")
        
        # View Response button
        def view_response():
            response_window = ctk.CTkToplevel(parent)
            response_window.title("LLM Response")
            response_window.geometry("600x400")
            
            response_text = ctk.CTkTextbox(response_window, wrap="word")
            response_text.pack(fill="both", expand=True, padx=10, pady=10)
            response_text.insert("1.0", self.response)
            
            copy_btn = ctk.CTkButton(
                response_window, 
                text="Copy to Clipboard",
                command=lambda: response_window.clipboard_append(self.response)
            )
            copy_btn.pack(pady=10)
        
        view_btn = ctk.CTkButton(
            controls_frame, 
            text="View Response", 
            command=view_response
        )
        view_btn.pack(pady=5, fill="x")
        
        return properties_frame
    
    def calculate_min_height(self):
        """Calculate minimum height based on content"""
        # Base height from parent calculation
        min_height = super().calculate_min_height()
        
        # Add space for response preview
        if self.response:
            min_height += 40  # Additional space for response preview
            
        return max(min_height, self.min_height)
