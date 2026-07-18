---
name: handoff-documenter
description: Use at the end of a work session or milestone to produce a handoff document summarizing what was done, what is stable, and what comes next. Writes to docs/handoffs/<date>_<topic>.md.
---

# Handoff documentation

When writing a handoff document:

1. Read `git log --oneline -20` and the CLAUDE.md "Status & roadmap" section.
2. Write `docs/handoffs/YYYY-MM-DD_<topic>.md` with sections:
   - **Contexte** (French): one paragraph on what was worked on and why.
   - **État stable** (French): bullet list of what is verified and safe to build on.
   - **Fichiers modifiés** (French): table of file → one-line change summary.
   - **Points ouverts** (French): numbered list of unresolved items and decisions needed.
   - **Prochaines étapes** (French): ordered list of next concrete tasks.
3. Keep under 400 words. A future engineer should be able to resume in under 10 minutes.
4. Cross-reference CLAUDE.md "Known open items" instead of duplicating content.
5. Create `docs/handoffs/` directory if it does not exist.
