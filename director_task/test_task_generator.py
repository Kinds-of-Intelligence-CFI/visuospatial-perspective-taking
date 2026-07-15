import unittest
from director_task.item import Item
from director_task.grid import Grid
from director_task.question import Question, QuestionConstraints, SelectionRuleType
from director_task.sample import Sample


class TestQuestion(unittest.TestCase):
    
    def setUp(self):
        # Create a test grid with various items
        self.grid = Grid(width=3, height=3)
        
        # Add test items (grid[y][x] format)
        # Position (0,0): small red star (size=1)
        self.grid.item_grid[0][0] = Item("item1", "path1", 
                                        {"star": True, "red": True}, 
                                        {"size": 1})
        # Position (1,0): large blue circle (size=3)  
        self.grid.item_grid[0][1] = Item("item2", "path2", 
                                        {"circle": True, "blue": True}, 
                                        {"size": 3})
        # Position (2,0): small blue star (size=1)
        self.grid.item_grid[0][2] = Item("item3", "path3", 
                                        {"star": True, "blue": True}, 
                                        {"size": 1})
        
        # Position (0,1): large red circle (size=2)
        self.grid.item_grid[1][0] = Item("item4", "path4", 
                                        {"circle": True, "red": True}, 
                                        {"size": 2})
        # Position (1,1): empty
        # Position (2,1): small red car (size=1)
        self.grid.item_grid[1][2] = Item("item5", "path5", 
                                        {"car": True, "red": True}, 
                                        {"size": 1})
        
        # Position (0,2): large blue star (size=2)
        self.grid.item_grid[2][0] = Item("item6", "path6", 
                                        {"star": True, "blue": True}, 
                                        {"size": 2})
        # Position (1,2): small red star (size=1)
        self.grid.item_grid[2][1] = Item("item7", "path7", 
                                        {"star": True, "red": True}, 
                                        {"size": 1})
        # Position (2,2): empty

    def test_natural_language_simple_boolean(self):
        # "the red car"
        q = Question("car", {"red": True, "car": True})
        self.assertEqual(q.to_natural_language(add_perspective_suffix=False), "the red car")
        
    def test_natural_language_with_selection(self):
        # "the smallest star"
        q = Question("star", {"star": True}, "smallest", "size")
        self.assertEqual(q.to_natural_language(add_perspective_suffix=False), "the smallest star")
        
    def test_natural_language_complex(self):
        # "the largest red circle"
        q = Question("circle", {"circle": True, "red": True}, "largest", "size")
        self.assertEqual(q.to_natural_language(add_perspective_suffix=False), "the largest red circle")
        
    def test_natural_language_topmost(self):
        # "the topmost blue star"
        q = Question("star", {"star": True, "blue": True}, "topmost")
        self.assertEqual(q.to_natural_language(add_perspective_suffix=False), "the topmost blue star")
        
    def test_natural_language_unmapped_property(self):
        # Test fallback for properties not in PROPERTY_TO_STRING
        q = Question("item", {"is_valuable": True}, "smallest", "size")
        self.assertEqual(q.to_natural_language(add_perspective_suffix=False), "the smallest valuable item")

    def test_find_target_simple_boolean(self):
        # Find "the red car" - should return (2, 1)
        q = Question("car", {"red": True, "car": True})
        result = q.find_target(self.grid)
        self.assertEqual(result, {(2, 1)})
        
    def test_find_target_smallest(self):
        # Find "the smallest star" - need to include star in filter for find_target to work
        q = Question("star", {"star": True}, "smallest", "size")
        result = q.find_target(self.grid)
        # Stars with size 1: (0,0), (2,0), (1,2)
        self.assertEqual(result, {(0, 0), (2, 0), (1, 2)})
        
    def test_find_target_largest(self):
        # Find "the largest star" - need to include star in filter for find_target to work
        q = Question("star", {"star": True}, "largest", "size")
        result = q.find_target(self.grid)
        self.assertEqual(result, {(0, 2)})
        
    def test_find_target_leftmost(self):
        # Find "the leftmost star" - need to include star in filter for find_target to work
        q = Question("star", {"star": True}, "leftmost")
        result = q.find_target(self.grid)
        self.assertEqual(result, {(0, 0), (0, 2)})
        
    def test_find_target_topmost(self):
        # Find "the topmost blue star" - need to include both star and blue for find_target to work
        q = Question("star", {"star": True, "blue": True}, "topmost")
        result = q.find_target(self.grid)
        self.assertEqual(result, {(2, 0)})
        
    def test_find_target_no_matches(self):
        # Try to find something that doesn't exist
        q = Question("triangle", {"triangle": True})
        with self.assertRaises(ValueError):
            q.find_target(self.grid)
            
    def test_find_target_invalid_selection_rule(self):
        q = Question("star", {"star": True}, "invalid_rule", "size")
        with self.assertRaises(ValueError):
            q.find_target(self.grid)


