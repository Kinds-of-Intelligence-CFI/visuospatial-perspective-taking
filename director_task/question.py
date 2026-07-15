from typing import Optional, Dict, Any
from enum import Enum
import json
import os
from director_task.grid import Grid


class SelectionRuleType(Enum):
    """Enum for different types of selection rules"""
    SIZE_RELATED = "size_related"
    SPATIAL_SAME_PERSPECTIVE = "spatial_same_perspective"
    SPATIAL_DIFFERENT_PERSPECTIVE = "spatial_different_perspective"
    NONE = "none"


class QuestionConstraints:
    """Represents constraints for generating questions with specific characteristics"""
    
    def __init__(self, selection_rule_type: SelectionRuleType, is_physics: bool):
        self.selection_rule_type = selection_rule_type  # Type of selection rule to use
        self.is_physics = is_physics    # Whether question involves physics-related properties
    
    @property
    def PHYSICS_PROPERTIES(self):
        """Get physics properties from Question class"""
        return Question.get_all_physics_properties()
    
    def get_selection_rules(self) -> list[Optional[str]]:
        """Map from SelectionRuleType to actual selection rules"""
        if self.selection_rule_type == SelectionRuleType.SIZE_RELATED:
            return ["smallest", "largest"]
        elif self.selection_rule_type == SelectionRuleType.SPATIAL_SAME_PERSPECTIVE:
            return ["topmost", "bottommost"]
        elif self.selection_rule_type == SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE:
            return ["leftmost", "rightmost"]
        elif self.selection_rule_type == SelectionRuleType.NONE:
            return [None]
        else:
            raise ValueError(f"Unknown selection rule type: {self.selection_rule_type}")
    


