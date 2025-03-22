import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QDockWidget, 
                              QStatusBar, QMenuBar, QMenu, QFileDialog,
                              QMessageBox)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, Signal, Slot

# Try to import NodeGraphQt and check version
try:
    import NodeGraphQt
    from NodeGraphQt import NodeGraph, PropertiesBinWidget
    print(f"NodeGraphQt version: {getattr(NodeGraphQt, '__version__', 'unknown')}")
except ImportError as e:
    print(f"Error importing NodeGraphQt: {e}")
    # Will be handled in the main block

# Ensure plugins can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class OllamaFlow(QMainWindow):
    """Main application window for Ollama Flow"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ollama Flow - Node-Based Workflow")
        self.resize(1600, 900)
        
        # Create the node graph
        self.graph = NodeGraph()
        self.graph_widget = self.graph.widget
        self.setCentralWidget(self.graph_widget)
        
        # Set up graph behavior
        # Set acyclic option if available
        if hasattr(self.graph, 'set_acyclic'):
            self.graph.set_acyclic(True)  # Prevent cyclic connections
            
        # Configure viewer settings
        viewer = self.graph.viewer()
        if viewer:
            # Set zoom sensitivity if the method exists
            if hasattr(viewer, 'set_zoom_sensitivity'):
                viewer.set_zoom_sensitivity(0.001)
        
        # Create the menu bar
        self.setup_menu()
        
        # Create the status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")
        
        # Create the properties panel
        self.properties_bin = PropertiesBinWidget(node_graph=self.graph)
        # Try to set any needed properties for the widget
        if hasattr(self.properties_bin, 'set_graph'):
            self.properties_bin.set_graph(self.graph)

        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setWidget(self.properties_bin)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        
        # Register node types
        self.register_nodes()
        
        # Add example nodes
        self.add_example_nodes()
        
        # Connect signals
        self.graph.node_selected.connect(self.on_node_selected)
        self.graph.node_created.connect(self.on_node_created)
        
        # Create workflow executor
        try:
            from workflow_executor import WorkflowExecutor
            self.executor = WorkflowExecutor(self.graph)
        except Exception as e:
            print(f"Error initializing workflow executor: {e}")
            import traceback
            traceback.print_exc()
    
    def setup_menu(self):
        """Set up the application menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_workflow)
        file_menu.addAction(new_action)
        
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_workflow)
        file_menu.addAction(save_action)
        
        load_action = QAction("Load", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self.load_workflow)
        file_menu.addAction(load_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Node menu
        node_menu = menubar.addMenu("Nodes")
        
        # Add node submenu with simplified options
        add_menu = node_menu.addMenu("Add Node")
        
        # Create action for adding a static text node directly
        add_static_action = QAction("Add Static Text", self)
        add_static_action.triggered.connect(self.add_static_text_node)
        add_menu.addAction(add_static_action)
        
        # Delete node action
        delete_action = QAction("Delete Selected", self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self.delete_selected_node)
        node_menu.addAction(delete_action)
        
        # Workflow menu
        workflow_menu = menubar.addMenu("Workflow")
        
        run_action = QAction("Run Workflow", self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self.run_workflow)
        workflow_menu.addAction(run_action)
        
        reset_action = QAction("Reset All", self)
        reset_action.triggered.connect(self.reset_workflow)
        workflow_menu.addAction(reset_action)
    
    def register_nodes(self):
        """Register custom node types with NodeGraphQt"""
        try:
            # Import node directly
            try:
                # Try direct import first
                from nodes.static_text_node import StaticTextNode
            except ImportError:
                # If that fails, try base import
                from nodes import StaticTextNode
            
            # Get node factory from graph
            if hasattr(self.graph, '_node_factory'):
                factory = self.graph._node_factory
            elif hasattr(self.graph, '_NodeGraph__node_factory'):
                factory = self.graph._NodeGraph__node_factory
            else:
                print("CRITICAL: Cannot find node factory in graph!")
                return
                
            # Try to use correct registration method - try only ONE method
            print(f"NodeGraphQt factory: {factory}")
            
            registered = False
            
            # Try graph registration first
            if not registered and hasattr(self.graph, 'register_node'):
                try:
                    print("Registering nodes using graph.register_node()")
                    self.graph.register_node(StaticTextNode)
                    registered = True
                except Exception as e:
                    print(f"Info: Could not register with graph.register_node(): {e}")
            
            # Try factory registration if graph registration failed
            if not registered and hasattr(factory, 'register_node'):
                try:
                    print("Registering nodes using factory.register_node()")
                    factory.register_node(StaticTextNode)
                    registered = True
                except Exception as e:
                    print(f"Info: Could not register with factory.register_node(): {e}")
                    
            # Try direct dictionary update as fallback
            if not registered and (hasattr(factory, '_factory_dict') or hasattr(factory, '_node_factory_dict')):
                try:
                    dict_name = '_factory_dict' if hasattr(factory, '_factory_dict') else '_node_factory_dict'
                    print(f"Registering nodes by updating factory.{dict_name} directly")
                    factory_dict = getattr(factory, dict_name)
                    
                    # Get the node's identifier and type
                    node_id = getattr(StaticTextNode, '__identifier__', 'com.ollamaflow.nodes')
                    node_type = getattr(StaticTextNode, '__type__', 'StaticTextNode')
                    full_id = f"{node_id}.{node_type}"
                    
                    # Check if already registered
                    if full_id not in factory_dict:
                        factory_dict[full_id] = StaticTextNode
                        registered = True
                except Exception as e:
                    print(f"Error during direct node registration: {e}")
            
            if registered:
                print("Successfully registered StaticTextNode")
            else:
                print("Note: StaticTextNode may already be registered")
                
            # Debug: print the registered node types
            print("Registered node types:")
            if hasattr(factory, '_factory_dict'):
                for name in factory._factory_dict.keys():
                    print(f"  - {name}")
            elif hasattr(factory, '_node_factory_dict'):
                for name in factory._node_factory_dict.keys():
                    print(f"  - {name}")
            
        except Exception as e:
            print(f"Error registering nodes: {e}")
            import traceback
            traceback.print_exc()
    
    def add_static_text_node(self):
        """Add a static text node directly without going through the graph factory"""
        try:
            # Create the node instance directly
            try:
                # Try direct import first
                from nodes.static_text_node import StaticTextNode
            except ImportError:
                # If that fails, try base import
                from nodes import StaticTextNode
                
            static_node = StaticTextNode()
            static_node.set_name("Static Text")
            
            # Add to the graph
            if hasattr(self.graph, 'add_node'):
                print("Adding node using graph.add_node()")
                self.graph.add_node(static_node)
            
            # Position the node in the center
            try:
                # Get center position of viewport
                view = self.graph.viewer()
                if view and hasattr(view, 'mapToScene') and hasattr(view, 'viewport'):
                    center_pos = view.mapToScene(view.viewport().rect().center())
                    if hasattr(static_node, 'set_pos'):
                        static_node.set_pos(center_pos.x(), center_pos.y())
            except Exception as e:
                print(f"Warning: Could not position node at center: {e}")
                
            # Set basic properties
            if hasattr(static_node, 'set_property'):
                static_node.set_property('text', 'New static text node')
                
            # Update status
            self.statusBar.showMessage(f"Created Static Text node")
            
        except Exception as e:
            print(f"Error creating Static Text node: {e}")
            import traceback
            traceback.print_exc()
            self.statusBar.showMessage(f"Error creating node: {str(e)}")
    
    def add_node_from_menu(self, node_type, display_name):
        """Add a node from menu selection to center of view"""
        try:
            # Create the node using the correct node type directly
            print(f"Creating node type: {node_type} with display name: {display_name}")
            
            try:
                # Try creating with type directly
                node = self.graph.create_node(node_type)
                
                # Set display name if it worked
                if hasattr(node, 'set_name'):
                    node.set_name(display_name)
            except Exception as e:
                print(f"Error creating node with type {node_type}: {e}")
                # Try creating with full namespace
                node_type_id = f"com.ollamaflow.nodes.{node_type}"
                try:
                    node = self.graph.create_node(node_type_id)
                    if hasattr(node, 'set_name'):
                        node.set_name(display_name)
                except Exception as e2:
                    print(f"Error creating node with full namespace {node_type_id}: {e2}")
                    # One more attempt - try creating by class
                    if node_type == "StaticTextNode":
                        from nodes.static_text_node_simple import StaticTextNode
                        node = StaticTextNode()
                    else:
                        raise ValueError(f"Unknown node type: {node_type}")
                    
                    # Manually add to graph
                    if hasattr(self.graph, 'add_node'):
                        self.graph.add_node(node)
                    
                    # Set name if possible
                    if hasattr(node, 'set_name'):
                        node.set_name(display_name)
            
            # Try to position at center of view
            try:
                # Get center position of viewport
                view = self.graph.viewer()
                if view and hasattr(view, 'mapToScene') and hasattr(view, 'viewport'):
                    center_pos = view.mapToScene(view.viewport().rect().center())
                    if hasattr(node, 'set_pos'):
                        node.set_pos(center_pos.x(), center_pos.y())
            except Exception as e:
                print(f"Warning: Could not position node at center: {e}")
            
            return node
            
        except Exception as e:
            print(f"Error adding node from menu: {e}")
            import traceback
            traceback.print_exc()
            self.statusBar.showMessage(f"Error adding node: {str(e)}")
            return None
    
    def add_example_nodes(self):
        """Add simplified example nodes to demonstrate the workflow"""
        try:
            # Try to create a static text node directly
            try:
                # Try direct import first
                from nodes.static_text_node import StaticTextNode
            except ImportError:
                # If that fails, try base import
                from nodes import StaticTextNode
            
            # Create the node instance directly
            static_node = StaticTextNode()
            static_node.set_name("Static Text")
            
            # Add to the graph
            if hasattr(self.graph, 'add_node'):
                print("Adding node using graph.add_node()")
                self.graph.add_node(static_node)
            
            # Position the node in the center
            try:
                # Get center position of viewport
                view = self.graph.viewer()
                if view and hasattr(view, 'mapToScene') and hasattr(view, 'viewport'):
                    center_pos = view.mapToScene(view.viewport().rect().center())
                    if hasattr(static_node, 'set_pos'):
                        static_node.set_pos(center_pos.x(), center_pos.y())
            except Exception as e:
                print(f"Warning: Could not position node at center: {e}")
                
            # Set basic properties
            if hasattr(static_node, 'set_property'):
                static_node.set_property('text', 'This is a test node created directly')
                
        except Exception as e:
            print(f"Error creating example nodes: {e}")
            import traceback
            traceback.print_exc()
    
    def connect_nodes(self, source_node, source_port_name, target_node, target_port_name):
        """Helper method to connect nodes with better error handling"""
        try:
            # Get the source output port
            source_port = None
            if hasattr(source_node, 'output') and callable(source_node.output):
                # Try to get by name first
                try:
                    source_port = source_node.output(source_port_name)
                except:
                    # If that fails, try by index (for the first port)
                    source_port = source_node.output(0)
            elif hasattr(source_node, 'outputs') and source_node.outputs:
                source_port = source_node.outputs[0]
            
            # Get the target input port
            target_port = None
            if hasattr(target_node, 'input') and callable(target_node.input):
                # Try to get by name first
                try:
                    target_port = target_node.input(target_port_name)
                except:
                    # If user prompt is second port (index 1)
                    if target_port_name == "User Prompt":
                        target_port = target_node.input(1)
                    else:
                        # Default to first port
                        target_port = target_node.input(0)
            elif hasattr(target_node, 'inputs') and target_node.inputs:
                if target_port_name == "User Prompt" and len(target_node.inputs) > 1:
                    target_port = target_node.inputs[1]
                else:
                    target_port = target_node.inputs[0]
            
            # Connect the ports if both are valid
            if source_port and target_port:
                if hasattr(source_port, 'connect_to'):
                    source_port.connect_to(target_port)
                    print(f"Connected: {source_node.name()} -> {target_node.name()}")
                elif hasattr(target_port, 'connect_from'):
                    target_port.connect_from(source_port)
                    print(f"Connected: {source_node.name()} -> {target_node.name()}")
            else:
                print(f"Could not connect: ports not found ({source_port_name} -> {target_port_name})")
        
        except Exception as e:
            print(f"Error connecting nodes: {e}")
            import traceback
            traceback.print_exc()
    
    def on_node_selected(self, node):
        """Handle node selection"""
        if node:
            try:
                # Update the properties bin - use newer API methods if available
                if hasattr(self.properties_bin, 'set_node'):
                    self.properties_bin.set_node(node)
                elif hasattr(self.properties_bin, 'add_node'):
                    self.properties_bin.add_node(node)
                elif hasattr(self.properties_bin, 'set_property'):
                    self.properties_bin.set_property(node)
                else:
                    # For newer versions that use the properties attribute
                    if hasattr(self.properties_bin, 'properties') and hasattr(self.properties_bin.properties, 'set_node'):
                        self.properties_bin.properties.set_node(node)
                    else:
                        print("Warning: Could not find method to set node in properties bin")
                
                # Get node name safely
                node_name = "Unknown"
                if hasattr(node, 'name') and callable(getattr(node, 'name')):
                    node_name = node.name()
                elif hasattr(node, 'get_name') and callable(getattr(node, 'get_name')):
                    node_name = node.get_name()
                
                self.statusBar.showMessage(f"Selected: {node_name}")
            except Exception as e:
                print(f"Error handling node selection: {e}")
                self.statusBar.showMessage(f"Error selecting node: {str(e)}")
        else:
            # Try different API methods for clearing the node
            if hasattr(self.properties_bin, 'set_node'):
                self.properties_bin.set_node(None)
            elif hasattr(self.properties_bin, 'add_node'):
                self.properties_bin.add_node(None)
            elif hasattr(self.properties_bin, 'clear'):
                self.properties_bin.clear()
            
            self.statusBar.showMessage("Ready")
    
    def on_node_created(self, node):
        """Handle node creation"""
        try:
            # Get node name safely
            node_name = "Unknown"
            if hasattr(node, 'name') and callable(getattr(node, 'name')):
                node_name = node.name()
            elif hasattr(node, 'get_name') and callable(getattr(node, 'get_name')):
                node_name = node.get_name()
                
            self.statusBar.showMessage(f"Created node: {node_name}")
            
            # Mark the node as dirty to ensure it gets processed
            if hasattr(node, 'mark_dirty'):
                node.mark_dirty()
        except Exception as e:
            print(f"Error handling node creation: {e}")
            self.statusBar.showMessage(f"Error with created node: {str(e)}")
    
    def delete_selected_node(self):
        """Delete the currently selected node"""
        try:
            # Get selected nodes - handle API differences
            selected = []
            if hasattr(self.graph, 'selected_nodes') and callable(self.graph.selected_nodes):
                selected = self.graph.selected_nodes()
            elif hasattr(self.graph, 'get_selected_nodes') and callable(self.graph.get_selected_nodes):
                selected = self.graph.get_selected_nodes()
            
            if selected:
                # Delete each selected node
                count = 0
                for node in selected:
                    try:
                        # Handle API differences
                        if hasattr(self.graph, 'delete_node') and callable(self.graph.delete_node):
                            self.graph.delete_node(node)
                        elif hasattr(self.graph, 'remove_node') and callable(self.graph.remove_node):
                            self.graph.remove_node(node)
                        count += 1
                    except Exception as e:
                        print(f"Error deleting node: {e}")
                
                self.statusBar.showMessage(f"Deleted {count} node(s)")
            else:
                self.statusBar.showMessage("No nodes selected")
        except Exception as e:
            print(f"Error in delete_selected_node: {e}")
            self.statusBar.showMessage(f"Error deleting node: {str(e)}")
    
    def new_workflow(self):
        """Create a new workflow"""
        self.graph.clear_all()
        self.statusBar.showMessage("New workflow created")
    
    def save_workflow(self):
        """Save the current workflow"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 'Save Workflow', '', 'JSON Files (*.json)'
        )
        
        if file_path:
            # Add .json extension if not provided
            if not file_path.endswith('.json'):
                file_path += '.json'
                
            # Use NodeGraphQt's save functionality
            self.graph.save(file_path)
            self.statusBar.showMessage(f"Workflow saved to {file_path}")
    
    def load_workflow(self):
        """Load a saved workflow"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Load Workflow', '', 'JSON Files (*.json)'
        )
        
        if file_path:
            # Use NodeGraphQt's load functionality
            self.graph.load(file_path)
            self.statusBar.showMessage(f"Workflow loaded from {file_path}")
    
    def run_workflow(self):
        """Run the workflow using the executor"""
        if hasattr(self, 'executor'):
            success, message = self.executor.execute_workflow(self.on_workflow_complete)
            self.statusBar.showMessage(message)
        else:
            self.statusBar.showMessage("Workflow executor not available")
    
    def on_workflow_complete(self, result):
        """Handle workflow completion"""
        success, message = result
        self.statusBar.showMessage(message)
    
    def reset_workflow(self):
        """Reset all nodes in the workflow"""
        try:
            # Get all nodes - handle API differences
            all_nodes = []
            if hasattr(self.graph, 'all_nodes') and callable(self.graph.all_nodes):
                all_nodes = self.graph.all_nodes()
            elif hasattr(self.graph, 'nodes') and callable(self.graph.nodes):
                all_nodes = self.graph.nodes()
            
            # Reset each node
            reset_count = 0
            for node in all_nodes:
                try:
                    if hasattr(node, 'mark_dirty'):
                        node.mark_dirty()
                        if hasattr(node, 'output_cache'):
                            node.output_cache = {}
                        reset_count += 1
                except Exception as e:
                    print(f"Error resetting node: {e}")
            
            self.statusBar.showMessage(f"Reset {reset_count} nodes")
        except Exception as e:
            print(f"Error in reset_workflow: {e}")
            self.statusBar.showMessage(f"Error resetting workflow: {str(e)}")


