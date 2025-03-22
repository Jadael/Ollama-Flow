from nodes.base_node import OllamaBaseNode
import requests
import json
import time
from threading import Thread, Event
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Slot, Signal

class PromptNode(OllamaBaseNode):
    """A node that sends prompts to an LLM and outputs the response"""
    
    # Node identifier and name
    __identifier__ = 'com.ollamaflow.nodes'
    __type__ = 'PromptNode'
    NODE_NAME = 'PromptNode'
    
    def __init__(self):
        super(PromptNode, self).__init__()
        
        # Set node name that will be displayed
        self.set_name('LLM Prompt')
        
        # Set async flag
        self.is_async_node = True
        
        # Create input and output ports
        self.add_input('System Prompt')
        self.add_input('User Prompt')
        self.add_output('Response')
        
        # Create properties with simpler API
        models = ['deepseek-r1:32b', 'llama3:8b', 'llama3:70b', 'phi3:14b']
        self.add_combo_menu('model', 'Model', items=models, default='deepseek-r1:32b')
        self.add_text_input('system_prompt', 'System Prompt', 'You are a helpful assistant.')
        self.add_float_slider('temperature', 'Temperature', value=0.7, range=(0.0, 1.5))
        
        # Add advanced parameters with simpler API
        self.add_float_slider('top_p', 'Top P', value=0.9, range=(0.0, 1.0))
        self.add_int_slider('top_k', 'Top K', value=40, range=(1, 100))
        self.add_float_slider('repeat_penalty', 'Repeat Penalty', value=1.1, range=(0.0, 2.0))
        self.add_int_slider('max_tokens', 'Max Tokens', value=2048, range=(1, 8192))
        
        # Add response preview
        self.add_text_input('response_preview', 'Response', '')
        
        # Additional prompt node state
        self.stop_event = Event()
        self.current_response = None
        self.response = ""
        self.token_count = 0
        self.start_time = None
        
        # Set node color
        self.set_color(217, 86, 59)
        
        # Create custom widget for extra controls
        self.create_widgets()
    
    def create_widgets(self):
        """Create custom control widget"""
        # Create widget to hold the buttons
        control_widget = QWidget()
        layout = QVBoxLayout(control_widget)
        
        # Create stop button
        self.stop_button = QPushButton("Stop Generation")
        self.stop_button.clicked.connect(self.stop)
        layout.addWidget(self.stop_button)
        
        # Create clear button
        self.clear_button = QPushButton("Clear Response")
        self.clear_button.clicked.connect(self.clear_response)
        layout.addWidget(self.clear_button)
        
        # Set layout
        control_widget.setLayout(layout)
        
        # Add widget to node
        self.add_custom_widget(control_widget, tab='Controls')
    
    def clear_response(self):
        """Clear the current response"""
        self.response = ""
        self.set_property('response_preview', "")
        self.output_cache = {}
        self.mark_dirty()
    
    def stop(self):
        """Stop the current generation process"""
        self.stop_event.set()
        if self.current_response:
            try:
                self.current_response.close()
            except:
                pass
        self.set_status("Stopped")
    
    def execute(self):
        """Process the node asynchronously"""
        # Get input values
        system_input = self.get_input_data('System Prompt')
        user_input = self.get_input_data('User Prompt')
        
        if not user_input:
            self.set_status("No user prompt input")
            self.processing = False
            self.processing_complete_event.set()
            return {'Response': ""}
        
        # Use system prompt from input if provided, otherwise use the node's system prompt
        system_prompt = system_input if system_input else self.get_property('system_prompt')
        
        # Clear previous response data
        self.response = ""
        self.token_count = 0
        self.stop_event.clear()
        
        # Start time tracking
        self.start_time = time.time()
        self.set_status("Generating...")
        
        # Start generation in a separate thread
        Thread(target=self._generation_thread, 
               args=(system_prompt, user_input), 
               daemon=True).start()
        
        # Return a placeholder result
        return {'Response': "Processing..."}
    
    def _generation_thread(self, system_prompt, user_prompt):
        """Thread for async generation"""
        try:
            self.generate_response(system_prompt, user_prompt)
            # Once complete, update output_cache and mark node as not dirty
            self.output_cache = {'Response': self.response}
            self.dirty = False
            self.set_status("Complete")
            self.processing = False
            self.processing_complete_event.set()
            
            # Update UI
            self.set_property('response_preview', self.response[:10000] + 
                            ('...' if len(self.response) > 10000 else ''))
            self.set_output_data('Response', self.response)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.set_status(f"Error: {str(e)}")
            self.processing = False
            self.processing_complete_event.set()
    
    def generate_response(self, system_prompt, user_prompt):
        """Generate a response from the LLM"""
        try:
            # Prepare API call parameters
            options = {
                "temperature": self.get_property('temperature'),
                "top_p": self.get_property('top_p'),
                "top_k": self.get_property('top_k'),
                "repeat_penalty": self.get_property('repeat_penalty'),
                "num_predict": self.get_property('max_tokens')
            }
            
            # Prepare payload
            payload = {
                "model": self.get_property('model'),
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
                self.set_status(f"API Error: {self.current_response.status_code}")
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
                            
                            # Update status every 10 tokens
                            if self.token_count % 10 == 0:
                                elapsed = time.time() - self.start_time
                                tps = self.token_count / elapsed if elapsed > 0 else 0
                                self.set_status(f"Generating: {self.token_count} tokens ({tps:.1f}/s)")
                                
                                # Update preview occasionally
                                if self.token_count % 30 == 0:
                                    preview = self.response[:10000] + ('...' if len(self.response) > 10000 else '')
                                    self.set_property('response_preview', preview)
                        
                        # Check for completion
                        if data.get('done', False):
                            elapsed = time.time() - self.start_time
                            tps = self.token_count / elapsed if elapsed > 0 else 0
                            self.set_status(f"Complete: {self.token_count} tokens ({tps:.1f}/s)")
                            
                            # Update final result
                            preview = self.response[:10000] + ('...' if len(self.response) > 10000 else '')
                            self.set_property('response_preview', preview)
                            print(f"Generation complete: {self.token_count} tokens in {elapsed:.2f}s ({tps:.1f}/s)")
                    
                    except json.JSONDecodeError:
                        print(f"Error decoding JSON from Ollama API: {line}")
                        self.set_status("Error: JSON decode failed")
            
        except Exception as e:
            print(f"Exception in generate_response: {str(e)}")
            import traceback
            traceback.print_exc()
            self.set_status(f"Error: {str(e)[:20]}...")
        
        finally:
            self.current_response = None
