---
name: ipynb-notebook
description: Create, edit, and inspect Jupyter notebook `.ipynb` files programmatically. Use when Codex needs to build a notebook from scratch, modify notebook JSON safely, insert/delete/reorder cells, preserve notebook structure, add Colab form fields, or troubleshoot malformed notebook cell data and metadata.
---

# IPYNB Notebook

Create and modify `.ipynb` files as structured JSON, not as ad hoc text blobs. Preserve valid notebook shape, keep cells logically ordered, and use stable cell IDs so later edits can target the right cell.

## Workflow

1. Read the notebook JSON before changing anything.
2. Identify target cells by `metadata.id` when possible.
3. Edit `cells` as structured objects.
4. Write the notebook back with consistent formatting.
5. Re-check IDs, cell ordering, and code-cell fields before finishing.

## Core Rules

- Treat `.ipynb` as JSON with top-level `nbformat`, `nbformat_minor`, `metadata`, and `cells`.
- Store each cell `source` as an array of strings, not one large string.
- End each source line with `\n` except when intentionally omitting the final trailing newline.
- Give every cell a unique, descriptive `metadata.id`.
- Include `execution_count: null` and `outputs: []` for new code cells unless there is a reason to preserve executed output.
- Keep imports and setup near the top unless the notebook already follows a different pattern.

## Editing Pattern

- Use Python `json` operations for notebook edits.
- Match cells by `metadata.id` instead of brittle positional assumptions whenever possible.
- When inserting new cells, choose an index based on notebook flow: intro, setup, config, work, results.
- When deleting cells, filter by `metadata.id` and verify nothing else shares that ID.
- Preserve existing notebook metadata unless the task requires changing kernel or Colab settings.

## Creation Pattern

- Start with a markdown title/introduction cell.
- Add a setup or imports cell near the top.
- Add configuration cells before expensive work.
- Group major sections with markdown dividers or headings.
- Prefer short, explicit success and warning messages in runnable cells.

For concrete JSON snippets and Colab-specific patterns, read [references/notebook-patterns.md](references/notebook-patterns.md).

## Colab Notes

- Use `#@title` headers in code cells when the notebook is intended for Google Colab.
- Use `#@param` annotations for user-editable configuration values.
- Keep Colab form cells near the top so users can configure the notebook before running later sections.

## Final Checks

- Ensure all cells have unique `metadata.id` values.
- Ensure markdown and code cells are in a sensible order.
- Ensure `source` fields remain arrays of strings.
- Ensure JSON escaping is correct for quotes, backslashes, and literal `\n`.
- Ensure outputs and execution counts are intentional, not accidental leftovers.
