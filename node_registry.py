"""
Node registry module for automatically discovering and registering node classes.
"""
import os
import sys
import importlib
import inspect
import pkgutil
from typing import Dict, List, Type, Optional

# Import base node to check for inheritance
try:
    from nodes.base_node import OllamaBaseNode
except ImportError:
    # Define a placeholder if the actual base node can't be imported
    class OllamaBaseNode:
        pass

class NodeRegistry:
    """
    Registry for discovering and managing nodes in the Ollama Flow application.
    """
    def __init__(self):
        self.nodes_by_id = {}  # Store nodes by identifier
        self.nodes_by_category = {}  # Store nodes by category
        self.discovered = False  # Flag to track if discovery has been done
    
    def discover_nodes(self, package_name='nodes'):
        """
        Discover all node classes in the specified package.
        
        Args:
            package_name: The package to scan for node classes
        """
        self.nodes_by_id = {}
        self.nodes_by_category = {}
        
        # Import the package
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            print(f"Error: Could not import package '{package_name}'")
            return
        
        # Get the package path
        package_path = getattr(package, '__path__', [None])[0]
        if not package_path:
            print(f"Error: Could not determine path for package '{package_name}'")
            return
        
        # Find all modules in the package
        for _, module_name, is_pkg in pkgutil.iter_modules([package_path]):
            if is_pkg:
                continue  # Skip subpackages for now
            
            # Import the module
            try:
                module = importlib.import_module(f"{package_name}.{module_name}")
                
                # Find all classes in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # Check if it's a node class (inherits from OllamaBaseNode)
                    if issubclass(obj, OllamaBaseNode) and obj != OllamaBaseNode:
                        # Get node metadata
                        self._register_node_class(obj)
                        
            except Exception as e:
                print(f"Error importing module {module_name}: {str(e)}")
        
        self.discovered = True
        print(f"Discovered {len(self.nodes_by_id)} node classes")
    
    def _register_node_class(self, node_class):
        """
        Register a node class in the registry.
        
        Args:
            node_class: The node class to register
        """
        # Get node identifier and type
        identifier = getattr(node_class, '__identifier__', 'com.ollamaflow.nodes')
        node_type = getattr(node_class, '__type__', node_class.__name__)
        
        # Get node display name
        display_name = getattr(node_class, 'NODE_NAME', node_class.__name__)
        
        # Get node category
        category = getattr(node_class, 'NODE_CATEGORY', 'Uncategorized')
        
        # Register by ID
        node_id = f"{identifier}.{node_type}"
        self.nodes_by_id[node_id] = {
            'class': node_class,
            'display_name': display_name,
            'category': category,
            'description': node_class.__doc__ or "No description"
        }
        
        # Register by category
        if category not in self.nodes_by_category:
            self.nodes_by_category[category] = []
        
        self.nodes_by_category[category].append({
            'id': node_id,
            'display_name': display_name,
            'description': node_class.__doc__ or "No description",
            'class': node_class
        })
    
    def get_node_class(self, node_id):
        """
        Get a node class by its ID.
        
        Args:
            node_id: The node ID to look up
            
        Returns:
            The node class if found, None otherwise
        """
        if not self.discovered:
            self.discover_nodes()
            
        node_info = self.nodes_by_id.get(node_id)
        return node_info['class'] if node_info else None
    
    def get_all_categories(self):
        """
        Get all node categories.
        
        Returns:
            List of category names
        """
        if not self.discovered:
            self.discover_nodes()
            
        return list(self.nodes_by_category.keys())
    
    def get_nodes_in_category(self, category):
        """
        Get all nodes in a category.
        
        Args:
            category: The category to get nodes for
            
        Returns:
            List of node info dictionaries
        """
        if not self.discovered:
            self.discover_nodes()
            
        return self.nodes_by_category.get(category, [])
    
    def get_all_node_classes(self):
        """
        Get all discovered node classes.
        
        Returns:
            List of node classes
        """
        if not self.discovered:
            self.discover_nodes()
            
        return [info['class'] for info in self.nodes_by_id.values()]
    
    def register_all_nodes(self, graph):
        """
        Register all discovered nodes with the NodeGraph instance.
        
        Args:
            graph: The NodeGraph instance to register nodes with
        """
        if not self.discovered:
            self.discover_nodes()
        
        # Use the appropriate registration method based on what's available
        try:
            if hasattr(graph, 'register_nodes'):
                graph.register_nodes(self.get_all_node_classes())
            elif hasattr(graph, 'register_node'):
                for node_class in self.get_all_node_classes():
                    graph.register_node(node_class)
            else:
                # Get node factory
                if hasattr(graph, '_node_factory'):
                    factory = graph._node_factory
                elif hasattr(graph, '_NodeGraph__node_factory'):
                    factory = graph._NodeGraph__node_factory
                else:
                    print("CRITICAL: Cannot find node factory in graph!")
                    return False
                
                # Register with factory
                if hasattr(factory, 'register_node'):
                    for node_class in self.get_all_node_classes():
                        factory.register_node(node_class)
                else:
                    # Manual registration by updating dictionary
                    dict_name = '_factory_dict' if hasattr(factory, '_factory_dict') else '_node_factory_dict'
                    if hasattr(factory, dict_name):
                        factory_dict = getattr(factory, dict_name)
                        for node_class in self.get_all_node_classes():
                            identifier = getattr(node_class, '__identifier__', 'com.ollamaflow.nodes')
                            node_type = getattr(node_class, '__type__', node_class.__name__)
                            node_id = f"{identifier}.{node_type}"
                            factory_dict[node_id] = node_class
                    else:
                        print("CRITICAL: Cannot find factory dictionary!")
                        return False
            
            return True
            
        except Exception as e:
            print(f"Error registering nodes: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


# Create a singleton instance
registry = NodeRegistry()
