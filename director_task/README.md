# Director task

This foldr contains all of the code for the director task where the director gives instructions to a participant that require the participant to consider the director's perspective to complete. This contains the code for generating the grid of objects and the questions to go along with them based on what ambigulity we want to test.


## Setup 
The first thing to do is to create a virtual environment and install the requirements. 
The followign commands should be run from the root of the repository rather than this directory.
```bash
python -m venv venv
source venv/bin/activate
pip install -e .
```

## Dataset generation
Note: the item images used to render the grids are not distributed with this
repository for licensing reasons. They are available in the OSF project linked
in the main README and should be placed in `director_task/images/` before
generating datasets.

To generate the dataset, run the following command from the root of the repository:
```bash
python -m director_task.task_generator --dataset_name <dataset_name> --dataset_size <dataset_size>
```
You can see other options by running:
```bash
python -m director_task.task_generator --help
```

## Reproducing Paper Results

To generate the exact datasets used in the paper, run the following commands. The main variable between datasets is the related item proportion (test_related_item_prop and control_related_item_prop), which varies between [0.3, 0.5, 0.7, 0.9]:

**Related item proportion 0.3:**
```bash
python -m director_task.task_generator \
    --dataset_name paper_dataset_rip_0.3 \
    --dataset_size 1000 \
    --grid_width 4 \
    --grid_height 4 \
    --control_portion 0.5 \
    --size_prop 0.25 \
    --spatial_same_prop 0.25 \
    --spatial_diff_prop 0.25 \
    --physics_prop 0.5 \
    --test_related_item_prop 0.3 \
    --control_related_item_prop 0.3 \
    --related_blocked_prop 0.5 \
    --item_fill_prop 0.9
```

**Related item proportion 0.5:**
```bash
python -m director_task.task_generator \
    --dataset_name paper_dataset_rip_0.5 \
    --dataset_size 1000 \
    --grid_width 4 \
    --grid_height 4 \
    --control_portion 0.5 \
    --size_prop 0.25 \
    --spatial_same_prop 0.25 \
    --spatial_diff_prop 0.25 \
    --physics_prop 0.5 \
    --test_related_item_prop 0.5 \
    --control_related_item_prop 0.5 \
    --related_blocked_prop 0.5 \
    --item_fill_prop 0.9
```

**Related item proportion 0.7:**
```bash
python -m director_task.task_generator \
    --dataset_name paper_dataset_rip_0.7 \
    --dataset_size 1000 \
    --grid_width 4 \
    --grid_height 4 \
    --control_portion 0.5 \
    --size_prop 0.25 \
    --spatial_same_prop 0.25 \
    --spatial_diff_prop 0.25 \
    --physics_prop 0.5 \
    --test_related_item_prop 0.7 \
    --control_related_item_prop 0.7 \
    --related_blocked_prop 0.5 \
    --item_fill_prop 0.9
```

**Related item proportion 0.9:**
```bash
python -m director_task.task_generator \
    --dataset_name paper_dataset_rip_0.9 \
    --dataset_size 1000 \
    --grid_width 4 \
    --grid_height 4 \
    --control_portion 0.5 \
    --size_prop 0.25 \
    --spatial_same_prop 0.25 \
    --spatial_diff_prop 0.25 \
    --physics_prop 0.5 \
    --test_related_item_prop 0.9 \
    --control_related_item_prop 0.9 \
    --related_blocked_prop 0.5 \
    --item_fill_prop 0.9
```

## Edit Items
To edit the items that are used in the dataset, you can modify the `items.json` file in this directory. This file contains a list of objects that can be used in the grid. Each object should have a unique name and a list of properties that describe it.
Rather than manually editing the file you can use the item_editor tool which will make it much easier and perform any validation that is needed.
To run the item editor, use the following command:
```bash
python -m director_task.item_editor
```

