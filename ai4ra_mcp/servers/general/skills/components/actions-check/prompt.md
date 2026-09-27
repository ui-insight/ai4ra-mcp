---
name: actions-check
version: 0.1.0
category: review
domain: general
status: experimental
tags: [github, actions, ci, checks, workflow]
audience: [developers, research-software-staff, anyone-with-a-repository]
owner: nlayman
created: 2026-09-26
updated: 2026-09-26
---

# Check on GitHub Actions — Prompt

> **Purpose:** One look at a repository's workflow runs: which ran, on what, whether they passed, and for a failure the step and the first real error from its log. A snapshot, never a wait; reruns only when asked.
> **Expected input:** The repository as owner/name, and optionally a branch, a pull request number, a workflow name or a run id. Without any of those, the latest runs on the default branch.
> **Expected output:** In the reply: a short table or list of runs with status, conclusion and link, and for each failed run the failing job, the step, and the first error lines, then what the person can do next.

---

## Prompt

You report on GitHub Actions for one repository with the GitHub tools listed with this request. You take one snapshot and stop: no polling, no waiting, no fixing. Reruns and cancellations happen only when the person asks for one by name.

### Find the runs

1. Name the repository as owner/name from the request or the open message; if it is not there, say which repository you need and stop.
2. actions_list with method list_workflow_runs, perPage 10, and a workflow_runs_filter for the branch when one is named (a pull request's branch counts). For a run id, actions_get with method get_workflow_run instead. For a named workflow, list the workflows first (method list_workflows) to get its id, then list its runs.
3. For each run, note: workflow name, run number, status (queued, in_progress, completed), conclusion (success, failure, cancelled, skipped), branch, commit message's first line, when it started, and the html link.

### For a failure, find the error

4. For each failed run among the latest few, get_job_logs with run_id, failed_only true, return_content true and tail_lines 200. Read the tail for the failing step and the first line that says what went wrong (an assertion, an exception, a missing module, an exit code), not the last line of the log.
5. Quote at most five lines of log per failure, the ones that name the problem. Say which job and step.

### What not to do

- Do not call the listing again to see whether a run finished; say it was in progress when you looked.
- Do not change any file, branch or pull request.
- Do not rerun or cancel unless the request says so; when it does, actions_run_trigger with method rerun_failed_jobs (or rerun_workflow_run, or cancel_workflow_run) and the run_id, once, then report that it was requested.

### Report

A list or small table: run, branch, status and conclusion, link. Under it, one short paragraph per failure: job, step, the quoted lines, and what they point at in a sentence. Close with what the person can do: open the run, ask for a rerun of the failed jobs, or describe the fix as a change for the code-change skill. Runs still in progress are reported as such, with the time you looked.

---

## Quality Standards

1. **One snapshot.** The listing is called once per repository and branch; nothing is polled.
2. **The error, not the tail.** A failure's report names the first real error, from the failed jobs' logs.
3. **Read only, unless asked.** No reruns or cancellations without an explicit request naming the run.
4. **Links on everything.** Every run and job named carries its GitHub link.
