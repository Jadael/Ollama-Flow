import customtkinter as ctk

def create_properties_panel(parent, node):
    """Create a properties panel for a node"""
    # Create a scrollable frame
    properties_frame = ctk.CTkScrollableFrame(parent)
    properties_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Add node title
    ctk.CTkLabel(
        properties_frame, 
        text=f"{node.title} Properties", 
        font=("Arial", 14, "bold")
    ).pack(pady=10)
    
    # Add node ID and position info
    info_frame = ctk.CTkFrame(properties_frame)
    info_frame.pack(fill="x", pady=5, padx=5)
    
    ctk.CTkLabel(info_frame, text=f"ID: {node.id[:8]}...").pack(anchor="w", padx=5, pady=2)
    
    pos_frame = ctk.CTkFrame(info_frame)
    pos_frame.pack(fill="x", padx=5, pady=5)
    
    ctk.CTkLabel(pos_frame, text="Position:").grid(row=0, column=0, padx=5, pady=5)
    
    x_var = ctk.StringVar(value=str(node.x))
    y_var = ctk.StringVar(value=str(node.y))
    
    x_entry = ctk.CTkEntry(pos_frame, textvariable=x_var, width=60)
    x_entry.grid(row=0, column=1, padx=5, pady=5)
    
    ctk.CTkLabel(pos_frame, text="X").grid(row=0, column=2, padx=2, pady=5)
    
    y_entry = ctk.CTkEntry(pos_frame, textvariable=y_var, width=60)
    y_entry.grid(row=0, column=3, padx=5, pady=5)
    
    ctk.CTkLabel(pos_frame, text="Y").grid(row=0, column=4, padx=2, pady=5)
    
    # Apply position button
    def apply_position():
        try:
            new_x = int(x_var.get())
            new_y = int(y_var.get())
            node.x = new_x
            node.y = new_y
            node.draw()
        except ValueError:
            pass
    
    apply_btn = ctk.CTkButton(pos_frame, text="Apply", command=apply_position, width=60)
    apply_btn.grid(row=0, column=5, padx=5, pady=5)
    
    # Add node-specific properties
    if hasattr(node.__class__, 'properties'):
        # Create property widgets for each property
        for name, config in node.__class__.properties.items():
            prop_frame = create_property_widget(properties_frame, node, name, config)
            if prop_frame:
                prop_frame.pack(fill="x", padx=5, pady=5)
    
    # Add processing controls
    controls_frame = ctk.CTkFrame(properties_frame)
    controls_frame.pack(fill="x", pady=10, padx=5)
    
    # Add clear cache button
    clear_btn = ctk.CTkButton(
        controls_frame, 
        text="Clear Output Cache", 
        command=node.clear_output
    )
    clear_btn.pack(pady=5, padx=10, fill="x")
    
    # Add process button
    process_btn = ctk.CTkButton(
        controls_frame, 
        text="Process Node", 
        command=lambda: node.process()
    )
    process_btn.pack(pady=5, padx=10, fill="x")
    
    return properties_frame

def create_property_widget(parent_frame, node, prop_name, config):
    """Create appropriate widget for a property based on its type"""
    prop_type = config.get('type', 'string')
    ui_config = config.get('ui', {})
    widget_type = ui_config.get('widget', 'entry')
    label = ui_config.get('label', prop_name)
    
    # Create a frame for this property
    frame = ctk.CTkFrame(parent_frame)
    
    # Add label
    ctk.CTkLabel(frame, text=label).pack(anchor="w", padx=10, pady=(10, 0))
    
    # Create the appropriate widget based on type and widget_type
    if prop_type == 'string':
        if widget_type == 'text_area':
            text_area = ctk.CTkTextbox(frame, height=100)
            text_area.pack(fill="x", padx=10, pady=5)
            
            # Set initial value
            current_value = getattr(node, prop_name, "")
            text_area.insert("1.0", current_value)
            
            # Add apply button
            def apply_text():
                new_value = text_area.get("1.0", "end-1c")
                setattr(node, prop_name, new_value)
                node.mark_dirty()
                node.draw()
            
            apply_btn = ctk.CTkButton(frame, text="Apply", command=apply_text)
            apply_btn.pack(pady=(0, 10), padx=10)
            
        else:  # Default to entry widget
            var = ctk.StringVar(value=getattr(node, prop_name, ""))
            entry = ctk.CTkEntry(frame, textvariable=var)
            entry.pack(fill="x", padx=10, pady=5)
            
            # Add apply button - doesn't auto-update to prevent constant recalculation
            def apply_entry():
                setattr(node, prop_name, var.get())
                node.mark_dirty()
                node.draw()
            
            apply_btn = ctk.CTkButton(frame, text="Apply", command=apply_entry)
            apply_btn.pack(pady=(0, 10), padx=10)
            
    elif prop_type == 'number':
        var = ctk.StringVar(value=str(getattr(node, prop_name, 0)))
        entry = ctk.CTkEntry(frame, textvariable=var)
        entry.pack(fill="x", padx=10, pady=5)
        
        # Add apply button
        def apply_number():
            try:
                value = float(var.get())
                setattr(node, prop_name, value)
                node.mark_dirty()
                node.draw()
            except ValueError:
                pass
        
        apply_btn = ctk.CTkButton(frame, text="Apply", command=apply_number)
        apply_btn.pack(pady=(0, 10), padx=10)
        
    elif prop_type == 'boolean':
        var = ctk.BooleanVar(value=getattr(node, prop_name, False))
        checkbox = ctk.CTkCheckBox(frame, text="", variable=var)
        checkbox.pack(padx=10, pady=5)
        
        # Add apply button
        def apply_boolean():
            setattr(node, prop_name, var.get())
            node.mark_dirty()
            node.draw()
        
        apply_btn = ctk.CTkButton(frame, text="Apply", command=apply_boolean)
        apply_btn.pack(pady=(0, 10), padx=10)
    
    elif prop_type == 'choice':
        # For dropdown menus
        options = config.get('options', [])
        var = ctk.StringVar(value=str(getattr(node, prop_name, options[0] if options else "")))
        dropdown = ctk.CTkOptionMenu(frame, values=options, variable=var)
        dropdown.pack(fill="x", padx=10, pady=5)
        
        # Add apply button
        def apply_choice():
            setattr(node, prop_name, var.get())
            node.mark_dirty()
            node.draw()
        
        apply_btn = ctk.CTkButton(frame, text="Apply", command=apply_choice)
        apply_btn.pack(pady=(0, 10), padx=10)
    
    return frame