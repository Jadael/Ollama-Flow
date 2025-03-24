from nodes.base_node import OllamaBaseNode
import requests
import json
import re
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
    NODE_CATEGORY = 'Basic'
    
    # Define class-level signals for UI updates
    class PromptSignals(QObject):
        update_filtered_preview = Signal(object, str)
        update_raw_preview = Signal(object, str)
        update_status = Signal(object, str)
    
    def __init__(self):
        super(PromptNode, self).__init__()
        
        # Set node name that will be displayed
        self.set_name('LLM Prompt')
        
        # Set async flag
        self.is_async_node = True
        
        # Initialize signals
        self.signals = PromptNode.PromptSignals()
        self.signals.update_filtered_preview.connect(self._update_filtered_preview, Qt.QueuedConnection)
        self.signals.update_raw_preview.connect(self._update_raw_preview, Qt.QueuedConnection)
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
        
        # Add response filtering options
        self.add_combo_menu('filter_mode', 'Filter Mode', 
                          ['None', 'Remove Pattern', 'Extract Pattern'], 
                          'Remove Pattern', tab='Filtering')
        self.add_text_input('filter_pattern', 'Filter Pattern', '<think>.*?</think>', tab='Filtering')
        
        # Use text input for boolean flags instead of checkboxes due to NodeGraphQt compatibility
        self.add_text_input('use_regex_flags', 'Use Regex Flags (true/false)', 'true', tab='Filtering')
        self.add_text_input('dotall_flag', 'Dot Matches Newline (true/false)', 'true', tab='Filtering')
        self.add_text_input('multiline_flag', 'Use Multiline Mode (true/false)', 'true', tab='Filtering')
        self.add_text_input('ignorecase_flag', 'Ignore Case (true/false)', 'false', tab='Filtering')
        
        # Create raw output port (unfiltered)
        self.add_output('Raw Response')
        
        # Create filtered output port
        self.add_output('Response')
        
        # Add response preview - exclude from auto-inputs
        self.exclude_property_from_input('response_preview')
        self.exclude_property_from_input('raw_response_preview')
        self.exclude_property_from_input('status_info')
        self.add_text_input('response_preview', 'Filtered Response', '', tab='Response')
        self.add_text_input('raw_response_preview', 'Raw Response', '', tab='Response')
        self.add_text_input('status_info', 'Status', 'Ready')
        
        # Add properties to store the full output values (not just previews)
        self.exclude_property_from_input('full_raw_response')
        self.exclude_property_from_input('full_filtered_response')
        self.add_text_input('full_raw_response', 'Full Raw Response', '')
        self.add_text_input('full_filtered_response', 'Full Filtered Response', '')
        
        # Additional prompt node state
        self.stop_requested = False
        self.current_response = None
        self.response = ""
        self.token_count = 0
        self.start_time = None
        
        # Set node color
        self.set_color(217, 86, 59)
    
    @Slot(object, str)
    def _update_filtered_preview(self, node, text):
        """Update the filtered response preview in the main thread"""
        if node != self:
            return
        # Use direct property setting here as we're in the main thread
        if QCoreApplication.instance() and QThread.currentThread() == QCoreApplication.instance().thread():
            self.set_property('response_preview', text)
    
    @Slot(object, str)
    def _update_raw_preview(self, node, text):
        """Update the raw response preview in the main thread"""
        if node != self:
            return
        # Use direct property setting here as we're in the main thread
        if QCoreApplication.instance() and QThread.currentThread() == QCoreApplication.instance().thread():
            self.set_property('raw_response_preview', text)
    
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
            return {'Response': "", 'Raw Response': ""}
        
        # Clear previous response data
        self.response = ""
        self.token_count = 0
        self.stop_requested = False
        
        # Start time tracking
        self.start_time = time.time()
        self.set_status("Generating...")
        
        # Clear previous preview content
        self.signals.update_filtered_preview.emit(self, "")
        self.signals.update_raw_preview.emit(self, "")
        
        # Start generation in a separate thread
        Thread(target=self._generation_thread, 
               args=(system_prompt, user_prompt), 
               daemon=True).start()
        
        # Return a placeholder result
        return {'Response': "Processing...", 'Raw Response': "Processing..."}
    
    def _generation_thread(self, system_prompt, user_prompt):
        """Thread for async generation"""
        try:
            self.generate_response(system_prompt, user_prompt)
            
            # Log the raw response size for debugging
            print(f"Raw response generated - {len(self.response)} characters")
            
            # Apply filtering to the response only after generation is complete
            print(f"Preparing to filter response with mode: {self.get_property_value('filter_mode')}")
            filtered_response = self.apply_response_filtering(self.response)
            
            print(f"Filtering complete - Raw: {len(self.response)} chars, Filtered: {len(filtered_response)} chars")
            
            # Verify filtering actually did something
            if filtered_response == self.response and self.get_property_value('filter_mode') != 'None':
                print("WARNING: Filtered response is identical to raw response despite filtering being enabled")
                if self.get_property_value('filter_mode') == 'Remove Pattern':
                    print(f"Check if pattern '{self.get_property_value('filter_pattern')}' exists in the response")
                elif self.get_property_value('filter_mode') == 'Extract Pattern':
                    print(f"Check if pattern '{self.get_property_value('filter_pattern')}' matches anything in the response")
            
            # Store the full output values in properties for serialization
            self.thread_safe_set_property('full_raw_response', self.response)
            self.thread_safe_set_property('full_filtered_response', filtered_response)
            
            # Prepare result dictionary
            result_dict = {
                'Raw Response': self.response,
                'Response': filtered_response
            }
            
            # Use the base node's method to handle async completion
            self.async_processing_complete(result_dict)
            
            # Use signal to update status from worker thread
            final_status = f"Complete: {self.token_count} tokens"
            self.signals.update_status.emit(self, final_status)
            
            # Update both raw and filtered previews with the final content
            raw_preview = self.response[:10000] + ('...' if len(self.response) > 10000 else '')
            self.signals.update_raw_preview.emit(self, raw_preview)
            
            filtered_preview = filtered_response[:10000] + ('...' if len(filtered_response) > 10000 else '')
            self.signals.update_filtered_preview.emit(self, filtered_preview)
            
            print(f"Generation thread completed with {self.token_count} tokens")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            # Use signals for thread-safe updates
            self.signals.update_status.emit(self, f"Error: {str(e)}")
            self.processing_error = str(e)
            self.processing = False
            self.processing_done = True
    
    def apply_response_filtering(self, text):
        """Apply regex filtering to the response based on filter settings"""
        filter_mode = self.get_property_value('filter_mode')
        
        print(f"Applying filter mode: '{filter_mode}'")
        
        # If no filtering is selected or filter mode is not recognized, return the original text
        if not filter_mode or filter_mode == 'None':
            print("No filtering applied - returning original text")
            return text
            
        try:
            # Get pattern
            pattern = self.get_property_value('filter_pattern')
            if not pattern:
                print("No filter pattern provided - returning original text")
                return text
                
            print(f"Using filter pattern: '{pattern}'")
            
            # Compile regex with flags if enabled
            flags = 0
            use_flags = self.get_property_value('use_regex_flags').lower() == 'true'
            
            if use_flags:
                if self.get_property_value('dotall_flag').lower() == 'true':
                    flags |= re.DOTALL
                    print("Using DOTALL flag")
                    
                if self.get_property_value('multiline_flag').lower() == 'true':
                    flags |= re.MULTILINE
                    print("Using MULTILINE flag")
                    
                if self.get_property_value('ignorecase_flag').lower() == 'true':
                    flags |= re.IGNORECASE
                    print("Using IGNORECASE flag")
            
            # Compile the regex with the flags
            try:
                compiled_pattern = re.compile(pattern, flags)
                print(f"Pattern compiled successfully with flags: {flags}")
            except re.error as e:
                print(f"Error compiling regex pattern: {e}")
                return text
            
            # Apply filtering based on mode
            if filter_mode == 'Remove Pattern':
                print("Applying 'Remove Pattern' filtering")
                result = compiled_pattern.sub('', text)
                print(f"Filtering removed {len(text) - len(result)} characters")
                return result
                
            elif filter_mode == 'Extract Pattern':
                print("Applying 'Extract Pattern' filtering")
                matches = compiled_pattern.findall(text)
                
                if not matches:
                    print("No matches found with pattern")
                    return ""
                    
                print(f"Found {len(matches)} matches")
                
                # Handle tuple results from capturing groups
                result = []
                for match in matches:
                    if isinstance(match, tuple):
                        # Use the first capturing group if there are multiple
                        result.append(match[0] if match else "")
                    else:
                        result.append(match)
                        
                joined_result = "\n".join(result)
                print(f"Extracted {len(joined_result)} characters")
                return joined_result
                
            else:
                print(f"Unrecognized filter mode: '{filter_mode}' - returning original text")
                return text
                
        except Exception as e:
            import traceback
            print(f"Error in response filtering: {e}")
            traceback.print_exc()
            return text  # Return original text on error
    
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
                                
                                # Only update the raw preview during streaming
                                if self.token_count % 10 == 0:
                                    raw_preview = self.response[:10000] + ('...' if len(self.response) > 10000 else '')
                                    self.signals.update_raw_preview.emit(self, raw_preview)
                        
                        # Check for completion
                        if data.get('done', False):
                            elapsed = time.time() - self.start_time
                            tps = self.token_count / elapsed if elapsed > 0 else 0
                            status_text = f"Complete: {self.token_count} tokens ({tps:.1f}/s)"
                            self.signals.update_status.emit(self, status_text)
                            
                            # Final update for raw preview
                            raw_preview = self.response[:10000] + ('...' if len(self.response) > 10000 else '')
                            self.signals.update_raw_preview.emit(self, raw_preview)
                            
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
    
    def deserialize(self, node_dict, namespace=None, context=None):
        """Called when the node is being deserialized from a saved workflow"""
        # Call the base class deserialize first
        super(PromptNode, self).deserialize(node_dict, namespace, context)
        
        # Get the saved output values from properties
        raw_response = self.get_property('full_raw_response')
        filtered_response = self.get_property('full_filtered_response')
        
        print(f"PromptNode {self.name()}: Checking saved outputs: raw={bool(raw_response)}, filtered={bool(filtered_response)}")
        
        # If we have output values, restore them to the output cache
        if raw_response or filtered_response:
            if not hasattr(self, 'output_cache'):
                self.output_cache = {}
                
            self.output_cache['Raw Response'] = raw_response
            self.output_cache['Response'] = filtered_response
            
            # Set previews
            raw_preview = raw_response[:10000] + ('...' if len(raw_response) > 10000 else '')
            self.set_property('raw_response_preview', raw_preview)
            
            filtered_preview = filtered_response[:10000] + ('...' if len(filtered_response) > 10000 else '')
            self.set_property('response_preview', filtered_preview)
            
            print(f"PromptNode {self.name()}: Restored outputs from properties")
            
            # Set dirty state based on recalculation mode
            recalc_mode = self.get_property('recalculation_mode')
            if recalc_mode == 'Never dirty':
                self.dirty = False
                print(f"PromptNode {self.name()}: Set to not dirty based on 'Never dirty' mode and restored outputs")
    
    def has_valid_cache(self):
        """Check if the prompt node has a valid output cache"""
        # Check the output properties first
        raw_response = self.get_property('full_raw_response')
        filtered_response = self.get_property('full_filtered_response')
        
        if raw_response and filtered_response:
            return True
            
        # Fallback to output_cache check
        return (hasattr(self, 'output_cache') and 
                'Raw Response' in self.output_cache and 
                'Response' in self.output_cache and
                self.output_cache['Raw Response'] and
                self.output_cache['Response'])
