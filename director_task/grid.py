from typing import List, Optional, TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from director_task.item import Item

TRANSPARENT_MATERIALS = [
    "Glass",
    "Transparent plastic",
    "None",
]

OPAQUE_MATERIALS = [
    "Steel",
    "Plywood",
    "cardboard",
    "Black plastic",
    "Green plastic",
]

class Grid:
    def __init__(self, width: int, height: int):
        """
        Initialize a Grid with specified dimensions.
        
        COORDINATE SYSTEM:
        - Coordinates stored as (x, y) where x=column (0 to width-1), y=row (0 to height-1)
        - Grid access pattern: grid[row][col] = grid[y][x]
        - Top-left is (0, 0), bottom-right is (width-1, height-1)
        """
        self.width = width
        self.height = height
        # Grid arrays: outer index = row (y), inner index = column (x)
        # Access pattern: item_grid[row][col] = item_grid[y][x]
        self.item_grid: List[List[Optional['Item']]] = [[None for _ in range(width)] for _ in range(height)]
        # Blocked positions: same structure as item_grid
        self.blocks: List[List[int]] = [[0 for _ in range(width)] for _ in range(height)]
    
    def get_director_perspective(self) -> 'Grid':
        """Returns a copy of the grid from the director's perspective where blocked items are treated as None"""
        director_grid = Grid(self.width, self.height)
        
        for y in range(self.height):      # y = row index
            for x in range(self.width):   # x = column index
                # If position is not blocked, copy the item
                # Grid access: [row][col] = [y][x]
                if self.blocks[y][x] == 0:
                    director_grid.item_grid[y][x] = self.item_grid[y][x]
                # If blocked, item remains None (already initialized as None)
                
        # Copy the blocks array (though it's not used in director perspective)
        director_grid.blocks = [row[:] for row in self.blocks]
        
        return director_grid
    
    def set_blocked(self, row: int, col: int, blocked: bool):
        """Set whether a grid position is blocked from director's view
        
        Args:
            row: Row index (y coordinate)
            col: Column index (x coordinate)
        """
        self.blocks[row][col] = 1 if blocked else 0  # Grid access: [row][col] = [y][x]
    
    def is_blocked(self, row: int, col: int) -> bool:
        """Check if a grid position is blocked from director's view
        
        Args:
            row: Row index (y coordinate) 
            col: Column index (x coordinate)
        """
        return self.blocks[row][col] == 1  # Grid access: [row][col] = [y][x]
    
    def pretty_print(self) -> str:
        """Return a formatted string representation of the grid in actual grid format"""
        lines = []
        lines.append(f"Grid ({self.width}x{self.height}):")
        lines.append("=" * (self.width * 20))
        
        # Create grid representation
        for y in range(self.height):      # y = row index
            row_cells = []
            
            for x in range(self.width):   # x = column index
                # Convert to task coordinate system: letter=column, number=row
                task_coord = chr(ord('A') + x) + str(y + 1)  # A1, B1, C2, etc.
                cell_content = f"{task_coord}\n"
                
                # Check if blocked - Grid access: [row][col] = [y][x]
                if self.blocks[y][x] == 1:
                    cell_content += "[BLOCKED]\n"
                
                # Check if item exists - Grid access: [row][col] = [y][x]
                item = self.item_grid[y][x]
                if item is None:
                    cell_content += "Empty"
                else:
                    cell_content += f"{item.name}\n"
                    
                    # Add boolean properties (only True ones)
                    if item.boolean_properties:
                        bool_props = [k for k, v in item.boolean_properties.items() if v]
                        if bool_props:
                            cell_content += f"B: {','.join(bool_props)}\n"
                    
                    # Add scalar properties
                    if item.scalar_properties:
                        scalar_props = [f"{k}:{v}" for k, v in item.scalar_properties.items()]
                        if scalar_props:
                            cell_content += f"S: {','.join(scalar_props)}"
                
                # Pad cell to fixed width
                cell_lines = cell_content.split('\n')
                padded_lines = []
                for line in cell_lines:
                    padded_lines.append(f"{line:<18}")
                
                row_cells.append(padded_lines)
            
            # Find max lines in any cell for this row
            max_lines = max(len(cell) for cell in row_cells)
            
            # Pad all cells to same height
            for cell in row_cells:
                while len(cell) < max_lines:
                    cell.append(" " * 18)
            
            # Print each line of the row
            for line_idx in range(max_lines):
                line = "| " + " | ".join(cell[line_idx] for cell in row_cells) + " |"
                lines.append(line)
            
            # Add separator between rows
            if y < self.height - 1:
                lines.append("-" * (self.width * 21 + 1))
        
        lines.append("=" * (self.width * 20))
        return "\n".join(lines)
    
    def load_from_dict(self, grid_data: Dict[str, Any]) -> None:
        """Load items and blocks arrays from dictionary format (as saved in JSON datasets)
        
        Args:
            grid_data: Dictionary containing 'width', 'height', and 'items' keys
                      - items is a flattened array with position, is_blocked, and item data
        """
        from director_task.item import Item  # Import here to avoid circular imports
        
        # Validate dimensions match
        if grid_data['grid_width'] != self.width or grid_data['grid_height'] != self.height:
            raise ValueError(f"Grid dimensions mismatch: expected {self.width}x{self.height}, "
                           f"got {grid_data['grid_width']}x{grid_data['grid_height']}")
        
        # Clear existing data
        self.item_grid = [[None for _ in range(self.width)] for _ in range(self.height)]
        self.blocks = [[0 for _ in range(self.width)] for _ in range(self.height)]
        
        # Process the flattened items array
        for item_data in grid_data['items']:
            x = item_data['position']['x']  # column
            y = item_data['position']['y']  # row
            is_blocked = item_data['is_blocked']
            item_info = item_data['item']
            
            # Set blocked status
            self.set_blocked(y, x, is_blocked)  # Grid method expects (row, col)
            
            # Create and place item if present
            if item_info is not None:
                item = Item(
                    name=item_info['name'],
                    image_path=item_info['image_path'],
                    boolean_properties=item_info['boolean_properties'],
                    scalar_properties=item_info['scalar_properties']
                )
                self.item_grid[y][x] = item  # Grid access: [row][col] = [y][x]
    
    def to_markdown(self) -> str:
        """Return a markdown table representation of the grid"""
        lines = []
        
        # Create header row with column indices
        header = "| " + " | ".join(f"Col {x}" for x in range(self.width)) + " |"
        lines.append(header)
        
        # Create separator row
        separator = "|" + "|".join("---" for _ in range(self.width)) + "|"
        lines.append(separator)
        
        # Create rows
        for y in range(self.height):
            row_cells = []
            for x in range(self.width):
                cell_parts = []
                
                # Convert to task coordinate system: letter=column, number=row
                task_coord = chr(ord('A') + x) + str(y + 1)  # A1, B1, C2, etc.
                cell_parts.append(f"**{task_coord}**")
                
                # Check if blocked
                key = (x + y) * (x + y + 1) // 2 + y
                if self.blocks[y][x] == 1:
                    material = OPAQUE_MATERIALS[key % len(OPAQUE_MATERIALS)]
                else:
                    material = TRANSPARENT_MATERIALS[key % len(TRANSPARENT_MATERIALS)]

                cell_parts.append(f"backing plate: {material}")
                
                # Check item
                item = self.item_grid[y][x]
                if item is None:
                    cell_parts.append("_Empty_")
                else:
                    cell_parts.append(f"**{item.name}**")
                    
                    # Add boolean properties
                    if item.boolean_properties:
                        bool_props = [k for k, v in item.boolean_properties.items() if v]
                        if bool_props:
                            cell_parts.append(f"Bool: {', '.join(bool_props)}")
                    
                    # Add scalar properties
                    if item.scalar_properties:
                        scalar_props = [f"{k}={v}" for k, v in item.scalar_properties.items()]
                        if scalar_props:
                            cell_parts.append(f"Scalar: {', '.join(scalar_props)}")
                
                # Join cell parts with line breaks
                row_cells.append("<br>".join(cell_parts))
            
            # Create the row
            row = "| " + " | ".join(row_cells) + " |"
            lines.append(row)
        
        return "\n".join(lines)