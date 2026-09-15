import unittest

import pandas as pd

from director_task.clean_results import CONTROL_BLOCK_DESCRIPTION, clean_director_results


class CleanResultsTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(
            dataset_path="dataset.json", image_path="sample.png", model="openai/o3",
            ascii_image=True, task_name="directors_task", block_description="Director prompt",
            sample_type="control", model_answer="A1",
        )

    def test_excludes_control_runs_with_missing_task_name(self):
        rows = [self.row, dict(self.row, task_name=None,
                              block_description=CONTROL_BLOCK_DESCRIPTION),
                dict(self.row, task_name="control_task")]
        result = clean_director_results(pd.DataFrame(rows))
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0].sample_type, "control")

    def test_removes_copies_but_preserves_models_formats_and_datasets(self):
        rows = [self.row, self.row, dict(self.row, ascii_image=False),
                dict(self.row, model="openai/gpt-4o"),
                dict(self.row, dataset_path="other.json")]
        result = clean_director_results(pd.DataFrame(rows))
        self.assertEqual(len(result), 4)
        pd.testing.assert_frame_equal(result, clean_director_results(result))

    def test_conflicting_answers_fail(self):
        with self.assertRaisesRegex(ValueError, "conflicting"):
            clean_director_results(pd.DataFrame([
                self.row, dict(self.row, model_answer="B2")]))

    def test_missing_director_task_name_is_normalized(self):
        result = clean_director_results(pd.DataFrame([dict(self.row, task_name=None)]))
        self.assertEqual(result.iloc[0].task_name, "directors_task")


if __name__ == "__main__":
    unittest.main()
