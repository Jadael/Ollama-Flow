import os
import sys
import pkgutil
import importlib
import inspect
from typing import List, Dict, Type, Optional

class NodeRegistry:
    """Registry for node types in the workflow system"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NodeRegistry, cls).__new__(cls)
            cls._instance._node_types = {}
            cls._instance._categories = {}
            cls._instance._initialized = False
        return cls._instance
    
    def register_node_type(self, node_class):
        """Register a node class in the registry"""
        # Get node type and category
        node_type = getattr(node_class, "node_type", node_class.__name__)
        category = getattr(node_class, "category", "Uncategorized")
        
        # Add to registry
        self._node_types[node_type] = node_class
        
        # Add to category
        if category not in self._categories:
            self._categories[category] = []
        
        if node_class not in self._categories[category]:
            self._categories[category].append(node_class)
        
        return node_class
    
    def discover_nodes(self):
        """Discover and register all node types in plugins directory"""
        if self._initialized:
            return
            
        # Get the plugins directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        plugins_dir = os.path.join(base_dir, "plugins")
        
        print(f"Scanning for nodes in {plugins_dir}")
        
        # Make sure plugins directory is in path
        if plugins_dir not in sys.path:
            sys.path.append(base_dir)
        
        # Walk the plugins directory and import all modules
        for root, dirs, files in os.walk(plugins_dir):
            if "__pycache__" in root:
                continue
                
            # Get relative path from base_dir
            rel_path = os.path.relpath(root, base_dir)
            package_name = rel_path.replace(os.path.sep, ".")
            
            # Look for Python files
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    module_name = file[:-3]  # Remove .py extension
                    full_module_name = f"{package_name}.{module_name}"
                    
                    try:
                        # Import the module
                        module = importlib.import_module(full_module_name)
                        
                        # Look for Node subclasses
                        for name, obj in inspect.getmembers(module):
                            if (inspect.isclass(obj) and 
                                hasattr(obj, "__module__") and 
                                obj.__module__ == module.__name__ and
                                "Node" in obj.__name__):
                                
                                # Check if it's a Node subclass
                                from core.node import Node
                                if issubclass(obj, Node) and obj != Node:
                                    self.register_node_type(obj)
                                    print(f"Registered node: {obj.node_type}")
                                    
                    except Exception as e:
                        print(f"Error importing module {full_module_name}: {str(e)}")
        
        self._initialized = True
    
    def get_node_types(self) -> Dict[str, Type]:
        """Get all registered node types"""
        if not self._initialized:
            self.discover_nodes()
        return self._node_types
    
    def get_node_categories(self) -> Dict[str, List[Type]]:
        """Get all registered node types organized by category"""
        if not self._initialized:
            self.discover_nodes()
        return self._categories
    
    def get_node_class(self, node_type: str) -> Optional[Type]:
        """Get a node class by its type name"""
        if not self._initialized:
            self.discover_nodes()
        return self._node_types.get(node_type)


# Create a singleton instance
registry = NodeRegistry()

# Export the register_node_type function for convenience
def register_node_type(node_class):
    return registry.register_node_type(node_class)

# Helper function to get all node types
def get_all_node_types():
    return registry.get_node_types()

# Helper function to get all node categories
def get_all_node_categories():
    return registry.get_node_categories()

# Helper function to get a node class by type
def get_node_class(node_type):
    return registry.get_node_class(node_type)