def ensure_directories():
    """Create required directories"""
    # Create nodes directory if it doesn't exist
    if not os.path.exists('nodes'):
        os.makedirs('nodes')
        print("Created nodes directory")
    
    # Create __init__.py in nodes directory if it doesn't exist
    init_file = os.path.join('nodes', '__init__.py')
    if not os.path.exists(init_file):
        with open(init_file, 'w') as f:
            f.write('"""Node package for Ollama Flow"""\n')
        print("Created nodes/__init__.py")


if __name__ == "__main__":
    try:
        # Ensure directories exist
        ensure_directories()
        
        # Check for missing dependencies before starting application
        missing_deps = []
        
        try:
            import PySide6
        except ImportError:
            missing_deps.append("PySide6")
            
        try:
            import NodeGraphQt
        except ImportError:
            missing_deps.append("NodeGraphQt")
            
        try:
            import requests
        except ImportError:
            missing_deps.append("requests")
        
        # If there are missing dependencies, show a helpful message
        if missing_deps:
            app = QApplication(sys.argv)
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Missing Dependencies")
            msg.setText(f"The following dependencies are missing: {', '.join(missing_deps)}")
            msg.setInformativeText("Please install them using pip:\n\npip install " + " ".join(missing_deps))
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
            sys.exit(1)
        
        # Start application
        app = QApplication(sys.argv)
        window = OllamaFlow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        
        # If QApplication is available, show error in a message box
        if 'QApplication' in locals():
            try:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowTitle("Application Error")
                msg.setText(f"Error starting application: {str(e)}")
                msg.setDetailedText(traceback.format_exc())
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec()
            except:
                pass
                
        # If PySide6 is missing, suggest installation
        if "No module named 'PySide6'" in str(e):
            print("\nMissing PySide6. Please install required dependencies:")
            print("pip install PySide6 NodeGraphQt requests")
            
        # If NodeGraphQt is missing, suggest installation
        if "No module named 'NodeGraphQt'" in str(e):
            print("\nMissing NodeGraphQt. Please install:")
            print("pip install NodeGraphQt")
        
        input("\nPress Enter to exit...")
