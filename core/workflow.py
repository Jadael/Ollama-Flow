from threading import Thread, Event
import time
import tkinter as tk

class NodeWorkflow:
    """Manages the collection of nodes and their execution"""
    def __init__(self, root):
        self.root = root
        self.nodes = []
        self.properties_frame = None
        self.active_ollama_node = None
        self.force_recompute = False
        self.execution_thread = None
        self.execution_complete_event = Event()
        self.execution_complete_event.set()  # Initially not executing
    
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
            for item_id in node.canvas_items:
                node.canvas.delete(item_id)
            
            # Remove from nodes list
            self.nodes.remove(node)
            
            # Clear properties if this was the selected node
            if hasattr(node.canvas, 'selected_node') and node.canvas.selected_node == node:
                node.canvas.selected_node = None
                self.show_node_properties(None)
    
    def execute_workflow(self, callback=None):
        """Execute the entire workflow with a callback when done"""
        # Don't allow multiple executions at once
        if self.execution_thread and self.execution_thread.is_alive():
            return False, "Workflow is already running"
            
        # Clear the completion event
        self.execution_complete_event.clear()
        
        # Create and start the execution thread
        self.execution_thread = Thread(target=self._execute_workflow_thread, args=(callback,), daemon=True)
        self.execution_thread.start()
        
        return True, "Workflow execution started"
    
    def _execute_workflow_thread(self, callback=None):
        """Internal method to execute the workflow in a background thread"""
        # Set force_recompute to ensure all nodes get processed
        original_force_recompute = self.force_recompute
        self.force_recompute = True
        
        # Set flag to track if any nodes were processed
        self.node_processed = False
        
        result = (False, "No nodes processed")
        
        try:
            # Process all terminal nodes
            terminal_nodes = self.get_terminal_nodes()
            
            # If no terminal nodes, try to process all nodes
            if not terminal_nodes:
                for node in self.nodes:
                    try:
                        # Process each node
                        node.process()
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        result = (False, f"Error executing node {node.title}: {str(e)}")
                        break
            else:
                # Process terminal nodes, which will recursively process inputs
                for node in terminal_nodes:
                    try:
                        # Process each terminal node
                        node.process()
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        result = (False, f"Error executing node {node.title}: {str(e)}")
                        break
            
            # Wait for a short time to allow async nodes to begin processing
            time.sleep(0.5)
            
            # Check if nodes are still processing and wait if needed
            processing_nodes = [node for node in self.nodes if node.processing]
            if processing_nodes:
                # Update UI to reflect processing state
                for node in processing_nodes:
                    if hasattr(node, 'draw'):
                        try:
                            node.draw()
                        except:
                            pass
                
                # For result message only - we'll still continue
                result = (True, f"Workflow started ({len(processing_nodes)} nodes processing)")
                self.node_processed = True
            
            # Check if any nodes were processed
            if self.node_processed:
                result = (True, f"Workflow executed successfully")
            else:
                result = (False, "No nodes needed processing")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            result = (False, f"Error executing workflow: {str(e)}")
        
        finally:
            # Reset force_recompute
            self.force_recompute = original_force_recompute
            
            # Set completion event
            self.execution_complete_event.set()
            
            # Call callback if provided
            if callback:
                # Schedule callback on the main thread
                if hasattr(self.root, 'after'):
                    self.root.after(0, lambda: callback(result))
    
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
                import customtkinter as ctk
                ctk.CTkLabel(
                    self.properties_frame,
                    text="No node selected",
                    font=("Verdana", 16)
                ).pack(padx=20, pady=20)
            return
        
        # Let the node create its properties UI
        node.create_properties_ui(self.properties_frame)
    
    def mark_all_dirty(self):
        """Mark all nodes as dirty (needing recalculation)"""
        for node in self.nodes:
            node.dirty = True
            node.draw()