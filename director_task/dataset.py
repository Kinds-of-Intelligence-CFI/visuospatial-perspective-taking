import json
import os
import inspect
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, validator, ValidationError
from director_task.sample import Sample
from director_task.renderer_2d import GridRenderer2D
from director_task.item import Item
from director_task.question import SelectionRuleType


# Pydantic validation models for dataset structure
class PositionModel(BaseModel):
    x: int
    y: int


class ItemDataModel(BaseModel):
    name: str
    image_path: str
    boolean_properties: Dict[str, bool]
    scalar_properties: Dict[str, Any]


class GridItemModel(BaseModel):
    position: PositionModel
    is_blocked: bool
    item: Optional[ItemDataModel] = None


class QuestionModel(BaseModel):
    """Validates JSON representation of questions (both standard and relational)
    
    Computed fields: natural_language, full_question
    Standard question fields: target_type, filter_criteria, selection_rule, selection_property
    Relational question fields: reference_criteria, spatial_relation, target_criteria
    """
    question_type: str  # "standard" or "relational"
    
    # Standard question fields (optional for relational questions)
    target_type: Optional[str] = None
    filter_criteria: Optional[Dict[str, Any]] = None
    selection_rule: Optional[str] = None
    selection_property: Optional[str] = None
    selection_rule_type: Optional[str] = None 
    
    # Relational question fields (optional for standard questions)
    reference_criteria: Optional[Dict[str, Any]] = None
    spatial_relation: Optional[str] = None
    target_criteria: Optional[Dict[str, Any]] = None
    
    # Common fields
    is_reversed: bool = False
    natural_language: str  # Computed from Question.to_natural_language()
    full_question: str     # Computed from Question.full_question()


class GridModel(BaseModel):
    """Validates JSON representation of grids
    
    Computed fields (not in Grid class): items (flattened from Grid.item_grid + Grid.blocks)
    Grid class fields not included: item_grid (2D array), blocks (2D array)
    """
    width: int
    height: int
    items: List[GridItemModel]  # Flattened representation of Grid's 2D structure
    
    @validator('items')
    def validate_grid_size(cls, v, values):
        if 'width' in values and 'height' in values:
            expected_count = values['width'] * values['height']
            if len(v) != expected_count:
                raise ValueError(f'Grid items count ({len(v)}) does not match width × height ({expected_count})')
        return v
    
    @validator('width', 'height')
    def validate_positive_dimensions(cls, v):
        if v <= 0:
            raise ValueError('Grid dimensions must be positive')
        return v


class AnswersModel(BaseModel):
    participant_coordinates: List[List[int]]
    director_coordinates: List[List[int]]
    is_ambiguous: bool


class SampleModel(BaseModel):
    """Validates JSON representation of samples
    
    Computed/metadata fields (not in Sample class): sample_id, sample_type, image_path, answers (combines answer_coordinates + director_answer_coordinates)
    Sample class fields not included: answer_coordinates (set), director_answer_coordinates (set) - merged into answers field
    """
    sample_id: int              # Export metadata (assigned during dataset generation)
    sample_type: str            # Export metadata ("control" or "test")
    image_path: str             # Export metadata (path to rendered image)
    question: QuestionModel
    grid: GridModel
    answers: AnswersModel       # Combines Sample.answer_coordinates + Sample.director_answer_coordinates
    selection_rule_type: str    # Type of selection rule (enum value)
    is_physics: bool = False    # Whether question uses physics-related constraints
    is_reversed: bool = False   # Whether spatial question is from director's perspective
    
    @validator('sample_type')
    def validate_sample_type(cls, v):
        if v not in ['control', 'test']:
            raise ValueError(f'sample_type must be "control" or "test", got "{v}"')
        return v
    
    @validator('sample_id')
    def validate_sample_id(cls, v):
        if v < 0:
            raise ValueError('sample_id must be non-negative')
        return v
    
    @validator('selection_rule_type')
    def validate_selection_rule_type(cls, v):
        valid_values = [rule_type.value for rule_type in SelectionRuleType]
        if v not in valid_values:
            raise ValueError(f'selection_rule_type must be one of {valid_values}, got "{v}"')
        return v


