import uuid
import math

class NodeSocket:
    """Represents an input or output connection point on a node"""
    
    # Socket type definitions
    DATA_TYPES = {
        "any": {"color": "#AAA", "compatible_with": ["any"]},
        "string": {"color": "#4CAF50", "compatible_with": ["string", "any"]},
        "number": {"color": "#2196F3", "compatible_with": ["number", "any"]},
        "boolean": {"color": "#FFC107", "compatible_with": ["boolean", "any"]},
        "object": {"color": "#9C27B0", "compatible_with": ["object", "any"]},
        "array": {"color": "#FF5722", "compatible_with": ["array", "any"]},
    }
    
    def __init__(self, node, name="Data", data_type="any", is_input=True, socket_id=None):
        self.node = node
        self.is_input = is_input
        self.name = name
        self.data_type = data_type
        self.id = socket_id or str(uuid.uuid4())
        self.connected_to = None  # Will store another socket if connected
        
        # Drawing properties
        self.radius = 8
        self.position = (0, 0)  # Will be calculated when drawing
        self.hover = False
    
    @property
    def color(self):
        """Get the color for this socket based on its data type"""
        socket_type = self.DATA_TYPES.get(self.data_type, self.DATA_TYPES["any"])
        return socket_type["color"]
    
    def is_connected(self):
        """Check if this socket is connected to another socket"""
        return self.connected_to is not None
    
    def can_connect_to(self, other_socket):
        """Check if this socket can connect to another socket"""
        # Must be different types (input to output or output to input)
        if self.is_input == other_socket.is_input:
            return False
            
        # Check data type compatibility
        my_type = self.DATA_TYPES.get(self.data_type, self.DATA_TYPES["any"])
        other_type = self.DATA_TYPES.get(other_socket.data_type, self.DATA_TYPES["any"])
        
        # Input socket accepts output socket's type
        if self.is_input:
            return other_socket.data_type in my_type["compatible_with"]
        else:
            return self.data_type in other_type["compatible_with"]
    
    def disconnect(self):
        """Disconnect this socket from any connection"""
        if self.is_connected():
            # Keep a reference to the connected socket
            connected_socket = self.connected_to
            
            # Update both sockets
            connected_socket.connected_to = None
            self.connected_to = None
            
            # Mark nodes as dirty if needed
            if self.is_input:
                self.node.mark_dirty()
            elif connected_socket.is_input:
                connected_socket.node.mark_dirty()
    
    def connect(self, other_socket):
        """Connect this socket to another socket"""
        # Ensure one socket is input and one is output
        if self.is_input == other_socket.is_input:
            return False
        
        # Check type compatibility
        if not self.can_connect_to(other_socket):
            return False
        
        # Disconnect any existing connections
        self.disconnect()
        other_socket.disconnect()
        
        # Make the connection
        self.connected_to = other_socket
        other_socket.connected_to = self
        
        # Mark the target node as dirty when a new connection is made
        if self.is_input:
            self.node.mark_dirty()
        else:
            other_socket.node.mark_dirty()

        return True
    
    def contains_point(self, x, y):
        """Check if a point is inside this socket"""
        socket_x, socket_y = self.position
        distance = math.sqrt((socket_x - x) ** 2 + (socket_y - y) ** 2)
        return distance <= self.radius
