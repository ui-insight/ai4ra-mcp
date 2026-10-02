# Changelog

## [0.1.0] — 2026-09-26

- Initial version: read whole files, one `agent/` branch, one commit with push_files, one pull request, checks started and not waited for, report with links. Written for the Office pane's GitHub fold after the request to drive repository changes from Excel and Outlook.

## [0.2.0] — 2026-10-02

- Names no client. The pull request body ended "Opened from MindRouter 365 by <login>", which is wrong from any other client; it now ends "Opened for <login>; the change was proposed by a model and needs review." The change and the repository are taken from the request alone: "the open message, document or selection" and "nothing is written into the document" assumed a client with a document open, and are gone. The tools are named for what they are, GitHub's own MCP server's.
