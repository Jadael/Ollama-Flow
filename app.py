import customtkinter as ctk
import os
import sys

# Ensure plugins can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.workflow import NodeWorkflow
from core.canvas import NodeCanvas
from core.node_registry import get_all_node_categories

class OllamaFlow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Ollama Flow - Node-Based Workflow")
        self.geometry("1600x900")
        
        # Configure dark theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Create the workflow
        self.workflow = NodeWorkflow(self)
        
        # Create main layout
        self.create_layout()
        
        # Add some example nodes
        self.add_example_nodes()
    
    def create_layout(self):
        # Configure grid layout
        self.grid_columnconfigure(0, weight=4)  # Canvas area
        self.grid_columnconfigure(1, weight=1)  # Properties panel
        self.grid_rowconfigure(0, weight=1)     # Main workflow area
        
        # Create main frames
        canvas_frame = ctk.CTkFrame(self)
        canvas_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        properties_frame = ctk.CTkFrame(self)
        properties_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        # Store reference to properties frame
        self.workflow.properties_frame = properties_frame
        
        # Setup canvas area
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.grid_rowconfigure(1, weight=1)
        
        # Toolbar with dynamic node buttons
        toolbar = ctk.CTkFrame(canvas_frame)
        toolbar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        # Create toolbar with dynamically discovered nodes grouped by category
        self.create_toolbar(toolbar)
        
        # Create node canvas
        self.node_canvas = NodeCanvas(
            canvas_frame,
            self.workflow,
            bg="#1e1e1e",
            highlightthickness=0
        )
        self.node_canvas.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Properties panel
        ctk.CTkLabel(
            properties_frame,
            text="Node Properties",
            font=("Verdana", 16, "bold")
        ).pack(pady=10)
        
        # Initially show "no node selected"
        self.workflow.show_node_properties(None)
    
    def create_toolbar(self, toolbar):
        """Create a toolbar with buttons for all registered node types, organized by category"""
        # Get all node categories
        node_categories = get_all_node_categories()
        
        # Sort categories with Core first, then alphabetically
        category_order = sorted(node_categories.keys())
        if "Core" in category_order:
            category_order.remove("Core")
            category_order.insert(0, "Core")
        
        # Create a notebook/tabs for categories
        tabview = ctk.CTkTabview(toolbar)
        tabview.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # Add tabs for each category and buttons for each node type
        for category in category_order:
            if category not in node_categories or not node_categories[category]:
                continue
                
            # Add a tab for this category
            tab = tabview.add(category)
            
            # Sort node classes by node_type
            node_classes = sorted(node_categories[category], key=lambda cls: cls.node_type)
            
            # Add buttons for each node type in this category
            for node_class in node_classes:
                btn = ctk.CTkButton(
                    tab,
                    text=f"Add {node_class.node_type}",
                    command=lambda cls=node_class: self.add_node(cls)
                )
                btn.pack(side="left", padx=5, pady=5)
        
        # Add workflow control buttons
        run_btn = ctk.CTkButton(
            toolbar,
            text="Run Workflow",
            command=self.run_workflow,
            fg_color="#4CAF50"
        )
        run_btn.pack(side="right", padx=5, pady=5)
        
        clear_btn = ctk.CTkButton(
            toolbar,
            text="Reset All",
            command=self.workflow.mark_all_dirty,
            fg_color="#FF5722"
        )
        clear_btn.pack(side="right", padx=5, pady=5)
    
    def add_node(self, node_class, x=100, y=100):
        """Add a new node to the workflow"""
        node = node_class(self.node_canvas, x=x, y=y)
        self.workflow.add_node(node)
        node.draw()
    
    def add_example_nodes(self):
        """Add some example nodes to demonstrate the workflow"""
        # Import nodes dynamically from the registry
        from core.node_registry import get_node_class
        
        # Get node classes
        static_node_cls = get_node_class("Static Text")
        prompt_node_cls = get_node_class("LLM Prompt")
        regex_node_cls = get_node_class("Regex Processor")
        
        if not static_node_cls or not prompt_node_cls:
            print("Warning: Could not find required node classes for example")
            return
        
        # Add a static text node
        static_node = static_node_cls(self.node_canvas, x=100, y=100)
        static_node.text = "Tell me a joke about programming."
        self.workflow.add_node(static_node)
        
        # Add a prompt node
        prompt_node = prompt_node_cls(self.node_canvas, x=400, y=100)
        prompt_node.system_prompt = "You are a helpful assistant with a good sense of humor."
        self.workflow.add_node(prompt_node)
        
        # Add regex node if available
        if regex_node_cls:
            regex_node = regex_node_cls(self.node_canvas, x=700, y=100)
            self.workflow.add_node(regex_node)
        
        # Draw the nodes
        static_node.draw()
        prompt_node.draw()
        if regex_node_cls:
            regex_node.draw()
        
        # Connect the static node to the prompt node
        static_output = static_node.outputs[0]
        prompt_input = prompt_node.inputs[1]  # User prompt input
        static_output.connect(prompt_input)
        
        # Connect prompt to regex if available
        if regex_node_cls:
            prompt_output = prompt_node.outputs[0]
            regex_input = regex_node.inputs[0]
            prompt_output.connect(regex_input)
        
        # Redraw the nodes to show the connection
        static_node.draw()
        prompt_node.draw()
        if regex_node_cls:
            regex_node.draw()
    
    def run_workflow(self):
        """Run the workflow in a non-blocking way"""
        # Find nodes that need processing
        dirty_nodes = [node for node in self.workflow.nodes if node.dirty]
        processing_nodes = [node for node in self.workflow.nodes if node.processing]
        
        if not dirty_nodes and not processing_nodes:
            from tkinter import messagebox
            messagebox.showinfo("Workflow Status", "All nodes are up to date. Nothing to process.")
            return
        
        # Show a non-modal status window
        status_window = ctk.CTkToplevel(self)
        status_window.title("Workflow Status")
        status_window.geometry("300x200")
        status_window.attributes("-topmost", True)
        
        # Add a label showing what's happening
        status_label = ctk.CTkLabel(
            status_window,
            text=f"Processing workflow...\n{len(dirty_nodes)} nodes to process\n{len(processing_nodes)} nodes already running",
            font=("Verdana", 14)
        )
        status_label.pack(pady=20)
        
        # Add a progress bar
        progress_bar = ctk.CTkProgressBar(status_window)
        progress_bar.pack(padx=20, pady=10, fill="x")
        progress_bar.configure(mode="indeterminate")
        progress_bar.start()
        
        # Add a "Show Results" button (initially disabled)
        results_button = ctk.CTkButton(
            status_window,
            text="Show Results",
            state="disabled",
            command=lambda: self.show_workflow_results()
        )
        results_button.pack(pady=10)
        
        # Add a close button
        close_button = ctk.CTkButton(
            status_window,
            text="Close",
            command=status_window.destroy
        )
        close_button.pack(pady=10)
        
        # Update function for periodic status checks
        def update_status():
            # Count currently processing nodes
            processing_count = len([node for node in self.workflow.nodes if node.processing])
            dirty_count = len([node for node in self.workflow.nodes if node.dirty])
            
            # Update status label
            if processing_count > 0:
                status_label.configure(text=f"Processing workflow...\n{processing_count} nodes still processing\n{dirty_count} nodes waiting")
            elif dirty_count > 0:
                status_label.configure(text=f"Waiting for processing...\n{dirty_count} nodes still dirty")
            else:
                status_label.configure(text="Processing complete!")
                progress_bar.stop()
                progress_bar.configure(mode="determinate")
                progress_bar.set(1.0)
                results_button.configure(state="normal")
            
            # Schedule next update if window still exists
            if status_window.winfo_exists():
                status_window.after(500, update_status)
        
        def on_workflow_complete(result):
            # Update any UI elements in status window if it still exists
            if status_window.winfo_exists():
                success, message = result
                
                if not success and "No nodes" not in message:
                    from tkinter import messagebox
                    messagebox.showerror("Workflow Error", message)
        
        # Execute workflow with callback
        self.workflow.execute_workflow(callback=on_workflow_complete)
        
        # Start periodic UI updates
        status_window.after(500, update_status)
    
    def show_workflow_results(self):
        """Show results from terminal nodes"""
        # Show result dialog
        result_window = ctk.CTkToplevel(self)
        result_window.title("Workflow Results")
        result_window.geometry("600x400")
        
        ctk.CTkLabel(
            result_window,
            text="Workflow Results",
            font=("Verdana", 16, "bold")
        ).pack(pady=10)
        
        # Get results from terminal nodes
        terminal_nodes = self.workflow.get_terminal_nodes()
        
        if not terminal_nodes:
            ctk.CTkLabel(
                result_window,
                text="No terminal nodes found with results.\nTerminal nodes are those with no outgoing connections.",
                font=("Verdana", 12)
            ).pack(pady=20)
            return
        
        results_frame = ctk.CTkScrollableFrame(result_window)
        results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        for node in terminal_nodes:
            if not node.output_cache:
                continue
                
            node_frame = ctk.CTkFrame(results_frame)
            node_frame.pack(fill="x", pady=5, padx=5)
            
            ctk.CTkLabel(
                node_frame,
                text=f"Node: {node.title}",
                font=("Verdana", 12, "bold")
            ).pack(anchor="w", padx=10, pady=5)
            
            # Show outputs
            for name, value in node.output_cache.items():
                output_text = ctk.CTkTextbox(node_frame, height=100, wrap="word")
                output_text.pack(fill="x", padx=10, pady=5)
                output_text.insert("1.0", str(value))
                output_text.configure(state="disabled")
                
                copy_btn = ctk.CTkButton(
                    node_frame,
                    text=f"Copy {name}",
                    command=lambda v=value: self.clipboard_append(str(v))
                )
                copy_btn.pack(pady=5)

# Create directory structure
def ensure_directories():
    """Create required directories if they don't exist"""
    dirs = [
        "core/ui",
        "plugins/Core",
        "plugins/Ollama"
    ]
    
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)
        
        # Create __init__.py files
        init_file = os.path.join(directory, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                pass  # Create empty file

if __name__ == "__main__":
    # Create directories
    ensure_directories()
    
    # Start application
    app = OllamaFlow()
    app.mainloop()