## Running the evaluation
To run the evaluation we used the Inspect AI framework. It allows us to run the evaluation several different way with different parameters. The simplest way is as follows:
```bash
inspect eval director_task/task.py@directors_task --model <model_name> -T dataset_path=<path_to_json>
```
You can see other options by running:
```bash
inspect eval --help
```
Additionally, you can run the evaluation from visual studio code by using the inspect extension. You can find more information on how to do this in the [Inspect AI documentation](https://inspect.aisi.org.uk/vscode.html).

## Evaluation sweep
`run_director_eval_sweep.py` automates running the evaluation across several datasets that vary the related item and fill proportions, in both image and ASCII modes, plus the control task. It was used to run the paper's evaluations.

```bash
python -m director_task.run_director_eval_sweep --model <model_name>
```

Note that it discovers datasets in the `datasets/` directory by name and only matches datasets named `director_task_large_related_prop_<X>_fill_prop_<Y>` (for example `director_task_large_related_prop_0.7_fill_prop_0.9`), so datasets generated with other names (including the commands above) will not be picked up. Run `python -m director_task.run_director_eval_sweep --help` for the full options, including `--dry-run` to preview what would be evaluated.


# How samples are generated
This section describes how each sample in the dataset is generated. it doesn't cover the specific details but should give a good idea of the flow.

## selecting sample options 
Before generating a sample for the dataset the code first calculates if the sample should be:
\- control or test
\- physics or non-physics related 
\- the selection rule to use for the question (None, size_related, spatial_same_perspective, spatial_different_perspective)

Once these values have been selected the code them moves to generate the actual sample.

## genarating the question

The first step to creating a sample is to first take the set of all items in the items file the selection rule and if the sample needs to be physics related and use that to generate a new question. The code does this by first collecting every combination of item and removeing the ones without physics related properties if the question if physics based and vice versa for non physics related. 

Next, if the selection rule is size related then we filter out any sets of items that only contain a single value for the size property.

Finally, we select a random combination of item name + boolean properties from the remaining combinations. Note that the item name is something like "car" or "book" but can also be "item" in the generic case. This combination creates a question object that handles converting the set of properies into natural language.
Additionally, each question is randomly set to either from the participants perspective or the directors perspective.

## generating the grid 

At this point the code splits into two different grid generation methods depending on if the sample is supposed to be control or test.

### Control samples

The first thing we do is to generate an empty grid object of the correct size. Then we use the question to filter only the items that match the criteria and select one randomly. We then place the item in the grid randomly. This item is known as the target item and is the one the director will be refering to in the question.

Next we calculate the number of items needed in the grid and the proportion of those items that are related to the question. Related items are any items that also match the filter criteria of the question that the target item matches. These might or might not be the same as the target item itself. 

Now we know how many related and unrelated items are needed we insert the related items making sure that when placed in the grid they do not affect the answer to the question. For example if the question asks for "the top most red clothes" and the target item is on the second top row then the code will ensure that all related items are placed strictly below it so that the target item is still the correct answer.

If the selection rule is set to None then we cannot place related items in the grid without changing the answer. Thus we instead place an unrealted item for each related item we would place.

Next we place the unrealted item randomly in the remaining places in the grid as they have no effect on the answer.

Finally, we calculate the number of cells that should be blocked from the directors view. We then randomly place blocks in grid making sure to avoid the target item.

### Test samples

When generating a test sample we create the grid and insert the target item the same as we do in a control sample. The main difference comes once we calculate the number of related items we also calculate the proportion of the related items that should be ruled out based on the selection rule and thus are unblocked from the directors point of view. we insert these unblocked related items the same way as the control samples making sure not to insert related items in positions that could change the answer.

If the selection rule is none then we skip this and place more blocked related items later.

Once the unblocked related items are placed we then place a single related item in a position that is garunteed to change the answer if it was not blocked and we then place a block in that position. We then place the remaining blocked related items randomly within the remaining spaces making sure to block them each time. 

Next we place the unrelated items randomly same as in the control sample and then randomly place any remaining blocks if needed. However, this time in addition to avoiding the target item we also avoid the existing blocked related items and the unblocked related items.

## Validation

Once the grid is created we check that the grid has generated properly by validating that the answer is either the same from the participant and directors perspective or different depending on if the sample is control or test.

Finally, we do some cleanup simplifying the question to remove adjectives that arent needed and creating the sample object containing the answers, details about the sample along with the grid and question objects.

The dataset of samples is then written to a json file containing all the information needed and each grid is rendered in to an image that is shown in the evaluation.

