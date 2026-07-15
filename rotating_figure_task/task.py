import base64
from io import BytesIO
import json
import os
from pathlib import Path
from typing import Any, Dict
import PIL
import PIL.Image
from inspect_ai import Task, task
from inspect_ai.dataset import Dataset, MemoryDataset, Sample, json_dataset
from inspect_ai.model import ChatMessageUser, ContentImage
from inspect_ai.solver import Generate, Solver, TaskState, basic_agent, system_message, use_tools, solver, user_message
from inspect_ai.scorer import Score, Scorer, Target, accuracy, grouped, includes, match, scorer
from inspect_ai.tool import Tool, ToolResult, tool

from rotating_figure_task.dataset import validate_dataset_file

SYSTEM_MESSAGE = """You are participating in a visual perspective-taking experiment. You will be shown images containing a person (or arrow) and possibly a number or symbol on the ground nearby.

Your task is to answer questions about what you can see in the image, considering both your own perspective as the viewer and the perspective of the person/figure in the image.

Pay careful attention to:
- The orientation and position of figures in the image
- Whether numbers appear as "6" or "9" depending on viewing angle
- Spatial relationships (left/right, front/behind) from different perspectives
- What is visible vs. hidden from different viewpoints

Answer exactly as requested in the prompt."""


@tool()
def think() -> Tool:
    async def execute(thoughts: str) -> str:
        """
        Use this tool to stop, think and reason about the task at hand. Particularly useful to build plans and reflect on them prior to executing actions.

        Args:
            thoughts (str): The thoughts or reasoning process of the agent.

        Returns:
            str: The thoughts or reasoning process of the agent.
        """
        return thoughts
    
    return execute


def encode_image(image: PIL.Image.Image):
    """Encode PIL image to base64 string."""
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")



@solver
def add_image() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        """
        Adds the stimulus image to the task state.
        """
        assert state.metadata is not None, "Task state metadata must be initialized."
        assert state.metadata["image_path"] is not None, "Image path must be provided in the task state metadata."
        
        image_path = state.metadata["image_path"]
        assert os.path.isfile(image_path), f"Image path must point to a valid file: {image_path}"
        
        # Add the image to the task state
        state.messages.append(ChatMessageUser(content=[ContentImage(image=image_path)]))
        return state

    return solve


def record_to_sample(record: Dict[str, Any], dataset_path: str) -> Sample:
    """Convert a dataset record to an Inspect AI Sample."""
    dataset_dir = os.path.dirname(dataset_path)
    sample_id = record["sample_id"]
    stimulus_set = record["stimulus_set"]
    question_type = record["question_type"]
    
    # Construct full image path
    image_path = os.path.join(dataset_dir, record["image_path"])
    
    # Get question prompt and correct answer
    question = record["question_prompt"]
    answer = record["correct_answer"]
    
    return Sample(
        input=question,
        id=f"{stimulus_set}_{sample_id:03d}_{question_type}",
        target=answer,
        metadata={
            "image_path": image_path,
            "stimulus_set": stimulus_set,
            "question_type": question_type,
            "sample_id": sample_id,
            "stimulus_metadata": record["metadata"]
        }
    )


def custom_loader(dataset_path: str) -> Dataset:
    """Custom dataset loader for rotating figure datasets."""
    # Validate dataset file before loading
    is_valid, errors = validate_dataset_file(dataset_path)
    if not is_valid:
        error_msg = f"Dataset validation failed for {dataset_path}:\n" + "\n".join(f"  - {error}" for error in errors)
        raise ValueError(error_msg)
    
    # Load JSON data
    json_data = json.load(open(dataset_path, 'r'))
    samples = []
    
    # Convert records to samples
    for item in json_data["samples"]:
        sample = record_to_sample(item, dataset_path)
        samples.append(sample)
    
    return MemoryDataset(
        samples=samples,
        name=json_data["dataset_name"],
        location=dataset_path,
        shuffled=False
    )


@scorer(metrics=[grouped(accuracy(), "stimulus_set"), grouped(accuracy(), "question_type")])
def simple_accuracy_scorer() -> Scorer:
    """Simple scorer that provides basic accuracy metrics."""
    async def score(state: TaskState, target: Target) -> Score:
        # Use the default includes() behavior for basic scoring
        includes_scorer = includes()
        base_score = await includes_scorer(state, target)
        return Score(
            value=base_score.value,
            answer=base_score.answer,
            explanation=base_score.explanation,
        )
    
    return score


@scorer(metrics=[accuracy()])
def exact_match_scorer() -> Scorer:
    """Scorer that requires exact string matching."""
    async def score(state: TaskState, target: Target) -> Score:
        # Use exact match scoring
        match_scorer = match()
        return await match_scorer(state, target)
    
    return score


@task
def rotating_figure_task(
    agent_solver: Solver | None = None,
    dataset_path: str | None = None,
    exact_match: bool = False
) -> Task:
    """
    Rotating figure visual perspective-taking task.

    Args:
        agent_solver: Custom solver to use (defaults to basic_agent)
        dataset_path: Path to dataset JSON file (defaults to looking in datasets/)
        exact_match: Whether to use exact string matching for scoring (default: False)
    """
    if dataset_path is None:
        # Look for datasets in the datasets directory
        dataset_path = os.path.join(Path(__file__).parent.parent, "datasets", "rotating_figure_default", "rotating_figure_default.json")
    else:
        # If dataset_path is relative, try current working directory first, then repo root
        if not os.path.isabs(dataset_path):
            # First try relative to current working directory
            cwd_path = os.path.join(os.getcwd(), dataset_path)
            if os.path.exists(cwd_path):
                dataset_path = cwd_path
            else:
                # Fall back to relative to repository root
                dataset_path = os.path.join(Path(__file__).parent.parent, dataset_path)

    # Choose scorer based on exact_match parameter
    if exact_match:
        scorer_func = exact_match_scorer()
    else:
        scorer_func = simple_accuracy_scorer()

    solver_chain = [
        system_message(SYSTEM_MESSAGE),
        use_tools([think()], tool_choice="any"),
        add_image(),
        agent_solver or basic_agent(message_limit=10),
    ]

    return Task(
        dataset=custom_loader(dataset_path),
        solver=solver_chain,
        scorer=scorer_func,
    )