class DatasetModel(BaseModel):
    dataset_name: str
    total_samples: int
    control_samples: int
    test_samples: int
    samples: List[SampleModel]
    
    @validator('total_samples')
    def validate_total_samples(cls, v, values):
        if 'control_samples' in values and 'test_samples' in values:
            expected = values['control_samples'] + values['test_samples']
            if v != expected:
                raise ValueError(f'total_samples ({v}) != control_samples + test_samples ({expected})')
        return v
    
    @validator('control_samples', 'test_samples')
    def validate_sample_counts(cls, v):
        if v < 0:
            raise ValueError('Sample counts must be non-negative')
        return v
    
    @validator('samples')
    def validate_samples_match_counts(cls, v, values):
        if 'control_samples' in values and 'test_samples' in values:
            control_count = sum(1 for s in v if s.sample_type == 'control')
            test_count = sum(1 for s in v if s.sample_type == 'test')
            
            if control_count != values['control_samples']:
                raise ValueError(f'Found {control_count} control samples, expected {values["control_samples"]}')
            if test_count != values['test_samples']:
                raise ValueError(f'Found {test_count} test samples, expected {values["test_samples"]}')
        return v


def verify_class_model_sync(cls, model_cls) -> List[str]:
    """Check if class and model have matching fields"""
    errors = []
    
    # Get class fields from __init__ if it exists
    if hasattr(cls, '__init__'):
        class_sig = inspect.signature(cls.__init__)
        class_fields = {name for name, param in class_sig.parameters.items() if name != 'self'}
    else:
        # If no __init__, get from __annotations__ or attributes
        class_fields = set(getattr(cls, '__annotations__', {}).keys())
    
    # Get model fields
    model_fields = set(model_cls.__fields__.keys())
    
    # Check for mismatches
    missing_in_model = class_fields - model_fields
    missing_in_class = model_fields - class_fields
    
    if missing_in_model:
        errors.append(f"Fields in {cls.__name__} but not in {model_cls.__name__}: {missing_in_model}")
    if missing_in_class:
        errors.append(f"Fields in {model_cls.__name__} but not in {cls.__name__}: {missing_in_class}")
    
    return errors


