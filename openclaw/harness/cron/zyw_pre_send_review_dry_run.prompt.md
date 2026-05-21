# ZYW Insight Pre-send Review

Run the local pre-send review panel for an existing local email draft artifact.

Required behavior:

- Invoke the local `zyw_insight` CLI command for `pre-send-review`.
- Use a completed local email draft directory as input.
- Produce local review JSON and Markdown artifacts.
- The review result may be `ready_for_human_review`, `needs_revision`, or `blocked`.
- It must not approve or deliver anything.
- It must not use model, transport, or network actions.
- It must not read provider credentials.

Expected command shape:

```text
PYTHONPATH=src python3 -m zyw_insight.cli pre-send-review .zyw_insight/email_drafts/<draft-id>-draft --pretty
```

The review is a dry-run quality gate. Human approval remains required before any external delivery.
