import time
from threading import Thread, Event

class WorkflowExecutor:
    """Handles the execution of a NodeGraphQt workflow"""
    
    def __init__(self, graph):
        self.graph = graph
        self.execution_thread = None
        self.execution_complete_event = Event()
        self.execution_complete_event.set()  # Initially not executing
    
    def execute_workflow(self, callback=None):
        """Execute the entire workflow with a callback when done"""
        # Don't allow multiple executions at once
        if self.execution_thread and self.execution_thread.is_alive():
            return False, "Workflow is already running"
            
        # Clear the completion event
        self.execution_complete_event.clear()
        
        # Create and start the execution thread
        self.execution_thread = Thread(target=self._execute_workflow_thread, 
                                      args=(callback,), 
                                      daemon=True)
        self.execution_thread.start()
        
        return True, "Workflow execution started"
    
    def _execute_workflow_thread(self, callback=None):
        """Internal method to execute the workflow in a background thread"""
        result = (False, "No nodes processed")
        node_processed = False
        
        try:
            # Find terminal nodes (with no outgoing connections)
            terminal_nodes = self._get_terminal_nodes()
            
            # If no terminal nodes, try to process all nodes with outputs
            if not terminal_nodes:
                # Get all nodes (handling either a list or a method)
                if callable(getattr(self.graph, 'all_nodes', None)):
                    all_nodes = self.graph.all_nodes()
                elif callable(getattr(self.graph, 'nodes', None)):
                    all_nodes = self.graph.nodes()
                else:
                    all_nodes = []
                    
                for node in all_nodes:
                    # Check if the node has outputs
                    has_outputs = False
                    if callable(getattr(node, 'output_ports', None)):
                        has_outputs = bool(node.output_ports())
                    elif hasattr(node, 'outputs'):
                        has_outputs = bool(node.outputs)
                        
                    if has_outputs:
                        try:
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
            else:
                # Process terminal nodes (which will recursively process inputs)
                for node in terminal_nodes:
                    try:
                        if hasattr(node, 'compute'):
                            node.compute()
                            node_processed = True
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        result = (False, f"Error executing node {node.name()}: {str(e)}")
                        break
            
            # Wait a bit for async nodes to begin processing
            time.sleep(0.5)
            
            # Check which nodes are still processing
            processing_nodes = self._get_processing_nodes()
            
            if processing_nodes:
                result = (True, f"Workflow started ({len(processing_nodes)} nodes processing)")
                node_processed = True
            
            # Wait for all processing nodes to complete (up to timeout)
            max_wait = 120  # 2 minutes
            start_time = time.time()
            
            while processing_nodes and time.time() - start_time < max_wait:
                time.sleep(1)  # Check every second
                processing_nodes = self._get_processing_nodes()
            
            # Check if any nodes were processed
            if node_processed:
                if processing_nodes:
                    result = (True, f"Workflow partially complete, {len(processing_nodes)} nodes still running")
                else:
                    result = (True, "Workflow executed successfully")
            else:
                result = (False, "No nodes needed processing")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            result = (False, f"Error executing workflow: {str(e)}")
        
        finally:
            # Set completion event
            self.execution_complete_event.set()
            
            # Call callback if provided
            if callback:
                callback(result)
    
    def _get_terminal_nodes(self):
        """Find nodes with no outgoing connections"""
        terminal_nodes = []
        
        # Get all nodes (handling either a list or a method)
        if callable(getattr(self.graph, 'all_nodes', None)):
            all_nodes = self.graph.all_nodes()
        else:
            all_nodes = self.graph.nodes()
        
        for node in all_nodes:
            has_outgoing = False
            
            # Get output ports (handling either a list or a method)
            if callable(getattr(node, 'output_ports', None)):
                output_ports = node.output_ports()
            elif hasattr(node, 'outputs'):
                output_ports = node.outputs
            else:
                output_ports = []
            
            # Check if any output port is connected
            for port in output_ports:
                if callable(getattr(port, 'connected_ports', None)):
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
        if callable(getattr(self.graph, 'all_nodes', None)):
            all_nodes = self.graph.all_nodes()
        elif callable(getattr(self.graph, 'nodes', None)):
            all_nodes = self.graph.nodes()
        else:
            all_nodes = []
        
        for node in all_nodes:
            if hasattr(node, 'processing') and node.processing:
                processing_nodes.append(node)
        
        return processing_nodes
