import time
from threading import Thread, Event
from PySide6.QtCore import QObject, Signal, Qt, Slot, QCoreApplication

class ExecutorSignalHandler(QObject):
    """Signal handler for workflow executor thread-safe operations"""
    execution_completed = Signal(tuple)  # (success, message)

    @Slot(tuple)
    def _emit_completion(self, result):
        """Receive result from worker thread and emit signal"""
        self.execution_completed.emit(result)

# Create a singleton instance of the signal handler
_executor_signals = None

def get_executor_signals():
    """Get or create the executor signals singleton"""
    global _executor_signals
    if _executor_signals is None:
        # Only create when we have a QApplication instance
        if QCoreApplication.instance() is not None:
            _executor_signals = ExecutorSignalHandler()
    return _executor_signals

class WorkflowExecutor:
    """Handles the execution of a NodeGraphQt workflow"""
    
    def __init__(self, graph):
        self.graph = graph
        self.execution_thread = None
        self.execution_complete_event = Event()
        self.execution_complete_event.set()  # Initially not executing
        
        # Store the callback for later use
        self.callback = None
    
    def execute_workflow(self, callback=None):
        """Execute the entire workflow with a callback when done"""
        # Don't allow multiple executions at once
        if self.execution_thread and self.execution_thread.is_alive():
            return False, "Workflow is already running"
            
        # Clear the completion event
        self.execution_complete_event.clear()
        
        # Store the callback
        self.callback = callback
        
        # Connect the signal if not already connected
        signal_handler = get_executor_signals()
        if callback and signal_handler:
            # We don't have a way to check if already connected in PySide6, 
            # so we'll just connect (Qt handles duplicate connections safely)
            signal_handler.execution_completed.connect(
                self._handle_completion_on_main_thread, 
                Qt.QueuedConnection
            )
        
        # Create and start the execution thread
        self.execution_thread = Thread(target=self._execute_workflow_thread, daemon=True)
        self.execution_thread.start()
        
        return True, "Workflow execution started"
    
    def _handle_completion_on_main_thread(self, result):
        """Handle the workflow completion on the main thread"""
        print(f"Handling workflow completion on main thread: {result}")
        if self.callback:
            try:
                self.callback(result)
            except Exception as e:
                print(f"Error in workflow completion callback: {e}")
                import traceback
                traceback.print_exc()
    
    def _execute_workflow_thread(self):
        """Internal method to execute the workflow in a background thread"""
        result = (False, "No nodes processed")
        node_processed = False
        
        try:
            print("Starting workflow execution in background thread...")
            
            # Get all nodes in the graph
            all_nodes = []
            if hasattr(self.graph, 'all_nodes') and callable(getattr(self.graph, 'all_nodes')):
                all_nodes = self.graph.all_nodes()
            elif hasattr(self.graph, 'nodes') and callable(getattr(self.graph, 'nodes')):
                all_nodes = self.graph.nodes()
            
            # Find all dirty nodes that need processing
            dirty_nodes = []
            for node in all_nodes:
                if hasattr(node, 'dirty') and node.dirty and hasattr(node, 'compute'):
                    dirty_nodes.append(node)
            
            print(f"Found {len(dirty_nodes)} dirty nodes to process")
            
            # Process dirty nodes if we have any
            if dirty_nodes:
                for node in dirty_nodes:
                    try:
                        node_name = "Unknown"
                        if hasattr(node, 'name') and callable(getattr(node, 'name')):
                            node_name = node.name()
                        print(f"Processing node: {node_name}")
                        node.compute()
                        node_processed = True
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        # Get node name safely
                        node_name = node.name() if callable(getattr(node, 'name', None)) else str(node)
                        result = (False, f"Error executing node {node_name}: {str(e)}")
                        break
            # If no dirty nodes found, fall back to processing terminal nodes
            # This maintains backward compatibility with the original approach
            elif terminal_nodes := self._get_terminal_nodes():
                print(f"No dirty nodes found, processing {len(terminal_nodes)} terminal nodes")
                for node in terminal_nodes:
                    try:
                        node_name = "Unknown"
                        if hasattr(node, 'name') and callable(getattr(node, 'name')):
                            node_name = node.name()
                        print(f"Processing terminal node: {node_name}")
                        if hasattr(node, 'compute'):
                            node.compute()
                            node_processed = True
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        # Get node name safely
                        node_name = node.name() if callable(getattr(node, 'name', None)) else str(node)
                        result = (False, f"Error executing node {node_name}: {str(e)}")
                        break
            # If still no nodes to process, try all nodes with outputs
            else:
                print("No dirty or terminal nodes found, trying all nodes with outputs")
                for node in all_nodes:
                    # Check if the node has outputs
                    has_outputs = False
                    if callable(getattr(node, 'output_ports', None)):
                        has_outputs = bool(node.output_ports())
                    elif hasattr(node, 'outputs'):
                        has_outputs = bool(node.outputs)
                        
                    if has_outputs:
                        try:
                            node_name = "Unknown"
                            if hasattr(node, 'name') and callable(getattr(node, 'name')):
                                node_name = node.name()
                            print(f"Processing node with outputs: {node_name}")
                            if hasattr(node, 'compute'):
                                node.compute()
                                node_processed = True
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            # Get node name safely
                            node_name = node.name() if callable(getattr(node, 'name', None)) else str(node)
                            result = (False, f"Error executing node {node_name}: {str(e)}")
                            break
            
            # Wait a bit for async nodes to begin processing
            time.sleep(0.5)
            
            # Check which nodes are still processing
            processing_nodes = self._get_processing_nodes()
            
            if processing_nodes:
                node_names = []
                for n in processing_nodes:
                    if hasattr(n, 'name') and callable(getattr(n, 'name')):
                        node_names.append(n.name())
                    else:
                        node_names.append('Unknown')
                print(f"Waiting for {len(processing_nodes)} nodes that are still processing: {', '.join(node_names)}")
                result = (True, f"Workflow started ({len(processing_nodes)} nodes processing)")
                node_processed = True
            
            # Wait for all processing nodes to complete (up to timeout)
            max_wait = 120  # 2 minute timeout (120 seconds)
            start_time = time.time()
            
            while processing_nodes and time.time() - start_time < max_wait:
                print(f"Waiting for {len(processing_nodes)} nodes to complete processing...")
                time.sleep(1)  # Check every second
                processing_nodes = self._get_processing_nodes()
            
            # Check if any nodes were processed
            if node_processed:
                if processing_nodes:
                    print(f"Timeout: {len(processing_nodes)} nodes are still processing")
                    result = (True, f"Workflow partially complete, {len(processing_nodes)} nodes still running")
                else:
                    print(f"Workflow execution completed successfully")
                    result = (True, f"Workflow executed successfully ({len(dirty_nodes)} nodes processed)")
            else:
                print("No nodes needed processing")
                result = (False, "No nodes needed processing")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            result = (False, f"Error executing workflow: {str(e)}")
        
        finally:
            # Set completion event
            self.execution_complete_event.set()
            print(f"Workflow execution completed with result: {result}")
            
            # Emit the signal for the callback to be called on the main thread
            if self.callback:
                signal_handler = get_executor_signals()
                if signal_handler:
                    print(f"Emitting workflow completion signal")
                    QCoreApplication.postEvent(signal_handler, 
                                             QCustomEvent(signal_handler._emit_completion, result))
                else:
                    # Fall back to direct callback - only for extreme cases
                    try:
                        print(f"No signal handler available, calling callback directly")
                        self.callback(result)
                    except Exception as e:
                        print(f"Error in callback: {e}")
    
    def _get_terminal_nodes(self):
        """Find nodes with no outgoing connections"""
        terminal_nodes = []
        
        # Get all nodes (handling either a list or a method)
        all_nodes = []
        if hasattr(self.graph, 'all_nodes') and callable(getattr(self.graph, 'all_nodes')):
            all_nodes = self.graph.all_nodes()
        elif hasattr(self.graph, 'nodes') and callable(getattr(self.graph, 'nodes')):
            all_nodes = self.graph.nodes()
        
        for node in all_nodes:
            has_outgoing = False
            
            # Get output ports (handling either a list or a method)
            output_ports = []
            if hasattr(node, 'output_ports') and callable(getattr(node, 'output_ports')):
                output_ports = node.output_ports()
            elif hasattr(node, 'outputs'):
                output_ports = node.outputs
            
            # Check if any output port is connected
            for port in output_ports:
                if hasattr(port, 'connected_ports') and callable(getattr(port, 'connected_ports')):
                    if port.connected_ports():
                        has_outgoing = True
                        break
                elif hasattr(port, 'connections'):
                    if port.connections:
                        has_outgoing = True
                        break
            
            # It's a terminal node if it has outputs but none are connected
            if not has_outgoing and output_ports:
                terminal_nodes.append(node)
        
        return terminal_nodes
    
    def _get_processing_nodes(self):
        """Get nodes that are currently processing"""
        processing_nodes = []
        
        # Get all nodes (handling either a list or a method)
        all_nodes = []
        if hasattr(self.graph, 'all_nodes') and callable(getattr(self.graph, 'all_nodes')):
            all_nodes = self.graph.all_nodes()
        elif hasattr(self.graph, 'nodes') and callable(getattr(self.graph, 'nodes')):
            all_nodes = self.graph.nodes()
        
        for node in all_nodes:
            if hasattr(node, 'processing') and node.processing:
                processing_nodes.append(node)
        
        return processing_nodes

# Custom event class for safe event posting
from PySide6.QtCore import QEvent

class QCustomEvent(QEvent):
    """Custom event for sending data to the main thread"""
    
    # Use a custom event type
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())
    
    def __init__(self, callback, data):
        super(QCustomEvent, self).__init__(QCustomEvent.EVENT_TYPE)
        self.callback = callback
        self.data = data
    
    def process(self):
        """Process the event by calling the callback with the data"""
        if callable(self.callback):
            self.callback(self.data)

# Override event method in ExecutorSignalHandler
def event(self, event):
    """Handle custom events"""
    if event.type() == QCustomEvent.EVENT_TYPE:
        event.process()
        return True
    return super(ExecutorSignalHandler, self).event(event)

# Add the event method to ExecutorSignalHandler
ExecutorSignalHandler.event = event