class TestSample(unittest.TestCase):
    
    def setUp(self):
        self.grid = Grid(width=2, height=2)
        self.grid.item_grid[0][0] = Item("star", "path", {"star": True}, {"size": 1})
        self.grid.item_grid[0][1] = Item("circle", "path", {"circle": True}, {"size": 2})
        
    def test_sample_creation(self):
        q = Question("star", {"star": True})
        sample = Sample(self.grid, q, {(0, 0)}, selection_rule_type=SelectionRuleType.NONE)
        self.assertEqual(sample.answer_coordinates, {(0, 0)})
        self.assertEqual(sample.selection_rule_type, SelectionRuleType.NONE)
        self.assertFalse(sample.is_physics)
        # Check if spatial based on selection rule type
        spatial_types = [SelectionRuleType.SPATIAL_SAME_PERSPECTIVE, SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE]
        is_spatial = sample.selection_rule_type in spatial_types
        self.assertFalse(is_spatial)
        
    def test_from_single_answer(self):
        q = Question("star", {"star": True})
        # Using explicit parameter names for clarity: answer_col=0, answer_row=0
        sample = Sample.from_single_answer(self.grid, q, answer_col=0, answer_row=0, 
                                         selection_rule_type=SelectionRuleType.SIZE_RELATED, 
                                         is_physics=True)
        self.assertEqual(sample.answer_coordinates, {(0, 0)})  # Expected: (x, y) = (col, row)
        self.assertEqual(sample.selection_rule_type, SelectionRuleType.SIZE_RELATED)
        self.assertTrue(sample.is_physics)
        # Check if spatial based on selection rule type
        spatial_types = [SelectionRuleType.SPATIAL_SAME_PERSPECTIVE, SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE]
        is_spatial = sample.selection_rule_type in spatial_types
        self.assertFalse(is_spatial)  # SIZE_RELATED is not spatial
        
    def test_verify_answer_correct(self):
        q = Question("star", {"star": True})
        sample = Sample(self.grid, q, {(0, 0)})
        self.assertTrue(sample.verify_answer())
        
    def test_verify_answer_incorrect(self):
        q = Question("star", {"star": True})
        sample = Sample(self.grid, q, {(0, 1)})  # Wrong answer
        self.assertFalse(sample.verify_answer())
    
    def test_spatial_sample_types(self):
        q = Question("star", {"star": True}, "leftmost")
        
        # Test SPATIAL_DIFFERENT_PERSPECTIVE
        spatial_diff_sample = Sample(self.grid, q, {(0, 0)}, 
                                   selection_rule_type=SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE)
        # Check if spatial based on selection rule type
        spatial_types = [SelectionRuleType.SPATIAL_SAME_PERSPECTIVE, SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE]
        is_spatial = spatial_diff_sample.selection_rule_type in spatial_types
        self.assertTrue(is_spatial)
        self.assertEqual(spatial_diff_sample.selection_rule_type, SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE)
        
        # Test SPATIAL_SAME_PERSPECTIVE
        spatial_same_sample = Sample(self.grid, q, {(0, 0)}, 
                                   selection_rule_type=SelectionRuleType.SPATIAL_SAME_PERSPECTIVE)
        # Check if spatial based on selection rule type
        spatial_types = [SelectionRuleType.SPATIAL_SAME_PERSPECTIVE, SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE]
        is_spatial = spatial_same_sample.selection_rule_type in spatial_types
        self.assertTrue(is_spatial)
        self.assertEqual(spatial_same_sample.selection_rule_type, SelectionRuleType.SPATIAL_SAME_PERSPECTIVE)
        
        # Test SIZE_RELATED (not spatial)
        size_sample = Sample(self.grid, q, {(0, 0)}, 
                           selection_rule_type=SelectionRuleType.SIZE_RELATED)
        # Check if spatial based on selection rule type
        spatial_types = [SelectionRuleType.SPATIAL_SAME_PERSPECTIVE, SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE]
        is_spatial = size_sample.selection_rule_type in spatial_types
        self.assertFalse(is_spatial)
        self.assertEqual(size_sample.selection_rule_type, SelectionRuleType.SIZE_RELATED)


