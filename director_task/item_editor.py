from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import os
from PIL import Image, ImageTk
from director_task.item import Item
from director_task.grid import Grid
from director_task.renderer_2d import GridRenderer2D


class ItemEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Item Editor")
        self.root.geometry("800x600")
        
        # Data
        self.items = []
        self.default_item = None
        self.current_item = None
        self.current_item_index = -1
        self.is_editing_defaults = False
        self.json_path = Path(__file__).parent / "items.json"
        
        # GUI Variables
        self.boolean_vars = {}
        self.scalar_vars = {}
        
        self.setup_gui()
        self.load_items()
        self.update_window_title()
    
    def setup_gui(self):
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left sidebar for item list
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        ttk.Label(left_frame, text="Items", font=("Arial", 12, "bold")).pack(pady=(0, 5))
        
        # Item listbox with scrollbar
        listbox_frame = ttk.Frame(left_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        self.item_listbox = tk.Listbox(listbox_frame, width=20)
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.item_listbox.yview)
        self.item_listbox.config(yscrollcommand=scrollbar.set)
        
        self.item_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.item_listbox.bind('<<ListboxSelect>>', self.on_item_select)
        
        # Buttons for Add/Remove
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(button_frame, text="Open File", command=self.open_file).pack(fill=tk.X, pady=(0, 2))
        ttk.Button(button_frame, text="Add Item", command=self.add_item).pack(fill=tk.X, pady=(0, 2))
        ttk.Button(button_frame, text="Remove Item", command=self.remove_item).pack(fill=tk.X)
        
        # Right panel for editing with scrollbar
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Create canvas and scrollbar for scrollable content
        self.canvas = tk.Canvas(right_frame)
        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind mousewheel for scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

        # Image display
        self.image_frame = ttk.LabelFrame(self.scrollable_frame, text="Image Preview")
        self.image_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.image_label = ttk.Label(self.image_frame, text="No image selected")
        self.image_label.pack(pady=20)
        
        # Item name
        name_frame = ttk.Frame(self.scrollable_frame)
        name_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(name_frame, text="Name:").pack(side=tk.LEFT)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var)
        self.name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Image path
        image_path_frame = ttk.Frame(self.scrollable_frame)
        image_path_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(image_path_frame, text="Image:").pack(side=tk.LEFT)
        self.image_path_var = tk.StringVar()
        self.image_path_entry = ttk.Entry(image_path_frame, textvariable=self.image_path_var)
        self.image_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        ttk.Button(image_path_frame, text="Browse", command=self.browse_image).pack(side=tk.LEFT)

        # Offset controls
        offset_frame = ttk.LabelFrame(self.scrollable_frame, text="Position Offset (pixels)")
        offset_frame.pack(fill=tk.X, pady=(0, 10))

        offset_controls = ttk.Frame(offset_frame)
        offset_controls.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(offset_controls, text="X:").pack(side=tk.LEFT)
        self.offset_x_var = tk.StringVar()
        self.offset_x_entry = ttk.Entry(offset_controls, textvariable=self.offset_x_var, width=10)
        self.offset_x_entry.pack(side=tk.LEFT, padx=(5, 15))

        ttk.Label(offset_controls, text="Y:").pack(side=tk.LEFT)
        self.offset_y_var = tk.StringVar()
        self.offset_y_entry = ttk.Entry(offset_controls, textvariable=self.offset_y_var, width=10)
        self.offset_y_entry.pack(side=tk.LEFT, padx=(5, 0))

        # Boolean properties
        self.bool_frame = ttk.LabelFrame(self.scrollable_frame, text="Boolean Properties")
        self.bool_frame.pack(fill=tk.X, pady=(0, 10))

        # Scalar properties
        self.scalar_frame = ttk.LabelFrame(self.scrollable_frame, text="Scalar Properties")
        self.scalar_frame.pack(fill=tk.X, pady=(0, 10))

        # Property management buttons (only shown when editing)
        self.property_mgmt_frame = ttk.LabelFrame(self.scrollable_frame, text="Property Management")
        self.property_mgmt_frame.pack(fill=tk.X, pady=(0, 10))

        prop_btn_frame = ttk.Frame(self.property_mgmt_frame)
        prop_btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(prop_btn_frame, text="Add Boolean Property", command=self.add_boolean_property).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(prop_btn_frame, text="Add Scalar Property", command=self.add_scalar_property).pack(side=tk.LEFT, padx=(0, 5))

        # Merge All and Save buttons
        button_frame = ttk.Frame(self.scrollable_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Merge All Matching", command=self.merge_all_properties).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Save All Changes", command=self.save_items).pack(side=tk.LEFT)
        
        # Bind entry changes to update current item
        self.name_var.trace('w', self.on_name_change)
        self.image_path_var.trace('w', self.on_image_path_change)
        self.offset_x_var.trace('w', lambda *args: self.on_offset_change('offset_x'))
        self.offset_y_var.trace('w', lambda *args: self.on_offset_change('offset_y'))
    
    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling"""
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")

    def load_items(self):
        try:
            self.items = Item.load_from_json(str(self.json_path), validate=True)
            self.default_item = Item.create_default_item()
            self.refresh_item_list()
            self.update_window_title()
        except FileNotFoundError:
            messagebox.showwarning("File Not Found", f"Could not find {self.json_path}")
            self.items = []  # Initialize empty list if file not found
            self.default_item = Item.create_default_item()
            self.refresh_item_list()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load items: {str(e)}")
            self.items = []  # Initialize empty list on error
            self.default_item = Item.create_default_item()
            self.refresh_item_list()
    
    def refresh_item_list(self):
        self.item_listbox.delete(0, tk.END)
        # Add default item first
        if self.default_item:
            self.item_listbox.insert(tk.END, self.default_item.name)
        # Add regular items
        for item in self.items:
            self.item_listbox.insert(tk.END, item.name)
    
    def on_item_select(self, event):
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            if index == 0 and self.default_item:
                # Selected default item
                self.current_item_index = -1
                self.current_item = self.default_item
                self.is_editing_defaults = True
            else:
                # Selected regular item
                actual_index = index - 1 if self.default_item else index
                self.current_item_index = actual_index
                self.current_item = self.items[actual_index]
                self.is_editing_defaults = False
            self.display_item_details()
    
    def display_item_details(self):
        if not self.current_item:
            return
        
        # Update name and image path
        self.name_var.set(self.current_item.name)
        self.image_path_var.set(self.current_item.image_path)

        # Update offset values
        self.offset_x_var.set(str(self.current_item.scalar_properties.get('offset_x', 0)))
        self.offset_y_var.set(str(self.current_item.scalar_properties.get('offset_y', 0)))

        # Display image
        self.display_image()
        
        # Clear existing property widgets
        for widget in self.bool_frame.winfo_children():
            widget.destroy()
        for widget in self.scalar_frame.winfo_children():
            widget.destroy()
        
        self.boolean_vars.clear()
        self.scalar_vars.clear()
        
        # Create boolean property checkboxes
        bool_props = self.current_item.boolean_properties
        row = 0
        col = 0
        max_cols = 2  # Reduced to make room for merge buttons
        
        for prop_name, prop_value in bool_props.items():
            var = tk.BooleanVar(value=prop_value)
            self.boolean_vars[prop_name] = var
            
            # Create frame for checkbox + label + merge button
            prop_frame = ttk.Frame(self.bool_frame)
            prop_frame.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            
            cb = ttk.Checkbutton(prop_frame, text=prop_name, variable=var, 
                               command=lambda pn=prop_name: self.on_boolean_change(pn))
            cb.pack(side=tk.LEFT)
            
            # Add default label if using default
            if self.current_item.is_using_default_boolean(prop_name):
                default_label = ttk.Label(prop_frame, text="(default)", foreground="gray")
                default_label.pack(side=tk.LEFT, padx=(5, 0))
            
            # Add merge button if can be merged (only for regular items)
            if not self.is_editing_defaults and self.current_item.can_merge_boolean_property(prop_name):
                merge_btn = ttk.Button(prop_frame, text="Merge", 
                                     command=lambda pn=prop_name: self.merge_boolean_property(pn))
                merge_btn.pack(side=tk.LEFT, padx=(5, 0))
            
            # Add remove button for properties
            if len(bool_props) > 1:  # Don't allow removing the last property
                remove_btn = ttk.Button(prop_frame, text="Remove", 
                                      command=lambda pn=prop_name: self.remove_boolean_property(pn))
                remove_btn.pack(side=tk.LEFT, padx=(5, 0))
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        # Create scalar property entries
        for prop_name, prop_value in self.current_item.scalar_properties.items():
            frame = ttk.Frame(self.scalar_frame)
            frame.pack(fill=tk.X, padx=5, pady=2)
            
            ttk.Label(frame, text=f"{prop_name}:").pack(side=tk.LEFT)
            
            var = tk.StringVar(value=str(prop_value))
            self.scalar_vars[prop_name] = var
            
            entry = ttk.Entry(frame, textvariable=var, width=10)
            entry.pack(side=tk.LEFT, padx=(5, 0))
            
            # Add default label if using default
            if self.current_item.is_using_default_scalar(prop_name):
                default_label = ttk.Label(frame, text="(default)", foreground="gray")
                default_label.pack(side=tk.LEFT, padx=(5, 0))
            
            # Add merge button if can be merged (only for regular items)
            if not self.is_editing_defaults and self.current_item.can_merge_scalar_property(prop_name):
                merge_btn = ttk.Button(frame, text="Merge",
                                     command=lambda pn=prop_name: self.merge_scalar_property(pn))
                merge_btn.pack(side=tk.LEFT, padx=(5, 0))
            
            # Add remove button for properties
            if len(self.current_item.scalar_properties) > 1:  # Don't allow removing the last property
                remove_btn = ttk.Button(frame, text="Remove", 
                                      command=lambda pn=prop_name: self.remove_scalar_property(pn))
                remove_btn.pack(side=tk.LEFT, padx=(5, 0))
            
            var.trace('w', lambda *args, pn=prop_name: self.on_scalar_change(pn))
    
    def display_image(self):
        if not self.current_item or not self.current_item.image_path:
            self.image_label.config(image='', text="No image")
            return

        try:
            # Try to find the image file
            image_path = self.current_item.image_path
            if not os.path.isabs(image_path):
                # Relative path - look in director_task directory
                image_path = os.path.join(os.path.dirname(self.json_path), image_path)

            if not os.path.exists(image_path):
                self.image_label.config(image='', text=f"Image not found:\n{image_path}")
                return

            # Create a small 3x3 grid to show offset effects
            grid = Grid(3, 3)

            # Fill the grid cells with the current item to demonstrate offsets
            for row in range(3):
                for col in range(3):
                    grid.item_grid[row][col] = self.current_item

            # Render the grid with smaller cell size to fit in preview
            renderer = GridRenderer2D(
                cell_size=60,
                shelf_depth=10,
                image_width=400,
                image_height=400,
                text_size=24
            )

            # Render without director image for cleaner preview
            rendered_grid = renderer.render_grid(grid, background_color=(220, 220, 220), director_image_path=None)

            # Convert to PhotoImage for tkinter
            photo = ImageTk.PhotoImage(rendered_grid)
            self.image_label.config(image=photo, text="")
            self.image_label.image = photo  # Keep a reference

        except Exception as e:
            self.image_label.config(image='', text=f"Error rendering preview:\n{str(e)}")
    
    def on_name_change(self, *args):
        if self.current_item:
            self.current_item.name = self.name_var.get()
            self.refresh_item_list()
            # Maintain selection
            if self.is_editing_defaults:
                self.item_listbox.select_set(0)
                # Save defaults immediately if editing defaults
                self.save_current_item()
            elif self.current_item_index >= 0:
                # Account for default item offset
                display_index = self.current_item_index + (1 if self.default_item else 0)
                self.item_listbox.select_set(display_index)
    
    def on_image_path_change(self, *args):
        if self.current_item:
            self.current_item.image_path = self.image_path_var.get()
            self.display_image()
            # Save defaults immediately if editing defaults
            if self.is_editing_defaults:
                self.save_current_item()

    def on_offset_change(self, offset_prop):
        if self.current_item:
            try:
                if offset_prop == 'offset_x':
                    value = self.offset_x_var.get()
                else:
                    value = self.offset_y_var.get()

                if value == '' or value == '-':
                    return

                value = int(value)
                self.current_item.set_scalar_property(offset_prop, value)

                # Refresh the preview to show offset changes in real-time
                self.display_image()

                if self.is_editing_defaults:
                    self.save_current_item()
            except ValueError:
                pass

    def on_boolean_change(self, prop_name):
        if self.current_item and prop_name in self.boolean_vars:
            self.current_item.set_boolean_property(prop_name, self.boolean_vars[prop_name].get())
            # Refresh display to update labels/buttons
            self.display_item_details()
            # Save defaults immediately if editing defaults
            if self.is_editing_defaults:
                self.save_current_item()
    
    def on_scalar_change(self, prop_name):
        if self.current_item and prop_name in self.scalar_vars:
            try:
                value = self.scalar_vars[prop_name].get()
                # Try to convert to number if possible
                if value.isdigit():
                    value = int(value)
                elif value.replace('.', '').isdigit():
                    value = float(value)
                self.current_item.set_scalar_property(prop_name, value)
                # Refresh display to update labels/buttons
                self.display_item_details()
                # Save defaults immediately if editing defaults
                if self.is_editing_defaults:
                    self.save_current_item()
            except ValueError:
                pass  # Keep as string if conversion fails
    
    def merge_boolean_property(self, prop_name):
        """Merge a boolean property back to using its default value"""
        if self.current_item:
            self.current_item.merge_boolean_property_to_default(prop_name)
            self.display_item_details()
    
    def merge_scalar_property(self, prop_name):
        """Merge a scalar property back to using its default value"""
        if self.current_item:
            self.current_item.merge_scalar_property_to_default(prop_name)
            self.display_item_details()
    
    def merge_all_properties(self):
        """Merge all properties that match defaults back to using defaults"""
        if self.current_item:
            merged_count = self.current_item.merge_all_matching_properties()
            if merged_count > 0:
                messagebox.showinfo("Merge Complete", f"Merged {merged_count} properties to defaults")
                self.display_item_details()
            else:
                messagebox.showinfo("No Changes", "No properties needed to be merged")
    
    def convert_to_relative_path(self, absolute_path):
        """Convert absolute path to relative path from the JSON file directory if possible"""
        try:
            json_dir = Path(self.json_path).parent.absolute()
            abs_path = Path(absolute_path).absolute()
            
            # Try to make it relative to the JSON file directory
            relative_path = abs_path.relative_to(json_dir)
            return str(relative_path).replace('\\', '/')  # Use forward slashes for cross-platform compatibility
        except ValueError:
            # If can't make relative, return the absolute path
            return absolute_path
    
    def browse_image(self):
        filename = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"), ("All files", "*.*")],
            initialdir=Path(__file__).parent / "images"  
        )
        if filename:
            # Convert to relative path if possible
            relative_path = self.convert_to_relative_path(filename)
            self.image_path_var.set(relative_path)
    
    def add_item(self):
        # Create a new item with default properties (Item class handles defaults automatically)
        new_name = f"new_item_{len(self.items) + 1}"
        
        new_item = Item(
            name=new_name,
            image_path=""
        )
        
        self.items.append(new_item)
        self.refresh_item_list()
        
        # Select the new item
        self.item_listbox.selection_clear(0, tk.END)
        self.item_listbox.selection_set(len(self.items) - 1)
        self.item_listbox.activate(len(self.items) - 1)
        self.on_item_select(type('Event', (), {'widget': self.item_listbox})())
    
    def remove_item(self):
        if self.current_item_index >= 0:
            result = messagebox.askyesno("Confirm Delete", 
                                       f"Are you sure you want to delete '{self.current_item.name}'?")
            if result:
                del self.items[self.current_item_index]
                self.refresh_item_list()
                self.current_item = None
                self.current_item_index = -1
                # Clear the display
                self.name_var.set("")
                self.image_path_var.set("")
                self.offset_x_var.set("")
                self.offset_y_var.set("")
                self.image_label.config(image='', text="No item selected")
                for widget in self.bool_frame.winfo_children():
                    widget.destroy()
                for widget in self.scalar_frame.winfo_children():
                    widget.destroy()
    
    def update_window_title(self):
        filename = os.path.basename(self.json_path)
        self.root.title(f"Item Editor - {filename}")
    
    def clear_display(self):
        self.name_var.set("")
        self.image_path_var.set("")
        self.offset_x_var.set("")
        self.offset_y_var.set("")
        self.image_label.config(image='', text="No item selected")
        for widget in self.bool_frame.winfo_children():
            widget.destroy()
        for widget in self.scalar_frame.winfo_children():
            widget.destroy()
    
    def open_file(self):
        filename = filedialog.askopenfilename(
            title="Open Item File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.json_path)
        )
        if filename:
            self.json_path = filename
            self.load_items()
            # Clear current selection
            self.current_item = None
            self.current_item_index = -1
            self.clear_display()
    
    def save_items(self):
        # Ask user where to save
        filename = filedialog.asksaveasfilename(
            title="Save Item File",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=os.path.basename(self.json_path),
            initialdir=os.path.dirname(self.json_path)
        )
        
        if filename:
            try:
                # Convert items back to JSON format and convert image paths to relative
                items_data = []
                for item in self.items:
                    item_dict = item.to_dict(compact=False)
                    # Convert image path to relative if possible
                    if item_dict["image_path"]:
                        item_dict["image_path"] = self.convert_to_relative_path(item_dict["image_path"])
                    items_data.append(item_dict)
                
                # Validate before saving
                is_valid, errors = Item.validate_json_schema(items_data)
                if not is_valid:
                    error_msg = "Cannot save - validation errors:\n" + "\n".join(f"  - {error}" for error in errors)
                    messagebox.showerror("Validation Error", error_msg)
                    return
                
                # Validate business rules
                business_errors = Item.validate_business_rules(self.items)
                if business_errors:
                    error_msg = "Cannot save - validation errors:\n" + "\n".join(f"  - {error}" for error in business_errors)
                    messagebox.showerror("Validation Error", error_msg)
                    return
                
                # Write to JSON file
                with open(filename, 'w') as f:
                    json.dump(items_data, f, indent=2)
                
                # Update current path
                self.json_path = filename
                self.update_window_title()
                
                messagebox.showinfo("Success", f"Items saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save items: {str(e)}")
    
    def save_current_item(self):
        """Save current item changes (especially for defaults)"""
        if self.is_editing_defaults and self.current_item:
            Item.save_default_item(self.current_item)
    
    def add_boolean_property(self):
        """Add a new boolean property"""
        prop_name = simpledialog.askstring("Add Boolean Property", "Enter property name:")
        if prop_name:
            try:
                if self.is_editing_defaults:
                    Item.add_boolean_property(prop_name, False, self.items)
                    # Reload defaults to reflect changes
                    self.default_item = Item.create_default_item()
                    self.current_item = self.default_item
                else:
                    Item.add_boolean_property(prop_name, False, self.items)
                    # Reload defaults since it was modified
                    self.default_item = Item.create_default_item()
                
                self.display_item_details()
                messagebox.showinfo("Success", f"Added boolean property '{prop_name}'")
            except ValueError as e:
                messagebox.showerror("Error", str(e))
    
    def add_scalar_property(self):
        """Add a new scalar property"""
        prop_name = simpledialog.askstring("Add Scalar Property", "Enter property name:")
        if prop_name:
            default_value = simpledialog.askinteger("Default Value", f"Enter default value for '{prop_name}':", initialvalue=0)
            if default_value is not None:
                try:
                    if self.is_editing_defaults:
                        Item.add_scalar_property(prop_name, default_value, self.items)
                        # Reload defaults to reflect changes
                        self.default_item = Item.create_default_item()
                        self.current_item = self.default_item
                    else:
                        Item.add_scalar_property(prop_name, default_value, self.items)
                        # Reload defaults since it was modified
                        self.default_item = Item.create_default_item()
                    
                    self.display_item_details()
                    messagebox.showinfo("Success", f"Added scalar property '{prop_name}'")
                except ValueError as e:
                    messagebox.showerror("Error", str(e))
    
    def remove_boolean_property(self, prop_name):
        """Remove a boolean property"""
        if messagebox.askyesno("Confirm Removal", f"Remove boolean property '{prop_name}'?"):
            try:
                Item.remove_boolean_property(prop_name, self.items)
                # Reload defaults to reflect changes
                self.default_item = Item.create_default_item()
                if self.is_editing_defaults:
                    self.current_item = self.default_item
                self.display_item_details()
                messagebox.showinfo("Success", f"Removed boolean property '{prop_name}'")
            except ValueError as e:
                messagebox.showerror("Error", str(e))
    
    def remove_scalar_property(self, prop_name):
        """Remove a scalar property"""
        if messagebox.askyesno("Confirm Removal", f"Remove scalar property '{prop_name}'?"):
            try:
                Item.remove_scalar_property(prop_name, self.items)
                # Reload defaults to reflect changes
                self.default_item = Item.create_default_item()
                if self.is_editing_defaults:
                    self.current_item = self.default_item
                self.display_item_details()
                messagebox.showinfo("Success", f"Removed scalar property '{prop_name}'")
            except ValueError as e:
                messagebox.showerror("Error", str(e))


def main():
    root = tk.Tk()
    app = ItemEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()