class Question:
    # Cache for property mappings loaded from defaults.json
    _property_to_string_cache = None
    
    # English adjective order categories based on properties from defaults.json
    ADJECTIVE_CATEGORIES = {
        "size": ["small", "large"],
        "shape": ["star", "circle"],
        "color": ["red", "blue", "brown", "yellow", "orange", "black", "purple", "green"],
        "material": ["lego"],
        "category": ["Music_instument", "fruit", "bag", "book", "calculator", "shoe", "camera", 
                    "clothes", "shirt", "plant", "socks", "dress", "car"],  # Only these can be target types
        "quality": ["is_food", "is_sweet", "stackable", "sharp", "hot", "used_for_cooking", 
                   "holds_water", "valuable", "cold", "holds_money"]  # Some of these are physics-related
    }
    
    # Physics properties (subset of quality properties only)
    PHYSICS_PROPERTIES = ["stackable", "sharp", "hot", "cold"]  # Only these qualities are physics-related
    
    @classmethod
    def _load_property_to_string(cls):
        """Load property names from defaults.json and apply manual overrides"""
        if cls._property_to_string_cache is not None:
            return cls._property_to_string_cache
            
        # Load all properties from defaults.json
        defaults_path = os.path.join(os.path.dirname(__file__), "defaults.json")
        try:
            with open(defaults_path, 'r') as f:
                defaults = json.load(f)
            
            # Start with all boolean properties using their property name as the string
            property_mapping = {}
            for prop_name in defaults.get("boolean_properties", {}):
                # Default: use property name, cleaned up
                clean_name = prop_name.replace("is_", "").replace("has_", "").replace("_", " ")
                property_mapping[prop_name] = clean_name
            
            # Manual overrides for specific properties that need better natural language
            manual_overrides = {
                "Music_instument": "musical instrument",  # Note: there's a typo in defaults.json
                "used_for_cooking": "cooking utensil",
                "holds_water": "water container", 
                "holds_money": "money container",
                "is_food": "food",
                "is_sweet": "sweet",
                # Add more overrides as needed
            }
            
            # Apply manual overrides
            property_mapping.update(manual_overrides)
            
            cls._property_to_string_cache = property_mapping
            return property_mapping
            
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Fallback to basic mapping if defaults.json can't be loaded
            print(f"Warning: Could not load defaults.json for property mapping: {e}")
            fallback_mapping = {
                "star": "star", "circle": "circle", "car": "car",
                "red": "red", "blue": "blue", "small": "small", "large": "large"
            }
            cls._property_to_string_cache = fallback_mapping
            return fallback_mapping
    
    @classmethod
    def get_property_to_string(cls):
        """Get the property to string mapping, loading it if necessary"""
        return cls._load_property_to_string()
    
    @classmethod
    def get_properties_by_category(cls, category: str) -> list[str]:
        """Get all properties in a specific adjective category"""
        return cls.ADJECTIVE_CATEGORIES.get(category, [])
    
    @classmethod
    def get_all_target_types(cls) -> list[str]:
        """Get all properties that can be used as target types (category properties)"""
        return cls.ADJECTIVE_CATEGORIES["category"]
    
    @classmethod
    def get_all_colors(cls) -> list[str]:
        """Get all color properties"""
        return cls.ADJECTIVE_CATEGORIES["color"]
    
    @classmethod
    def get_all_physics_properties(cls) -> list[str]:
        """Get all physics-related properties (subset of quality)"""
        return cls.PHYSICS_PROPERTIES
    
    @classmethod
    def get_all_non_physics_properties(cls) -> list[str]:
        """Get all non-physics properties from all categories"""
        non_physics = []
        for category, properties in cls.ADJECTIVE_CATEGORIES.items():
            if category != "quality":
                non_physics.extend(properties)
            else:
                # For quality, only include non-physics properties
                non_physics.extend([prop for prop in properties if prop not in cls.PHYSICS_PROPERTIES])
        return non_physics
    
    @classmethod
    def categorize_property(cls, property_name: str) -> str:
        """Find which category a property belongs to, returns 'quality' as default"""
        for category, properties in cls.ADJECTIVE_CATEGORIES.items():
            if property_name in properties:
                return category
        return "quality"  # Default fallback as specified by user
    
    # Property for backward compatibility
    @property
    def PROPERTY_TO_STRING(self):
        return self.__class__.get_property_to_string()
    question_prefix = "Please select "
    
    def __init__(self, target_type: str, filter_criteria: dict, 
                 selection_rule: Optional[str] = None, 
                 selection_property: Optional[str] = None,
                 selection_rule_type: Optional[SelectionRuleType] = None,
                 is_reversed: bool = False):
        self.target_type = target_type  # "star", "car", "item" 
        self.filter_criteria = filter_criteria  # {"star": True, "red": True}
        self.selection_rule = selection_rule  # "smallest", "largest", "leftmost", "rightmost", "topmost", None
        self.selection_property = selection_property  # "size", "x_position", "y_position", None
        self.selection_rule_type = selection_rule_type  # Type of selection rule (size-related, spatial, etc.)
        self.is_reversed = is_reversed  # Whether spatial question is from director's perspective
        
    def find_target(self, grid: Grid) -> set[tuple[int, int]]:
        matching_items = []
        
        # Find all items that match the boolean filter criteria
        for y in range(grid.height):
            for x in range(grid.width):
                item = grid.item_grid[y][x]
                if item is None:
                    continue
                    
                # Check if item matches all filter criteria
                matches = True
                for prop_name, required_value in self.filter_criteria.items():
                    if item.boolean_properties.get(prop_name, False) != required_value:
                        matches = False
                        break
                        
                if matches:
                    matching_items.append((x, y, item))
        
        if not matching_items:
            raise ValueError(f"No items found matching criteria: {self.filter_criteria}")
            
        # If no selection rule, return all matches
        if self.selection_rule is None:
            return {(x, y) for x, y, item in matching_items}
            
        # Apply selection rule
        if self.selection_rule == "smallest":
            min_value = min(item.scalar_properties.get(self.selection_property, float('inf')) 
                           for x, y, item in matching_items)
            return {(x, y) for x, y, item in matching_items 
                   if item.scalar_properties.get(self.selection_property, float('inf')) == min_value}
        elif self.selection_rule == "largest":
            max_value = max(item.scalar_properties.get(self.selection_property, float('-inf')) 
                           for x, y, item in matching_items)
            return {(x, y) for x, y, item in matching_items 
                   if item.scalar_properties.get(self.selection_property, float('-inf')) == max_value}
        elif self.selection_rule == "leftmost":
            min_x = min(x for x, y, item in matching_items)
            return {(x, y) for x, y, item in matching_items if x == min_x}
        elif self.selection_rule == "rightmost":
            max_x = max(x for x, y, item in matching_items)
            return {(x, y) for x, y, item in matching_items if x == max_x}
        elif self.selection_rule == "topmost":
            min_y = min(y for x, y, item in matching_items) 
            return {(x, y) for x, y, item in matching_items if y == min_y}
        elif self.selection_rule == "bottommost":
            max_y = max(y for x, y, item in matching_items) 
            return {(x, y) for x, y, item in matching_items if y == max_y}
        else:
            raise ValueError(f"Unknown selection rule: {self.selection_rule}")

    def full_question(self) -> str:
        # returns the full version of the question with fluff
        return Question.question_prefix + self.to_natural_language()

    def to_natural_language(self, add_perspective_suffix: bool = True) -> str:
        # returns a natural language description of the question in minimal form.
        # for example "The red car" or "The smallest candle" with out the fluff

        # Build adjective list from filter criteria, excluding the target type
        # Group adjectives by their category to ensure proper English adjective order
        adjectives_by_category: dict[str, list[str]] = {
            "size": [],
            "shape": [],
            "color": [],
            "material": [],
            "quality": []
        }
        
        for prop_name, value in self.filter_criteria.items():
            if value:  # Only include properties that are True
                # Don't include the target type as an adjective
                if prop_name == self.target_type:
                    continue
                # Also don't include other target types (category properties) 
                if self.categorize_property(prop_name) == "category":
                    continue
                    
                if prop_name in self.PROPERTY_TO_STRING:
                    adjective = self.PROPERTY_TO_STRING[prop_name]
                else:
                    # Fallback: use property name directly, removing common prefixes
                    adjective = prop_name.replace("is_", "").replace("has_", "").replace("_", " ")
                
                # Categorize and add to appropriate list
                category = self.categorize_property(prop_name)
                if category in adjectives_by_category:
                    adjectives_by_category[category].append(adjective)
                else:
                    # Fallback to quality for uncategorized properties
                    adjectives_by_category["quality"].append(adjective)
        
        # Build adjectives in proper English order: size, shape, color, material, quality
        ordered_adjectives = []
        for category in ["size", "shape", "color", "material", "quality"]:
            ordered_adjectives.extend(adjectives_by_category[category])
        
        # Build the phrase
        phrase_parts = ["the"]
        
        if self.selection_rule:
            # For reversed spatial questions, flip leftmost/rightmost
            if self.is_reversed and self.selection_rule in ["leftmost", "rightmost"]:
                if self.selection_rule == "leftmost":
                    phrase_parts.append("rightmost")  # Director's left becomes participant's right
                elif self.selection_rule == "rightmost":
                    phrase_parts.append("leftmost")   # Director's right becomes participant's left
            else:
                phrase_parts.append(self.selection_rule)
            
            # For size-based selection rules, don't include size adjectives to avoid redundancy
            if self.selection_rule in ["smallest", "largest"]:
                # Remove size adjectives since they're implied by the selection rule
                ordered_adjectives = [adj for adj in ordered_adjectives 
                                    if adj not in Question.get_properties_by_category("size")]
            
        phrase_parts.extend(ordered_adjectives)
        phrase_parts.append(self.target_type)
        
        result = " ".join(phrase_parts)
        
        # Add perspective suffix if requested
        if add_perspective_suffix:
            if self.is_reversed:
                result += " from my point of view"
            else:
                result += " from your point of view"
        
        return result

    @classmethod
    def from_dict(cls, question_data: Dict[str, Any]) -> 'Question':
        """Create a Question object from its JSON representation (as saved in datasets)
        
        Args:
            question_data: Dictionary containing question data from JSON dataset
        
        Returns:
            Question object reconstructed from the data
        
        Raises:
            ValueError: If question_data is not a standard question or has invalid data
        """
        # Verify this is a standard question
        if question_data.get('question_type') != 'standard':
            raise ValueError(f"Expected standard question, got: {question_data.get('question_type')}")
        
        # Convert selection_rule_type string back to enum
        selection_rule_type_str = question_data.get('selection_rule_type')
        if selection_rule_type_str:
            try:
                selection_rule_type = SelectionRuleType(selection_rule_type_str)
            except ValueError:
                raise ValueError(f"Invalid selection_rule_type: {selection_rule_type_str}")
        else:
            selection_rule_type = None
        
        # Create Question object with original parameters
        return cls(
            target_type=question_data['target_type'],
            filter_criteria=question_data['filter_criteria'],
            selection_rule=question_data.get('selection_rule'),
            selection_property=question_data.get('selection_property'),
            selection_rule_type=selection_rule_type,
            is_reversed=question_data.get('is_reversed', False)
        )


