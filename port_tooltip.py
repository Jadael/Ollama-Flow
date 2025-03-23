"""
Port and connection tooltip functionality for Ollama Flow.
Adds tooltips to ports and connections showing node details and data values.
"""
from PySide6.QtCore import Qt, QEvent, QPoint, QRect, QTimer, QObject
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import QToolTip, QGraphicsItem, QApplication
import traceback

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
        self.debug_mode = False  # Set to True for verbose value retrieval info
        
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
                # Check if it's a port - try different detection methods
                if self._is_port_item(item):
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
        
        # Handle port items - check more comprehensively
        if self._is_port_item(item):
            # Extract port and node info
            port = self._extract_port_from_item(item)
            if not port:
                return ""
                
            port_name = self._get_port_name(port)
            node = self._get_port_node(port)
            node_name = self._get_node_name(node)
            
            tooltip_lines.append(f"<b>Port:</b> {port_name}")
            tooltip_lines.append(f"<b>Node:</b> {node_name}")
            
            # Try multiple connection detection methods
            connected_ports = self._get_port_connections(port, node)
            port_is_connected = self._port_has_connections(port, node)
            
            # If it's an output port, show its current value directly
            if self._is_output_port(port, node):
                # Get the value from this port
                value = self._get_raw_connection_value(node, port)
                if value is not None:
                    formatted_value = self._format_value(value)
                    if formatted_value:
                        tooltip_lines.append("<b>Current Value:</b>")
                        tooltip_lines.append(formatted_value)
            
            # If not connected, say so and stop here
            if not connected_ports and not port_is_connected:
                tooltip_lines.append("<i>Not connected</i>")
                return "<br>".join(tooltip_lines)
            
            # If we have actual port objects
            if connected_ports:
                for conn_port in connected_ports:
                    conn_node = self._get_port_node(conn_port)
                    if not conn_node:
                        continue
                        
                    # Determine source and target (regardless of which side we're hovering)
                    is_output = self._is_output_port(port, node)
                    
                    # Always show source -> target format
                    if is_output:
                        source_node, source_port = node, port
                        target_node, target_port = conn_node, conn_port
                    else:
                        source_node, source_port = conn_node, conn_port
                        target_node, target_port = node, port
                    
                    source_name = f"{self._get_node_name(source_node)} : {self._get_port_name(source_port)}"
                    target_name = f"{self._get_node_name(target_node)} : {self._get_port_name(target_port)}"
                    
                    tooltip_lines.append("<b>Connected:</b>")
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
            # If the port is connected but we couldn't get the connected port objects
            elif port_is_connected:
                tooltip_lines.append("<b>Connected</b> (connection details not available)")
                
                # Even if we don't have port details, try to get the value
                if not self._is_output_port(port, node):
                    # For input ports, try to get the value from the node's property mappings
                    value = self._get_input_port_value(node, port)
                    if value is not None:
                        formatted_value = self._format_value(value)
                        if formatted_value:
                            tooltip_lines.append("<b>Value:</b>")
                            tooltip_lines.append(formatted_value)
        
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
    
    def _is_port_item(self, item):
        """More comprehensive check to detect if an item is a port"""
        # Common signatures for port items in different NodeGraphQt versions
        if hasattr(item, 'port_type'):
            return True
        if 'port' in str(type(item)).lower():
            return True
        if hasattr(item, 'nodzInst') and hasattr(item, 'portCircle'):
            return True
        if hasattr(item, 'port'):
            return True
        if hasattr(item, '_port'):
            return True
        # Additional checks for more specific NodeGraphQt implementations
        if hasattr(item, 'itemChange') and ('port' in str(item.__class__.__name__).lower()):
            return True
        return False
    
    def _extract_port_from_item(self, item):
        """Extract the port object from a port item"""
        if hasattr(item, 'port'):
            return item.port
        elif hasattr(item, '_port'):
            return item._port
        elif hasattr(item, 'port_type') or 'port' in str(type(item)).lower():
            return item  # The item itself is the port
        
        return None
    
    def _port_has_connections(self, port, node):
        """Check if a port has any connections via multiple methods"""
        # Method 1: Check connected_ports attribute/method
        if hasattr(port, 'connected_ports'):
            if callable(port.connected_ports):
                connections = port.connected_ports()
                if connections:
                    return True
            elif port.connected_ports:
                return True
        
        # Method 2: Check connections attribute
        if hasattr(port, 'connections'):
            if callable(port.connections):
                connections = port.connections()
            else:
                connections = port.connections
            if connections:
                return True
        
        # Method 3: Check node for connections
        if node:
            # Check if there's a scene with edges
            if hasattr(node, 'scene') and callable(node.scene):
                scene = node.scene()
                if scene and hasattr(scene, 'edges'):
                    for edge in scene.edges:
                        if hasattr(edge, 'source') and hasattr(edge, 'target'):
                            if (hasattr(edge.source, 'node') and edge.source.node() == node) or \
                               (hasattr(edge.target, 'node') and edge.target.node() == node):
                                return True
            
            # Check for visible connections in the node view
            if hasattr(node, 'view') and callable(node.view):
                view = node.view()
                if view:
                    # Look for connection lines
                    for child in view.childItems():
                        if 'connection' in str(type(child)).lower() or \
                           'edge' in str(type(child)).lower():
                            return True
        
        # Method 4: Check for _connected_ports attribute
        if hasattr(port, '_connected_ports') and port._connected_ports:
            return True
        
        # Method 5: Check via port's parent node for explicit connection tracking
        port_name = self._get_port_name(port)
        if node and hasattr(node, '_input_properties') and hasattr(node, '_property_inputs'):
            # Check if this is an OllamaBaseNode with mapped port->property connections
            if port_name in node._input_properties:
                return True
        
        # Method 6: Check for edges in the scene via port name
        if node and hasattr(node, 'graph') and callable(node.graph):
            graph = node.graph()
            if graph and hasattr(graph, 'edges'):
                port_node_name = self._get_node_name(node)
                for edge in graph.edges:
                    # Check if this edge connects to our port
                    if (hasattr(edge, 'source_name') and hasattr(edge, 'source_node') and
                        edge.source_name == port_name and edge.source_node == port_node_name):
                        return True
                    if (hasattr(edge, 'target_name') and hasattr(edge, 'target_node') and
                        edge.target_name == port_name and edge.target_node == port_node_name):
                        return True
        
        return False
    
    def _is_output_port(self, port, node=None):
        """Determine if a port is an output port using various methods"""
        # Method 1: Check port_type attribute
        if hasattr(port, 'port_type'):
            return port.port_type == 'out'
        
        # Method 2: Check explicit output flag
        if hasattr(port, 'isOutput') and callable(port.isOutput):
            return port.isOutput()
        if hasattr(port, 'is_output') and callable(port.is_output):
            return port.is_output()
        if hasattr(port, 'is_output'):
            return port.is_output
        
        # Method 3: Check if port is in node's outputs collection
        if node:
            port_name = self._get_port_name(port)
            # Check if this is an input or output port based on the node's collections
            if hasattr(node, 'output_ports') and callable(node.output_ports):
                outputs = node.output_ports()
                for output in outputs:
                    if self._get_port_name(output) == port_name:
                        return True
            
            # Check ports by side (common in graphical node systems)
            if hasattr(port, 'port_side'):
                return port.port_side in ['right', 'output', 'out']
        
        # Method 4: Check position in node (outputs are usually on the right)
        if hasattr(port, 'pos') and callable(port.pos):
            pos = port.pos()
            node_rect = None
            if node and hasattr(node, 'boundingRect') and callable(node.boundingRect):
                node_rect = node.boundingRect()
                if pos.x() > node_rect.width() / 2:
                    return True
        
        # Method 5: Check the port name for common patterns
        port_name = self._get_port_name(port)
        output_indicators = ['output', 'out', 'result', 'return', 'response', 'text']
        for indicator in output_indicators:
            if indicator.lower() == port_name.lower():
                return True
        
        # Default: Assume false (input port)
        return False
    
    def _get_port_connections(self, port, node=None):
        """Get connected ports for a given port, trying multiple methods"""
        if not port:
            return []
        
        connected_ports = []
        
        # Method 1: Use connected_ports method/attribute
        if hasattr(port, 'connected_ports'):
            if callable(port.connected_ports):
                connected_ports = port.connected_ports()
            else:
                connected_ports = port.connected_ports
            
            if connected_ports:
                return connected_ports
        
        # Method 2: Check connections attribute
        if hasattr(port, 'connections'):
            connections = None
            if callable(port.connections):
                connections = port.connections()
            else:
                connections = port.connections
                
            # Handle different connection object formats
            if connections:
                if hasattr(connections[0], 'source_port') and hasattr(connections[0], 'target_port'):
                    # Connection objects have source and target ports
                    if port == connections[0].source_port:
                        return [conn.target_port for conn in connections]
                    else:
                        return [conn.source_port for conn in connections]
                else:
                    # Connections are already port objects
                    return connections
        
        # Method 3: Check _connected_ports attribute
        if hasattr(port, '_connected_ports'):
            if port._connected_ports:
                return port._connected_ports
        
        # Method 4: Check connectedPorts method
        if hasattr(port, 'connectedPorts') and callable(port.connectedPorts):
            return port.connectedPorts()
        
        # Method 5: Try to get connections from the scene/graph
        if node and hasattr(node, 'graph') and callable(node.graph):
            graph = node.graph()
            if graph and hasattr(graph, 'edges'):
                # Identify our port
                port_name = self._get_port_name(port)
                node_name = self._get_node_name(node)
                is_output = self._is_output_port(port, node)
                
                # Get all connected ports
                for edge in graph.edges:
                    connected_port = None
                    connected_node_name = None
                    
                    # Check based on direction
                    if is_output and hasattr(edge, 'source_name') and hasattr(edge, 'target_node'):
                        if edge.source_name == port_name and edge.source_node == node_name:
                            connected_node_name = edge.target_node
                            connected_port_name = edge.target_name
                    elif not is_output and hasattr(edge, 'target_name') and hasattr(edge, 'source_node'):
                        if edge.target_name == port_name and edge.target_node == node_name:
                            connected_node_name = edge.source_node
                            connected_port_name = edge.source_name
                    
                    # If we found a connected node, add to our list
                    if connected_node_name:
                        # Try to find the actual port object
                        connected_port = {"name": connected_port_name, "node_name": connected_node_name}
                        connected_ports.append(connected_port)
        
        return connected_ports
    
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
        
        # If port is a dictionary with node_name (from our custom approach)
        if isinstance(port, dict) and 'node_name' in port:
            # We don't have the actual node object, but we have the name
            return {"name": port["node_name"]}
        
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
        
        # If port is a dictionary with name (from our custom approach)
        if isinstance(port, dict) and 'name' in port:
            return port["name"]
        
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
        
        # If node is a dictionary with name (from our custom approach)
        if isinstance(node, dict) and 'name' in node:
            return node["name"]
        
        return "Unknown"
    
    def _get_input_port_value(self, node, port):
        """Get the value coming into an input port through property mapping"""
        if not node or not port:
            return None
            
        try:
            # Get the port name
            port_name = self._get_port_name(port)
            
            # Check if we have property mappings (for OllamaBaseNode)
            if hasattr(node, '_input_properties') and port_name in node._input_properties:
                prop_name = node._input_properties[port_name]
                
                # Use the node's get_property_value method which checks inputs first
                if hasattr(node, 'get_property_value') and callable(node.get_property_value):
                    return node.get_property_value(prop_name)
                
                # Fallback to regular property getter
                if hasattr(node, 'get_property') and callable(node.get_property):
                    return node.get_property(prop_name)
            
            # Try to get the value via the node's direct input tracking
            if hasattr(node, 'get_input_data') and callable(node.get_input_data):
                return node.get_input_data(port_name)
        except Exception as e:
            if self.debug_mode:
                print(f"Error getting input port value: {e}")
                traceback.print_exc()
        
        return None
    
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
            
        debug_info = [] if self.debug_mode else None
        
        # Get port name
        port_name = port
        if hasattr(port, 'name') and callable(port.name):
            port_name = port.name()
        elif hasattr(port, 'name') and not callable(port.name):
            port_name = port.name
        elif hasattr(port, '_name'):
            port_name = port._name
        elif isinstance(port, dict) and 'name' in port:
            port_name = port['name']
        
        if self.debug_mode:
            debug_info.append(f"Looking for value of port: {port_name}")
            debug_info.append(f"Node: {self._get_node_name(node)}")
        
        # Get the value using multiple approaches
        
        # 1. Direct from output_cache - most common approach for OllamaFlow
        if hasattr(node, 'output_cache') and isinstance(node.output_cache, dict):
            if self.debug_mode:
                debug_info.append(f"Checking output_cache, keys: {list(node.output_cache.keys())}")
                
            value = node.output_cache.get(port_name)
            if value is not None:
                if self.debug_mode:
                    debug_info.append(f"Found value in output_cache: {type(value)}")
                return value
        
        # 2. From node.execute result
        if hasattr(node, 'execute') and callable(node.execute):
            try:
                if self.debug_mode:
                    debug_info.append("Trying node.execute()")
                    
                result = node.execute()
                if isinstance(result, dict) and port_name in result:
                    if self.debug_mode:
                        debug_info.append(f"Found value in execute result: {type(result[port_name])}")
                    return result[port_name]
            except Exception as e:
                if self.debug_mode:
                    debug_info.append(f"execute() error: {str(e)}")
        
        # 3. Check for a value in a property with the same name as the port
        if hasattr(node, 'get_property') and callable(node.get_property):
            # Try to find a property matching the port name or variations
            property_candidates = [
                port_name,
                port_name.lower(),
                'text' if port_name.lower() == 'text' else None,
                'value' if port_name.lower() in ['result', 'output', 'return'] else None
            ]
            
            # Filter out None values
            property_candidates = [p for p in property_candidates if p is not None]
            
            if self.debug_mode:
                debug_info.append(f"Checking properties: {property_candidates}")
                
            for prop_name in property_candidates:
                try:
                    value = node.get_property(prop_name)
                    if value is not None:
                        if self.debug_mode:
                            debug_info.append(f"Found value in property {prop_name}: {type(value)}")
                        return value
                except Exception as e:
                    if self.debug_mode:
                        debug_info.append(f"get_property({prop_name}) error: {str(e)}")
        
        # 4. From a specific output getter if available
        if hasattr(node, 'get_output') and callable(node.get_output):
            try:
                if self.debug_mode:
                    debug_info.append("Trying node.get_output()")
                    
                value = node.get_output(port_name)
                if value is not None:
                    if self.debug_mode:
                        debug_info.append(f"Found value in get_output: {type(value)}")
                    return value
            except Exception as e:
                if self.debug_mode:
                    debug_info.append(f"get_output() error: {str(e)}")
        
        # 5. For OllamaBaseNode, check if this port maps to a property value
        if hasattr(node, '_property_inputs') and isinstance(node._property_inputs, dict):
            # This maps input port names to property names
            # But for outputs, the property name often directly matches the output name
            try:
                # Try common property names that might match this output
                common_props = ['text', 'result', 'output', 'value', port_name]
                
                if self.debug_mode:
                    debug_info.append(f"Checking OllamaBaseNode properties: {common_props}")
                    
                for prop in common_props:
                    if hasattr(node, 'get_property_value') and callable(node.get_property_value):
                        value = node.get_property_value(prop)
                        if value is not None:
                            if self.debug_mode:
                                debug_info.append(f"Found value in property {prop}: {type(value)}")
                            return value
            except Exception as e:
                if self.debug_mode:
                    debug_info.append(f"property lookup error: {str(e)}")
        
        # Final debug info
        if self.debug_mode:
            debug_info.append("No value found")
            print("\n".join(debug_info))
            
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
