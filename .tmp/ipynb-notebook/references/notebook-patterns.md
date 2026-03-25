# Notebook Patterns

Load this reference when you need concrete notebook JSON snippets, Colab form syntax, or reminders about safe `.ipynb` editing details.

## Notebook Shape

```json
{
  "nbformat": 4,
  "nbformat_minor": 0,
  "metadata": {
    "colab": {"provenance": []},
    "kernelspec": {"name": "python3", "display_name": "Python 3"}
  },
  "cells": [
    {
      "cell_type": "markdown",
      "source": ["line 1\n", "line 2\n"],
      "metadata": {"id": "unique_id"}
    }
  ]
}
```

## Source Formatting Rules

- Represent `source` as an array of strings.
- End each line with `\n` except optionally the final line.
- Use escaped JSON sequences when writing notebook JSON directly:
  - `\"` for quotes
  - `\\n` for a literal backslash-n inside JSON text
  - `\\` for backslashes

Example:

```json
["print('hello')\n", "print('world')"]
```

## Markdown Cell

```python
{
    "cell_type": "markdown",
    "source": [
        "# My Notebook\n",
        "\n",
        "Description here.\n"
    ],
    "metadata": {"id": "intro"}
}
```

## Code Cell

```python
{
    "cell_type": "code",
    "source": [
        "import torch\n",
        "import numpy as np\n",
        "\n",
        "print('Ready!')\n"
    ],
    "metadata": {"id": "imports"},
    "execution_count": null,
    "outputs": []
}
```

## Colab Form Fields

```python
"#@title Cell Title { display-mode: \"form\" }\n",
"param = \"default\"  #@param {type:\"string\"}\n",
"number = 10  #@param {type:\"integer\"}\n",
"flag = True  #@param {type:\"boolean\"}\n",
"choice = \"A\"  #@param [\"A\", \"B\", \"C\"]\n",
```

Use `#@title` on code cells for collapsible sections in Colab.

## Safe Edit Pattern

```python
import json

with open("notebook.ipynb", "r") as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell.get("metadata", {}).get("id") == "target_id":
        cell["source"] = ["# updated\n"]
        break

with open("notebook.ipynb", "w") as f:
    json.dump(nb, f, indent=2)
```

## Insert Cell

```python
new_cell = {
    "cell_type": "code",
    "source": ["# new code\n"],
    "metadata": {"id": "new_cell"},
    "execution_count": None,
    "outputs": []
}
nb["cells"].insert(index, new_cell)
```

## Delete Cell

```python
nb["cells"] = [
    c for c in nb["cells"]
    if c.get("metadata", {}).get("id") != "cell_to_delete"
]
```

## Common Patterns

Setup cell:

```python
[
    "#@title Setup\n",
    "!pip install -q package1 package2\n",
    "\n",
    "import package1\n",
    "import package2\n",
    "\n",
    "print('✓ Setup complete')\n"
]
```

Config cell:

```python
[
    "#@title Configuration { display-mode: \"form\" }\n",
    "\n",
    "MODEL_NAME = \"gpt2\"  #@param {type:\"string\"}\n",
    "BATCH_SIZE = 32  #@param {type:\"integer\"}\n",
    "USE_GPU = True  #@param {type:\"boolean\"}\n"
]
```

Progress display:

```python
[
    "from tqdm.notebook import tqdm\n",
    "\n",
    "for i in tqdm(range(100)):\n",
    "    pass\n"
]
```

## Quality Checklist

- Ensure every cell has a unique `metadata.id`.
- Ensure markdown has clear headings and section breaks.
- Ensure code cells run in a sensible top-to-bottom order.
- Ensure imports and setup appear near the top.
- Ensure Colab forms are used when the notebook needs user-configurable inputs.
- Ensure output messages are explicit and readable.
- Ensure major sections are visually separated.
