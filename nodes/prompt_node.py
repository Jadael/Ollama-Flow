from nodes.base_node import OllamaBaseNode
import requests
import json
import time
from threading import Thread
from PySide6.QtCore import QObject, Signal, Slot, Qt, QCoreApplication, QThread

class PromptNode(OllamaBaseNode):
    """A node that sends prompts to an LLM and outputs the response"""
    
    # Node identifier and type
    __identifier__ = 'com.ollamaflow.nodes'
    __type__ = 'PromptNode'
    
    # Node display name
    NODE_NAME = 'LLM Prompt'
    
    # Node category for menu organization
    NODE_CATEGORY = 'LLM'
    
    # Define class-level signals for UI updates
    class PromptSignals(QObject):
        update_preview = Signal(object, str)
        update_status = Signal(object, str)
    
    def __init__(self):
        super(PromptNode, self).__init__()
        
        # Set node name that will be displayed
        self.set_name('LLM Prompt')
        
        # Set async flag
        self.is_async_node = True
        
        # Initialize signals
        self.signals = PromptNode.PromptSignals()
        self.signals.update_preview.connect(self._update_preview, Qt.QueuedConnection)
        self.signals.update_status.connect(self._update_status, Qt.QueuedConnection)
        
        # Create basic text properties
        # Each property will automatically create an input
        self.add_text_input('model', 'Model', 'deepseek-r1:32b')
        self.add_text_input('system_prompt', 'System Prompt', 'You are a helpful assistant.')
        self.add_text_input('user_prompt', 'User Prompt', '')
        self.add_text_input('temperature', 'Temperature', '0.7')
        self.add_text_input('top_p', 'Top P', '0.9')
        self.add_text_input('top_k', 'Top K', '40')
        self.add_text_input('repeat_penalty', 'Repeat Penalty', '1.1')
        self.add_text_input('max_tokens', 'Max Tokens', '2048')
        
        # Create output port
        self.add_output('Response')
        
        # Add response preview - exclude from auto-inputs
        self.exclude_property_from_input('response_preview')
        self.exclude_property_from_input('status_info')
        self.add_text_input('response_preview', 'Response', '')
        self.add_text_input('status_info', 'Status', 'Ready')
        
        # Additional prompt node state
        self.stop_requested = False
        self.current_response = None
        self.response = ""
        self.token_count = 0
        self.start_time = None
        
        # Set node color
        self.set_color(217, 86, 59)
    
    @Slot(object, str)
    def _update_preview(self, node, text):
        """Update the response preview in the main thread"""
        if node != self:
            return
        # Use direct property setting here as we're in the main thread
        if QCoreApplication.instance() and QThread.currentThread() == QCoreApplication.instance().thread():
            self.set_property('response_preview', text)
    
    @Slot(object, str)
    def _update_status(self, node, status):
        """Update the node status in the main thread"""
        if node != self:
            return
        # Use direct status setting here as we're in the main thread
        if QCoreApplication.instance() and QThread.currentThread() == QCoreApplication.instance().thread():
            self.set_status(status)
    
    def execute(self):
        """Process the node asynchronously"""
        # Get input values using our new property input system
        system_prompt = self.get_property_value('system_prompt')
        user_prompt = self.get_property_value('user_prompt')
        
        if not user_prompt:
            self.set_status("No user prompt input")
            self.processing = False
            self.processing_done = True
            return {'Response': ""}
        
        # Clear previous response data
        self.response = ""
        self.token_count = 0
        self.stop_requested = False
        
        # Start time tracking
        self.start_time = time.time()
        self.set_status("Generating...")
        
        # Start generation in a separate thread
        Thread(target=self._generation_thread, 
               args=(system_prompt, user_prompt), 
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
            
            # Use signal to update status from worker thread
            final_status = f"Complete: {self.token_count} tokens"
            self.signals.update_status.emit(self, final_status)
            
            # Mark as not processing and done
            self.processing = False
            self.processing_done = True
            
            # Update UI using signal
            preview_text = self.response[:10000] + ('...' if len(self.response) > 10000 else '')
            self.signals.update_preview.emit(self, preview_text)
            
            print(f"Generation thread completed with {self.token_count} tokens")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            # Use signals for thread-safe updates
            self.signals.update_status.emit(self, f"Error: {str(e)}")
            self.processing_error = str(e)
            self.processing = False
            self.processing_done = True
    
    def generate_response(self, system_prompt, user_prompt):
        """Generate a response from the LLM"""
        try:
            # Prepare API call parameters using property values
            options = {
                "temperature": float(self.get_property_value('temperature')),
                "top_p": float(self.get_property_value('top_p')),
                "top_k": int(self.get_property_value('top_k')),
                "repeat_penalty": float(self.get_property_value('repeat_penalty')),
                "num_predict": int(self.get_property_value('max_tokens'))
            }
            
            # Prepare payload
            payload = {
                "model": self.get_property_value('model'),
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
                self.signals.update_status.emit(self, f"API Error: {self.current_response.status_code}")
                print(f"Error from Ollama API: {self.current_response.text}")
                return
            
            # Process the streaming response
            for line in self.current_response.iter_lines():
                if self.stop_requested:
                    print("Generation stopped by user")
                    break
                
                if line:
                    try:
                        data = json.loads(line)
                        if 'response' in data:
                            response_text = data['response']
                            self.response += response_text
                            self.token_count += 1
                            
                            # Update status every few tokens using signal
                            if self.token_count % 5 == 0:
                                elapsed = time.time() - self.start_time
                                tps = self.token_count / elapsed if elapsed > 0 else 0
                                status_text = f"Generating: {self.token_count} tokens ({tps:.1f}/s)"
                                self.signals.update_status.emit(self, status_text)
                                
                                # Update preview occasionally using signal
                                if self.token_count % 10 == 0:
                                    preview = self.response[:10000] + ('...' if len(self.response) > 10000 else '')
                                    self.signals.update_preview.emit(self, preview)
                        
                        # Check for completion
                        if data.get('done', False):
                            elapsed = time.time() - self.start_time
                            tps = self.token_count / elapsed if elapsed > 0 else 0
                            status_text = f"Complete: {self.token_count} tokens ({tps:.1f}/s)"
                            self.signals.update_status.emit(self, status_text)
                            
                            # Update final result using signal
                            preview = self.response[:10000] + ('...' if len(self.response) > 10000 else '')
                            self.signals.update_preview.emit(self, preview)
                            print(f"Generation complete: {self.token_count} tokens in {elapsed:.2f}s ({tps:.1f}/s)")
                    
                    except json.JSONDecodeError:
                        print(f"Error decoding JSON from Ollama API: {line}")
                        self.signals.update_status.emit(self, "Error: JSON decode failed")
            
        except Exception as e:
            print(f"Exception in generate_response: {str(e)}")
            import traceback
            traceback.print_exc()
            self.signals.update_status.emit(self, f"Error: {str(e)[:20]}...")
        
        finally:
            self.current_response = None
