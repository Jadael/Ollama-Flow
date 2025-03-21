import customtkinter as ctk

def create_properties_panel(parent, node):
    """Create a properties panel for a node with real-time updates and output display"""
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
    
    # Apply position button (keeping this single button for position changes)
    def apply_position():
        try:
            new_x = int(x_var.get())
            new_y = int(y_var.get())
            node.x = new_x
            node.y = new_y
            node.draw()
            x_entry.configure(border_color=None)
            y_entry.configure(border_color=None)
        except ValueError:
            x_entry.configure(border_color="orange")
            y_entry.configure(border_color="orange")
    
    apply_btn = ctk.CTkButton(pos_frame, text="Apply", command=apply_position, width=60)
    apply_btn.grid(row=0, column=5, padx=5, pady=5)
    
    # Add node-specific properties section
    if hasattr(node.__class__, 'properties'):
        # Section header
        ctk.CTkLabel(
            properties_frame, 
            text="Properties", 
            font=("Arial", 12, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        # Create property widgets for each property
        for name, config in node.__class__.properties.items():
            prop_frame = create_property_widget(properties_frame, node, name, config)
            if prop_frame:
                prop_frame.pack(fill="x", padx=5, pady=5)
    
    # Add outputs section
    if hasattr(node, 'output_cache') and node.output_cache:
        # Section header
        ctk.CTkLabel(
            properties_frame, 
            text="Outputs", 
            font=("Arial", 12, "bold")
        ).pack(anchor="w", padx=10, pady=(15, 5))
        
        # Create output display for each output
        for name, value in node.output_cache.items():
            output_frame = create_output_widget(properties_frame, node, name, value)
            if output_frame:
                output_frame.pack(fill="x", padx=5, pady=5)
    
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
    """Create appropriate widget for a property based on its type with real-time updates"""
    prop_type = config.get('type', 'string')
    ui_config = config.get('ui', {})
    widget_type = ui_config.get('widget', 'entry')
    label = ui_config.get('label', prop_name)
    
    # Create a frame for this property
    frame = ctk.CTkFrame(parent_frame)
    
    # Add label and header row
    header_frame = ctk.CTkFrame(frame)
    header_frame.pack(fill="x", padx=10, pady=(10, 0))
    
    # Label on the left
    ctk.CTkLabel(header_frame, text=label).pack(side="left", padx=5)
    
    # "Show on node" checkbox on the right
    is_visible = node.property_visibility.get(prop_name, ui_config.get('preview_on_node', False))
    preview_var = ctk.BooleanVar(value=is_visible)
    
    def update_preview():
        node.property_visibility[prop_name] = preview_var.get()
        node.draw()
    
    preview_check = ctk.CTkCheckBox(header_frame, text="Show on node", variable=preview_var, command=update_preview)
    preview_check.pack(side="right", padx=5)
    
    # Create the appropriate widget based on type and widget_type with real-time updates
    if prop_type == 'string':
        if widget_type == 'text_area':
            text_area = ctk.CTkTextbox(frame, height=100)
            text_area.pack(fill="x", padx=10, pady=5)
            
            # Set initial value
            current_value = getattr(node, prop_name, "")
            text_area.insert("1.0", current_value)
            
            # Real-time updates with validation
            def on_text_change(event=None):
                new_value = text_area.get("1.0", "end-1c")
                try:
                    setattr(node, prop_name, new_value)
                    node.mark_dirty()
                    node.draw()
                    text_area.configure(border_color=None)  # Reset border
                except ValueError:
                    # Highlight in orange to indicate error
                    text_area.configure(border_color="orange")
            
            # Bind to key release and focus out events
            text_area.bind("<KeyRelease>", on_text_change)
            text_area.bind("<FocusOut>", on_text_change)
            
        else:  # Default to entry widget
            entry = ctk.CTkEntry(frame)
            entry.pack(fill="x", padx=10, pady=5)
            entry.insert(0, getattr(node, prop_name, ""))
            
            def on_entry_change(event=None):
                new_value = entry.get()
                try:
                    setattr(node, prop_name, new_value)
                    node.mark_dirty()
                    node.draw()
                    entry.configure(border_color=None)  # Reset border
                except ValueError:
                    # Highlight in orange to indicate error
                    entry.configure(border_color="orange")
            
            # Bind to key release and focus out events
            entry.bind("<KeyRelease>", on_entry_change)
            entry.bind("<FocusOut>", on_entry_change)
            
    elif prop_type == 'number':
        entry = ctk.CTkEntry(frame)
        entry.pack(fill="x", padx=10, pady=5)
        entry.insert(0, str(getattr(node, prop_name, 0)))
        
        def on_number_change(event=None):
            new_value = entry.get()
            try:
                value = float(new_value)
                setattr(node, prop_name, value)
                node.mark_dirty()
                node.draw()
                entry.configure(border_color=None)  # Reset border
            except ValueError:
                # Highlight in orange to indicate error
                entry.configure(border_color="orange")
        
        # Bind to key release and focus out events
        entry.bind("<KeyRelease>", on_number_change)
        entry.bind("<FocusOut>", on_number_change)
        
    elif prop_type == 'boolean':
        var = ctk.BooleanVar(value=getattr(node, prop_name, False))
        
        def on_checkbox_change():
            setattr(node, prop_name, var.get())
            node.mark_dirty()
            node.draw()
        
        checkbox = ctk.CTkCheckBox(frame, text="", variable=var, command=on_checkbox_change)
        checkbox.pack(padx=10, pady=5)
    
    elif prop_type == 'choice':
        # For dropdown menus
        options = config.get('options', [])
        current_value = getattr(node, prop_name, options[0] if options else "")
        
        def on_dropdown_change(choice):
            setattr(node, prop_name, choice)
            node.mark_dirty()
            node.draw()
        
        dropdown = ctk.CTkOptionMenu(frame, values=options, command=on_dropdown_change)
        dropdown.pack(fill="x", padx=10, pady=5)
        dropdown.set(current_value)
    
    return frame

def create_output_widget(parent_frame, node, output_name, output_value):
    """Create a widget to display an output value with copy functionality"""
    # Create a frame for this output
    frame = ctk.CTkFrame(parent_frame)
    
    # Add header row with name and show on node checkbox
    header_frame = ctk.CTkFrame(frame)
    header_frame.pack(fill="x", padx=10, pady=(10, 0))
    
    # Output name on the left
    ctk.CTkLabel(header_frame, text=f"Output: {output_name}").pack(side="left", padx=5)
    
    # "Show on node" checkbox on the right
    is_visible = node.output_visibility.get(output_name, True)  # Default to showing outputs
    show_var = ctk.BooleanVar(value=is_visible)
    
    def update_output_visibility():
        node.output_visibility[output_name] = show_var.get()
        node.draw()
    
    show_check = ctk.CTkCheckBox(header_frame, text="Show on node", variable=show_var, command=update_output_visibility)
    show_check.pack(side="right", padx=5)
    
    # Display the output value in a text box
    text_area = ctk.CTkTextbox(frame, height=100, wrap="word")
    text_area.pack(fill="x", padx=10, pady=5)
    text_area.insert("1.0", str(output_value))
    text_area.configure(state="disabled")  # Make read-only
    
    # Add copy button
    def copy_to_clipboard():
        parent_frame.master.clipboard_clear()
        parent_frame.master.clipboard_append(str(output_value))
    
    copy_btn = ctk.CTkButton(frame, text="Copy to Clipboard", command=copy_to_clipboard)
    copy_btn.pack(pady=5, padx=10)
    
    return frame
