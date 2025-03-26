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