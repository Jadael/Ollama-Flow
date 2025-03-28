import time
from threading import Thread, Event
from PySide6.QtCore import QObject, Signal, Qt, Slot, QCoreApplication, QThread

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
            
            # Reset the processing state for all nodes to avoid stale states
            self._reset_processing_states(all_nodes)
            
            # Build dependency graph
            # For each node, identify its ancestors (nodes it depends on)
            ancestors = {}
            descendants = {}  # Reverse map: nodes that depend on this node
            
            for node in all_nodes:
                # Initialize ancestor lists
                ancestors[node] = []
                if node not in descendants:
                    descendants[node] = []
                
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
                    
                    # Add each connected node as an ancestor
                    for connected_port in connected_ports:
                        if hasattr(connected_port, 'node') and callable(getattr(connected_port, 'node')):
                            ancestor_node = connected_port.node()
                            if ancestor_node in all_nodes:
                                ancestors[node].append(ancestor_node)
                                if ancestor_node not in descendants:
                                    descendants[ancestor_node] = []
                                descendants[ancestor_node].append(node)
            
            print("Built dependency graph:")
            for node in ancestors:
                node_name = node.name() if hasattr(node, 'name') and callable(getattr(node, 'name')) else "Unknown"
                anc_names = [anc.name() if hasattr(anc, 'name') and callable(getattr(anc, 'name')) else "Unknown" for anc in ancestors[node]]
                print(f"  Node {node_name} depends on: {', '.join(anc_names) if anc_names else 'None'}")
            
            # Find nodes that should be processed
            nodes_to_process = set()
            initially_dirty_nodes = set()

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
                        # Skip processing for Never dirty with valid cache
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
                    initially_dirty_nodes.add(node)

            # Mark downstream nodes as potentially dirty
            print("Identifying downstream nodes that will potentially need processing...")
            potentially_dirty_nodes = self._mark_downstream_nodes_potentially_dirty(initially_dirty_nodes, descendants)

            # Add potentially dirty nodes to the processing queue
            for node in potentially_dirty_nodes:
                if node not in nodes_to_process and hasattr(node, 'compute') and callable(getattr(node, 'compute')):
                    node_name = node.name() if hasattr(node, 'name') and callable(getattr(node, 'name')) else "Unknown"
                    print(f"Node {node_name}: Adding to processing queue (potentially dirty)")
                    nodes_to_process.add(node)

            # No nodes to process? We're done
            if not nodes_to_process:
                print("No nodes need processing - workflow is up to date")
                return (True, "Workflow is up to date")

            print(f"Found {len(nodes_to_process)} nodes to process ({len(potentially_dirty_nodes)} potentially dirty)")
            
            # Create processing queue with proper topological sort
            # In a topological sort, if A depends on B, B must come before A in the output
            processing_queue = self._topological_sort(nodes_to_process, ancestors)
            
            print("Processing queue order:")
            for i, node in enumerate(processing_queue):
                node_name = node.name() if hasattr(node, 'name') and callable(getattr(node, 'name')) else "Unknown"
                print(f"  {i+1}. {node_name}")
            
            # Now process nodes in order (ancestors first)
            processed_count = 0
            
            for node in processing_queue:
                try:
                    node_name = node.name() if hasattr(node, 'name') and callable(getattr(node, 'name')) else "Unknown"
                    
                    # Skip if already processing (to prevent cycles/duplicates)
                    if hasattr(node, 'processing') and node.processing:
                        print(f"Skipping node that's already processing: {node_name}")
                        continue
                    
                    print(f"Processing node: {node_name}")
                    
                    # Call compute with flag to indicate we're calling from workflow executor
                    # This helps nodes avoid redundant dependency processing
                    self._process_node_with_executor_flag(node)
                    processed_count += 1
                    node_processed = True
                    
                    # Wait for this node to complete if it's asynchronous
                    if hasattr(node, 'is_async_node') and node.is_async_node:
                        print(f"Node {node_name} is asynchronous, waiting for completion...")
                        
                        # Wait for the node to complete (up to timeout)
                        max_wait = 3600  # 1 hour timeout (3600 seconds)
                        start_time = time.time()
                        
                        while hasattr(node, 'processing') and node.processing and time.time() - start_time < max_wait:
                            print(f"Waiting for async node {node_name} to complete...")
                            time.sleep(1)  # Check every second
                        
                        if hasattr(node, 'processing') and node.processing:
                            print(f"Timeout waiting for async node {node_name} to complete")
                        else:
                            print(f"Async node {node_name} completed")
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    node_name = node.name() if hasattr(node, 'name') and callable(getattr(node, 'name')) else "Unknown"
                    result = (False, f"Error executing node {node_name}: {str(e)}")
                    break
            
            # Check if any async nodes are still processing
            processing_nodes = self._get_processing_nodes()
            
            if processing_nodes:
                node_names = []
                for n in processing_nodes:
                    node_name = n.name() if hasattr(n, 'name') and callable(getattr(n, 'name')) else "Unknown"
                    node_names.append(node_name)
                print(f"There are still {len(processing_nodes)} nodes processing: {', '.join(node_names)}")
                result = (True, f"Workflow partially complete, {len(processing_nodes)} nodes still running")
            else:
                print(f"Workflow execution completed successfully")
                result = (True, f"Workflow executed successfully ({processed_count} nodes processed)")
        
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
    
    def _topological_sort(self, nodes_to_process, ancestors):
        """
        Perform a topological sort on the nodes to process.
        In the result, if node A depends on node B, then B comes before A.
        
        Args:
            nodes_to_process: Set of nodes that need processing
            ancestors: Dictionary mapping each node to its ancestors (nodes it depends on)
            
        Returns:
            List of nodes in topological order (ancestors first)
        """
        # Create a proper topological sort
        result = []
        temp_mark = set()  # Temporary mark for cycle detection
        perm_mark = set()  # Permanent mark for completed nodes
        
        def visit(node):
            """Visit a node and its ancestors recursively"""
            # Check for cycles
            if node in temp_mark:
                print(f"Warning: Cycle detected involving node {node.name() if hasattr(node, 'name') else 'Unknown'}")
                return
                
            # Skip if already processed
            if node in perm_mark:
                return
                
            # Mark temporarily for cycle detection
            temp_mark.add(node)
            
            # Visit all ancestors (dependencies) first that need processing
            for ancestor in ancestors[node]:
                if ancestor in nodes_to_process and ancestor not in perm_mark:
                    visit(ancestor)
            
            # Remove temporary mark and add permanent mark
            temp_mark.remove(node)
            perm_mark.add(node)
            
            # Add to result
            result.append(node)
        
        # Visit all nodes that need processing
        for node in nodes_to_process:
            if node not in perm_mark:
                visit(node)
                
        return result
    
    def _process_node_with_executor_flag(self, node):
        """
        Process a node with a flag to indicate we're calling from the workflow executor.
        This allows nodes to avoid redundant dependency processing.
        
        Args:
            node: The node to process
        """
        # Set a flag on the node to indicate we're calling from the workflow executor
        # This can be used by the node to avoid redundant dependency processing
        try:
            from_executor = getattr(node, '_from_workflow_executor', False)
            node._from_workflow_executor = True
            
            # Call the node's compute method
            node.compute()
            
            # Reset the flag
            node._from_workflow_executor = from_executor
        except AttributeError:
            # If the node doesn't have the attribute, just call compute directly
            node.compute()
    
    def _reset_processing_states(self, nodes):
        """
        Reset processing states for all nodes to avoid stale states.
        
        Args:
            nodes: List of nodes to reset
        """
        for node in nodes:
            # Reset processing flags if node is not actually processing
            # This handles cases where a node crashed without cleaning up its state
            if hasattr(node, 'processing'):
                # Only reset if node is marked as processing but actually isn't
                if node.processing and (hasattr(node, 'processing_done') and node.processing_done):
                    print(f"Resetting stale processing state for node: {node.name() if hasattr(node, 'name') else 'Unknown'}")
                    node.processing = False
    
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
    
    def _mark_downstream_nodes_potentially_dirty(self, dirty_nodes, descendants_map):
        """
        Mark all downstream nodes as potentially dirty.
        This ensures that nodes that depend on changing nodes are included in processing.
        
        Args:
            dirty_nodes: Set of nodes that are known to be dirty/processing
            descendants_map: Map of node -> list of nodes that depend on it
            
        Returns:
            Set of nodes that were marked as potentially dirty
        """
        potentially_dirty = set()
        for node in dirty_nodes:
            # Get all descendants (nodes that depend on this node)
            if node in descendants_map:
                for descendant in descendants_map[node]:
                    # Skip Never dirty nodes
                    recalc_mode = "Dirty if inputs change"  # Default
                    if hasattr(descendant, 'get_property') and callable(getattr(descendant, 'get_property')):
                        try:
                            recalc_mode = descendant.get_property('recalculation_mode')
                        except:
                            pass
                            
                    if recalc_mode != 'Never dirty':
                        # Mark as potentially dirty
                        if hasattr(descendant, 'set_potentially_dirty'):
                            descendant.set_potentially_dirty(True)
                            print(f"Marked node {descendant.name()} as potentially dirty (depends on {node.name()})")
                        potentially_dirty.add(descendant)
                        
                        # Recursively mark descendants of this node
                        if descendant in descendants_map:
                            more_potentially_dirty = self._mark_downstream_nodes_potentially_dirty([descendant], descendants_map)
                            potentially_dirty.update(more_potentially_dirty)
        
        return potentially_dirty

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
