from threading import Thread

class NodeWorkflow:
    """Manages the collection of nodes and their execution"""
    def __init__(self, root):
        self.root = root
        self.nodes = []
        self.properties_frame = None
        self.active_ollama_node = None
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
            for item_id in node.canvas_items:
                node.canvas.delete(item_id)
            
            # Remove from nodes list
            self.nodes.remove(node)
            
            # Clear properties if this was the selected node
            if hasattr(node.canvas, 'selected_node') and node.canvas.selected_node == node:
                node.canvas.selected_node = None
                self.show_node_properties(None)
    
    def execute_workflow(self):
        """Execute the entire workflow"""
        # Set force_recompute to ensure all nodes get processed
        original_force_recompute = self.force_recompute
        self.force_recompute = True
        
        # Find terminal nodes (nodes with no outgoing connections)
        terminal_nodes = self.get_terminal_nodes()
        
        if not terminal_nodes:
            self.force_recompute = original_force_recompute
            return False, "No terminal nodes found"
        
        # Execute each terminal node, which will recursively process dependencies
        success = True
        message = "Workflow executed successfully"
        
        for node in terminal_nodes:
            try:
                node.process()
            except Exception as e:
                success = False
                message = f"Error executing node {node.title}: {str(e)}"
                break
        
        # Reset force_recompute
        self.force_recompute = original_force_recompute
        
        return success, message
    
    def execute_workflow_async(self, callback=None):
        """Execute the workflow asynchronously"""
        def execute_thread():
            # Store original value
            original_force_recompute = self.force_recompute
            
            # Set force_recompute to ensure all nodes get processed
            self.force_recompute = True
            
            # Execute workflow
            result = self.execute_workflow()
            
            # Reset force_recompute
            self.force_recompute = original_force_recompute
            
            # Call callback
            if callback:
                self.root.after(0, lambda: callback(result))
        
        thread = Thread(target=execute_thread, daemon=True)
        thread.start()
        return thread
    
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