class TestQuestionConstraints(unittest.TestCase):
    
    def test_constraint_creation(self):
        constraints = QuestionConstraints(SelectionRuleType.SIZE_RELATED, is_physics=True)
        self.assertEqual(constraints.selection_rule_type, SelectionRuleType.SIZE_RELATED)
        self.assertTrue(constraints.is_physics)
        # Check if spatial based on selection rule type
        spatial_types = [SelectionRuleType.SPATIAL_SAME_PERSPECTIVE, SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE]
        is_spatial = constraints.selection_rule_type in spatial_types
        self.assertFalse(is_spatial)
        
    def test_spatial_constraints(self):
        spatial_diff_constraints = QuestionConstraints(SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE, False)
        spatial_same_constraints = QuestionConstraints(SelectionRuleType.SPATIAL_SAME_PERSPECTIVE, False)
        
        # Check if spatial based on selection rule type
        spatial_types = [SelectionRuleType.SPATIAL_SAME_PERSPECTIVE, SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE]
        is_spatial_diff = spatial_diff_constraints.selection_rule_type in spatial_types
        is_spatial_same = spatial_same_constraints.selection_rule_type in spatial_types
        
        self.assertTrue(is_spatial_diff)
        self.assertTrue(is_spatial_same)
        
    def test_selection_rule_mapping(self):
        # Test SIZE_RELATED
        size_constraints = QuestionConstraints(SelectionRuleType.SIZE_RELATED, False)
        expected_size_rules = ["smallest", "largest"]
        self.assertEqual(size_constraints.get_selection_rules(), expected_size_rules)
        
        # Test SPATIAL_SAME_PERSPECTIVE
        spatial_same_constraints = QuestionConstraints(SelectionRuleType.SPATIAL_SAME_PERSPECTIVE, False)
        expected_spatial_same_rules = ["topmost", "bottommost"]
        self.assertEqual(spatial_same_constraints.get_selection_rules(), expected_spatial_same_rules)
        
        # Test SPATIAL_DIFFERENT_PERSPECTIVE
        spatial_diff_constraints = QuestionConstraints(SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE, False)
        expected_spatial_diff_rules = ["leftmost", "rightmost"]
        self.assertEqual(spatial_diff_constraints.get_selection_rules(), expected_spatial_diff_rules)
        
        # Test NONE
        none_constraints = QuestionConstraints(SelectionRuleType.NONE, False)
        expected_none_rules = [None]
        self.assertEqual(none_constraints.get_selection_rules(), expected_none_rules)
    
    def test_question_roundtrip_serialization(self):
        """Test that Question -> dict -> Question preserves all data"""
        from director_task.dataset import _serialize_question, load_question_from_dict
        
        # Test various types of questions
        test_cases = [
            # Simple question with no selection rule
            Question("car", {"red": True, "car": True}, selection_rule_type=SelectionRuleType.NONE),
            
            # Question with size-based selection rule
            Question("star", {"star": True, "blue": True}, "smallest", "size", 
                    SelectionRuleType.SIZE_RELATED, is_reversed=False),
            
            # Question with spatial selection rule and reversal
            Question("circle", {"circle": True, "red": True}, "leftmost", None,
                    SelectionRuleType.SPATIAL_DIFFERENT_PERSPECTIVE, is_reversed=True),
            
            # Question with physics properties
            Question("book", {"book": True, "stackable": True}, "largest", "size",
                    SelectionRuleType.SIZE_RELATED, is_reversed=False)
        ]
        
        for original_question in test_cases:
            with self.subTest(question=original_question.to_natural_language()):
                # Step 1: Serialize question to dict (as done in dataset generation)
                question_dict = _serialize_question(original_question)
                
                # Step 2: Deserialize dict back to question object
                reconstructed_question = load_question_from_dict(question_dict)
                
                # Step 3: Verify all fields are preserved
                self.assertEqual(original_question.target_type, reconstructed_question.target_type)
                self.assertEqual(original_question.filter_criteria, reconstructed_question.filter_criteria)
                self.assertEqual(original_question.selection_rule, reconstructed_question.selection_rule)
                self.assertEqual(original_question.selection_property, reconstructed_question.selection_property)
                self.assertEqual(original_question.selection_rule_type, reconstructed_question.selection_rule_type)
                self.assertEqual(original_question.is_reversed, reconstructed_question.is_reversed)
                
                # Step 4: Verify generated natural language is identical
                self.assertEqual(original_question.to_natural_language(), 
                               reconstructed_question.to_natural_language())
                self.assertEqual(original_question.full_question(), 
                               reconstructed_question.full_question())


if __name__ == '__main__':
    unittest.main()