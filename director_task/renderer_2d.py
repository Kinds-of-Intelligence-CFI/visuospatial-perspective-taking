"""
2D Grid Renderer for Director Task

Renders isometric grid layouts for visual perspective-taking experiments.
"""

from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple, Optional, Dict
import math
from collections import OrderedDict
from director_task.grid import Grid
from director_task.item import Item


class GridRenderer2D:
    """2D isometric renderer for director task grids using PIL/Pillow."""
    
    def __init__(self, cell_size: int = 100, shelf_depth: int = 20, image_width: int = 800, image_height: int = 600, text_size: int = 36, items: Optional[List[Item]] = None, director_image_path: Optional[str] = None, cache_size: int = 100):
        """
        Initialize the 2D grid renderer.
        
        Args:
            cell_size: Size of each grid cell in pixels
            shelf_depth: Depth of shelf rendering in pixels for 3D effect
            image_width: Total width of generated image
            image_height: Total height of generated image
            text_size: Size of heading text in pixels
            items: Optional list of items to pre-cache
            director_image_path: Optional path to director image for caching
            cache_size: Maximum number of items to cache in each cache (default: 100)
        """
        self.cell_size = cell_size
        self.shelf_depth = shelf_depth
        self.image_width = image_width
        self.image_height = image_height
        self.text_size = text_size
        self.cache_size = cache_size
        
        # Initialize LRU caches using OrderedDict
        self.font_cache: OrderedDict[Tuple[str, int], ImageFont.ImageFont] = OrderedDict()
        self.raw_image_cache: OrderedDict[str, Image.Image] = OrderedDict()
        self.resized_image_cache: OrderedDict[Tuple[str, int, int], Image.Image] = OrderedDict()
        
        # Store director image path for caching
        self.director_image_path = director_image_path or "director_task/director_image.png"
        
        # Warmup caches if items are provided
        if items:
            self.warmup_caches(items)
        
    def render_grid(self, grid: Grid, background_color: Tuple[int, int, int] = (64, 224, 208), director_image_path: Optional[str] = None) -> Image.Image:
        """
        Render a grid as an isometric 2D image.
        
        Args:
            grid: Grid object containing layout and blocking information
            background_color: RGB tuple for background color
            director_image_path: Optional path to director image to render behind grid
            
        Returns:
            PIL Image of the rendered grid
        """
        # Create image and drawing context
        img = Image.new('RGB', (self.image_width, self.image_height), background_color)
        draw = ImageDraw.Draw(img)
        
        # Draw director image behind grid if provided
        if director_image_path is None:
            director_image_path = self.director_image_path
        self._draw_director_image(img, director_image_path)
        
        # Calculate starting position (center the grid with space for headings)
        heading_margin = 40  # Space for column letters and row numbers
        start_x = self.image_width // 2 - (grid.width * self.cell_size // 2) + heading_margin - self.shelf_depth
        start_y = self.image_height // 2 - (grid.height * self.cell_size // 2) + heading_margin - self.shelf_depth
        
        # Store start position for item placement calculations
        self.grid_start_x = start_x
        self.grid_start_y = start_y
        
        # Draw each cell (both blocked and unblocked)
        for row in range(grid.height):
            for col in range(grid.width):
                is_blocked = grid.is_blocked(row, col)
                self._draw_cell(draw, row, col, start_x, start_y, is_blocked)

        # Draw top and right edges of the entire grid for perspective
        # These cover overlapping lines from individual cells and improve the 3D effect
        self._draw_top_edge(draw, grid, start_x, start_y)
        self._draw_right_edge(draw, grid, start_x, start_y)

        # Draw column and row headings
        self._draw_headings(draw, grid, start_x, start_y)

        # Draw each item in the grid 
        # Grid access pattern: item_grid[y][x] where y=row, x=col
        for row in range(grid.height):      # row = y coordinate
            for col in range(grid.width):   # col = x coordinate
                item = grid.item_grid[row][col]  # [y][x] = [row][col]
                if item is not None:
                    self._draw_item(img, row, col, item)
        
        return img
    
    def _draw_item(self, img: Image.Image, row: int, col: int, item: Item):
        try:
            image_path = f"director_task/{item.image_path}"
            item_size = self.get_item_size()
            cache_key = (image_path, item_size, item_size)
            
            # Check resized cache first
            if cache_key in self.resized_image_cache:
                item_image = self.resized_image_cache[cache_key]
                # Move to end (most recently used)
                self.resized_image_cache.move_to_end(cache_key)
            else:
                # Check raw cache
                if image_path in self.raw_image_cache:
                    raw_image = self.raw_image_cache[image_path]
                    # Move to end (most recently used)
                    self.raw_image_cache.move_to_end(image_path)
                else:
                    # Load from disk and cache
                    raw_image = Image.open(image_path)

                    # Convert palette images with transparency to RGBA to handle transparency properly
                    if raw_image.mode == 'P' and 'transparency' in raw_image.info:
                        raw_image = raw_image.convert('RGBA')
                    elif raw_image.mode != 'RGBA' and raw_image.mode != 'RGB':
                        raw_image = raw_image.convert('RGBA')

                    self._cache_with_lru(self.raw_image_cache, image_path, raw_image)
                
                # Resize and cache
                item_image = raw_image.resize((item_size, item_size), Image.Resampling.LANCZOS)
                self._cache_with_lru(self.resized_image_cache, cache_key, item_image)

            # Place it at position (0, 1) - top row, second column
            item_x, item_y = self.get_item_position(row, col)

            # Apply item offsets if specified
            offset_x = item.scalar_properties.get('offset_x', 0)
            offset_y = item.scalar_properties.get('offset_y', 0)
            item_x += offset_x
            item_y += offset_y

            # Handle transparency if the image has an alpha channel
            if item_image.mode == 'RGBA':
                img.paste(item_image, (item_x, item_y), item_image)
            else:
                img.paste(item_image, (item_x, item_y))
        except FileNotFoundError:
            print(f"Warning: Could not find item image at {item.image_path}")
            print("Continuing without item placement...")

    def _draw_cell(self, draw: ImageDraw.Draw, row: int, col: int, start_x: int, start_y: int, is_blocked: bool):
        """
        Draw a single rectangular shelf compartment (like furniture view).
        
        Args:
            draw: PIL ImageDraw object
            row: Grid row position
            col: Grid column position
            start_x: Starting X coordinate for grid
            start_y: Starting Y coordinate for grid
            is_blocked: Whether this cell is blocked (has back wall)
        """
        # Calculate rectangular grid position (no rotation)
        cell_x = start_x + col * self.cell_size
        cell_y = start_y + row * self.cell_size
        
        # Define shelf colors
        shelf_light = (200, 200, 200)  # Light gray for top/horizontal surfaces
        shelf_dark = (120, 120, 120)   # Dark gray for vertical surfaces/sides
        shelf_back = (100, 100, 100)   # Darker color for back wall (blocked cells)
        shelf_edge = (80, 80, 80)      # Edge color
        
        # Draw back wall first (only for blocked cells)
        if is_blocked:
            back_rect = [
                cell_x , 
                cell_y ,
                cell_x + self.cell_size,
                cell_y + self.cell_size
            ]
            draw.rectangle(back_rect, fill=shelf_back, outline=shelf_edge)
        
         # Draw vertical walls on top for correct layering
        # Draw left side wall
        left_points = [
            (cell_x, cell_y),
            (cell_x + self.shelf_depth, cell_y),
            (cell_x + self.shelf_depth, cell_y + self.cell_size - self.shelf_depth),
            (cell_x, cell_y + self.cell_size)
        ]
        draw.polygon(left_points, fill=shelf_dark, outline=shelf_edge)


        # Draw bottom shelf surface
        bottom_points = [
            (cell_x, cell_y + self.cell_size),
            (cell_x + self.cell_size, cell_y + self.cell_size),
            (cell_x + self.cell_size + self.shelf_depth, cell_y + self.cell_size - self.shelf_depth),
            (cell_x + self.shelf_depth, cell_y + self.cell_size - self.shelf_depth)
        ]
        draw.polygon(bottom_points, fill=shelf_light, outline=shelf_edge)
        
       
        
        # Draw right side wall
        right_points = [
            (cell_x + self.cell_size, cell_y),
            (cell_x + self.cell_size + self.shelf_depth, cell_y),
            (cell_x + self.cell_size + self.shelf_depth, cell_y + self.cell_size - self.shelf_depth),
            (cell_x + self.cell_size, cell_y + self.cell_size)
        ]
        draw.polygon(right_points, fill=shelf_dark, outline=shelf_edge)
        
        # Draw front opening outline
        front_rect = [cell_x, cell_y, cell_x + self.cell_size, cell_y + self.cell_size]
        draw.rectangle(front_rect, fill=None, outline=shelf_edge)
    
    def _draw_top_edge(self, draw: ImageDraw.Draw, grid: Grid, start_x: int, start_y: int):
        """
        Draw a top edge strip along the entire grid for better 3D perspective.
        
        Args:
            draw: PIL ImageDraw object
            grid: Grid object containing dimensions
            start_x: Starting X coordinate for grid
            start_y: Starting Y coordinate for grid
        """
        shelf_light = (200, 200, 200)  # Light gray for horizontal surfaces
        shelf_edge = (80, 80, 80)      # Edge color
        
        # Calculate top edge position
        top_y = start_y
        
        # Draw top edge strip across entire grid width
        top_points = [
            (start_x, top_y),
            (start_x + grid.width * self.cell_size, top_y),
            (start_x + grid.width * self.cell_size + self.shelf_depth, top_y - self.shelf_depth),
            (start_x + self.shelf_depth, top_y - self.shelf_depth)
        ]
        draw.polygon(top_points, fill=shelf_light, outline=shelf_edge)
    
    def _draw_right_edge(self, draw: ImageDraw.Draw, grid: Grid, start_x: int, start_y: int):
        """
        Draw a right edge strip along the entire grid for better 3D perspective.
        
        Args:
            draw: PIL ImageDraw object
            grid: Grid object containing dimensions
            start_x: Starting X coordinate for grid
            start_y: Starting Y coordinate for grid
        """
        shelf_dark = (120, 120, 120)   # Dark gray for vertical surfaces/sides
        shelf_edge = (80, 80, 80)      # Edge color
        
        # Calculate right edge position
        right_x = start_x + grid.width * self.cell_size
        
        # Draw right edge strip across entire grid height
        right_points = [
            (right_x, start_y),
            (right_x + self.shelf_depth, start_y - self.shelf_depth),
            (right_x + self.shelf_depth, start_y + grid.height * self.cell_size - self.shelf_depth),
            (right_x, start_y + grid.height * self.cell_size)
        ]
        draw.polygon(right_points, fill=shelf_dark, outline=shelf_edge)
    
    def _draw_director_image(self, img: Image.Image, director_image_path: str):
        """
        Draw the director image behind the grid.
        
        Args:
            img: PIL Image to draw on
            director_image_path: Path to the director image
        """
        try:
            # Size as proportion of full image (customize these values later)
            director_width = int(self.image_width * 0.4)  # 30% of image width
            director_height = int(self.image_height * 0.5)  # 40% of image height
            
            cache_key = (director_image_path, director_width, director_height)
            
            # Check resized cache first
            if cache_key in self.resized_image_cache:
                director_img = self.resized_image_cache[cache_key]
                # Move to end (most recently used)
                self.resized_image_cache.move_to_end(cache_key)
            else:
                # Check raw cache
                if director_image_path in self.raw_image_cache:
                    raw_director = self.raw_image_cache[director_image_path]
                    # Move to end (most recently used)
                    self.raw_image_cache.move_to_end(director_image_path)
                else:
                    # Load from disk and cache
                    raw_director = Image.open(director_image_path)
                    
                    # Convert palette images with transparency to RGBA to handle transparency properly
                    if raw_director.mode == 'P' and 'transparency' in raw_director.info:
                        raw_director = raw_director.convert('RGBA')
                    elif raw_director.mode != 'RGBA' and raw_director.mode != 'RGB':
                        raw_director = raw_director.convert('RGBA')
                    
                    self._cache_with_lru(self.raw_image_cache, director_image_path, raw_director)
                
                # Resize and cache (using thumbnail to maintain aspect ratio)
                director_img = raw_director.copy()
                director_img.thumbnail((director_width, director_height), Image.Resampling.LANCZOS)
                self._cache_with_lru(self.resized_image_cache, cache_key, director_img)
            
            # Position as proportion of full image (customize these values later)  
            director_x = int(self.image_width * 0.63)  
            director_y = int(self.image_height * 0.20)   
            
            # Always use alpha channel for transparency if available
            if director_img.mode == 'RGBA':
                img.paste(director_img, (director_x, director_y), director_img)
            else:
                img.paste(director_img, (director_x, director_y))
                
        except FileNotFoundError:
            print(f"Warning: Could not find director image at {director_image_path}")
            print("Continuing without director image...")
    
    def _draw_headings(self, draw: ImageDraw.Draw, grid: Grid, start_x: int, start_y: int):
        """
        Draw column letters (A, B, C...) and row numbers (1, 2, 3...)
        
        Args:
            draw: PIL ImageDraw object
            grid: Grid object containing dimensions
            start_x: Starting X coordinate for grid
            start_y: Starting Y coordinate for grid
        """
        font = None
        use_default_font = False
        
        # Try common system fonts with specified size
        font_names = ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "liberation-sans.ttf"]
        for font_name in font_names:
            cache_key = (font_name, self.text_size)
            
            # Check font cache first
            if cache_key in self.font_cache:
                font = self.font_cache[cache_key]
                # Move to end (most recently used)
                self.font_cache.move_to_end(cache_key)
                break
            
            try:
                font = ImageFont.truetype(font_name, self.text_size)
                self._cache_with_lru(self.font_cache, cache_key, font)
                break
            except (OSError, IOError):
                continue
        
        # If no TrueType font found, use default (but it won't scale)
        if font is None:
            default_cache_key = ("default", self.text_size)
            if default_cache_key in self.font_cache:
                font = self.font_cache[default_cache_key]
                # Move to end (most recently used)
                self.font_cache.move_to_end(default_cache_key)
                use_default_font = True
            else:
                try:
                    font = ImageFont.load_default()
                    self._cache_with_lru(self.font_cache, default_cache_key, font)
                    use_default_font = True
                except Exception:
                    font = None
        
        text_color = (0, 0, 0)  # Black text
        
        # Draw column letters (A, B, C, etc.)
        for col in range(grid.width):
            letter = chr(ord('A') + col)  # Convert to A, B, C, etc.
            text_x = start_x + col * self.cell_size + self.cell_size // 2
            text_y = start_y - (self.cell_size)  # Above the grid
            
            # Center the text horizontally
            if font:
                bbox = draw.textbbox((0, 0), letter, font=font)
                text_width = bbox[2] - bbox[0]
                text_x -= text_width // 2
            
            # For default font, simulate larger text by drawing multiple times with slight offsets
            if use_default_font and self.text_size > 12:
                offset_range = max(1, self.text_size // 20)  # Scale offset based on desired size
                for dx in range(-offset_range, offset_range + 1):
                    for dy in range(-offset_range, offset_range + 1):
                        draw.text((text_x + dx, text_y + dy), letter, fill=text_color, font=font)
            else:
                draw.text((text_x, text_y), letter, fill=text_color, font=font)
        
        # Draw row numbers (1, 2, 3, etc.)
        for row in range(grid.height):
            number = str(row + 1)  # 1-indexed
            text_x = start_x - self.cell_size  # To the left of the grid
            text_y = start_y + row * self.cell_size + self.cell_size // 2
            
            # Center the text vertically
            if font:
                bbox = draw.textbbox((0, 0), number, font=font)
                text_height = bbox[3] - bbox[1]
                text_y -= text_height // 2
            
            # For default font, simulate larger text by drawing multiple times with slight offsets
            if use_default_font and self.text_size > 12:
                offset_range = max(1, self.text_size // 20)  # Scale offset based on desired size
                for dx in range(-offset_range, offset_range + 1):
                    for dy in range(-offset_range, offset_range + 1):
                        draw.text((text_x + dx, text_y + dy), number, fill=text_color, font=font)
            else:
                draw.text((text_x, text_y), number, fill=text_color, font=font)
    
    def get_item_position(self, grid_row: int, grid_col: int) -> Tuple[int, int]:
        """
        Calculate the pixel coordinates where an item should be placed for a given grid position.
        Items are positioned to look like they're sitting on the shelf floor.
        
        Args:
            grid_row: Row in the grid
            grid_col: Column in the grid  
            
        Returns:
            Tuple of (x, y) pixel coordinates for item placement
        """
        # Calculate rectangular position using stored grid start coordinates
        cell_x = self.grid_start_x + grid_col * self.cell_size
        cell_y = self.grid_start_y + grid_row * self.cell_size
        
        # Position item centered horizontally, sitting on shelf floor (80% down from top)
        item_x = cell_x + self.shelf_depth
        item_y = cell_y 
        
        return (item_x, item_y)
    
    def get_item_size(self) -> int:
        """
        Get the recommended size for item images to fit nicely in shelf compartments.
        
        Returns:
            Size in pixels (80% of cell size for good fit with margins)
        """
        return int(self.cell_size * 0.8)
    
    def warmup_caches(self, items: List[Item]):
        """
        Pre-load caches with commonly used fonts and images.
        
        Args:
            items: List of items to pre-cache images for
        """
        # Pre-load ALL available fonts (not just the first one)
        font_names = ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "liberation-sans.ttf"]
        for font_name in font_names:
            cache_key = (font_name, self.text_size)
            if cache_key not in self.font_cache:
                try:
                    font = ImageFont.truetype(font_name, self.text_size)
                    self._cache_with_lru(self.font_cache, cache_key, font)
                except (OSError, IOError):
                    continue
        
        # Pre-load default font
        default_cache_key = ("default", self.text_size)
        if default_cache_key not in self.font_cache:
            try:
                font = ImageFont.load_default()
                self._cache_with_lru(self.font_cache, default_cache_key, font)
            except Exception:
                pass
        
        # Pre-load director image (raw and resized)
        if self.director_image_path:
            try:
                if self.director_image_path not in self.raw_image_cache:
                    raw_director = Image.open(self.director_image_path)
                    
                    # Convert palette images with transparency to RGBA to handle transparency properly
                    if raw_director.mode == 'P' and 'transparency' in raw_director.info:
                        raw_director = raw_director.convert('RGBA')
                    elif raw_director.mode != 'RGBA' and raw_director.mode != 'RGB':
                        raw_director = raw_director.convert('RGBA')
                    
                    self._cache_with_lru(self.raw_image_cache, self.director_image_path, raw_director)
                
                # Pre-load resized director image
                director_width = int(self.image_width * 0.4)
                director_height = int(self.image_height * 0.5)
                cache_key = (self.director_image_path, director_width, director_height)
                
                if cache_key not in self.resized_image_cache:
                    raw_director = self.raw_image_cache[self.director_image_path]
                    resized_director = raw_director.copy()
                    resized_director.thumbnail((director_width, director_height), Image.Resampling.LANCZOS)
                    self._cache_with_lru(self.resized_image_cache, cache_key, resized_director)
                    
            except FileNotFoundError:
                print(f"Warning: Could not find director image at {self.director_image_path} during warmup")
        
        # Pre-load item images (raw and resized)
        item_size = self.get_item_size()
        for item in items:
            image_path = f"director_task/{item.image_path}"
            
            try:
                # Load raw image if not cached
                if image_path not in self.raw_image_cache:
                    raw_image = Image.open(image_path)

                    # Convert palette images with transparency to RGBA to handle transparency properly
                    if raw_image.mode == 'P' and 'transparency' in raw_image.info:
                        raw_image = raw_image.convert('RGBA')
                    elif raw_image.mode != 'RGBA' and raw_image.mode != 'RGB':
                        raw_image = raw_image.convert('RGBA')

                    self._cache_with_lru(self.raw_image_cache, image_path, raw_image)
                
                # Load resized image if not cached
                resize_cache_key = (image_path, item_size, item_size)
                if resize_cache_key not in self.resized_image_cache:
                    raw_image = self.raw_image_cache[image_path]
                    resized_image = raw_image.resize((item_size, item_size), Image.Resampling.LANCZOS)
                    self._cache_with_lru(self.resized_image_cache, resize_cache_key, resized_image)
                    
            except FileNotFoundError:
                print(f"Warning: Could not find item image at {item.image_path} during warmup")
    
    def _cache_with_lru(self, cache: OrderedDict, key, value):
        """
        Add an item to cache with LRU eviction.
        
        Args:
            cache: The OrderedDict cache to add to
            key: The cache key
            value: The value to cache
        """
        # If key already exists, move to end
        if key in cache:
            cache.move_to_end(key)
            return
        
        # Add new item
        cache[key] = value
        
        # Evict oldest items if cache is full
        while len(cache) > self.cache_size:
            cache.popitem(last=False)  # Remove oldest item
    
    def clear_caches(self):
        """
        Clear all caches. Useful for testing and memory management.
        """
        self.font_cache.clear()
        self.raw_image_cache.clear()
        self.resized_image_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics for monitoring.
        
        Returns:
            Dict with cache sizes and limits
        """
        return {
            "font_cache_size": len(self.font_cache),
            "raw_image_cache_size": len(self.raw_image_cache),
            "resized_image_cache_size": len(self.resized_image_cache),
            "cache_size_limit": self.cache_size
        }