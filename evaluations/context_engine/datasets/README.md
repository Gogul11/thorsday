# Datasets

Put local benchmark files in this directory after downloading them from their
official source.

Recommended order:

1. LoCoMo for long conversational memory questions.
2. LongMemEval for multi-session, temporal, update, extraction, and abstention
   tests.
3. A small AgentOS-specific JSONL set covering page-out/page-in behaviour,
   task resumption, tool results, conflicting updates, and missing facts.

Keep a `manifest.json` beside each converted dataset containing the source
URL, commit or version, checksum, conversion date, and any filtering applied.
Do not commit datasets that are not permitted by their license.
