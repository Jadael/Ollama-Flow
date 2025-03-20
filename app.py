import customtkinter as ctk
import os
import sys

# Ensure plugins can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.workflow import NodeWorkflow
from core.canvas import NodeCanvas
from plugins.Core.static_text import StaticTextNode
from plugins.Ollama.prompt import PromptNode

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
        
        # Toolbar
        toolbar = ctk.CTkFrame(canvas_frame)
        toolbar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        # Add basic node buttons
        static_text_btn = ctk.CTkButton(
            toolbar,
            text="Add Text Node",
            command=lambda: self.add_node(StaticTextNode)
        )
        static_text_btn.pack(side="left", padx=5, pady=5)
        
        prompt_btn = ctk.CTkButton(
            toolbar,
            text="Add Prompt Node",
            command=lambda: self.add_node(PromptNode)
        )
        prompt_btn.pack(side="left", padx=5, pady=5)
        
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
    
    def add_node(self, node_class, x=100, y=100):
        """Add a new node to the workflow"""
        node = node_class(self.node_canvas, x=x, y=y)
        self.workflow.add_node(node)
        node.draw()
    
    def add_example_nodes(self):
        """Add some example nodes to demonstrate the workflow"""
        # Add a static text node
        static_node = StaticTextNode(self.node_canvas, x=100, y=100)
        static_node.text = "Tell me a joke about programming."
        self.workflow.add_node(static_node)
        
        # Add a prompt node
        prompt_node = PromptNode(self.node_canvas, x=400, y=100)
        prompt_node.system_prompt = "You are a helpful assistant with a good sense of humor."
        self.workflow.add_node(prompt_node)
        
        # Draw the nodes
        static_node.draw()
        prompt_node.draw()
        
        # Connect the static node to the prompt node
        static_output = static_node.outputs[0]
        prompt_input = prompt_node.inputs[1]  # User prompt input
        static_output.connect(prompt_input)
        
        # Redraw the nodes to show the connection
        static_node.draw()
        prompt_node.draw()
    
    def run_workflow(self):
        """Run the workflow"""
        # Find and execute terminal nodes
        success, message = self.workflow.execute_workflow()
        
        if not success:
            import tkinter as tk
            from tkinter import messagebox
            messagebox.showerror("Workflow Error", message)
        else:
            # Show result dialog
            result_window = ctk.CTkToplevel(self)
            result_window.title("Workflow Results")
            result_window.geometry("600x400")
            
            ctk.CTkLabel(
                result_window,
                text="Workflow Execution Complete",
                font=("Verdana", 16, "bold")
            ).pack(pady=10)
            
            # Get results from terminal nodes
            terminal_nodes = self.workflow.get_terminal_nodes()
            
            results_frame = ctk.CTkScrollableFrame(result_window)
            results_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            for node in terminal_nodes:
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