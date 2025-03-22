"""
CSV Table Node for Ollama Flow

This node demonstrates how to create a practical node that reads CSV data,
performs operations on it, and outputs the results.

It serves as a complete example that beginners can use as a reference.
"""

from nodes.base_node import OllamaBaseNode
import csv
import io
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFileDialog


class CSVTableNode(OllamaBaseNode):
    """
    A node that processes CSV data, allowing column selection and basic operations.
    
    This node can import CSV data from text input or files, select columns,
    filter rows, and perform basic calculations on numeric columns.
    """
    
    # === NODE METADATA ===
    __identifier__ = 'com.ollamaflow.nodes'
    __type__ = 'CSVTableNode'
    NODE_NAME = 'CSV Table'
    NODE_CATEGORY = 'Data Processing'
    
    def __init__(self):
        """Initialize the CSV Table Node with input/output ports and properties."""
        super(CSVTableNode, self).__init__()
        
        # Set node display name and color
        self.set_name('CSV Table')
        self.set_color(60, 180, 120)  # Green color
        
        # === INPUT PORTS ===
        self.add_input('CSV Text')
        
        # === OUTPUT PORTS ===
        self.add_output('Table Data')  # Full processed table
        self.add_output('Selected Column')  # Just the selected column
        self.add_output('Summary Stats')  # Statistical summary
        
        # === PROPERTIES ===
        # CSV parsing options
        self.add_checkbox('has_header', 'Has Header Row', True)
        self.add_text_input('delimiter', 'Delimiter', ',')
        
        # Column selection
        self.add_text_input('column_select', 'Column to Select', '0')
        self.add_text_input('filter_value', 'Filter Rows (regex)', '')
        
        # Operation options
        operations = ['None', 'Sum', 'Average', 'Min', 'Max', 'Count']
        self.add_combo_menu('operation', 'Operation', items=operations, default='None')
        
        # Display options
        self.add_int_slider('max_rows', 'Preview Rows', value=10, range=(1, 100))
        
        # === PREVIEW PROPERTIES ===
        self.add_text_input('input_preview', 'Input Preview', '')
        self.add_text_input('output_preview', 'Output Preview', '')
        self.add_text_input('stats_preview', 'Stats Preview', '')
        
        # === STATE VARIABLES ===
        self.csv_data = []  # Will store the parsed CSV data
        self.headers = []   # Will store column headers if present
        
        # === CUSTOM WIDGETS ===
        self.create_widgets()
    
    def create_widgets(self):
        """Create custom widgets for the node."""
        # Create main widget
        control_widget = QWidget()
        layout = QVBoxLayout(control_widget)
        
        # Create a button to load CSV from file
        self.load_button = QPushButton("Load CSV from File")
        self.load_button.clicked.connect(self.load_csv_file)
        layout.addWidget(self.load_button)
        
        # Create a refresh button
        self.refresh_button = QPushButton("Process CSV Now")
        self.refresh_button.clicked.connect(self.mark_dirty)
        layout.addWidget(self.refresh_button)
        
        # Set layout
        control_widget.setLayout(layout)
        self.add_custom_widget(control_widget, tab='CSV Controls')
    
    def load_csv_file(self):
        """Open a file dialog to load a CSV file."""
        try:
            # Show file dialog
            file_path, _ = QFileDialog.getOpenFileName(
                None, 'Open CSV File', '', 'CSV Files (*.csv);;All Files (*.*)'
            )
            
            if file_path:
                # Read the file
                with open(file_path, 'r', encoding='utf-8') as f:
                    csv_text = f.read()
                
                # Update preview
                preview = csv_text[:500] + ('...' if len(csv_text) > 500 else '')
                self.set_property('input_preview', preview)
                
                # Process the CSV data
                self.process_csv_data(csv_text)
                
                # Update status
                self.set_status(f"Loaded CSV from {file_path}")
                
                # Mark the node for processing
                self.mark_dirty()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.set_status(f"Error loading CSV: {str(e)[:20]}...")
    
    def process_csv_data(self, csv_text):
        """Parse CSV text and store the data."""
        try:
            # If input is empty, clear the data
            if not csv_text:
                self.csv_data = []
                self.headers = []
                return
            
            # Get CSV options
            has_header = self.get_property('has_header')
            delimiter = self.get_property('delimiter')
            
            # Parse the CSV data
            reader = csv.reader(io.StringIO(csv_text), delimiter=delimiter)
            rows = list(reader)
            
            if not rows:
                self.set_status("CSV contains no data")
                self.csv_data = []
                self.headers = []
                return
            
            # Handle headers
            if has_header and len(rows) > 0:
                self.headers = rows[0]
                self.csv_data = rows[1:]
            else:
                self.headers = [f"Column {i}" for i in range(len(rows[0]))]
                self.csv_data = rows
            
            # Update status
            self.set_status(f"Processed CSV: {len(self.csv_data)} rows, {len(self.headers)} columns")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.set_status(f"Error processing CSV: {str(e)[:20]}...")
            self.csv_data = []
            self.headers = []
    
    def execute(self):
        """Process the node's data and return the results."""
        # Get input CSV text
        csv_text = self.get_input_data('CSV Text')
        
        # Update input preview if we have data
        if csv_text:
            preview = csv_text[:500] + ('...' if len(csv_text) > 500 else '')
            self.set_property('input_preview', preview)
        
        # Process the CSV data
        self.process_csv_data(csv_text)
        
        # If we have no data, return empty results
        if not self.csv_data:
            self.set_status("No CSV data to process")
            self.set_property('output_preview', "")
            self.set_property('stats_preview', "")
            return {
                'Table Data': "",
                'Selected Column': "",
                'Summary Stats': ""
            }
        
        # Get the column to select
        col_select = self.get_property('column_select')
        try:
            # Try to parse as an integer index
            col_idx = int(col_select)
            if col_idx < 0 or col_idx >= len(self.headers):
                self.set_status(f"Column index {col_idx} out of range")
                col_idx = 0
        except ValueError:
            # If not an integer, try to find by column name
            if col_select in self.headers:
                col_idx = self.headers.index(col_select)
            else:
                self.set_status(f"Column '{col_select}' not found, using first column")
                col_idx = 0
        
        # Extract the selected column values
        selected_column = []
        for row in self.csv_data:
            if col_idx < len(row):
                selected_column.append(row[col_idx])
            else:
                selected_column.append("")
        
        # Apply filter if specified
        filter_value = self.get_property('filter_value')
        filtered_data = self.csv_data
        if filter_value:
            import re
            try:
                pattern = re.compile(filter_value)
                filtered_data = []
                for row in self.csv_data:
                    for value in row:
                        if pattern.search(value):
                            filtered_data.append(row)
                            break
                
                self.set_status(f"Filter applied: {len(filtered_data)} of {len(self.csv_data)} rows match")
            except Exception as e:
                self.set_status(f"Filter error: {str(e)[:20]}...")
                filtered_data = self.csv_data
        
        # Perform operation on selected column if specified
        operation = self.get_property('operation')
        stats_result = ""
        
        if operation != 'None':
            try:
                # Try to convert column values to numbers
                numeric_values = []
                for value in selected_column:
                    try:
                        numeric_values.append(float(value))
                    except (ValueError, TypeError):
                        pass
                
                if numeric_values:
                    if operation == 'Sum':
                        result = sum(numeric_values)
                        stats_result = f"Sum of {self.headers[col_idx]}: {result}"
                    elif operation == 'Average':
                        result = sum(numeric_values) / len(numeric_values)
                        stats_result = f"Average of {self.headers[col_idx]}: {result}"
                    elif operation == 'Min':
                        result = min(numeric_values)
                        stats_result = f"Minimum of {self.headers[col_idx]}: {result}"
                    elif operation == 'Max':
                        result = max(numeric_values)
                        stats_result = f"Maximum of {self.headers[col_idx]}: {result}"
                    elif operation == 'Count':
                        result = len(numeric_values)
                        stats_result = f"Count of numeric values in {self.headers[col_idx]}: {result}"
                else:
                    stats_result = f"No numeric values found in column '{self.headers[col_idx]}'"
            except Exception as e:
                stats_result = f"Error performing operation: {str(e)}"
        
        # Create output previews
        max_rows = self.get_property('max_rows')
        
        # Create table preview
        table_preview = []
        if self.headers:
            table_preview.append(",".join(self.headers))
        
        for i, row in enumerate(filtered_data):
            if i >= max_rows:
                table_preview.append("...")
                break
            table_preview.append(",".join(row))
        
        table_output = "\n".join(table_preview)
        
        # Create column preview
        column_preview = []
        column_preview.append(self.headers[col_idx])
        
        for i, value in enumerate(selected_column):
            if i >= max_rows:
                column_preview.append("...")
                break
            column_preview.append(value)
        
        column_output = "\n".join(column_preview)
        
        # Update previews
        self.set_property('output_preview', table_output)
        self.set_property('stats_preview', stats_result)
        
        # Create final outputs as strings
        full_table_output = "\n".join([",".join(self.headers)] + [",".join(row) for row in filtered_data])
        full_column_output = "\n".join([self.headers[col_idx]] + selected_column)
        
        # Return the results
        return {
            'Table Data': full_table_output,
            'Selected Column': full_column_output,
            'Summary Stats': stats_result
        }

# === EXAMPLE USAGE ===
"""
This CSV Table Node can be used in various ways:

1. Connect a Static Text node with CSV content to the 'CSV Text' input
2. Use the "Load CSV from File" button to load data from a file
3. Select a specific column by index (0, 1, 2...) or name
4. Filter rows using regular expressions
5. Perform operations like Sum or Average on numeric columns

Output can be connected to:
- Text displays
- File nodes to save processed data
- Other processing nodes for further manipulation
"""