def validate_dataset_json(dataset_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate dataset JSON structure using Pydantic models"""
    try:
        DatasetModel(**dataset_data)
        return True, []
    except ValidationError as e:
        errors = []
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error['loc'])
            errors.append(f"{loc}: {error['msg']}")
        return False, errors
    except Exception as e:
        return False, [f"Validation error: {str(e)}"]


def validate_dataset_file(dataset_path: str) -> Tuple[bool, List[str]]:
    """Validate a dataset JSON file"""
    try:
        with open(dataset_path, 'r') as f:
            dataset_data = json.load(f)
        return validate_dataset_json(dataset_data)
    except FileNotFoundError:
        return False, [f"Dataset file not found: {dataset_path}"]
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON in dataset file: {str(e)}"]
    except Exception as e:
        return False, [f"Error reading dataset file: {str(e)}"]


def validate_items_before_dataset(items_json_path: str = "director_task/items.json") -> None:
    """Validate items file before generating dataset - raises exception if invalid"""
    is_valid, errors = Item.validate_items_file(items_json_path)
    if not is_valid:
        error_msg = f"Items file validation failed for {items_json_path}:\n" + "\n".join(f"  - {error}" for error in errors)
        raise ValueError(error_msg)


def save_dataset(dataset_name: str, control_samples: List[Sample], test_samples: List[Sample], output_dir: str = "datasets", validate_items: bool = True):
    """
    Save a complete dataset with rendered images and comprehensive JSON metadata.
    
    Args:
        dataset_name: Name of the dataset (used for directory creation)
        control_samples: List of control samples (no ambiguity)
        test_samples: List of test samples (with ambiguity)
        output_dir: Base directory to save datasets in
        validate_items: Whether to validate items.json before proceeding (default: True)
    """
    # Validate items file if requested
    if validate_items:
        validate_items_before_dataset()
    # Create dataset directory structure
    dataset_dir = os.path.join(output_dir, dataset_name)
    images_dir = os.path.join(dataset_dir, "images")
    
    os.makedirs(dataset_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)
    
    # Load items for cache warmup
    try:
        items = Item.load_from_json("director_task/items.json", validate=False)
    except (FileNotFoundError, ValueError):
        items = []
        print("Warning: Could not load items.json for cache warmup. Renderer will work without pre-caching.")
    
    # Initialize renderer with items for cache warmup
    renderer = GridRenderer2D(items=items if items else None)
    
    # Process all samples and build dataset
    dataset_data = {
        "dataset_name": dataset_name,
        "total_samples": len(control_samples) + len(test_samples),
        "control_samples": len(control_samples),
        "test_samples": len(test_samples),
        "samples": []
    }
    
    sample_id = 0
    
    # Process control samples
    for sample in control_samples:
        sample_data = _process_sample(sample, sample_id, "control", renderer, images_dir, dataset_name)
        dataset_data["samples"].append(sample_data)
        sample_id += 1
    
    # Process test samples
    for sample in test_samples:
        sample_data = _process_sample(sample, sample_id, "test", renderer, images_dir, dataset_name)
        dataset_data["samples"].append(sample_data)
        sample_id += 1
    
    # Validate dataset before saving
    is_valid, errors = validate_dataset_json(dataset_data)
    if not is_valid:
        error_msg = f"Generated dataset validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
        raise ValueError(error_msg)
    
    # Save JSON dataset file
    json_path = os.path.join(dataset_dir, f"{dataset_name}.json")
    with open(json_path, 'w') as f:
        json.dump(dataset_data, f, indent=2)
    
    print(f"Dataset saved to {dataset_dir}")
    print(f"  - JSON metadata: {json_path}")
    print(f"  - Rendered images: {images_dir}")
    print(f"  - Total samples: {len(dataset_data['samples'])}")


def load_dataset(dataset_path: str) -> Dict[str, Any]:
    """
    Load a dataset from JSON file.
    
    Args:
        dataset_path: Path to the dataset JSON file
        
    Returns:
        Dict containing the loaded dataset
        
    Raises:
        FileNotFoundError: If dataset file doesn't exist
        ValueError: If dataset validation fails
    """
    # Load the JSON file
    try:
        with open(dataset_path, 'r') as f:
            dataset_data = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in dataset file: {str(e)}")
    
    # Validate the dataset
    is_valid, errors = validate_dataset_json(dataset_data)
    if not is_valid:
        error_msg = f"Dataset validation failed for {dataset_path}:\n" + "\n".join(f"  - {error}" for error in errors)
        raise ValueError(error_msg)
    
    return dataset_data


def _process_sample(sample: Sample, sample_id: int, sample_type: str, renderer: GridRenderer2D, 
                   images_dir: str, dataset_name: str) -> Dict[str, Any]:
    """Process a single sample: render image and extract metadata."""
    
    # Render the grid image
    image_filename = f"{dataset_name}_sample_{sample_id:04d}.png"
    image_path = os.path.join(images_dir, image_filename)
    
    rendered_image = renderer.render_grid(sample.grid)
    rendered_image.save(image_path)
    
    # Extract grid layout details
    grid_items = []
    for y in range(sample.grid.height):    # y = row index
        for x in range(sample.grid.width): # x = column index
            item = sample.grid.item_grid[y][x]  # Grid access: [row][col] = [y][x]
            is_blocked = sample.grid.is_blocked(y, x)  # y=row, x=col
            
            grid_items.append({
                "position": {"x": x, "y": y},  # Store as {x: col, y: row}
                "is_blocked": is_blocked,
                "item": _serialize_item(item) if item else None
            })
    
    # Build sample data structure
    sample_data = {
        "sample_id": sample_id,
        "sample_type": sample_type,
        "image_path": os.path.join("images", image_filename),
        "question": _serialize_question(sample.question),
        "grid": {
            "width": sample.grid.width,
            "height": sample.grid.height,
            "items": grid_items
        },
        "answers": {
            "participant_coordinates": list(sample.answer_coordinates),
            "director_coordinates": list(sample.director_answer_coordinates),
            "is_ambiguous": sample.has_ambiguous_answer()
        },
        "selection_rule_type": sample.selection_rule_type.value,
        "is_physics": sample.is_physics,
        "is_reversed": sample.is_reversed
    }
    
    return sample_data


def _serialize_question(question) -> Dict[str, Any]:
    """Convert a Question or RelationalQuestion object to a serializable dictionary."""
    from director_task.question import RelationalQuestion
    
    if isinstance(question, RelationalQuestion):
        # Handle RelationalQuestion
        return {
            "question_type": "relational",
            "reference_criteria": question.reference_criteria,
            "spatial_relation": question.spatial_relation,
            "target_criteria": question.target_criteria,
            "is_reversed": question.is_reversed,
            "natural_language": question.to_natural_language(),
            "full_question": question.full_question()
        }
    else:
        # Handle regular Question
        return {
            "question_type": "standard",
            "target_type": question.target_type,
            "filter_criteria": question.filter_criteria,
            "selection_rule": question.selection_rule,
            "selection_property": question.selection_property,
            "selection_rule_type": question.selection_rule_type.value,
            "is_reversed": question.is_reversed,
            "natural_language": question.to_natural_language(),
            "full_question": question.full_question()
        }


def _serialize_item(item) -> Dict[str, Any]:
    """Convert an Item object to a serializable dictionary."""
    return {
        "name": item.name,
        "image_path": item.image_path,
        "boolean_properties": item.boolean_properties,
        "scalar_properties": item.scalar_properties
    }


def load_question_from_dict(question_data: Dict[str, Any]):
    """Create a Question object from its JSON representation (as saved in datasets)
    
    Args:
        question_data: Dictionary containing question data from JSON dataset
        
    Returns:
        Question object reconstructed from the data
        
    Raises:
        ValueError: If question_data has invalid format or unsupported question type
    """
    from director_task.question import Question
    
    # Currently only supporting standard questions
    if question_data.get('question_type') != 'standard':
        raise ValueError(f"Only standard questions are currently supported, got: {question_data.get('question_type')}")
    
    return Question.from_dict(question_data)


def test_model_sync() -> None:
    """Test that Pydantic models stay synced with their corresponding classes"""
    from director_task.grid import Grid
    from director_task.question import Question
    from director_task.sample import Sample
    
    # Check sync for classes that have corresponding models
    # add more classes as needed
    sync_checks = [
        (Item, ItemDataModel),  # Item class vs ItemDataModel
        (Grid, GridModel),
        (Question, QuestionModel),
        (Sample, SampleModel)  
    ]
    
    
    all_errors = []
    for cls, model in sync_checks:
        try:
            errors = verify_class_model_sync(cls, model)
            all_errors.extend(errors)
        except ImportError as e:
            # Skip classes that don't exist
            print(f"Skipping sync check for {cls.__name__}: {e}")
            continue
    
    if all_errors:
        raise AssertionError(f"Model sync errors:\n" + "\n".join(all_errors))
    print("All model sync checks passed!")


if __name__ == "__main__":
    # Run sync tests when dataset.py is executed directly
    print("Running model sync verification...")
    try:
        test_model_sync()
    except Exception as e:
        print(f"Sync test failed: {e}")
    
    print("\nTesting validation on a simple dataset structure...")
    # Test validation with a minimal valid dataset
    test_dataset = {
        "dataset_name": "test_dataset",
        "total_samples": 1,
        "control_samples": 1,
        "test_samples": 0,
        "samples": [
            {
                "sample_id": 0,
                "sample_type": "control",
                "image_path": "images/test.png",
                "question": {
                    "question_type": "standard",
                    "target_type": "star",
                    "filter_criteria": {"red": True},
                    "selection_rule": "first",
                    "selection_property": "color",
                    "is_reversed": False,
                    "natural_language": "Select the red star",
                    "full_question": "Please select the red star from the grid"
                },
                "grid": {
                    "width": 2,
                    "height": 2,
                    "items": [
                        {"position": {"x": 0, "y": 0}, "is_blocked": False, "item": None},
                        {"position": {"x": 1, "y": 0}, "is_blocked": False, "item": None},
                        {"position": {"x": 0, "y": 1}, "is_blocked": False, "item": None},
                        {"position": {"x": 1, "y": 1}, "is_blocked": False, "item": None}
                    ]
                },
                "answers": {
                    "participant_coordinates": [[0, 0]],
                    "director_coordinates": [[0, 0]],
                    "is_ambiguous": False
                },
                "selection_rule_type": "none",
                "is_physics": False,
                "is_reversed": False
            }
        ]
    }
    
    is_valid, errors = validate_dataset_json(test_dataset)
    if is_valid:
        print("✓ Test dataset validation passed!")
    else:
        print("✗ Test dataset validation failed:")
        for error in errors:
            print(f"  - {error}")