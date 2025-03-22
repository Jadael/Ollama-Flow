# Ollama Flow

A node-based workflow editor for Ollama, allowing you to create complex LLM processing pipelines visually.

## Features

- Visual node-based editor using NodeGraphQt
- Connect LLM prompts with text processing nodes
- Supports async processing for LLM generation
- Save and load workflows
- Property inspector for node configuration

## Installation

### Prerequisites

- Python 3.8+
- Ollama installed and running (at http://localhost:11434)

### Install Steps

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/ollamaflow.git
   cd ollamaflow
   ```

2. Install dependencies:
   ```
   pip install -e .
   ```

## Usage

Run Ollama Flow:

```
python app.py
```

### Available Nodes

- **Static Text**: Provides static text as input to other nodes
- **LLM Prompt**: Sends prompts to Ollama models and gets responses
- **Regex**: Process text using regular expressions
- **Join**: Combines multiple text inputs with a configurable delimiter

### Creating Workflows

1. Add nodes by right-clicking on the canvas
2. Connect node ports by dragging from an output port to an input port
3. Configure node properties in the Properties panel
4. Run the workflow using the "Run Workflow" button or F5 key

### Saving and Loading

You can save your workflows to JSON files and load them later using the File menu.

## Development

### Adding New Nodes

Create a new node by subclassing `OllamaBaseNode` in the `nodes` directory:

```python
from nodes.base_node import OllamaBaseNode

class MyCustomNode(OllamaBaseNode):
    __identifier__ = 'com.ollamaflow.nodes'
    NODE_NAME = 'MyCustomNode'
    
    def __init__(self):
        super(MyCustomNode, self).__init__()
        self.set_name('My Custom Node')
        
        # Add ports
        self.add_input('Input')
        self.add_output('Output')
        
        # Add properties
        self.add_text_input('my_property', 'My Property', 'Default Value')
        
        # Set node color
        self.set_color(100, 100, 100)
    
    def execute(self):
        # Process input data
        input_data = self.get_input_data('Input')
        
        # Do something with the data
        result = process_data(input_data)
        
        # Return output
        return {'Output': result}
```

Register your node in `app.py`:

```python
# Add to register_nodes method
from nodes.my_custom_node import MyCustomNode
self.graph.register_node(MyCustomNode)
```

## License

MIT
