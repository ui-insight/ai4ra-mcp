# Check on GitHub Actions

One look at a repository's workflow runs through the GitHub MCP server's tools: which ran, on which branch and commit, whether they passed, and for a failure the job, the step and the first real error from the failed jobs' logs. It takes a snapshot and stops; it never polls, never changes anything, and reruns or cancels a run only when the person asks for that by name.

**Version:** 0.1.0 · **Category:** review · **Status:** experimental · **Output:** reply

## Inputs

The repository as owner/name; optionally a branch, a pull request number, a workflow name or a run id.

## Outputs

A list of runs with status, conclusion and links; for each failure, the job, step and quoted error lines; and what the person can do next.

## Tools it needs

`actions_list`, `actions_get`, `get_job_logs`, and `actions_run_trigger` for a requested rerun, from GitHub's remote MCP server with the `actions` toolset.

## With code-change

`code-change` starts the checks and stops. This skill is the look afterwards. A fix is a new request to `code-change`, described by the person after reading the failure: the loop is theirs, on purpose.

## Evals

See [`evals/`](evals/). None yet.
