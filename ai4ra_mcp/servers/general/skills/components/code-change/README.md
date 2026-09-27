# Code Change as a Pull Request

Makes a described change to a GitHub repository through the GitHub MCP server's tools, the safe way: read the files first, commit the whole changed files to a new `agent/<login>/<slug>` branch, open a pull request against the default branch, start the repository's checks (or a named workflow), and report the links. It never writes to main, never merges, never waits for checks and never commits a secret. Review and merge are the person's.

**Version:** 0.1.0 · **Category:** development · **Status:** experimental · **Output:** reply

## Inputs

The change, in the message or read from the open message, document or selection, and the repository as owner/name. Without the repository it stops and asks.

## Outputs

The branch, the commit's first line and files, the pull request link, the workflow runs started with their links, and what was not done and why.

## Tools it needs

`get_me`, `get_file_contents`, `search_code`, `create_branch`, `push_files`, `create_pull_request`, `actions_run_trigger`, `actions_list`, from GitHub's remote MCP server with the `context`, `repos`, `pull_requests` and `actions` toolsets (the Office pane reaches it through its host's `/github/*` proxy).

## Not here

The test-and-fix loop. The skill starts checks and stops; a person looks at the run, or asks with `actions-check`, and decides what to fix. Iteration belongs to GitHub Actions or to a coding agent, not to a pane.

## Evals

See [`evals/`](evals/). None yet.
