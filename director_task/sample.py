import random
from typing import List, Optional, Union
from director_task.item import Item
from director_task.grid import Grid
from director_task.question import Question, QuestionConstraints, RelationalQuestion, SelectionRuleType


class GridGenerationError(Exception):
    """Raised when grid generation fails due to incompatible items/questions but could succeed with different inputs"""
    pass


"""
COORDINATE SYSTEM REFERENCE:
- Coordinates are stored as (x, y) tuples where x=column, y=row
- Grid access uses [row][col] pattern: grid.item_grid[y][x] or grid.blocks[y][x]
- x increases left-to-right (column index)
- y increases top-to-bottom (row index)
- Grid dimensions: width = columns, height = rows
"""


class Sample:
    def __init__(self, grid: Grid, question: Union[Question, RelationalQuestion], answer_coordinates: set[tuple[int, int]], 
                 director_answer_coordinates: set[tuple[int, int]] = None,
                 selection_rule_type: SelectionRuleType = SelectionRuleType.NONE, 
                 is_physics: bool = False, is_reversed: bool = False):
        """
        Initialize a Sample with grid, question, and answer coordinates.
        
        Args:
            answer_coordinates: Set of (x, y) tuples where x=column, y=row
            director_answer_coordinates: Set of (x, y) tuples for director's perspective
            selection_rule_type: Type of selection rule used in this sample
            is_physics: Whether this sample uses physics-related question constraints
            is_reversed: Whether spatial question is from director's perspective
        """
        self.grid = grid
        self.question = question
        self.answer_coordinates = answer_coordinates  # Set of (x, y) = (col, row) tuples
        self.selection_rule_type = selection_rule_type  # Type of selection rule used
        self.is_physics = is_physics  # Whether question uses physics constraints
        self.is_reversed = is_reversed  # Whether spatial question is reversed
        
        # Calculate director's answer if not provided
        if director_answer_coordinates is None:
            director_grid = grid.get_director_perspective()
            self.director_answer_coordinates = question.find_target(director_grid)
        else:
            self.director_answer_coordinates = director_answer_coordinates
        
        
    @classmethod
    def from_single_answer(cls, grid: Grid, question: Union[Question, RelationalQuestion], answer_col: int, answer_row: int,
                          selection_rule_type: SelectionRuleType = SelectionRuleType.NONE, 
                          is_physics: bool = False, is_reversed: bool = False):
        """Create sample with single answer coordinate.
        
        Args:
            answer_col: Column position (x coordinate, 0-based from left)
            answer_row: Row position (y coordinate, 0-based from top)
            selection_rule_type: Type of selection rule used in this sample
            is_physics: Whether this sample uses physics-related question constraints
            is_reversed: Whether spatial question is from director's perspective
        """
        return cls(grid, question, {(answer_col, answer_row)}, 
                  selection_rule_type=selection_rule_type, is_physics=is_physics, is_reversed=is_reversed)  # Store as (x, y) = (col, row)
        
    def verify_answer(self) -> bool:
        """Verify that the question's find_target method returns the expected coordinates"""
        expected = self.question.find_target(self.grid)
        return expected == self.answer_coordinates
    
    def has_ambiguous_answer(self) -> bool:
        """Check if the question has different answers from participant vs director perspective"""
        # Get answer from participant's perspective (full grid)
        participant_answer = self.question.find_target(self.grid)
        
        # Get answer from director's perspective (blocked items treated as None)
        director_grid = self.grid.get_director_perspective()
        director_answer = self.question.find_target(director_grid)
        
        # Return True if answers are different (ambiguous)
        return participant_answer != director_answer

    @classmethod
    def generate_control_samples(cls, items: List[Item], grid_width: int, grid_height: int, num_samples: int, 
                               item_fill_ratio: float = 0.5, block_ratio: float = 0.4,
                               size_prop: float = 0.25, spatial_same_prop: float = 0.25, 
                               spatial_diff_prop: float = 0.25, physics_prop: float = 0.5,
                               related_item_prop: float = 0.3) -> List['Sample']:
        """Generate control samples with no ambiguity between participant and director perspectives"""
        samples = []
        
        # Validate that proportions don't exceed 1.0
        if size_prop + spatial_same_prop + spatial_diff_prop > 1.0:
            raise ValueError(f"Size, spatial_same, and spatial_diff proportions cannot exceed 1.0. "
                           f"Got: {size_prop} + {spatial_same_prop} + {spatial_diff_prop} = "
                           f"{size_prop + spatial_same_prop + spatial_diff_prop}")
        
        # Calculate exact counts for each of the 4 selection rule categories with rounding compensation
        size_count = int(num_samples * size_prop)
        spatial_same_count = int(num_samples * spatial_same_prop)
        spatial_diff_count = int(num_samples * spatial_diff_prop)
        none_count = num_samples - (size_count + spatial_same_count + spatial_diff_count)  # Handle rounding compensation
        
        # Create constraint assignment list ensuring all combinations are represented
        constraint_assignments = []
        
        # For each selection rule type, distribute samples between physics and non-physics proportionally
        selection_rule_counts = {
            SelectionRuleType.SIZE_RELATED: size_count,
            SelectionRuleType.SPATIAL_SAME_PERSPECTIVE: spatial_same_count,
            SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE: spatial_diff_count,
            SelectionRuleType.NONE: none_count
        }
        
        for rule_type, rule_count in selection_rule_counts.items():
            if rule_count > 0:
                # Distribute physics/non-physics proportionally within each rule type
                physics_for_rule = int(rule_count * physics_prop)
                non_physics_for_rule = rule_count - physics_for_rule
                
                # Add physics=True combinations for this rule type
                constraint_assignments.extend([(rule_type, True)] * physics_for_rule)
                # Add physics=False combinations for this rule type  
                constraint_assignments.extend([(rule_type, False)] * non_physics_for_rule)
        
        # Shuffle to ensure random distribution across samples instead of deterministic assignment
        random.shuffle(constraint_assignments)
        
        
        for selection_rule_type, is_physics in constraint_assignments:
            constraints = QuestionConstraints(selection_rule_type, is_physics)
            
            # Retry grid generation with different questions if GridGenerationError occurs
            max_retries = 200
            for attempt in range(max_retries):
                try:
                    # Create question with constraints
                    question = cls._generate_constrained_question(items, constraints)
                    
                    # Create grid that satisfies the question without ambiguity
                    grid = cls._create_grid_for_question(items, question, grid_width, grid_height, item_fill_ratio, block_ratio, related_item_prop)
                    break  # Success, exit retry loop
                except GridGenerationError as e:
                    if attempt == max_retries - 1:
                        # Final attempt failed, raise with context
                        raise GridGenerationError(f"Failed to generate control sample after {max_retries} attempts. "
                                                f"Selection rule: {selection_rule_type}, Physics: {is_physics}. "
                                                f"question: {question.to_natural_language()}\n"
                                                f"Last error: {str(e)}")
                    # Continue to next attempt with new question
            
            # Simplify question by removing unnecessary adjectives
            question = cls._simplify_question(question, grid, constraints)
            
            # Get the expected answer
            answer_coords = question.find_target(grid)
            
            # Create sample and verify it's not ambiguous
            sample = cls(grid, question, answer_coords, selection_rule_type=selection_rule_type, is_physics=is_physics, is_reversed=question.is_reversed)
            
            # Ensure no ambiguity (should always pass for control samples)
            if sample.has_ambiguous_answer():
                raise RuntimeError(f"Generated ambiguous control sample - this should not happen\n question: {sample.question.to_natural_language()}\n director answer: {sample.director_answer_coordinates}\n participant answers: {sample.answer_coordinates} grid layout:\n{grid.pretty_print()}")
                
            samples.append(sample)
        
        return samples
    
    @classmethod
    def add_related_items_unambiguous(cls, grid: Grid, question: Union[Question, RelationalQuestion], target_item: Item, items: List[Item], num_related_items: int) -> None:
        """Add related items to the grid that match the question criteria without changing the answer."""
        width, height = grid.width, grid.height
        
        # Find the target item in the grid (there should only be 1 item in the grid)
        target_positions = []
        for y in range(height):
            for x in range(width):
                if grid.item_grid[y][x] is not None:
                    target_positions.append((x, y))  # Store as (x, y) = (col, row)
        
        # Validate that there is exactly one item in the grid
        if len(target_positions) == 0:
            raise ValueError("Grid must contain exactly one item, but found 0 items")
        elif len(target_positions) > 1:
            raise ValueError(f"Grid must contain exactly one item, but found {len(target_positions)} items at positions: {target_positions}")
        
        # Get the target position
        target_col, target_row = target_positions[0]  # Unpack (x, y) = (col, row)
        
        # Verify that the item at this position matches the provided target_item
        grid_item = grid.item_grid[target_row][target_col]
        if grid_item is None:
            raise ValueError("Expected an item at the target position but found None")
        if (grid_item.boolean_properties != target_item.boolean_properties or 
            grid_item.scalar_properties != target_item.scalar_properties):
            raise ValueError("The item found in the grid does not match the provided target_item")

        # next check we can add the items to the grid without errors
        if question.selection_rule_type is None:
            raise ValueError("Question must have a selection rule if related items are present")
        
        if question.selection_rule_type == SelectionRuleType.SIZE_RELATED:
            # Check if there are other items that match the same filter criteria but have the right size relationship
            matching_items = []
            target_size = target_item.scalar_properties.get(question.selection_property, 0)
            
            for item in items:
                # Check if this item matches all filter criteria
                matches_criteria = True
                for prop_name, required_value in question.filter_criteria.items():
                    item_value = item.boolean_properties.get(prop_name, False)
                    if item_value != required_value:
                        matches_criteria = False
                        break
                
                if matches_criteria:
                    item_size = item.scalar_properties.get(question.selection_property, 0)
                    
                    # Check size relationship based on selection rule
                    if question.selection_rule == "largest":
                        # For largest rule, related items should be smaller than target
                        if item_size < target_size:
                            matching_items.append(item)
                    elif question.selection_rule == "smallest":
                        # For smallest rule, related items should be larger than target
                        if item_size > target_size:
                            matching_items.append(item)
            
            if not matching_items:
                raise GridGenerationError(f"No items in pool can serve as related items for {question.selection_rule} selection rule. "
                                        f"Target {question.selection_property}: {target_size}, "
                                        f"Need items with {'smaller' if question.selection_rule == 'largest' else 'larger'} {question.selection_property}")
            
            related_item_positions = [(x, y) for x in range(width) for y in range(height) if (x, y) != (target_col, target_row)]  # Positions stored as (x,y) = (col,row)
        elif question.selection_rule_type in [SelectionRuleType.SPATIAL_SAME_PERSPECTIVE, SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE]:
            # For spatial selection rules, get positions based on the rule
            if question.selection_rule == "topmost":
                # Get positions below the target item
                if target_row == height - 1:
                    raise GridGenerationError("Target item cannot be at the bottom row for topmost selection rule")
                related_item_positions = [(x, y) for x in range(width) for y in range(target_row + 1, height)]
            elif question.selection_rule == "bottommost":
                # Get positions above the target item
                if target_row == 0:
                    raise GridGenerationError("Target item cannot be at the top row for bottommost selection rule")
                related_item_positions = [(x, y) for x in range(width) for y in range(0, target_row)]
            elif question.selection_rule == "leftmost":
                # Get positions to the right of the target item
                if target_col == width - 1:
                    raise GridGenerationError("Target item cannot be at the rightmost column for leftmost selection rule")
                related_item_positions = [(x, y) for x in range(target_col + 1, width) for y in range(height)]
            elif question.selection_rule == "rightmost":
                # Get positions to the left of the target item
                if target_col == 0:
                    raise GridGenerationError("Target item cannot be at the leftmost column for rightmost selection rule")
                related_item_positions = [(x, y) for x in range(0, target_col) for y in range(height)]
        else:
            raise ValueError(f"Unsupported spatial selection rule: {question.selection_rule}")
        # Select positions for related items
        if related_item_positions:
            # For spatial rules, check if we have enough selection positions for related items
            if len(related_item_positions) < num_related_items:
                raise GridGenerationError(f"Not enough selection positions ({len(related_item_positions)}) for required related items ({num_related_items})")
            
            # Place related items in selection positions first
            related_positions = random.sample(related_item_positions, num_related_items)
        else:
            # when the selection rule is not spatial, we can just randomly select positions for related and unrelated items
            item_positions = random.sample([(x, y) for x in range(width) for y in range(height) if (x, y) != (target_col, target_row)], width * height - 1)
            related_positions = item_positions[:num_related_items]

        # Place related items (match filter criteria)
        for x, y in related_positions:  # x=col, y=row
            if question.selection_rule_type == SelectionRuleType.SIZE_RELATED:
                # For size-based rules, use the pre-validated matching items
                selected_item = random.choice(matching_items)
                related_item = Item(
                    name=selected_item.name,
                    image_path=selected_item.image_path,
                    boolean_properties=selected_item.boolean_properties.copy(),
                    scalar_properties=selected_item.scalar_properties.copy()
                )
            else:
                # For other rules, use the standard method
                related_item = Sample._create_director_item(items, question)
            grid.item_grid[y][x] = related_item  # Grid access: [row][col] = [y][x]
            
    @classmethod
    def add_unrelated_items_random(cls, grid: Grid, question: Union[Question, RelationalQuestion], target_item: Item, items: List[Item], num_unrelated_items: int) -> None:
        """Add unrelated items to the grid at random positions that don't match the question criteria."""
        width, height = grid.width, grid.height
        
        # Find all occupied positions in the grid
        occupied_positions = []
        for y in range(height):
            for x in range(width):
                if grid.item_grid[y][x] is not None:
                    occupied_positions.append((x, y))  # Store as (x, y) = (col, row)
        
        # Get all available positions (not occupied)
        available_positions = [(x, y) for x in range(width) for y in range(height) 
                              if (x, y) not in occupied_positions]
        
        # Check if we have enough available positions
        if len(available_positions) < num_unrelated_items:
            raise GridGenerationError(f"Not enough available positions ({len(available_positions)}) for required unrelated items ({num_unrelated_items})")
        
        # Select random positions for unrelated items
        unrelated_positions = random.sample(available_positions, num_unrelated_items)
        
        # Place unrelated items (don't match filter criteria)
        for x, y in unrelated_positions:  # x=col, y=row
            distractor_item = Sample._create_distractor_item(items, question)
            grid.item_grid[y][x] = distractor_item  # Grid access: [row][col] = [y][x]

    @classmethod
    def add_related_items_random(cls, grid: Grid, question: Union[Question, RelationalQuestion], target_item: Item, items: List[Item], num_related_items: int) -> None:
        """Add related items to the grid at random positions that match the question criteria, ignoring ambiguity effects."""
        width, height = grid.width, grid.height
        
        # Find all occupied positions in the grid
        occupied_positions = []
        for y in range(height):
            for x in range(width):
                if grid.item_grid[y][x] is not None:
                    occupied_positions.append((x, y))  # Store as (x, y) = (col, row)
        
        # Get all available positions (not occupied)
        available_positions = [(x, y) for x in range(width) for y in range(height) 
                              if (x, y) not in occupied_positions]
        
        # Check if we have enough available positions
        if len(available_positions) < num_related_items:
            raise GridGenerationError(f"Not enough available positions ({len(available_positions)}) for required related items ({num_related_items})")
        
        # Select random positions for related items
        related_positions = random.sample(available_positions, num_related_items)
        
        # Place related items (match filter criteria)
        for x, y in related_positions:  # x=col, y=row
            related_item = Sample._create_director_item(items, question)
            grid.item_grid[y][x] = related_item  # Grid access: [row][col] = [y][x]
            grid.blocks[y][x] = 1  # Ensure the cell is blocked from director's perspective

    @classmethod
    def generate_test_samples(cls, items: List[Item], grid_width: int, grid_height: int, num_samples: int, 
                             item_fill_ratio: float = 0.5, block_ratio: float = 0.4,
                             size_prop: float = 0.25, spatial_same_prop: float = 0.25, 
                             spatial_diff_prop: float = 0.25, physics_prop: float = 0.5,
                             related_item_prop: float = 0.3, related_blocked_prop: float = 0.5) -> List['Sample']:
        """Generate test samples with ambiguity between participant and director perspectives"""
        samples = []
        
        # Validate that proportions don't exceed 1.0
        if size_prop + spatial_same_prop + spatial_diff_prop > 1.0:
            raise ValueError(f"Size, spatial_same, and spatial_diff proportions cannot exceed 1.0. "
                           f"Got: {size_prop} + {spatial_same_prop} + {spatial_diff_prop} = "
                           f"{size_prop + spatial_same_prop + spatial_diff_prop}")
        
        # Calculate exact counts for each of the 4 selection rule categories with rounding compensation
        size_count = int(num_samples * size_prop)
        spatial_same_count = int(num_samples * spatial_same_prop)
        spatial_diff_count = int(num_samples * spatial_diff_prop)
        none_count = num_samples - (size_count + spatial_same_count + spatial_diff_count)  # Handle rounding compensation
        
        # Create constraint assignment list ensuring all combinations are represented
        constraint_assignments = []
        
        # For each selection rule type, distribute samples between physics and non-physics proportionally
        selection_rule_counts = {
            SelectionRuleType.SIZE_RELATED: size_count,
            SelectionRuleType.SPATIAL_SAME_PERSPECTIVE: spatial_same_count,
            SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE: spatial_diff_count,
            SelectionRuleType.NONE: none_count
        }
        
        for rule_type, rule_count in selection_rule_counts.items():
            if rule_count > 0:
                # Distribute physics/non-physics proportionally within each rule type
                physics_for_rule = int(rule_count * physics_prop)
                non_physics_for_rule = rule_count - physics_for_rule
                
                # Add physics=True combinations for this rule type
                constraint_assignments.extend([(rule_type, True)] * physics_for_rule)
                # Add physics=False combinations for this rule type  
                constraint_assignments.extend([(rule_type, False)] * non_physics_for_rule)
        
        # Shuffle to ensure random distribution across samples instead of deterministic assignment
        random.shuffle(constraint_assignments)
        
        
        for selection_rule_type, is_physics in constraint_assignments:
            constraints = QuestionConstraints(selection_rule_type, is_physics)
            
            # Retry grid generation with different questions if GridGenerationError occurs
            max_retries = 200
            for attempt in range(max_retries):
                try:
                    # Create question with constraints
                    question = cls._generate_constrained_question(items, constraints)
                    
                    # Create grid that creates ambiguity between perspectives
                    grid = cls._create_ambiguous_grid_for_question(
                        items, question, grid_width, grid_height, item_fill_ratio, block_ratio, related_item_prop, related_blocked_prop=related_blocked_prop
                    )
                    break  # Success, exit retry loop
                except GridGenerationError as e:
                    if attempt == max_retries - 1:
                        # Final attempt failed, raise with context
                        raise GridGenerationError(f"Failed to generate test sample after {max_retries} attempts. "
                                                f"Selection rule: {selection_rule_type}, Physics: {is_physics}. "
                                                f"Last error: {str(e)}")
                    # Continue to next attempt with new question
            
            # Simplify question by removing unnecessary adjectives (from director's perspective)
            question = cls._simplify_question(question, grid, constraints)
            
            # Get the expected answer from participant's perspective
            answer_coords = question.find_target(grid)
            
            # Create sample and verify it IS ambiguous
            sample = cls(grid, question, answer_coords, selection_rule_type=selection_rule_type, is_physics=is_physics, is_reversed=question.is_reversed)
            
            # Ensure ambiguity exists (should always pass for test samples)
            if not sample.has_ambiguous_answer():
                participant_answer = sample.answer_coordinates
                director_answer = sample.director_answer_coordinates
                raise RuntimeError(
                    f"Generated non-ambiguous test sample - this should not happen!\n"
                    f"Question: {question.to_natural_language()}\n"
                    f"Filter criteria: {question.filter_criteria}\n"
                    f"Selection rule: {question.selection_rule}\n"
                    f"Participant answer: {participant_answer}\n"
                    f"Director answer: {director_answer}\n"
                    f"Answers are equal: {participant_answer == director_answer}\n\n"
                    f"Grid layout:\n{grid.pretty_print()}"
                )
                
            samples.append(sample)
        
        return samples

    @staticmethod
    def _generate_constrained_question(items: List[Item], constraints: QuestionConstraints) -> Question:
        """Generate a question based on spatial and physics constraints"""
        
        # First, analyze what combinations actually exist in the item pool
        available_combinations = Sample._get_available_combinations(items)
        
        # Filter combinations based on constraints
        if constraints.is_physics:
            # Filter to only combinations that include physics properties
            physics_combinations = []
            for combo in available_combinations:
                has_physics = any(prop in Question.get_all_physics_properties() for prop in combo.keys())
                if has_physics:
                    physics_combinations.append(combo)
            
            if not physics_combinations:
                raise ValueError("No physics property combinations available in item pool")
            combinations = physics_combinations

        else:
            # Filter to combinations that don't include physics properties
            non_physics_combinations = []
            for combo in available_combinations:
                has_physics = any(prop in Question.get_all_physics_properties() for prop in combo.keys())
                if not has_physics:
                    non_physics_combinations.append(combo)
            
            if not non_physics_combinations:
                raise ValueError("No non-physics property combinations available in item pool")
            
            combinations = non_physics_combinations

        # check that the selected combination has multiple sizes if size-related rule is used
        if constraints.selection_rule_type == SelectionRuleType.SIZE_RELATED:
            combinations_with_size = []
            for combo in combinations:
                # find all matching items 
                matching_items = []
                for item in items:
                    # Check if this item matches all filter criteria
                    matches = True
                    
                    for prop_name, required_value in combo.items():
                        item_value = item.boolean_properties.get(prop_name, False)
                        if item_value != required_value:
                            matches = False
                            break
                    
                    if matches:
                        matching_items.append(item)
                sizes = set()
                for item in matching_items:
                    size = item.scalar_properties["size"]
                    sizes.add(size)

                if len(sizes) > 1:
                    combinations_with_size.append(combo)
                    
            if len(combinations_with_size) == 0:
                raise ValueError("Not enough size variation in items for size-related question")
            else:
                combinations = combinations_with_size
        
                    
        selected_combo = random.choice(combinations)
        # Find the target type from the selected combination
        target_type = None
        for prop in selected_combo.keys():
            if Question.categorize_property(prop) == "category":
                target_type = prop
                break
        
        if not target_type:
            # Fallback to "item" if no category property found
            target_type = "item"
        
        filter_criteria = selected_combo.copy()
        
        # 4. Determine selection rule and reversal based on constraints
        available_rules = constraints.get_selection_rules()
        selection_rule = random.choice(available_rules)
        
        # Set selection property based on rule type
        selection_property = "size" if selection_rule in ["smallest", "largest"] else None
        
        # Determine reversal - any question type can be reversed
        # For spatial questions, reversal affects the directional interpretation
        # For non-spatial questions, reversal affects the perspective suffix
        is_reversed = random.choice([True, False])
        
        return Question(target_type, filter_criteria, selection_rule, selection_property, constraints.selection_rule_type, is_reversed)
    
    @staticmethod
    def _get_available_combinations(items: List[Item]) -> List[dict]:
        """Get all property combinations that actually exist in the item pool"""
        combinations = []
        
        for item in items:
            # Get all True properties for this item
            true_props = {prop: True for prop, value in item.boolean_properties.items() if value}
            
            # Generate useful combinations (target type + color, target type + color + others)
            target_props = [prop for prop in true_props.keys() 
                           if Question.categorize_property(prop) == "category"]
            color_props = [prop for prop in true_props.keys() 
                          if Question.categorize_property(prop) == "color"]
            other_props = [prop for prop in true_props.keys() 
                          if Question.categorize_property(prop) not in ["category", "color"]]
            
            # Basic combination: target + color
            for target in target_props:
                for color in color_props:
                    basic_combo = {target: True, color: True}
                    if basic_combo not in combinations:
                        combinations.append(basic_combo)
                    
                    # Extended combinations: target + color + one other property
                    for other in other_props:
                        extended_combo = {target: True, color: True, other: True}
                        if extended_combo not in combinations:
                            combinations.append(extended_combo)
        
        return combinations
    
    @staticmethod
    def _simplify_question(question: Question, grid: Grid, constraints: QuestionConstraints, remove_all: bool = True) -> Question:
        """Simplify question by removing unnecessary adjectives from director's perspective"""
        
        if Sample(grid, question, question.find_target(grid)).has_ambiguous_answer():
            grid = grid.get_director_perspective()
        
        
        # Get the original answer from director's perspective
        try:
            original_answer = question.find_target(grid)
        except ValueError:
            # If question doesn't work from director's perspective, return as-is
            return question
        # Find removable adjective candidates (exclude target type and other category properties)
        removable_candidates = []
        for prop in question.filter_criteria.keys():
            prop_category = Question.categorize_property(prop)
            # Don't remove target types (category properties) - these define what we're looking for
            if prop != question.target_type and prop_category != "category":
                removable_candidates.append(prop)
        
        # Test each adjective to see if it can be removed
        actually_removable = []
        for adjective in removable_candidates:
            # Create test question without this adjective
            test_criteria = {k: v for k, v in question.filter_criteria.items() 
                           if k != adjective}
            
            # Skip if we'd have no criteria left (besides target type)
            if not test_criteria:
                continue
                
            test_question = Question(
                question.target_type, 
                test_criteria, 
                question.selection_rule, 
                question.selection_property,
                question.selection_rule_type,
                question.is_reversed
            )
            try:
                # Check if removing this adjective still gives same answer
                test_answer = test_question.find_target(grid)
                if test_answer == original_answer:
                    # Check constraint preservation for physics questions
                    if constraints.is_physics:
                        # Must keep at least one physics property
                        has_physics = any(prop in Question.get_all_physics_properties() 
                                        for prop in test_criteria.keys())
                        if has_physics:
                            actually_removable.append(adjective)
                    else:
                        # Non-physics questions: just check that we don't add physics properties
                        has_physics = any(prop in Question.get_all_physics_properties() 
                                        for prop in test_criteria.keys())
                        if not has_physics:
                            actually_removable.append(adjective)
                            
            except ValueError:
                # If test question fails, this adjective is needed
                continue
        
        # Randomly decide how many removable adjectives to actually remove (0 to all)
        if actually_removable:
            if remove_all:
                num_to_remove = len(actually_removable)
            else:
                num_to_remove = random.randint(0, len(actually_removable))
            if num_to_remove > 0:
                to_remove = random.sample(actually_removable, num_to_remove)
                
                # Create simplified question
                final_criteria = {k: v for k, v in question.filter_criteria.items() 
                                if k not in to_remove}
                
                simplified_question = Question(
                    question.target_type,
                    final_criteria, 
                    question.selection_rule, 
                    question.selection_property,
                    question.selection_rule_type,
                    question.is_reversed
                )
                
                # Final verification that simplified question still works
                try:
                    if simplified_question.find_target(grid) == original_answer:
                        return simplified_question
                except ValueError:
                    pass
        
        # Return original question if simplification didn't work or wasn't beneficial
        return question

    @staticmethod
    def _create_grid_for_question(items: List[Item], question: Question, width: int, height: int, 
                                 item_fill_ratio: float, block_ratio: float, related_item_prop: float = 0.3) -> Grid:
        """Create a grid that satisfies the given question without ambiguity"""
        grid = Grid(width, height)
        total_positions = width * height
        num_items = int(total_positions * item_fill_ratio)
        num_blocks = int(total_positions * block_ratio)
        
        # Step 1: Place target item that matches the question
        target_item = Sample._create_director_item(items, question)
        target_col, target_row = random.randint(0, width-1), random.randint(0, height-1)  # x=col, y=row
        grid.item_grid[target_row][target_col] = target_item  # Grid access: [row][col] = [y][x]

        # Step 2: Fill remaining positions with related and unrelated items based on proportion
        available_positions = [(x, y) for x in range(width) for y in range(height) 
                              if (x, y) != (target_col, target_row)]  # Positions stored as (x,y) = (col,row)
        
        # Calculate how many items to place (excluding target)
        total_non_target_positions = min((max(num_items - 1, 0)), len(available_positions))
        
        # Calculate how many should be related (match criteria) vs unrelated (don't match criteria)
        num_related_items = int(total_non_target_positions * related_item_prop)
        num_unrelated_items = total_non_target_positions - num_related_items
        
        if question.selection_rule_type != SelectionRuleType.NONE:
            Sample.add_related_items_unambiguous(grid, question, target_item, items, num_related_items)
            Sample.add_unrelated_items_random(grid, question, target_item, items, num_unrelated_items)
        else:
            # If no selection rule, just fill with random items but fill more
            Sample.add_unrelated_items_random(grid, question, target_item, items, num_items)
        
        
        # Step 3: Place blocks (can be anywhere except target position)
        blockable_positions = [(x, y) for x in range(width) for y in range(height) 
                              if (x, y) != (target_col, target_row)]  # Positions as (x,y) = (col,row)
        block_positions = random.sample(blockable_positions, min(num_blocks, len(blockable_positions)))
        
        for x, y in block_positions:  # x=col, y=row
            grid.blocks[y][x] = 1  # Grid access: [row][col] = [y][x]
        
        return grid

    @staticmethod
    def _create_ambiguous_grid_for_question(items: List[Item], question: Question, width: int, height: int, 
                                          item_fill_ratio: float, block_ratio: float,
                                          related_item_prop: float = 0.3, related_blocked_prop: float = 0.5)-> Grid:
        """Create a grid where participant and director see different answers to the question"""
        grid = Grid(width, height)
        total_positions = width * height
        num_items = int(total_positions * item_fill_ratio)
        num_blocks = int(total_positions * block_ratio)
        
        # Step 1: Place director's target item (unblocked, matches criteria)
        director_target = Sample._create_director_item(items, question)
        director_col, director_row = random.randint(0, width-1), random.randint(0, height-1)  # x=col, y=row
        grid.item_grid[director_row][director_col] = director_target  # Grid access: [row][col] = [y][x]

        # Step 2: Place the single item that must be ruled out by blocks meaning it must beat the selection rule but be blocked 
        # Calculate how many items to place (excluding target)
        available_positions = [(x, y) for x in range(width) for y in range(height) 
                              if (x, y) != (director_col, director_row)]  # Positions stored as (x,y) = (col,row)
        total_non_target_positions = min((max(num_items - 1, 0)), len(available_positions))
        
        # Calculate how many should be related (match criteria) vs unrelated (don't match criteria)
        num_related_unblocked_items = int(total_non_target_positions * related_item_prop * (1-related_blocked_prop))
        num_related_blocked_items = max(int(total_non_target_positions * related_item_prop * related_blocked_prop), 1)
        available_positions = [(x, y) for x in range(width) for y in range(height) 
                              if (x, y) != (director_col, director_row)]  # Positions as (x,y) = (col,row)
        
        # first fill with related items that are not blocked but ruled out 
        if question.selection_rule_type != SelectionRuleType.NONE:
            Sample.add_related_items_unambiguous(grid, question, director_target, items, num_related_unblocked_items)
            # note the positions of these items as we dont watn to block them later
            none_blockable_positions = [(x, y) for x in range(width) for y in range(height)
                                if grid.item_grid[y][x] is not None]  # Positions as (x,y) = (col,row)
        else:
            # If no selection rule, the just block all of the related items 
            num_related_blocked_items += num_related_unblocked_items
            none_blockable_positions = []
        
        # then add a single realted item that is block and breaks selection rule
        participant_item, (x, y) = Sample._create_participant_only_item(items, question, director_target, 
                                             (director_col, director_row), available_positions)
        grid.item_grid[y][x] = participant_item  # Grid access: [row][col] = [y][x]
        # Block this position from director's view
        grid.blocks[y][x] = 1  # Grid access: [row][col] = [y][x]
        num_related_blocked_items -= 1  # One item already placed
        
        # Step 3: Fill remaining positions with related and unrelated items based on proportion
        Sample.add_unrelated_items_random(grid, question, director_target, items, int(num_items * (1 - related_item_prop)))
        Sample.add_related_items_random(grid, question, director_target, items, num_related_blocked_items)
        
        # Step 4: Place additional blocks (avoiding director's target)
        blocks_already_placed = num_related_blocked_items + 1
        additional_blocks_needed = max(0, num_blocks - blocks_already_placed)
        
        if additional_blocks_needed > 0:
            blockable_positions = [(x, y) for x in range(width) for y in range(height) 
                                 if (x, y) != (director_col, director_row) and grid.blocks[y][x] == 0]  # Positions as (x,y)
            for pos in blockable_positions:
                if pos in none_blockable_positions:
                    blockable_positions.remove(pos)
            if blockable_positions:
                additional_block_positions = random.sample(blockable_positions, 
                                                         min(additional_blocks_needed, len(blockable_positions)))
                
                for x, y in additional_block_positions:  # x=col, y=row
                    grid.blocks[y][x] = 1  # Grid access: [row][col] = [y][x]
        
        return grid

    @staticmethod
    def _create_director_item(items: List[Item], question: Question) -> Item:
        """Find an item from items that matches the question's filter criteria"""
        matching_items = []
        
        for item in items:
            # Check if this item matches all filter criteria
            matches = True
            for prop_name, required_value in question.filter_criteria.items():
                item_value = item.boolean_properties.get(prop_name, False)
                if item_value != required_value:
                    matches = False
                    break
            
            if matches:
                matching_items.append(item)
        
        if not matching_items:
            raise ValueError(f"No items in items pool match the question criteria: {question.filter_criteria}")
        
        # Select a random matching item and create a copy
        selected_item = random.choice(matching_items)
        return Item(
            name=selected_item.name,
            image_path=selected_item.image_path,
            boolean_properties=selected_item.boolean_properties.copy(),
            scalar_properties=selected_item.scalar_properties.copy()
        )

    @staticmethod
    def _create_participant_only_item(items: List[Item], question: Question, director_target: Item, 
                                    director_position: tuple[int, int],
                                    available_positions: list[tuple[int, int]]) -> tuple[Item, tuple[int, int]]:
        """Find an item and position that would 'beat' or 'tie with' director's target based on selection rule
        
        Args:
            director_position: Director's position as (x, y) = (col, row)
            available_positions: Available positions as list of (x, y) = (col, row) tuples
            
        Returns:
            Tuple of (Item, position) where position is (x, y) = (col, row)
        """
        director_col, director_row = director_position  # Unpack (x, y) = (col, row)
        
        # Step 1: Filter positions based on selection rule
        valid_positions = []
        
        if question.selection_rule == "leftmost":
            # Only positions that are same or more left than director (smaller x/col values)
            valid_positions = [(x, y) for x, y in available_positions if x <= director_col]
        elif question.selection_rule == "rightmost":
            # Only positions that are same or more right than director (larger x/col values)
            valid_positions = [(x, y) for x, y in available_positions if x >= director_col]
        elif question.selection_rule == "topmost":
            # Only positions that are same or more top than director (smaller y/row values)
            valid_positions = [(x, y) for x, y in available_positions if y <= director_row]
        elif question.selection_rule == "bottommost":
            # Only positions that are same or more bottom than director (larger y/row values)
            valid_positions = [(x, y) for x, y in available_positions if y >= director_row]
        else:
            # For scalar rules or no rule, any position works
            valid_positions = available_positions[:]
        
        if not valid_positions:
            raise ValueError(
                f"No valid positions available for selection rule '{question.selection_rule}'\n"
                f"Director position: {director_position}, Available positions: {available_positions}"
            )
        
        # Step 2: Find items that match criteria and can beat/tie director for scalar rules
        valid_items = []
        
        for item in items:
            # First check if this item matches all filter criteria
            matches_criteria = True
            for prop_name, required_value in question.filter_criteria.items():
                item_value = item.boolean_properties.get(prop_name, False)
                if item_value != required_value:
                    matches_criteria = False
                    break
            
            if not matches_criteria:
                continue
                
            # For scalar rules, check if item can beat/tie director's target
            can_compete = True
            if question.selection_rule == "smallest":
                participant_size = item.scalar_properties.get(question.selection_property, float('inf'))
                director_size = director_target.scalar_properties.get(question.selection_property, float('inf'))
                can_compete = participant_size <= director_size  # Allow ties
            elif question.selection_rule == "largest":
                participant_size = item.scalar_properties.get(question.selection_property, float('-inf'))
                director_size = director_target.scalar_properties.get(question.selection_property, float('-inf'))
                can_compete = participant_size >= director_size  # Allow ties
            # For positional rules, competition is determined by position (already filtered above)
            
            if can_compete:
                valid_items.append(item)
        
        if not valid_items:
            raise ValueError(
                f"No items in items pool can serve as participant-only matches that would beat or tie with director's target.\n"
                f"Question: {question.to_natural_language()}\n"
                f"Selection rule: {question.selection_rule}\n"
                f"Director target: {director_target.name} with properties {director_target.scalar_properties}\n"
                f"Director position: {director_position}\n"
                f"Valid positions: {valid_positions}"
            )
        
        # Step 3: Select random valid item and position
        selected_item = random.choice(valid_items)
        selected_position = random.choice(valid_positions)
        
        selected_item_copy = Item(
            name=selected_item.name,
            image_path=selected_item.image_path,
            boolean_properties=selected_item.boolean_properties.copy(),
            scalar_properties=selected_item.scalar_properties.copy()
        )
        return selected_item_copy, selected_position

    @staticmethod
    def _create_distractor_item(items: List[Item], question: Question) -> Item:
        """Find an item from items that does NOT match the question's filter criteria"""
        non_matching_items = []
        
        for item in items:
            # Check if this item fails to match at least one filter criterion
            matches_all = True
            for prop_name, required_value in question.filter_criteria.items():
                item_value = item.boolean_properties.get(prop_name, False)
                if item_value != required_value:
                    matches_all = False
                    break
            
            # If it doesn't match all criteria, it's a valid distractor
            if not matches_all:
                non_matching_items.append(item)
        
        if not non_matching_items:
            raise ValueError(f"No items in items pool can serve as distractors for criteria: {question.filter_criteria}")
        
        # Select a random non-matching item and create a copy
        selected_item = random.choice(non_matching_items)
        return Item(
            name=selected_item.name,
            image_path=selected_item.image_path,
            boolean_properties=selected_item.boolean_properties.copy(),
            scalar_properties=selected_item.scalar_properties.copy()
        )
    
    # === VALIDATION METHODS ===
    
    @staticmethod
    def validate_constraint_distribution(samples: List['Sample'], 
                                       expected_size_prop: float = 0.25,
                                       expected_spatial_same_prop: float = 0.25, 
                                       expected_spatial_diff_prop: float = 0.25,
                                       expected_physics_prop: float = 0.5,
                                       tolerance: float = 0.02) -> tuple[bool, dict, list[str]]:
        """
        Validate that generated samples match expected constraint distributions and all combinations exist.
        
        Args:
            samples: List of Sample objects to validate
            expected_*_prop: Expected proportions for each constraint type
            tolerance: Acceptable deviation from expected proportions
            
        Returns:
            Tuple of (is_valid, distribution_stats, error_messages)
        """
        if not samples:
            return False, {}, ["No samples provided for validation"]
        
        total_samples = len(samples)
        errors = []
        
        # Count actual distributions
        rule_type_counts = {rule_type: 0 for rule_type in SelectionRuleType}
        physics_count = 0
        combination_counts = {}
        
        for sample in samples:
            # Count selection rule types
            rule_type_counts[sample.selection_rule_type] += 1
            
            # Count physics usage
            if sample.is_physics:
                physics_count += 1
            
            # Count all combinations for comprehensive analysis
            combo_key = (
                sample.selection_rule_type,
                sample.is_physics,
                sample.has_ambiguous_answer(),  # control vs test
                sample.is_reversed
            )
            combination_counts[combo_key] = combination_counts.get(combo_key, 0) + 1
        
        # Calculate actual proportions
        actual_size_prop = rule_type_counts[SelectionRuleType.SIZE_RELATED] / total_samples
        actual_spatial_same_prop = rule_type_counts[SelectionRuleType.SPATIAL_SAME_PERSPECTIVE] / total_samples
        actual_spatial_diff_prop = rule_type_counts[SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE] / total_samples  
        actual_none_prop = rule_type_counts[SelectionRuleType.NONE] / total_samples
        actual_physics_prop = physics_count / total_samples
        
        # Validate proportions within tolerance
        if abs(actual_size_prop - expected_size_prop) > tolerance:
            errors.append(f"Size rule proportion mismatch: expected {expected_size_prop:.3f}, got {actual_size_prop:.3f}")
        
        if abs(actual_spatial_same_prop - expected_spatial_same_prop) > tolerance:
            errors.append(f"Spatial same rule proportion mismatch: expected {expected_spatial_same_prop:.3f}, got {actual_spatial_same_prop:.3f}")
            
        if abs(actual_spatial_diff_prop - expected_spatial_diff_prop) > tolerance:
            errors.append(f"Spatial different rule proportion mismatch: expected {expected_spatial_diff_prop:.3f}, got {actual_spatial_diff_prop:.3f}")
            
        if abs(actual_physics_prop - expected_physics_prop) > tolerance:
            errors.append(f"Physics proportion mismatch: expected {expected_physics_prop:.3f}, got {actual_physics_prop:.3f}")
        
        # Validate that all expected rule type + physics combinations exist
        expected_rule_physics_combinations = [
            (SelectionRuleType.SIZE_RELATED, True),
            (SelectionRuleType.SIZE_RELATED, False),
            (SelectionRuleType.SPATIAL_SAME_PERSPECTIVE, True),
            (SelectionRuleType.SPATIAL_SAME_PERSPECTIVE, False),
            (SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE, True),
            (SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE, False),
            (SelectionRuleType.NONE, True),
            (SelectionRuleType.NONE, False)
        ]
        
        missing_combinations = []
        for rule_type, is_physics in expected_rule_physics_combinations:
            # Check if this combination exists in any form (control/test, reversed/not reversed)
            combo_exists = any(
                combo_key[0] == rule_type and combo_key[1] == is_physics
                for combo_key in combination_counts.keys()
            )
            if not combo_exists:
                missing_combinations.append((rule_type, is_physics))
        
        if missing_combinations:
            missing_str = ", ".join([f"({combo[0].value}, physics={combo[1]})" for combo in missing_combinations])
            errors.append(f"Missing rule type + physics combinations: {missing_str}")
        
        # Create detailed distribution statistics
        distribution_stats = {
            "total_samples": total_samples,
            "rule_type_counts": {rule_type.value: count for rule_type, count in rule_type_counts.items()},
            "rule_type_proportions": {
                "size_related": actual_size_prop,
                "spatial_same_perspective": actual_spatial_same_prop,
                "spatial_different_perspective": actual_spatial_diff_prop,
                "none": actual_none_prop
            },
            "physics_count": physics_count,
            "physics_proportion": actual_physics_prop,
            "combination_counts": {
                f"{combo[0].value}_physics-{combo[1]}_ambiguous-{combo[2]}_reversed-{combo[3]}": count
                for combo, count in combination_counts.items()
            },
            "unique_combinations": len(combination_counts),
            "missing_combinations": len(missing_combinations)
        }
        
        is_valid = len(errors) == 0
        return is_valid, distribution_stats, errors
    
    @staticmethod
    def print_distribution_report(samples: List['Sample'], 
                                expected_size_prop: float = 0.25,
                                expected_spatial_same_prop: float = 0.25, 
                                expected_spatial_diff_prop: float = 0.25,
                                expected_physics_prop: float = 0.5) -> None:
        """Print a detailed distribution report for generated samples."""
        is_valid, stats, errors = Sample.validate_constraint_distribution(
            samples, expected_size_prop, expected_spatial_same_prop, 
            expected_spatial_diff_prop, expected_physics_prop
        )
        
        print(f"\n=== Sample Distribution Report ===")
        print(f"Total samples: {stats['total_samples']}")
        print(f"Validation status: {'✓ PASSED' if is_valid else '✗ FAILED'}")
        
        print(f"\nSelection Rule Distribution:")
        for rule_name, count in stats['rule_type_counts'].items():
            proportion = count / stats['total_samples']
            print(f"  {rule_name}: {count} samples ({proportion:.3f})")
        
        print(f"\nPhysics Distribution:")
        print(f"  Physics=True: {stats['physics_count']} samples ({stats['physics_proportion']:.3f})")
        print(f"  Physics=False: {stats['total_samples'] - stats['physics_count']} samples ({1 - stats['physics_proportion']:.3f})")
        
        print(f"\nCombination Analysis:")
        print(f"  Unique combinations found: {stats['unique_combinations']}")
        print(f"  Missing combinations: {stats['missing_combinations']}")
        
        if errors:
            print(f"\nValidation Errors:")
            for error in errors:
                print(f"  • {error}")
        
        print(f"\nDetailed Combination Counts:")
        for combo_name, count in sorted(stats['combination_counts'].items()):
            print(f"  {combo_name}: {count}")
        
        print("=" * 40)
    
    # === RELATIONAL QUESTION METHODS ===
    
    @classmethod
    def generate_relational_control_samples(cls, items: List[Item], grid_width: int, grid_height: int, 
                                           num_samples: int, item_fill_ratio: float = 0.5, 
                                           block_ratio: float = 0.4) -> List['Sample']:
        """Generate control samples with relational questions (no ambiguity)"""
        samples = []
        
        for _ in range(num_samples):
            # Generate a relational question
            question = cls._generate_relational_question(items)
            
            # Create grid that satisfies the relational question without ambiguity
            grid = cls._create_grid_for_relational_question(
                items, question, grid_width, grid_height, item_fill_ratio, block_ratio
            )
            
            # Get the expected answer
            answer_coords = question.find_target(grid)
            
            # Create sample and verify it's not ambiguous
            sample = cls(grid, question, answer_coords, selection_rule_type=SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE, is_physics=False, is_reversed=question.is_reversed)
            
            # Ensure no ambiguity (should always pass for control samples)
            if sample.has_ambiguous_answer():
                raise RuntimeError("Generated ambiguous relational control sample - this should not happen")
                
            samples.append(sample)
        
        return samples
    
    @classmethod
    def generate_relational_test_samples(cls, items: List[Item], grid_width: int, grid_height: int, 
                                        num_samples: int, item_fill_ratio: float = 0.5, 
                                        block_ratio: float = 0.4) -> List['Sample']:
        """Generate test samples with relational questions (with ambiguity)"""
        samples = []
        
        for _ in range(num_samples):
            # Generate a relational question
            question = cls._generate_relational_question(items)
            
            # Create grid that creates ambiguity for the relational question
            grid = cls._create_ambiguous_grid_for_relational_question(
                items, question, grid_width, grid_height, item_fill_ratio, block_ratio
            )
            
            # Get the expected answer from participant's perspective
            answer_coords = question.find_target(grid)
            
            # Create sample and verify it IS ambiguous
            sample = cls(grid, question, answer_coords, selection_rule_type=SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE, is_physics=False, is_reversed=question.is_reversed)
            
            # Ensure ambiguity exists (should always pass for test samples)
            if not sample.has_ambiguous_answer():
                participant_answer = sample.answer_coordinates
                director_answer = sample.director_answer_coordinates
                raise RuntimeError(
                    f"Generated non-ambiguous relational test sample - this should not happen!\n"
                    f"Question: {question.to_natural_language()}\n"
                    f"Reference criteria: {question.reference_criteria}\n"
                    f"Spatial relation: {question.spatial_relation}\n"
                    f"Participant answer: {participant_answer}\n"
                    f"Director answer: {director_answer}\n"
                )
                
            samples.append(sample)
        
        return samples
    
    @staticmethod
    def _generate_relational_question(items: List[Item]) -> RelationalQuestion:
        """Generate a random relational question"""
        
        # 1. Choose reference object criteria
        # Use dynamic properties from Question class
        reference_type = random.choice(Question.get_all_target_types())
        reference_color = random.choice(Question.get_all_colors())
        reference_criteria = {reference_type: True, reference_color: True}
        
        # 2. Choose spatial relation
        spatial_relations = ["right_of", "left_of", "above", "below"]
        spatial_relation = random.choice(spatial_relations)
        
        # 3. Target criteria - hardcoded to None for now
        target_criteria = None
        
        # 4. Reversal - can be random for relational questions
        is_reversed = random.choice([True, False])
        
        return RelationalQuestion(reference_criteria, spatial_relation, target_criteria, is_reversed)
    
    @staticmethod
    def _create_grid_for_relational_question(items: List[Item], question: RelationalQuestion, 
                                            width: int, height: int, item_fill_ratio: float, 
                                            block_ratio: float) -> Grid:
        """Create a grid that satisfies the relational question without ambiguity"""
        grid = Grid(width, height)
        total_positions = width * height
        num_items = int(total_positions * item_fill_ratio)
        num_blocks = int(total_positions * block_ratio)
        
        # Step 1: Place reference object strategically to ensure valid target positions
        valid_ref_positions = Sample._get_valid_reference_positions(question.spatial_relation, width, height)
        ref_col, ref_row = random.choice(valid_ref_positions)
        
        reference_item = Sample._create_reference_item(items, question.reference_criteria)
        grid.item_grid[ref_row][ref_col] = reference_item
        
        # Step 2: Place target object in the specified spatial relation
        target_positions = Sample._get_valid_target_positions(question.spatial_relation, (ref_col, ref_row), width, height)
        
        target_col, target_row = random.choice(target_positions)
        target_item = Sample._create_relational_target_item(items, question)
        grid.item_grid[target_row][target_col] = target_item
        
        # Step 3: Fill remaining positions with distractor items
        used_positions = {(ref_col, ref_row), (target_col, target_row)}
        available_positions = [(x, y) for x in range(width) for y in range(height) 
                              if (x, y) not in used_positions]
        
        remaining_items_needed = max(0, num_items - 2)  # Subtract reference and target
        if remaining_items_needed > 0 and available_positions:
            distractor_positions = random.sample(available_positions, 
                                               min(remaining_items_needed, len(available_positions)))
            
            for x, y in distractor_positions:
                distractor_item = Sample._create_relational_distractor_item(items, question)
                grid.item_grid[y][x] = distractor_item
                used_positions.add((x, y))
        
        # Step 4: Place blocks (avoiding reference and target)
        blockable_positions = [pos for pos in available_positions if pos not in used_positions]
        block_positions = random.sample(blockable_positions, min(num_blocks, len(blockable_positions)))
        
        for x, y in block_positions:
            grid.blocks[y][x] = 1
        
        return grid
    
    @staticmethod
    def _create_ambiguous_grid_for_relational_question(items: List[Item], question: RelationalQuestion, 
                                                      width: int, height: int, item_fill_ratio: float, 
                                                      block_ratio: float) -> Grid:
        """Create a grid where participant and director see different answers for relational question"""
        grid = Grid(width, height)
        total_positions = width * height
        num_items = int(total_positions * item_fill_ratio)
        num_blocks = int(total_positions * block_ratio)
        
        # Step 1: Place reference object strategically (ensuring multiple target positions for ambiguity)
        valid_ref_positions = Sample._get_valid_reference_positions_for_ambiguity(question.spatial_relation, width, height)
        ref_col, ref_row = random.choice(valid_ref_positions)
        
        reference_item = Sample._create_reference_item(items, question.reference_criteria)
        grid.item_grid[ref_row][ref_col] = reference_item
        
        # Step 2: Place director's target (unblocked) 
        director_target_positions = Sample._get_valid_target_positions(question.spatial_relation, (ref_col, ref_row), width, height)
        
        # Ensure we have at least 2 target positions for ambiguity
        if len(director_target_positions) < 2:
            raise ValueError(f"Not enough target positions for ambiguity: need at least 2, got {len(director_target_positions)}")
        
        director_col, director_row = random.choice(director_target_positions)
        director_target = Sample._create_relational_target_item(items, question)
        grid.item_grid[director_row][director_col] = director_target
        
        # Step 3: Place participant-only target (blocked from director)
        remaining_target_positions = [pos for pos in director_target_positions if pos != (director_col, director_row)]
        
        if remaining_target_positions:
            participant_col, participant_row = random.choice(remaining_target_positions)
            participant_target = Sample._create_relational_target_item(items, question)
            grid.item_grid[participant_row][participant_col] = participant_target
            # Block this position from director
            grid.blocks[participant_row][participant_col] = 1
            used_positions = {(ref_col, ref_row), (director_col, director_row), (participant_col, participant_row)}
        else:
            used_positions = {(ref_col, ref_row), (director_col, director_row)}
        
        # Step 4: Fill remaining positions and add more blocks
        available_positions = [(x, y) for x in range(width) for y in range(height) 
                              if (x, y) not in used_positions]
        
        # Add more items
        items_placed = len(used_positions)
        remaining_items_needed = max(0, num_items - items_placed)
        if remaining_items_needed > 0 and available_positions:
            distractor_positions = random.sample(available_positions, 
                                               min(remaining_items_needed, len(available_positions)))
            
            for x, y in distractor_positions:
                distractor_item = Sample._create_relational_distractor_item(items, question)
                grid.item_grid[y][x] = distractor_item
                used_positions.add((x, y))
        
        # Add more blocks
        blocks_placed = 1 if len(used_positions) > 2 else 0  # Count participant-only block
        additional_blocks_needed = max(0, num_blocks - blocks_placed)
        
        if additional_blocks_needed > 0:
            blockable_positions = [(x, y) for x in range(width) for y in range(height) 
                                 if (x, y) not in used_positions and (x, y) != (ref_col, ref_row)]
            
            if blockable_positions:
                additional_block_positions = random.sample(blockable_positions, 
                                                         min(additional_blocks_needed, len(blockable_positions)))
                
                for x, y in additional_block_positions:
                    grid.blocks[y][x] = 1
        
        return grid
    
    @staticmethod
    def _create_reference_item(items: List[Item], reference_criteria: dict) -> Item:
        """Create an item that matches the reference criteria"""
        matching_items = []
        
        for item in items:
            matches = True
            for prop_name, required_value in reference_criteria.items():
                if item.boolean_properties.get(prop_name, False) != required_value:
                    matches = False
                    break
            
            if matches:
                matching_items.append(item)
        
        if not matching_items:
            raise ValueError(f"No items in pool match reference criteria: {reference_criteria}")
        
        selected_item = random.choice(matching_items)
        return Item(
            name=selected_item.name,
            image_path=selected_item.image_path,
            boolean_properties=selected_item.boolean_properties.copy(),
            scalar_properties=selected_item.scalar_properties.copy()
        )
    
    @staticmethod
    def _create_relational_target_item(items: List[Item], question: RelationalQuestion) -> Item:
        """Create a target item for relational questions"""
        # For now, target criteria is None, so any item can be a target
        # In the future, this would filter by question.target_criteria
        available_items = [item for item in items]  # Any item can be target for now
        
        if not available_items:
            raise ValueError("No items available for relational target")
        
        selected_item = random.choice(available_items)
        return Item(
            name=selected_item.name,
            image_path=selected_item.image_path,
            boolean_properties=selected_item.boolean_properties.copy(),
            scalar_properties=selected_item.scalar_properties.copy()
        )
    
    @staticmethod
    def _create_relational_distractor_item(items: List[Item], question: RelationalQuestion) -> Item:
        """Create a distractor item for relational questions"""
        # Any item can be a distractor for relational questions
        selected_item = random.choice(items)
        return Item(
            name=selected_item.name,
            image_path=selected_item.image_path,
            boolean_properties=selected_item.boolean_properties.copy(),
            scalar_properties=selected_item.scalar_properties.copy()
        )
    
    @staticmethod
    def _get_valid_target_positions(spatial_relation: str, ref_pos: tuple[int, int], 
                                   width: int, height: int) -> List[tuple[int, int]]:
        """Get all valid positions for the target given the spatial relation and reference position"""
        ref_x, ref_y = ref_pos
        valid_positions = []
        
        if spatial_relation == "right_of":
            # Same row, positions to the right
            for x in range(ref_x + 1, width):
                valid_positions.append((x, ref_y))
        elif spatial_relation == "left_of":
            # Same row, positions to the left
            for x in range(0, ref_x):
                valid_positions.append((x, ref_y))
        elif spatial_relation == "above":
            # Same column, positions above
            for y in range(0, ref_y):
                valid_positions.append((ref_x, y))
        elif spatial_relation == "below":
            # Same column, positions below
            for y in range(ref_y + 1, height):
                valid_positions.append((ref_x, y))
        
        return valid_positions
    
    @staticmethod
    def _get_valid_reference_positions(spatial_relation: str, width: int, height: int) -> List[tuple[int, int]]:
        """Get valid reference positions that ensure at least one target position exists"""
        valid_positions = []
        
        if spatial_relation == "right_of":
            # Reference must have space to the right (not in rightmost column)
            for y in range(height):
                for x in range(width - 1):  # Leave at least one column to the right
                    valid_positions.append((x, y))
        elif spatial_relation == "left_of":
            # Reference must have space to the left (not in leftmost column)
            for y in range(height):
                for x in range(1, width):  # Leave at least one column to the left
                    valid_positions.append((x, y))
        elif spatial_relation == "above":
            # Reference must have space above (not in top row)
            for y in range(1, height):  # Leave at least one row above
                for x in range(width):
                    valid_positions.append((x, y))
        elif spatial_relation == "below":
            # Reference must have space below (not in bottom row)
            for y in range(height - 1):  # Leave at least one row below
                for x in range(width):
                    valid_positions.append((x, y))
        
        return valid_positions
    
    @staticmethod
    def _get_valid_reference_positions_for_ambiguity(spatial_relation: str, width: int, height: int) -> List[tuple[int, int]]:
        """Get valid reference positions that ensure at least 2 target positions for ambiguity"""
        valid_positions = []
        
        if spatial_relation == "right_of":
            # Reference must have at least 2 spaces to the right
            for y in range(height):
                for x in range(width - 2):  # Leave at least 2 columns to the right
                    valid_positions.append((x, y))
        elif spatial_relation == "left_of":
            # Reference must have at least 2 spaces to the left
            for y in range(height):
                for x in range(2, width):  # Leave at least 2 columns to the left
                    valid_positions.append((x, y))
        elif spatial_relation == "above":
            # Reference must have at least 2 spaces above
            for y in range(2, height):  # Leave at least 2 rows above
                for x in range(width):
                    valid_positions.append((x, y))
        elif spatial_relation == "below":
            # Reference must have at least 2 spaces below
            for y in range(height - 2):  # Leave at least 2 rows below
                for x in range(width):
                    valid_positions.append((x, y))
        
        return valid_positions