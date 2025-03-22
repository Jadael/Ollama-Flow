"""
Port and connection tooltip functionality for Ollama Flow.
Adds tooltips to ports and connections showing node details and data values.
"""
from PySide6.QtCore import Qt, QEvent, QPoint, QRect, QTimer, QObject
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import QToolTip, QGraphicsItem, QApplication

class PortTooltipManager(QObject):
    """
    Manages tooltips for ports and connection lines in the node graph.
    Shows information about connected nodes and the current value.
    """
    
    def __init__(self, viewer):
        """
        Initialize the tooltip manager with a reference to the node graph viewer.
        
        Args:
            viewer: The NodeGraphQt viewer instance
        """
        super(PortTooltipManager, self).__init__()
        self.viewer = viewer
        self.hover_item = None
        self.hover_timer = QTimer()
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.show_tooltip)
        self.hover_pos = QPoint()
        
        # Disable native tooltips in the viewer if possible
        if hasattr(viewer, 'setToolTip'):
            viewer.setToolTip("")
        
        # Disable QGraphicsView tooltips
        if hasattr(viewer, 'setToolTipDuration'):
            viewer.setToolTipDuration(-1)  # Disable automatic tooltips
            
        # Install event filter on the viewer
        if hasattr(viewer, 'viewport') and viewer.viewport():
            viewer.viewport().installEventFilter(self)
            print("PortTooltipManager: Installed event filter on viewer viewport")
        else:
            viewer.installEventFilter(self)
            print("PortTooltipManager: Installed event filter on viewer")
    
    def eventFilter(self, obj, event):
        """Filter events to detect hover over ports and connections"""
        if event.type() == QEvent.MouseMove:
            # Find item under mouse cursor
            items = self.viewer.items(event.pos())
            port_item = None
            conn_item = None
            
            # Try to identify port or connection items
            for item in items:
                # Check if it's a port
                if hasattr(item, 'port_type') or ('port' in str(type(item)).lower()):
                    port_item = item
                    break
                
                # Check if it's a connection
                if (hasattr(item, 'source_port') and hasattr(item, 'target_port')) or \
                   ('connection' in str(type(item)).lower() and hasattr(item, 'source') and hasattr(item, 'target')):
                    conn_item = item
                    break
            
            # If we found a port or connection, start the hover timer
            if port_item or conn_item:
                self.hover_item = port_item or conn_item
                self.hover_pos = event.globalPos()
                self.hover_timer.start(300)  # 300ms delay before showing tooltip
            else:
                # Hide tooltip if no port or connection is under the cursor
                self.hover_item = None
                self.hover_timer.stop()
                QToolTip.hideText()
        
        # Hide tooltip when mouse leaves
        elif event.type() == QEvent.Leave:
            self.hover_item = None
            self.hover_timer.stop()
            QToolTip.hideText()
        
        # Block any native tooltips
        if event.type() == QEvent.ToolTip:
            return True  # Block the event
            
        return False  # Continue processing other events
    
    def show_tooltip(self):
        """Show tooltip with connection information at the current hover position"""
        if not self.hover_item:
            return
        
        tooltip_text = self.get_tooltip_text(self.hover_item)
        if tooltip_text:
            QToolTip.showText(self.hover_pos, tooltip_text)
    
    def get_tooltip_text(self, item):
        """
        Generate tooltip text for a port or connection item.
        
        Args:
            item: The port or connection item
            
        Returns:
            Formatted tooltip text with connection information
        """
        tooltip_lines = []
        
        # Handle port items
        if hasattr(item, 'port_type') or ('port' in str(type(item)).lower()):
            # Extract port and node info
            port = self._extract_port_from_item(item)
            if not port:
                return ""
                
            port_name = self._get_port_name(port)
            node = self._get_port_node(port)
            node_name = self._get_node_name(node)
            
            # Get connected ports
            connected_ports = self._get_port_connections(port)
            if not connected_ports:
                # If not connected, just show the port info
                tooltip_lines.append(f"<b>Port:</b> {port_name}")
                tooltip_lines.append(f"<b>Node:</b> {node_name}")
                tooltip_lines.append("<i>Not connected</i>")
                return "<br>".join(tooltip_lines)
            
            # For each connection, show source -> target and value
            for conn_port in connected_ports:
                conn_node = self._get_port_node(conn_port)
                if not conn_node:
                    continue
                    
                # Determine source and target (regardless of which side we're hovering)
                is_output = self._is_output_port(port)
                is_connected_output = self._is_output_port(conn_port)
                
                # Always show source -> target format
                if is_output:
                    source_node, source_port = node, port
                    target_node, target_port = conn_node, conn_port
                else:
                    source_node, source_port = conn_node, conn_port
                    target_node, target_port = node, port
                
                source_name = f"{self._get_node_name(source_node)} : {self._get_port_name(source_port)}"
                target_name = f"{self._get_node_name(target_node)} : {self._get_port_name(target_port)}"
                
                tooltip_lines.append("<b>Connection:</b>")
                tooltip_lines.append(f"<b>From:</b> {source_name}")
                tooltip_lines.append(f"<b>To:</b> {target_name}")
                
                # Get the connection value from the output port (source)
                value = self._get_raw_connection_value(source_node, source_port)
                if value is not None:
                    formatted_value = self._format_value(value)
                    if formatted_value:
                        tooltip_lines.append("<b>Value:</b>")
                        tooltip_lines.append(formatted_value)
                
                break  # Only show the first connection for simplicity
        
        # Handle connection items
        elif hasattr(item, 'source_port') and hasattr(item, 'target_port'):
            # Direct access to source and target ports
            source_port = item.source_port
            target_port = item.target_port
            
            source_node = self._get_port_node(source_port)
            target_node = self._get_port_node(target_port)
            
            if not source_node or not target_node:
                return ""
                
            source_name = f"{self._get_node_name(source_node)} : {self._get_port_name(source_port)}"
            target_name = f"{self._get_node_name(target_node)} : {self._get_port_name(target_port)}"
            
            tooltip_lines.append("<b>Connection:</b>")
            tooltip_lines.append(f"<b>From:</b> {source_name}")
            tooltip_lines.append(f"<b>To:</b> {target_name}")
            
            # Get the value directly from the source node's output cache
            value = self._get_raw_connection_value(source_node, source_port)
            if value is not None:
                formatted_value = self._format_value(value)
                if formatted_value:
                    tooltip_lines.append("<b>Value:</b>")
                    tooltip_lines.append(formatted_value)
        
        # Some NodeGraphQt implementations use different attribute names
        elif hasattr(item, 'source') and hasattr(item, 'target'):
            source = item.source
            target = item.target
            
            source_node = None
            source_port_name = "Unknown"
            if hasattr(source, 'node') and callable(source.node):
                source_node = source.node()
                if hasattr(source, 'name') and callable(source.name):
                    source_port_name = source.name()
            
            target_node = None
            target_port_name = "Unknown"
            if hasattr(target, 'node') and callable(target.node):
                target_node = target.node()
                if hasattr(target, 'name') and callable(target.name):
                    target_port_name = target.name()
            
            if source_node and target_node:
                source_name = f"{self._get_node_name(source_node)} : {source_port_name}"
                target_name = f"{self._get_node_name(target_node)} : {target_port_name}"
                
                tooltip_lines.append("<b>Connection:</b>")
                tooltip_lines.append(f"<b>From:</b> {source_name}")
                tooltip_lines.append(f"<b>To:</b> {target_name}")
                
                # Get the value directly from the source node's output cache
                value = self._get_raw_connection_value(source_node, source)
                if value is not None:
                    formatted_value = self._format_value(value)
                    if formatted_value:
                        tooltip_lines.append("<b>Value:</b>")
                        tooltip_lines.append(formatted_value)
        
        return "<br>".join(tooltip_lines) if tooltip_lines else ""
    
    def _extract_port_from_item(self, item):
        """Extract the port object from a port item"""
        if hasattr(item, 'port'):
            return item.port
        elif hasattr(item, '_port'):
            return item._port
        elif hasattr(item, 'port_type'):
            return item  # The item itself is the port
        
        return None
    
    def _is_output_port(self, port):
        """Determine if a port is an output port"""
        if hasattr(port, 'port_type'):
            return port.port_type == 'out'
        elif hasattr(port, 'isOutput') and callable(port.isOutput):
            return port.isOutput()
        elif hasattr(port, 'is_output') and callable(port.is_output):
            return port.is_output()
        elif hasattr(port, 'is_output'):
            return port.is_output
        
        # Try to determine from connections
        if hasattr(port, 'connected_ports') and callable(port.connected_ports):
            # Often output ports connect TO other ports, inputs connect FROM others
            return len(port.connected_ports()) > 0
        
        return False  # Default assumption: it's an input port
    
    def _get_port_node(self, port):
        """Extract the node from a port object, handling different implementations"""
        if not port:
            return None
            
        if hasattr(port, 'node') and callable(port.node):
            return port.node()
        elif hasattr(port, 'node') and not callable(port.node):
            return port.node
        elif hasattr(port, '_node'):
            return port._node
        elif hasattr(port, 'parent') and callable(port.parent):
            return port.parent()
        elif hasattr(port, 'parentItem') and callable(port.parentItem):
            return port.parentItem()
        
        return None
    
    def _get_port_name(self, port):
        """Extract the name from a port object, handling different implementations"""
        if not port:
            return "Unknown"
            
        if hasattr(port, 'name') and callable(port.name):
            return port.name()
        elif hasattr(port, 'name') and not callable(port.name):
            return port.name
        elif hasattr(port, '_name'):
            return port._name
        elif hasattr(port, 'displayName') and callable(port.displayName):
            return port.displayName()
        elif hasattr(port, 'displayName'):
            return port.displayName
        
        return "Unknown"
    
    def _get_node_name(self, node):
        """Extract the name from a node object, handling different implementations"""
        if not node:
            return "Unknown"
            
        if hasattr(node, 'name') and callable(node.name):
            return node.name()
        elif hasattr(node, 'name') and not callable(node.name):
            return node.name
        elif hasattr(node, '_name'):
            return node._name
        elif hasattr(node, 'get_name') and callable(node.get_name):
            return node.get_name()
        elif hasattr(node, 'getName') and callable(node.getName):
            return node.getName()
        
        return "Unknown"
    
    def _get_port_connections(self, port):
        """Get connected ports for a given port, handling different implementations"""
        if not port:
            return []
            
        if hasattr(port, 'connected_ports') and callable(port.connected_ports):
            return port.connected_ports()
        elif hasattr(port, 'connections'):
            if callable(port.connections):
                connections = port.connections()
            else:
                connections = port.connections
                
            # If connections is a list of connection objects, extract the connected ports
            if connections and hasattr(connections[0], 'source_port') and hasattr(connections[0], 'target_port'):
                if port == connections[0].source_port:
                    return [conn.target_port for conn in connections]
                else:
                    return [conn.source_port for conn in connections]
                    
            return connections
        elif hasattr(port, 'connectedPorts') and callable(port.connectedPorts):
            return port.connectedPorts()
        elif hasattr(port, '_connected_ports'):
            return port._connected_ports
        
        return []
    
    def _get_raw_connection_value(self, node, port):
        """
        Get the raw value from a node's output port, bypassing any summaries
        
        Args:
            node: The node object
            port: The port object or port name
            
        Returns:
            The raw value or None if not found
        """
        if not node:
            return None
            
        # Get port name
        port_name = port
        if hasattr(port, 'name') and callable(port.name):
            port_name = port.name()
        elif hasattr(port, 'name') and not callable(port.name):
            port_name = port.name
        elif hasattr(port, '_name'):
            port_name = port._name
        
        # Get the value using multiple approaches
        
        # 1. Direct from output_cache - most common approach
        if hasattr(node, 'output_cache') and isinstance(node.output_cache, dict):
            value = node.output_cache.get(port_name)
            if value is not None:
                return value
        
        # 2. From node.execute result
        if hasattr(node, 'execute') and callable(node.execute):
            try:
                result = node.execute()
                if isinstance(result, dict) and port_name in result:
                    return result[port_name]
            except:
                pass
        
        # 3. From a specific output getter if available
        if hasattr(node, 'get_output') and callable(node.get_output):
            try:
                return node.get_output(port_name)
            except:
                pass
        
        # 4. From the node's properties - for OllamaBaseNode
        if hasattr(node, 'get_property') and callable(node.get_property):
            # Common naming patterns for properties that become outputs
            property_names = [port_name, port_name.lower(), 'text', 'output', 'result', 'value']
            for prop in property_names:
                try:
                    value = node.get_property(prop)
                    if value is not None:
                        return value
                except:
                    continue
        
        return None
    
    def _format_value(self, value):
        """Format a value for display in a tooltip (showing raw value)"""
        if value is None:
            return "None"
            
        if isinstance(value, str):
            # Handle string representation but avoid truncation for debug purposes
            # Escape HTML entities to display tags literally
            value_str = value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            return f"<pre style='margin:0;white-space:pre-wrap;'>{value_str}</pre>"
            
        if isinstance(value, (int, float, bool)):
            return str(value)
            
        if hasattr(value, '__iter__'):
            # For lists, tuples, dicts - use raw display for debug purposes
            try:
                # Use repr for raw representation
                return f"<pre style='margin:0;white-space:pre-wrap;'>{repr(value)}</pre>"
            except:
                return str(value)
        
        # For other types, show their raw representation
        return repr(value)

def install_port_tooltips(graph):
    """
    Install tooltip functionality on a NodeGraph instance.
    
    Args:
        graph: The NodeGraph instance
    
    Returns:
        PortTooltipManager instance
    """
    # Get the viewer from the graph
    viewer = None
    if hasattr(graph, 'viewer') and callable(graph.viewer):
        viewer = graph.viewer()
    elif hasattr(graph, '_viewer'):
        viewer = graph._viewer
        
    if not viewer:
        print("Warning: Could not find viewer in graph")
        return None
    
    # Remove any previous tooltip manager to avoid duplicates
    if hasattr(graph, '_tooltip_manager'):
        if hasattr(viewer, 'viewport') and viewer.viewport():
            viewer.viewport().removeEventFilter(graph._tooltip_manager)
        else:
            viewer.removeEventFilter(graph._tooltip_manager)
        
    # Create tooltip manager
    tooltip_manager = PortTooltipManager(viewer)
    
    # Store reference to prevent garbage collection
    graph._tooltip_manager = tooltip_manager
    
    print("Port tooltips installed")
    return tooltip_manager
