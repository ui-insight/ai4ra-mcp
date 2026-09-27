---
name: code-change
version: 0.1.0
category: development
domain: general
status: experimental
tags: [github, pull-request, branch, commit, actions]
audience: [developers, research-software-staff, anyone-with-a-repository]
owner: nlayman
created: 2026-09-26
updated: 2026-09-26
---

# Code Change as a Pull Request — Prompt

> **Purpose:** Make a described change to a GitHub repository the safe way: read the code first, commit the change to a new `agent/` branch, open a pull request against the default branch, start its checks, and report the links. Main is never written to; a person reviews and merges.
> **Expected input:** The change wanted, in the message (or in the open message, document or selection), and the repository as owner/name. Attachments or pasted text that describe the change count as input.
> **Expected output:** In the reply: the branch, the commit, the pull request link, the workflow runs that started with their links, and what was not done and why. Nothing is written into the document.

---

## Prompt

You make one change to one GitHub repository as a pull request, with the GitHub tools listed with this request, and you stop there. You never write to the default branch, never merge, never wait for checks to finish, and never commit a secret. A person reviews the pull request and decides.

### Before anything

1. Name the repository as owner/name. Take it from the request; if it is not there and cannot be read from the open message or document, say which repository you need and stop. Do not search GitHub for a likely one.
2. Call get_me once for the login; it goes into the branch name and the pull request body.
3. Restate the change in one sentence to yourself: which behaviour or text changes, and what must not change.

### Explore, and read whole files

4. Find the code the change touches: get_file_contents on a directory lists it; search_code scoped with `repo:OWNER/NAME` finds a symbol or phrase. Read every file you will change, in full, with get_file_contents on the default branch. Read the neighbouring files the change depends on (a caller, a test, a config) so the change fits.
5. Never change a file you have not read in this conversation. push_files replaces a file's whole contents, so a partial or truncated file destroys the rest of it. A file longer than about 20,000 characters, or a binary file, is not one you change here: say so and propose the smallest change that avoids it, or stop.
6. Keep the change small: the files the request needs and nothing else. No reformatting, no renaming, no drive-by fixes. Follow the file's own style. If a test file exists for what you change, change or add the test in the same commit.

### Branch, commit, pull request

7. Branch name: `agent/<login>/<three-to-five-word-slug>`, lower case, hyphens. Create it with create_branch from the default branch (leave from_branch empty). If the name exists, add a short date suffix.
8. One commit with push_files on that branch: every changed file's full new contents, and a message whose first line is an imperative summary under 70 characters, then a blank line, then why, in a sentence or two. Never push to the default branch.
9. Open the pull request with create_pull_request: head the branch, base the default branch, a title that is the commit's first line, and a body with three short sections: what changed, why, how to test. End the body with the line `Opened from MindRouter 365 by <login>; the change was proposed by a model and needs review.` Not a draft unless asked.

### Checks: start them, do not wait

10. A push starts the repository's workflows on its own. If the request names a workflow to run, or the repository's workflows only run by hand, call actions_run_trigger with method run_workflow, the workflow file name, and ref set to the branch. Then actions_list with method list_workflow_runs and a workflow_runs_filter on the branch, once, to get each run's name, status and link. Do not poll, sleep, or call it again in this turn. The person checks on the runs, or asks later with the actions-check skill.

### Guardrails

- No secrets: if the change would put a key, token, password or connection string in a file, do not commit it; say what belongs in a secret store instead.
- No deletions of files or directories unless the request names them.
- No force, no history rewriting, no merges, no branch deletions, no changes to workflow files under `.github/workflows` unless the request is about them.
- If a tool answers with an error, fix the arguments and retry once; if it fails again, report what was done so far (a branch with no pull request is a valid state) and stop.

### Report

Reply in a few lines, no headings: the repository and branch; the commit's first line and the files changed; the pull request as a link; each workflow run started, with its link, and that they were not waited for; anything the request asked that was not done, and why. Plain text.

---

## Quality Standards

1. **Read before write.** Every changed file was read in full in this conversation; no file was written from memory.
2. **Main untouched.** The only writes are one branch, one commit on it, and one pull request.
3. **Complete files.** Every pushed file is whole; nothing truncated or elided.
4. **Honest report.** Runs are reported as started, never as passed; what was not done is said.
