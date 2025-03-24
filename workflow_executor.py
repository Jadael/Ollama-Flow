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
            
            # Build dependency graph first
            # This is a map of node -> list of nodes it depends on
            dependencies = {}
            dependents = {}  # Reverse map: nodes that depend on this node
            
            for node in all_nodes:
                # Initialize dependency lists
                dependencies[node] = []
                if node not in dependents:
                    dependents[node] = []
                
                # Get input ports
                input_ports = []
                if hasattr(node, 'input_ports') and callable(getattr(node, 'input_ports')):
                    input_ports = node.input_ports()
                elif hasattr(node, 'inputs'):
                    input_ports = node.inputs
                    
                # For each input port, find connected nodes
                for input_port in input_ports:
                    connected_ports = []
                    if hasattr(input_port, 'connected_ports') and callable(getattr(input_port, 'connected_ports')):
                        connected_ports = input_port.connected_ports()
                    elif hasattr(input_port, 'connections'):
                        connected_ports = input_port.connections
                    
                    # Add each connected node as a dependency
                    for connected_port in connected_ports:
                        if hasattr(connected_port, 'node') and callable(getattr(connected_port, 'node')):
                            connected_node = connected_port.node()
                            if connected_node in all_nodes:
                                dependencies[node].append(connected_node)
                                if connected_node not in dependents:
                                    dependents[connected_node] = []
                                dependents[connected_node].append(node)
            
            print("Built dependency graph:")
            for node in dependencies:
                node_name = node.name() if hasattr(node, 'name') and callable(getattr(node, 'name')) else "Unknown"
                dep_names = [dep.name() if hasattr(dep, 'name') and callable(getattr(dep, 'name')) else "Unknown" for dep in dependencies[node]]
                print(f"  Node {node_name} depends on: {', '.join(dep_names) if dep_names else 'None'}")
            
            # Find nodes that should be processed
            nodes_to_process = set()

            for node in all_nodes:
                node_name = node.name() if hasattr(node, 'name') and callable(getattr(node, 'name')) else "Unknown"
                
                # Check recalculation mode
                recalc_mode = "Dirty if inputs change"  # Default mode
                if hasattr(node, 'get_property') and callable(getattr(node, 'get_property')):
                    try:
                        recalc_mode = node.get_property('recalculation_mode')
                    except:
                        pass
                
                # Determine if node should be processed
                should_process = False
                
                if recalc_mode == 'Always dirty':
                    # Always process these nodes
                    print(f"Node {node_name}: Adding to processing queue (Always dirty mode)")
                    should_process = True
                    # Mark as dirty to ensure processing
                    if hasattr(node, 'dirty'):
                        node.dirty = True
                elif recalc_mode == 'Never dirty':
                    # Check if the node has a valid cache
                    has_valid_cache = False
                    
                    if hasattr(node, 'has_valid_cache') and callable(getattr(node, 'has_valid_cache')):
                        has_valid_cache = node.has_valid_cache()
                    elif hasattr(node, 'output_cache') and node.output_cache:
                        has_valid_cache = True
                    
                    if has_valid_cache:
                        # Skip processing for Never dirty with valid cached output
                        print(f"Node {node_name}: Skipping (Never dirty mode with valid cache)")
                        should_process = False
                        # Ensure it's marked not dirty
                        if hasattr(node, 'dirty'):
                            node.dirty = False
                    else:
                        # Process even in Never dirty mode if cache is invalid
                        print(f"Node {node_name}: Adding to processing queue (Never dirty but invalid cache)")
                        should_process = True
                elif hasattr(node, 'dirty') and node.dirty:
                    print(f"Node {node_name}: Adding to processing queue (dirty)")
                    should_process = True
                
                if should_process and hasattr(node, 'compute') and callable(getattr(node, 'compute')):
                    nodes_to_process.add(node)
            
            # No nodes to process? We're done
            if not nodes_to_process:
                print("No nodes need processing - workflow is up to date")
                return (True, "Workflow is up to date")
            
            print(f"Found {len(nodes_to_process)} nodes to process")
            
            # Create processing queue with proper dependency order
            processing_queue = []
            visited = set()
            temp_visited = set()  # For cycle detection
            
            def visit(node):
                """DFS traversal to build topological sort"""
                if node in temp_visited:
                    # Cycle detected - graph is not acyclic
                    print(f"Warning: Cycle detected involving node {node.name() if hasattr(node, 'name') and callable(getattr(node, 'name')) else 'Unknown'}")
                    return
                
                if node in visited:
                    return
                    
                temp_visited.add(node)
                
                # Visit dependencies first
                for dep in dependencies[node]:
                    if dep in nodes_to_process:  # Only visit nodes that need processing
                        visit(dep)
                
                # Done with dependencies, add to processing queue
                temp_visited.remove(node)
                visited.add(node)
                processing_queue.append(node)
            
            # Start with "root" nodes - those that need processing but have no dependencies in the processing set
            for node in nodes_to_process:
                # Check if this node has any dependencies that need processing
                has_unprocessed_deps = any(dep in nodes_to_process for dep in dependencies[node])
                if not has_unprocessed_deps:
                    visit(node)
            
            # Process any remaining nodes (in case of cycles)
            for node in nodes_to_process:
                if node not in visited:
                    visit(node)
            
            # Reverse the queue for proper processing order (dependencies first)
            processing_queue.reverse()
            
            print("Processing queue order:")
            for i, node in enumerate(processing_queue):
                node_name = node.name() if hasattr(node, 'name') and callable(getattr(node, 'name')) else "Unknown"
                print(f"  {i+1}. {node_name}")
            
            # Now process nodes in order
            processed_count = 0
            
            for node in processing_queue:
                try:
                    node_name = node.name() if hasattr(node, 'name') and callable(getattr(node, 'name')) else "Unknown"
                    print(f"Processing node: {node_name}")
                    
                    # Call compute - make sure upstream dependencies are handled properly
                    # Note: compute() typically has its own dependency processing, but our topological sort
                    # should ensure minimal redundant processing
                    node.compute()
                    processed_count += 1
                    node_processed = True
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    node_name = node.name() if hasattr(node, 'name') and callable(getattr(node, 'name')) else "Unknown"
                    result = (False, f"Error executing node {node_name}: {str(e)}")
                    break
            
            # Wait for async nodes to complete
            time.sleep(0.5)  # Brief pause for any async nodes to begin processing
            
            # Check which nodes are still processing
            processing_nodes = self._get_processing_nodes()
            
            if processing_nodes:
                node_names = []
                for n in processing_nodes:
                    node_name = n.name() if hasattr(n, 'name') and callable(getattr(n, 'name')) else "Unknown"
                    node_names.append(node_name)
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
                    result = (True, f"Workflow executed successfully ({processed_count} nodes processed)")
            elif result[0]:  # If successful but no nodes processed
                result = (True, "Workflow up to date - no processing needed")
        
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
