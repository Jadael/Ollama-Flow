# Ollama Flow Technical Documentation

## 1. Introduction

Ollama Flow is a node-based workflow application designed to create and execute data processing pipelines with a focus on Large Language Model (LLM) integration. It provides a visual interface for connecting nodes that represent different processing steps, allowing users to build complex workflows without extensive programming.

### 1.1 Key Features

- **Visual Node-Based Interface**: Create workflows by connecting nodes with a drag-and-drop interface
- **LLM Integration**: Seamless connection to Ollama's language models
- **Extensible Architecture**: Custom node creation for extending functionality
- **Workflow Management**: Save, load, and execute complex workflows
- **Asynchronous Processing**: Support for both synchronous and asynchronous node execution
- **Thread-Safe UI Updates**: Real-time status updates without blocking the user interface

## 2. Architecture Overview

Ollama Flow follows a component-based architecture built on PySide6 (Qt) and the NodeGraphQt library. It utilizes several design patterns including:

- **MVC Pattern**: Separation of the node graph model, view, and controller logic
- **Factory Pattern**: Dynamic node creation and registration
- **Observer Pattern**: Signal-slot mechanism for UI updates
- **Singleton Pattern**: For thread-safe signal handling

### 2.1 Core Components

![Architecture Diagram](https://via.placeholder.com/800x400?text=Ollama+Flow+Architecture)

The application consists of these primary components:

1. **Main Application** (`app.py`): The central application controller and UI
2. **Node Registry** (`node_registry.py`): Manages node discovery and registration
3. **Workflow Executor** (`workflow_executor.py`): Handles workflow execution logic
4. **Base Node** (`base_node.py`): Base class for all nodes with common functionality
5. **Node Implementations**: Various specialized node types for different operations
6. **Port Tooltip System** (`port_tooltip.py`): Provides dynamic tooltips for node connections

## 3. Installation and Setup

### 3.1 Dependencies

Ollama Flow requires the following dependencies:

- Python 3.6 or higher
- PySide6
- NodeGraphQt
- Requests

### 3.2 Installation Steps

1. Ensure Python 3.6+ is installed on your system
2. Install the required dependencies:

```bash
pip install PySide6 NodeGraphQt requests
```

3. Clone or download the Ollama Flow source code
4. Run the application using:

```bash
python main.py
```

### 3.3 Directory Structure

```
ollama-flow/
├── app.py                # Main application window and logic
├── main.py               # Entry point
├── node_registry.py      # Node discovery and registration
├── workflow_executor.py  # Workflow execution engine
├── port_tooltip.py       # Tooltip functionality for ports
├── nodes/                # Node implementations
│   ├── __init__.py
│   ├── base_node.py      # Base node class
│   ├── static_text_node.py
│   ├── prompt_node.py
│   ├── join_node.py
│   ├── split_node.py
│   └── regex_node.py
```

## 4. User Interface

### 4.1 Main Window

The main Ollama Flow window consists of:

1. **Node Graph Area**: Central workspace for creating and connecting nodes
2. **Properties Panel**: Docked on the right side, displays selected node properties
3. **Menu Bar**: Access to file operations, node creation, and workflow execution
4. **Status Bar**: Shows current application status and operation feedback

### 4.2 Menus

The application provides the following menus:

- **File Menu**: New, Save, Load, and Exit operations
- **Nodes Menu**: Create different types of nodes organized by category
- **Workflow Menu**: Run and Reset workflow operations

### 4.3 Node Graph

The node graph is the primary workspace where:

- Nodes can be added via the Nodes menu
- Connections are created by dragging from an output port to an input port
- Nodes can be selected, moved, and deleted
- Connections show data flow between nodes

### 4.4 Properties Panel

The properties panel shows editable properties for the selected node:

- Text inputs, checkboxes, dropdown menus, etc.
- Properties are organized in tabs for better organization
- Changes to properties can trigger node recalculation based on the node's settings

### 4.5 Port Tooltips

The port tooltip system provides dynamic information when hovering over ports or connections:

- Shows the connected nodes and ports
- Displays the current value being passed through the connection
- Updates in real-time as data changes

## 5. Workflow System

### 5.1 Creating Workflows

Workflows are created by:

1. Adding nodes to the graph from the Nodes menu
2. Configuring node properties in the properties panel
3. Connecting output ports to input ports to establish data flow

### 5.2 Saving and Loading Workflows

Workflows can be saved to and loaded from JSON files:

- **Save Workflow**: Exports the entire node graph including node positions, connections, and properties
- **Load Workflow**: Imports a previously saved workflow, recreating all nodes and connections

### 5.3 Workflow Execution

The workflow execution process follows these steps:

1. **Initialization**: The executor analyzes the workflow to determine execution order
2. **Processing**: Nodes are processed in dependency order (inputs before outputs)
3. **Result Propagation**: Results from one node flow to connected nodes
4. **Completion Handling**: Final results are displayed and the workflow is marked as complete

### 5.4 Execution Modes

Ollama Flow supports multiple execution modes controlled by node properties:

- **Dirty if Inputs Change**: Node recalculates only when inputs change (default)
- **Always Dirty**: Node always recalculates when workflow is executed
- **Never Dirty**: Node uses cached results until explicitly reset

## 6. Core Components

### 6.1 Application Core (app.py)

The `OllamaFlow` class in `app.py` is the main application controller that:

- Creates and configures the NodeGraphQt graph
- Sets up the UI components (menus, panels, etc.)
- Handles user interactions (selections, deletions, etc.)
- Manages workflow operations (save, load, run)

```python
class OllamaFlow(QMainWindow):
    """Main application window for Ollama Flow"""
    
    def __init__(self):
        # Initialize application components
        
    def setup_menu(self):
        # Create application menus
        
    def build_nodes_menu(self, menubar):
        # Dynamically build the nodes menu from registry
        
    def run_workflow(self):
        # Execute the current workflow
```

### 6.2 Node Registry System

The `NodeRegistry` class in `node_registry.py` handles:

- Discovering node classes in the `nodes` directory
- Registering nodes with the NodeGraphQt system
- Organizing nodes by category for the menu system
- Providing node metadata for the UI

```python
class NodeRegistry:
    """Registry for discovering and managing nodes in the Ollama Flow application."""
    
    def discover_nodes(self, package_name='nodes'):
        # Find all node classes in the package
        
    def register_all_nodes(self, graph):
        # Register all discovered nodes with the NodeGraph
```

### 6.3 Workflow Executor

The `WorkflowExecutor` class in `workflow_executor.py` is responsible for:

- Analyzing the dependency graph of nodes
- Processing nodes in the correct order
- Handling asynchronous node execution
- Managing execution status and error handling

```python
class WorkflowExecutor:
    """Handles the execution of a NodeGraphQt workflow"""
    
    def execute_workflow(self, callback=None):
        # Start workflow execution process
        
    def _execute_workflow_thread(self):
        # Background thread for execution
```

### 6.4 Signal Handler for Thread Safety

Ollama Flow uses a signal handler system to ensure thread safety:

- `NodeSignalHandler` in `base_node.py` provides signals for UI updates
- Allows background threads to safely update the UI
- Handles property updates, status changes, and widget refreshes

```python
class NodeSignalHandler(QObject):
    # Define signals for thread-safe operations
    property_updated = Signal(object, str, object)  # node, property_name, value
    status_updated = Signal(object, str)  # node, status_text
    widget_refresh = Signal(object)  # node to refresh widgets
```

### 6.5 Port Tooltips System

The port tooltips system in `port_tooltip.py` provides:

- Real-time data visualization for connections
- Tooltip content based on the current node state
- Automatic value extraction from nodes

```python
class PortTooltipManager(QObject):
    """Manages tooltips for ports and connection lines in the node graph."""
    
    def get_tooltip_text(self, item):
        # Generate tooltip text for a port or connection item
```

## 7. Node System

### 7.1 Base Node Implementation

The `OllamaBaseNode` class in `base_node.py` is the foundation for all nodes and provides:

- Common functionality for all node types
- Property system with automatic port creation
- Thread-safe UI updates
- Input/output management
- Processing state handling

```python
class OllamaBaseNode(BaseNode):
    """Base class for all Ollama nodes that uses minimal API features"""
    
    def __init__(self):
        # Initialize base node components
        
    def compute(self):
        # Process the node and its dependencies
        
    def get_property_value(self, prop_name):
        # Get property values considering input connections
```

### 7.2 Node Properties

Each node can define properties that:

- Appear in the properties panel for user configuration
- Can be connected via input ports for dynamic values
- Trigger recalculation when changed (based on recalculation mode)
- Are saved and loaded with the workflow

Properties are created using methods like:

```python
self.add_text_input('property_name', 'Display Label', 'default_value')
self.add_combo_menu('property_name', 'Display Label', ['Option1', 'Option2'], 'Option1')
self.add_checkbox('property_name', 'Display Label', False)
```

### 7.3 Input/Output Ports

Nodes communicate via input and output ports:

- **Input Ports**: Receive data from other nodes
- **Output Ports**: Send data to other nodes
- Ports can be created explicitly or automatically from properties

```python
# Create ports directly
self.add_input('Input Name')
self.add_output('Output Name')

# Or automatically from properties
self.add_text_input('property_name', 'Display Label', 'default_value')
```

### 7.4 Node Processing

Node processing follows this general flow:

1. **Dependency Resolution**: Process all input nodes first
2. **Input Collection**: Gather values from all input ports
3. **Processing Logic**: Execute the node-specific logic
4. **Output Generation**: Produce output values
5. **State Update**: Update node status and cache results

The processing is controlled by the `compute()` and `execute()` methods:

```python
def compute(self):
    """Process this node and its dependencies"""
    # Process dependencies
    # Handle caching
    # Call execute() for node-specific logic
    # Update state
    
def execute(self):
    """Node-specific processing logic (override in subclasses)"""
    # Implement in each node type
    return {'Output Name': result}
```

### 7.5 Asynchronous Nodes

Ollama Flow supports asynchronous processing for long-running operations:

- Nodes can set `self.is_async_node = True` to indicate asynchronous processing
- Asynchronous nodes use background threads for processing
- Thread-safe signals update the UI without blocking
- Status updates show processing progress

## 8. Built-in Node Types

### 8.1 Input Nodes

#### 8.1.1 Static Text Node (static_text_node.py)

The Static Text Node provides constant text output:

- **Properties**:
  - `text`: The text content to output
- **Outputs**:
  - `Text`: The configured text content

```python
class StaticTextNode(OllamaBaseNode):
    """A node that outputs static text"""
    
    def execute(self):
        text = self.get_property_value('text')
        return {'Text': text}
```

### 8.2 LLM Nodes

#### 8.2.1 Prompt Node (prompt_node.py)

The Prompt Node sends prompts to an LLM and processes the response:

- **Properties**:
  - `model`: Model to use (e.g., "deepseek-r1:32b")
  - `system_prompt`: System instruction for the LLM
  - `user_prompt`: User input to send to the LLM
  - Multiple configuration options (temperature, top_p, etc.)
  - Filtering options for post-processing responses
- **Outputs**:
  - `Raw Response`: Unfiltered response from the LLM
  - `Response`: Filtered response based on settings

```python
class PromptNode(OllamaBaseNode):
    """A node that sends prompts to an LLM and outputs the response"""
    
    def __init__(self):
        # Initialize prompt node
        self.is_async_node = True  # Mark as asynchronous
        
    def execute(self):
        # Start asynchronous processing
        Thread(target=self._generation_thread, args=(system_prompt, user_prompt), daemon=True).start()
        return {'Response': "Processing...", 'Raw Response': "Processing..."}
        
    def _generation_thread(self, system_prompt, user_prompt):
        # Connect to Ollama API
        # Process streaming response
        # Apply filtering
        # Update output
```

### 8.3 Text Processing Nodes

#### 8.3.1 Join Node (join_node.py)

The Join Node combines multiple text inputs into a single output:

- **Properties**:
  - 8 input properties (`input_1` through `input_8`)
  - `delimiter`: Text to insert between joined parts
  - `skip_empty`: Whether to skip empty inputs
  - `trim_whitespace`: Whether to trim whitespace from inputs
- **Outputs**:
  - `Result`: The combined text

```python
class JoinNode(OllamaBaseNode):
    """A node that joins multiple inputs with a configurable delimiter"""
    
    def execute(self):
        # Get input values
        # Apply configuration options
        # Join values with delimiter
        return {"Result": result}
```

#### 8.3.2 Split Node (split_node.py)

The Split Node divides text into multiple outputs:

- **Properties**:
  - `input_text`: Text to split
  - `delimiter`: Where to split the text
  - `trim_whitespace`: Whether to trim whitespace
  - `max_splits`: Maximum number of splits
  - `use_regex`: Whether to use regex for splitting
- **Outputs**:
  - `Output 1` through `Output 8`: Individual parts
  - `Overflow`: Additional parts beyond 8

```python
class SplitNode(OllamaBaseNode):
    """A node that splits input text into multiple outputs based on a delimiter"""
    
    def execute(self):
        # Get input text
        # Split based on configuration
        # Assign parts to output ports
        return output_data
```

#### 8.3.3 Regex Node (regex_node.py)

The Regex Node applies regular expression operations to text:

- **Properties**:
  - `input_text`: Text to process
  - `pattern`: Regular expression pattern
  - `replacement`: Replacement text (for replace operations)
  - `operation`: Operation to perform (replace, match, split, findall)
  - Regex flags configuration
- **Outputs**:
  - `Result`: Processed text

```python
class RegexNode(OllamaBaseNode):
    """A node that applies a regex pattern to its input text"""
    
    def execute(self):
        # Get input text
        # Apply selected regex operation
        # Return result
        return {"Result": result}
```

## 9. Extending Ollama Flow

### 9.1 Creating Custom Nodes

Custom nodes can be created by:

1. Creating a new Python file in the `nodes` directory
2. Defining a class that inherits from `OllamaBaseNode`
3. Implementing the required methods and properties

Basic structure for a custom node:

```python
from nodes.base_node import OllamaBaseNode

class MyCustomNode(OllamaBaseNode):
    """Description of your custom node"""
    
    # Node identifier and type
    __identifier__ = 'com.ollamaflow.nodes'
    __type__ = 'MyCustomNode'
    
    # Node display name
    NODE_NAME = 'My Custom Node'
    
    # Node category for menu organization
    NODE_CATEGORY = 'Custom'
    
    def __init__(self):
        super(MyCustomNode, self).__init__()
        
        # Set node name
        self.set_name('My Custom Node')
        
        # Create properties (automatically creates input ports)
        self.add_text_input('input_property', 'Input Property', 'default')
        
        # Create output ports
        self.add_output('Result')
        
        # Set node color
        self.set_color(100, 100, 200)
    
    def execute(self):
        """Process the node and return output"""
        # Get property values
        input_value = self.get_property_value('input_property')
        
        # Process data
        result = process_data(input_value)
        
        # Return output values
        return {"Result": result}
```

### 9.2 Node Registration

Custom nodes are automatically registered through the node registry system:

1. The `NodeRegistry` discovers node classes in the `nodes` directory
2. Nodes are categorized based on their `NODE_CATEGORY` attribute
3. Discovered nodes appear in the Nodes menu under their category
4. No manual registration is required beyond placing the file in the correct directory

### 9.3 Asynchronous Node Development

For nodes that perform long-running operations:

1. Set `self.is_async_node = True` in the `__init__` method
2. Use a separate thread for processing
3. Use thread-safe methods for updating properties and status:
   - `self.thread_safe_set_property(name, value)`
   - `self.thread_safe_set_status(status_text)`
4. Update `output_cache` when processing is complete
5. Set `self.processing_done = True` when finished

### 9.4 Best Practices

- **Keep nodes focused**: Each node should perform a specific, well-defined task
- **Handle errors gracefully**: Catch and report exceptions clearly
- **Provide useful status updates**: Keep users informed of processing status
- **Optimize computations**: Cache results when appropriate
- **Use thread-safe methods**: Always use thread-safe methods for UI updates
- **Document nodes clearly**: Use docstrings and clear property labels

## 10. Troubleshooting and FAQs

### 10.1 Common Issues

1. **Missing Dependencies**:
   - Ensure all required packages are installed: `pip install PySide6 NodeGraphQt requests`
   - Check console output for import errors

2. **Node Registration Problems**:
   - Verify node class has correct `__identifier__` and `__type__` attributes
   - Ensure the Python file is in the `nodes` directory
   - Check `nodes/__init__.py` exists

3. **Workflow Execution Errors**:
   - Look for error messages in node status
   - Check the console for detailed error traces
   - Verify inputs are connected correctly

4. **UI Update Issues**:
   - Ensure thread-safe methods are used for background operations
   - Check signal connections

### 10.2 Debugging Tips

1. **Enable Node Tooltips**: Hover over ports to see current values
2. **Check Node Status**: Node status shows processing state and errors
3. **Console Output**: Important debug information is printed to the console
4. **Reset Workflow**: Use "Reset All" to clear cached data

### 10.3 FAQ

**Q: How do I create a simple workflow?**
A: Add a Static Text node, connect it to a Prompt node, and configure the prompts. Then click "Run Workflow" to execute.

**Q: How do I save my workflow?**
A: Use File > Save to save your workflow as a JSON file.

**Q: Can I run multiple LLM nodes in parallel?**
A: Yes, nodes that don't have direct dependencies can run in parallel.

**Q: How do I create a custom node?**
A: Create a new Python file in the `nodes` directory that inherits from `OllamaBaseNode` and implements the required methods.

**Q: Why is my node not appearing in the menu?**
A: Ensure your node class has the correct attributes (`__identifier__`, `__type__`, `NODE_NAME`, `NODE_CATEGORY`) and is placed in the `nodes` directory.

**Q: How do I debug a node that's not working?**
A: Check the node status, look for error messages in the console, and use port tooltips to inspect the data flow.