class RelationalQuestion:
    """Question that involves spatial relationships between objects"""
    
    def __init__(self, reference_criteria: dict, spatial_relation: str, 
                 target_criteria: Optional[dict] = None, is_reversed: bool = False):
        """
        Initialize a relational question.
        
        Args:
            reference_criteria: Properties of the reference object (e.g., {"blue": True, "car": True})
            spatial_relation: Spatial relationship ("right_of", "left_of", "above", "below") 
            target_criteria: Properties target must have (None for any object)
            is_reversed: Whether question is from director's perspective
        """
        self.reference_criteria = reference_criteria
        self.spatial_relation = spatial_relation
        self.target_criteria = target_criteria  # None for now, could be used later
        self.is_reversed = is_reversed
        
    def find_target(self, grid: Grid) -> set[tuple[int, int]]:
        """Find all positions that satisfy the relational constraint"""
        # 1. Find reference object(s) that match reference criteria
        reference_positions = self._find_reference_objects(grid)
        
        if not reference_positions:
            raise ValueError(f"No reference objects found matching criteria: {self.reference_criteria}")
        
        # 2. For each reference, find objects in the specified spatial relation
        target_positions = set()
        for ref_pos in reference_positions:
            related_positions = self._find_spatially_related_objects(grid, ref_pos)
            target_positions.update(related_positions)
            
        return target_positions
        
    def _find_reference_objects(self, grid: Grid) -> set[tuple[int, int]]:
        """Find all objects that match the reference criteria"""
        matching_positions = set()
        
        for y in range(grid.height):
            for x in range(grid.width):
                item = grid.item_grid[y][x]
                if item is None:
                    continue
                    
                # Check if item matches all reference criteria
                matches = True
                for prop_name, required_value in self.reference_criteria.items():
                    if item.boolean_properties.get(prop_name, False) != required_value:
                        matches = False
                        break
                        
                if matches:
                    matching_positions.add((x, y))
                    
        return matching_positions
        
    def _find_spatially_related_objects(self, grid: Grid, reference_pos: tuple[int, int]) -> set[tuple[int, int]]:
        """Find objects in spatial relation to the reference position"""
        related_positions = set()
        
        for y in range(grid.height):
            for x in range(grid.width):
                if grid.item_grid[y][x] is None:
                    continue
                    
                # Skip the reference object itself
                if (x, y) == reference_pos:
                    continue
                    
                if self._is_in_spatial_relation((x, y), reference_pos):
                    # Apply target criteria if specified (for future use)
                    if self.target_criteria is None:
                        related_positions.add((x, y))
                    else:
                        # Check target criteria when implemented
                        item = grid.item_grid[y][x]
                        matches_target = True
                        for prop_name, required_value in self.target_criteria.items():
                            if item.boolean_properties.get(prop_name, False) != required_value:
                                matches_target = False
                                break
                        if matches_target:
                            related_positions.add((x, y))
                        
        return related_positions
        
    def _is_in_spatial_relation(self, pos: tuple[int, int], ref_pos: tuple[int, int]) -> bool:
        """Check if pos is in the specified spatial relation to ref_pos"""
        x, y = pos
        ref_x, ref_y = ref_pos
        
        if self.spatial_relation == "right_of":
            return x > ref_x and y == ref_y  # Same row, to the right
        elif self.spatial_relation == "left_of":
            return x < ref_x and y == ref_y  # Same row, to the left
        elif self.spatial_relation == "above":
            return y < ref_y and x == ref_x  # Same column, above
        elif self.spatial_relation == "below":
            return y > ref_y and x == ref_x  # Same column, below
        else:
            raise ValueError(f"Unknown spatial relation: {self.spatial_relation}")
            
    def to_natural_language(self, add_perspective_suffix: bool = True) -> str:
        """Generate natural language description of the relational question"""
        # Build reference object description
        ref_adjectives = []
        target_type = None
        
        for prop_name, value in self.reference_criteria.items():
            if value:
                property_mapping = Question.get_property_to_string()
                if prop_name in property_mapping:
                    adjective = property_mapping[prop_name]
                    if prop_name in ["star", "car", "circle"]:
                        target_type = prop_name
                    else:
                        ref_adjectives.append(adjective)
                        
        ref_description = " ".join(ref_adjectives + [target_type]) if target_type else " ".join(ref_adjectives + ["object"])
        
        # Convert spatial relation to natural language
        relation_map = {
            "right_of": "to the right of",
            "left_of": "to the left of", 
            "above": "above",
            "below": "below"
        }
        
        relation_phrase = relation_map.get(self.spatial_relation, self.spatial_relation)
        
        result = f"the object {relation_phrase} the {ref_description}"
        
        # Add perspective suffix if requested
        if add_perspective_suffix:
            if self.is_reversed:
                result += " from my point of view"
            else:
                result += " from your point of view"
        
        return result
            
    def full_question(self) -> str:
        """Return the full question with prefix"""
        return Question.question_prefix + self.to_natural_language()