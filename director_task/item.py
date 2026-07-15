import json
from typing import Optional, List, Tuple
import copy
import os
import jsonschema


class Item:
    _default_properties_cache = None
    
    @classmethod
    def get_default_properties(cls):
        """Load default properties from defaults.json file"""
        if cls._default_properties_cache is None:
            defaults_path = os.path.join(os.path.dirname(__file__), "defaults.json")
            try:
                with open(defaults_path, 'r') as f:
                    cls._default_properties_cache = json.load(f)
            except FileNotFoundError:
                raise FileNotFoundError(f"defaults.json not found at {defaults_path}")
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in defaults.json: {str(e)}")
        return cls._default_properties_cache
    
    @classmethod
    def reload_defaults(cls):
        """Force reload of default properties from file"""
        cls._default_properties_cache = None
        return cls.get_default_properties()
    
    @classmethod
    def save_default_properties(cls, defaults):
        """Save default properties to defaults.json file"""
        defaults_path = os.path.join(os.path.dirname(__file__), "defaults.json")
        with open(defaults_path, 'w') as f:
            json.dump(defaults, f, indent=2)
        cls._default_properties_cache = defaults
    
    @classmethod
    def create_default_item(cls):
        """Create an Item object representing default values"""
        defaults = cls.get_default_properties()
        return cls(
            name=defaults.get("name", "[DEFAULT VALUES]"),
            image_path=defaults.get("image_path", ""),
            boolean_properties=defaults["boolean_properties"],
            scalar_properties=defaults["scalar_properties"]
        )
    
    @classmethod
    def save_default_item(cls, default_item):
        """Save a default item back to defaults.json"""
        defaults = {
            "name": default_item.name,
            "image_path": default_item.image_path,
            "boolean_properties": default_item.boolean_properties,
            "scalar_properties": default_item.scalar_properties
        }
        cls.save_default_properties(defaults)
    
    @classmethod
    def add_boolean_property(cls, prop_name: str, default_value: bool = False, items: Optional[List['Item']] = None):
        """Add a new boolean property to defaults and all existing items"""
        defaults = cls.get_default_properties()
        if prop_name in defaults["boolean_properties"]:
            raise ValueError(f"Boolean property '{prop_name}' already exists")
        
        defaults["boolean_properties"][prop_name] = default_value
        cls.save_default_properties(defaults)
        
        # Add to all existing items
        if items:
            for item in items:
                if prop_name not in item.boolean_properties:
                    item.boolean_properties[prop_name] = default_value
    
    @classmethod
    def add_scalar_property(cls, prop_name: str, default_value: int = 0, items: Optional[List['Item']] = None):
        """Add a new scalar property to defaults and all existing items"""
        defaults = cls.get_default_properties()
        if prop_name in defaults["scalar_properties"]:
            raise ValueError(f"Scalar property '{prop_name}' already exists")
        
        defaults["scalar_properties"][prop_name] = default_value
        cls.save_default_properties(defaults)
        
        # Add to all existing items
        if items:
            for item in items:
                if prop_name not in item.scalar_properties:
                    item.scalar_properties[prop_name] = default_value
    
    @classmethod
    def can_remove_boolean_property(cls, prop_name: str, items: List['Item']) -> Tuple[bool, str]:
        """Check if a boolean property can be removed (all items use default value)"""
        defaults = cls.get_default_properties()
        if prop_name not in defaults["boolean_properties"]:
            return False, f"Boolean property '{prop_name}' does not exist"
        
        default_value = defaults["boolean_properties"][prop_name]
        non_default_items = []
        
        for item in items:
            if (prop_name in item._explicit_boolean_properties or 
                item.boolean_properties.get(prop_name) != default_value):
                non_default_items.append(item.name)
        
        if non_default_items:
            return False, f"Cannot remove '{prop_name}': items using non-default values: {', '.join(non_default_items)}"
        
        return True, ""
    
    @classmethod
    def can_remove_scalar_property(cls, prop_name: str, items: List['Item']) -> Tuple[bool, str]:
        """Check if a scalar property can be removed (all items use default value)"""
        defaults = cls.get_default_properties()
        if prop_name not in defaults["scalar_properties"]:
            return False, f"Scalar property '{prop_name}' does not exist"
        
        default_value = defaults["scalar_properties"][prop_name]
        non_default_items = []
        
        for item in items:
            if (prop_name in item._explicit_scalar_properties or 
                item.scalar_properties.get(prop_name) != default_value):
                non_default_items.append(item.name)
        
        if non_default_items:
            return False, f"Cannot remove '{prop_name}': items using non-default values: {', '.join(non_default_items)}"
        
        return True, ""
    
    @classmethod
    def remove_boolean_property(cls, prop_name: str, items: List['Item']):
        """Remove a boolean property from defaults and all items"""
        can_remove, error_msg = cls.can_remove_boolean_property(prop_name, items)
        if not can_remove:
            raise ValueError(error_msg)
        
        defaults = cls.get_default_properties()
        del defaults["boolean_properties"][prop_name]
        cls.save_default_properties(defaults)
        
        # Remove from all items
        for item in items:
            if prop_name in item.boolean_properties:
                del item.boolean_properties[prop_name]
            if prop_name in item._explicit_boolean_properties:
                item._explicit_boolean_properties.remove(prop_name)
    
    @classmethod
    def remove_scalar_property(cls, prop_name: str, items: List['Item']):
        """Remove a scalar property from defaults and all items"""
        can_remove, error_msg = cls.can_remove_scalar_property(prop_name, items)
        if not can_remove:
            raise ValueError(error_msg)
        
        defaults = cls.get_default_properties()
        del defaults["scalar_properties"][prop_name]
        cls.save_default_properties(defaults)
        
        # Remove from all items
        for item in items:
            if prop_name in item.scalar_properties:
                del item.scalar_properties[prop_name]
            if prop_name in item._explicit_scalar_properties:
                item._explicit_scalar_properties.remove(prop_name)
    
    def __init__(self, name: str, image_path: str, boolean_properties: Optional[dict] = None, scalar_properties: Optional[dict] = None):
        self.name = name
        self.image_path = image_path
        
        # Track which properties were explicitly set (not using defaults)
        self._explicit_boolean_properties = set()
        self._explicit_scalar_properties = set()
        
        # Merge with defaults
        defaults = self.get_default_properties()
        self.boolean_properties = copy.deepcopy(defaults["boolean_properties"])
        self.scalar_properties = copy.deepcopy(defaults["scalar_properties"])
        
        if boolean_properties:
            self.boolean_properties.update(boolean_properties)
            self._explicit_boolean_properties.update(boolean_properties.keys())
        if scalar_properties:
            self.scalar_properties.update(scalar_properties)
            self._explicit_scalar_properties.update(scalar_properties.keys())

    @classmethod
    def load_from_json(cls, json_path: str, validate: bool = True) -> List['Item']:
        """Load item templates from a JSON file and return as list of Item objects
        
        Args:
            json_path: Path to the JSON file
            validate: Whether to validate the file before loading (default: True)
            
        Raises:
            ValueError: If validation fails and validate=True
        """
        if validate:
            is_valid, errors = cls.validate_items_file(json_path)
            if not is_valid:
                error_msg = "Item validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
                raise ValueError(error_msg)
        
        with open(json_path, 'r') as f:
            items_data = json.load(f)
        
        items = []
        for item_data in items_data:
            item = cls(
                name=item_data["name"],
                image_path=item_data["image_path"],
                boolean_properties=item_data.get("boolean_properties", {}),
                scalar_properties=item_data.get("scalar_properties", {})
            )
            items.append(item)
        
        return items
    
    def get_non_default_properties(self) -> dict:
        """Return only properties that differ from defaults for compact storage"""
        result = {}
        
        # Check boolean properties
        defaults = self.get_default_properties()
        non_default_bool = {}
        for key, value in self.boolean_properties.items():
            if value != defaults["boolean_properties"].get(key, False):
                non_default_bool[key] = value
        if non_default_bool:
            result["boolean_properties"] = non_default_bool
        
        # Check scalar properties
        non_default_scalar = {}
        for key, value in self.scalar_properties.items():
            if value != defaults["scalar_properties"].get(key, 0):
                non_default_scalar[key] = value
        if non_default_scalar:
            result["scalar_properties"] = non_default_scalar
        
        return result
    
    def is_using_default_boolean(self, prop_name: str) -> bool:
        """Check if a boolean property is using its default value (not explicitly set)"""
        return prop_name not in self._explicit_boolean_properties
    
    def is_using_default_scalar(self, prop_name: str) -> bool:
        """Check if a scalar property is using its default value (not explicitly set)"""
        return prop_name not in self._explicit_scalar_properties
    
    def can_merge_boolean_property(self, prop_name: str) -> bool:
        """Check if a boolean property can be merged (explicitly set but matches default)"""
        defaults = self.get_default_properties()
        return (prop_name in self._explicit_boolean_properties and 
                self.boolean_properties[prop_name] == defaults["boolean_properties"].get(prop_name, False))
    
    def can_merge_scalar_property(self, prop_name: str) -> bool:
        """Check if a scalar property can be merged (explicitly set but matches default)"""
        defaults = self.get_default_properties()
        return (prop_name in self._explicit_scalar_properties and 
                self.scalar_properties[prop_name] == defaults["scalar_properties"].get(prop_name, 0))
    
    def merge_boolean_property_to_default(self, prop_name: str):
        """Merge a boolean property back to using its default value"""
        if prop_name in self._explicit_boolean_properties:
            self._explicit_boolean_properties.remove(prop_name)
            defaults = self.get_default_properties()
            self.boolean_properties[prop_name] = defaults["boolean_properties"].get(prop_name, False)
    
    def merge_scalar_property_to_default(self, prop_name: str):
        """Merge a scalar property back to using its default value"""
        if prop_name in self._explicit_scalar_properties:
            self._explicit_scalar_properties.remove(prop_name)
            defaults = self.get_default_properties()
            self.scalar_properties[prop_name] = defaults["scalar_properties"].get(prop_name, 0)
    
    def merge_all_matching_properties(self):
        """Merge all properties that match their default values back to using defaults"""
        # Check boolean properties
        bool_props_to_merge = []
        for prop_name in list(self._explicit_boolean_properties):
            if self.can_merge_boolean_property(prop_name):
                bool_props_to_merge.append(prop_name)
        
        for prop_name in bool_props_to_merge:
            self.merge_boolean_property_to_default(prop_name)
        
        # Check scalar properties
        scalar_props_to_merge = []
        for prop_name in list(self._explicit_scalar_properties):
            if self.can_merge_scalar_property(prop_name):
                scalar_props_to_merge.append(prop_name)
        
        for prop_name in scalar_props_to_merge:
            self.merge_scalar_property_to_default(prop_name)
        
        return len(bool_props_to_merge) + len(scalar_props_to_merge)
    
    def set_boolean_property(self, prop_name: str, value: bool):
        """Explicitly set a boolean property value"""
        self.boolean_properties[prop_name] = value
        self._explicit_boolean_properties.add(prop_name)
    
    def set_scalar_property(self, prop_name: str, value):
        """Explicitly set a scalar property value"""
        self.scalar_properties[prop_name] = value
        self._explicit_scalar_properties.add(prop_name)
    
    def to_dict(self, compact: bool = False) -> dict:
        """Convert item to dictionary for JSON serialization"""
        if compact:
            result = {
                "name": self.name,
                "image_path": self.image_path
            }
            result.update(self.get_non_default_properties())
            return result
        else:
            return {
                "name": self.name,
                "image_path": self.image_path,
                "boolean_properties": self.boolean_properties,
                "scalar_properties": self.scalar_properties
            }
    
    @classmethod
    def validate_json_schema(cls, json_data: List[dict], schema_path: str = None) -> Tuple[bool, List[str]]:
        """Validate JSON data against the items schema"""
        if schema_path is None:
            schema_path = os.path.join(os.path.dirname(__file__), "items_schema.json")
        
        try:
            with open(schema_path, 'r') as f:
                schema = json.load(f)
            
            jsonschema.validate(json_data, schema)
            return True, []
        except jsonschema.ValidationError as e:
            return False, [f"Schema validation error: {e.message}"]
        except FileNotFoundError:
            return False, [f"Schema file not found: {schema_path}"]
        except Exception as e:
            return False, [f"Validation error: {str(e)}"]
    
    @classmethod
    def validate_business_rules(cls, items: List['Item']) -> List[str]:
        """Validate business rules like unique names, consistent properties"""
        errors = []
        
        if not items:
            return errors
        
        # Check for unique names
        names = set()
        for item in items:
            if item.name in names:
                errors.append(f"Duplicate item name: '{item.name}'")
            names.add(item.name)
        
        # Check for consistent property structure
        defaults = cls.get_default_properties()
        expected_bool_props = set(defaults["boolean_properties"].keys())
        expected_scalar_props = set(defaults["scalar_properties"].keys())
        
        for item in items:
            # Check boolean properties
            actual_bool_props = set(item.boolean_properties.keys())
            if actual_bool_props != expected_bool_props:
                missing = expected_bool_props - actual_bool_props
                extra = actual_bool_props - expected_bool_props
                if missing:
                    errors.append(f"Item '{item.name}' missing boolean properties: {missing}")
                if extra:
                    errors.append(f"Item '{item.name}' has unexpected boolean properties: {extra}")
            
            # Check scalar properties
            actual_scalar_props = set(item.scalar_properties.keys())
            if actual_scalar_props != expected_scalar_props:
                missing = expected_scalar_props - actual_scalar_props
                extra = actual_scalar_props - expected_scalar_props
                if missing:
                    errors.append(f"Item '{item.name}' missing scalar properties: {missing}")
                if extra:
                    errors.append(f"Item '{item.name}' has unexpected scalar properties: {extra}")
        
        return errors
    
    @classmethod
    def validate_items_file(cls, json_path: str) -> Tuple[bool, List[str]]:
        """Comprehensive validation of an items JSON file"""
        all_errors = []
        
        try:
            # Load and validate JSON structure
            with open(json_path, 'r') as f:
                json_data = json.load(f)
            
            # Schema validation
            schema_valid, schema_errors = cls.validate_json_schema(json_data)
            all_errors.extend(schema_errors)
            
            if schema_valid:
                # Create Item objects and validate business rules
                items = []
                for item_data in json_data:
                    item = cls(
                        name=item_data["name"],
                        image_path=item_data["image_path"],
                        boolean_properties=item_data.get("boolean_properties", {}),
                        scalar_properties=item_data.get("scalar_properties", {})
                    )
                    items.append(item)
                
                business_errors = cls.validate_business_rules(items)
                all_errors.extend(business_errors)
            
            return len(all_errors) == 0, all_errors
            
        except FileNotFoundError:
            return False, [f"File not found: {json_path}"]
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON: {str(e)}"]
        except Exception as e:
            return False, [f"Validation error: {str(e)}"]