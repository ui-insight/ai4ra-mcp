# Feature Definition Interview

Interviews a subject matter expert about one OpenERA feature and writes the finished definition into the feature's ClickUp task. The expert talks about how their work happens; the skill translates it into the thirteen-heading definition, writes the acceptance criteria in Gherkin and reads each back in plain English, pushes back on "looks fine" with specific hypotheses, and treats the AI first pass draft as material to take apart. With two assignees each reviewer gets their own pass subtask, the second is interviewed blind, the passes are compared and a discrepancy subtask holds what is unresolved. Finished criteria are fingerprinted against the acceptance-criteria index task, never against other features' documents. Two rules do not bend: it never takes attachments (they go onto the ClickUp task) and never takes the contents of a real record (identifiers and descriptions only).

**Version:** 0.1.0 · **Category:** research · **Status:** experimental · **Output:** the definition written to ClickUp, and an account of every change

## Where it lives and what it needs

Cell 3 of the grid: it calls no host tools and needs Idaho's own knowledge, so it is on the `uidaho` server and usable from any MCP client. Every fact of the work (the OpenERA list, the `feature` tag, the subtask names, the headings, the index task, the Data Sensitivity field) is in the `openera-feature-guide` guide beside it, fetched first with `uidaho_guide`; the skill's text names none of them, so when the list or the index moves the guide is the one file that changes.

Its ClickUp work is the `clickup` server's, named fully qualified in the text (`clickup:clickup_task`), so a client needs both servers connected and the `clickup` deployment's writes turned on (`AI4RA_MCP_CLICKUP_WRITES=1`). It reads with `clickup_tasks_search` (by assignee and tag), `clickup_task` and `clickup_list_fields`, and writes with `clickup_task_create` (subtasks), `clickup_task_update` (descriptions, replaced whole; statuses) and `clickup_task_field_set`. Without the ClickUp tools it says so and hands the person markdown to paste, naming the task.

## Inputs

As an MCP prompt it takes one optional argument, `feature` (a roadmap ID or task name); without it, the person's queue is found from their tasks. Everything else comes from the conversation and from ClickUp. Never an attachment, never a record's contents.

## Outputs

The definition under the guide's thirteen headings, in the expert's vocabulary, written below the Roadmap status block (one assignee) or into the reviewer's own pass subtask (two or more), with the subtasks closed as the method says, the index task updated with the feature's fingerprint and prefilter lines and any overlap, the Data Sensitivity field set when the section 5 answer maps onto one option, and a plain statement to the person of every change made in ClickUp.

## Source

Converted on 2026-10-07 (#32) from a `.skill` package written for claude.ai (`SKILL.md` with `references/second-reviewer.md` and `references/ac-overlap.md`). The two references were methods, so they are sections of this prompt; the facts went to the guide; the interviewing craft stayed, shortened.

## Evals

See [`evals/`](evals/). None yet.
