import sys
import os
import json
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

try:
    from port_tooltip import install_port_tooltips
except ImportError as e:
    print(f"Warning: Could not import port_tooltip module: {e}")

# Ensure plugins can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import node registry
try:
    from node_registry import registry
except ImportError as e:
    print(f"Error importing node registry: {e}")
    registry = None

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
        
        # Set up port tooltips
        self.setup_port_tooltips()

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
        
        # Register and discover node types
        self.register_nodes()
        
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
        
        # Build Nodes menu dynamically from registry
        self.build_nodes_menu(menubar)
        
        # Workflow menu
        workflow_menu = menubar.addMenu("Workflow")
        
        run_action = QAction("Run Workflow", self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self.run_workflow)
        workflow_menu.addAction(run_action)
        
        reset_action = QAction("Reset All", self)
        reset_action.triggered.connect(self.reset_workflow)
        workflow_menu.addAction(reset_action)
    
    def setup_port_tooltips(self):
        """Set up tooltips for ports and connections"""
        try:
            # Check if the port_tooltip module is available
            if 'install_port_tooltips' in globals():
                # Install tooltips on the graph
                self.tooltip_manager = install_port_tooltips(self.graph)
                if self.tooltip_manager:
                    self.statusBar.showMessage("Port tooltips enabled", 3000)
                    print("Port tooltips enabled")
                else:
                    print("Warning: Could not initialize port tooltips")
        except Exception as e:
            print(f"Error setting up port tooltips: {e}")
            import traceback
            traceback.print_exc()

    def build_nodes_menu(self, menubar):
        """Build the Nodes menu dynamically from registered node categories"""
        # Node menu
        node_menu = menubar.addMenu("Nodes")
        
        # Delete node action
        delete_action = QAction("Delete Selected", self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self.delete_selected_node)
        node_menu.addAction(delete_action)
        
        node_menu.addSeparator()
        
        # Check if registry is available
        if not registry:
            # Create a basic nodes menu without registry
            add_menu = node_menu.addMenu("Add Node")
            add_static_action = QAction("Add Static Text", self)
            add_static_action.triggered.connect(self.add_static_text_node)
            add_menu.addAction(add_static_action)
            return
        
        # Add node submenus by category
        for category in sorted(registry.get_all_categories()):
            category_menu = node_menu.addMenu(f"Add {category}")
            
            # Add nodes for this category
            for node_info in registry.get_nodes_in_category(category):
                node_action = QAction(node_info['display_name'], self)
                # Use lambda with default args to capture the current values
                node_action.triggered.connect(
                    lambda checked=False, node_id=node_info['id'], 
                    display_name=node_info['display_name']: 
                    self.create_node_from_registry(node_id, display_name))
                category_menu.addAction(node_action)
    
    def create_node_from_registry(self, node_id, display_name):
        """Create a node from its registry ID"""
        try:
            # Try to create node using graph.create_node
            if hasattr(self.graph, 'create_node'):
                node = self.graph.create_node(node_id)
                if node:
                    self.position_node_at_center(node)
                    self.statusBar.showMessage(f"Created {display_name} node")
                    return
            
            # If that failed, get the class from registry and create manually
            node_class = registry.get_node_class(node_id)
            if node_class:
                node = node_class()
                self.graph.add_node(node)
                self.position_node_at_center(node)
                self.statusBar.showMessage(f"Created {display_name} node")
            else:
                self.statusBar.showMessage(f"Error: Node type {node_id} not found")
                
        except Exception as e:
            print(f"Error creating node from registry: {e}")
            import traceback
            traceback.print_exc()
            self.statusBar.showMessage(f"Error creating node: {str(e)}")
    
    def position_node_at_center(self, node):
        """Position a node at the center of the current view"""
        try:
            # Get center position of viewport
            view = self.graph.viewer()
            if view and hasattr(view, 'mapToScene') and hasattr(view, 'viewport'):
                center_pos = view.mapToScene(view.viewport().rect().center())
                if hasattr(node, 'set_pos'):
                    node.set_pos(center_pos.x(), center_pos.y())
        except Exception as e:
            print(f"Warning: Could not position node at center: {e}")
    
    def register_nodes(self):
        """Register all node types with NodeGraphQt"""
        if registry:
            # First discover all available nodes
            registry.discover_nodes()
            
            # Then register them with the graph
            success = registry.register_all_nodes(self.graph)
            
            if success:
                print("Successfully registered all nodes from registry")
                # Print registered nodes for debugging
                print(f"Registered {len(registry.nodes_by_id)} nodes in {len(registry.nodes_by_category)} categories")
            else:
                print("Failed to register nodes from registry")
                # Fall back to manual registration of StaticTextNode
                self.register_static_text_node()
        else:
            # Fallback to manual registration
            self.register_static_text_node()
    
    def register_static_text_node(self):
        """Fallback method to manually register the StaticTextNode"""
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
            
            # Try different registration methods until one works
            try:
                if hasattr(self.graph, 'register_node'):
                    self.graph.register_node(StaticTextNode)
                elif hasattr(factory, 'register_node'):
                    factory.register_node(StaticTextNode)
                else:
                    # Manual registration by updating dictionary
                    dict_name = '_factory_dict' if hasattr(factory, '_factory_dict') else '_node_factory_dict'
                    if hasattr(factory, dict_name):
                        factory_dict = getattr(factory, dict_name)
                        node_id = getattr(StaticTextNode, '__identifier__', 'com.ollamaflow.nodes')
                        node_type = getattr(StaticTextNode, '__type__', 'StaticTextNode')
                        full_id = f"{node_id}.{node_type}"
                        factory_dict[full_id] = StaticTextNode
            except Exception as e:
                print(f"Error during node registration: {e}")
                
        except Exception as e:
            print(f"Error registering StaticTextNode: {e}")
            import traceback
            traceback.print_exc()
    
    def add_static_text_node(self):
        """Add a static text node directly"""
        try:
            # Create the node instance directly
            try:
                from nodes.static_text_node import StaticTextNode
            except ImportError:
                from nodes import StaticTextNode
                
            static_node = StaticTextNode()
            
            # Add to the graph
            if hasattr(self.graph, 'add_node'):
                self.graph.add_node(static_node)
            
            # Position the node at the center of the view
            self.position_node_at_center(static_node)
                
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
                
            # Use NodeGraphQt's export_session functionality instead of save
            try:
                if hasattr(self.graph, 'export_session'):
                    self.graph.export_session(file_path)
                elif hasattr(self.graph, 'serialize_session'):
                    # Alternative method used in some versions
                    session_data = self.graph.serialize_session()
                    with open(file_path, 'w') as f:
                        json.dump(session_data, f, indent=2)
                else:
                    self.statusBar.showMessage("Error: Unable to save workflow - method not found")
                    return
                    
                self.statusBar.showMessage(f"Workflow saved to {file_path}")
            except Exception as e:
                print(f"Error saving workflow: {e}")
                import traceback
                traceback.print_exc()
                self.statusBar.showMessage(f"Error saving workflow: {str(e)}")

    def load_workflow(self):
        """Load a saved workflow"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Load Workflow', '', 'JSON Files (*.json)'
        )
        
        if file_path:
            # Use NodeGraphQt's import_session functionality instead of load
            try:
                if hasattr(self.graph, 'import_session'):
                    self.graph.import_session(file_path)
                elif hasattr(self.graph, 'deserialize_session'):
                    # Alternative method used in some versions
                    with open(file_path, 'r') as f:
                        session_data = json.load(f)
                    self.graph.deserialize_session(session_data)
                else:
                    self.statusBar.showMessage("Error: Unable to load workflow - method not found")
                    return
                    
                self.statusBar.showMessage(f"Workflow loaded from {file_path}")
            except Exception as e:
                print(f"Error loading workflow: {e}")
                import traceback
                traceback.print_exc()
                self.statusBar.showMessage(f"Error loading workflow: {str(e)}")
    
    def run_workflow(self):
        """Run the workflow using the executor"""
        if hasattr(self, 'executor'):
            print("Starting workflow execution...")
            try:
                success, message = self.executor.execute_workflow(self.on_workflow_complete)
                print(f"Workflow execution initiated: {success}, {message}")
                self.statusBar.showMessage(message)
            except Exception as e:
                print(f"Error starting workflow execution: {e}")
                import traceback
                traceback.print_exc()
                self.statusBar.showMessage(f"Error: {str(e)}")
        else:
            self.statusBar.showMessage("Workflow executor not available")
    
    def on_workflow_complete(self, result):
        """Handle workflow completion"""
        success, message = result
        print(f"Workflow completion received: Success={success}, Message={message}")
        self.statusBar.showMessage(message)
        
        # Provide visual feedback to the user
        try:
            msg = QMessageBox()
            msg.setWindowTitle("Workflow Execution")
            if success:
                msg.setIcon(QMessageBox.Information)
                msg.setText("Workflow execution completed")
            else:
                msg.setIcon(QMessageBox.Warning)
                msg.setText("Workflow execution issue")
            msg.setInformativeText(message)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
        except Exception as e:
            print(f"Error showing workflow completion message: {e}")
    
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
