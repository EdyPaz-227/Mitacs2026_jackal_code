# Protected files — never modify
- data/raw/**             (raw thermal measurements — read only)
- notebooks_originals/**  (original / Chaima notebooks — read only; dir not present yet)
- codigo_de_chaima_3_fase6_lite.py  (golden-master reference at repo root — read only)
- .env, .env.*, secrets/**, **/credentials*   (never read or edit)

Enforced by permissions.deny in .claude/settings.local.json (NOT settings.json,
which does not exist). If a path here does not match the real layout, update BOTH
this file and settings.local.json.

NOTE (audit F9): settings.local.json currently denies Edit/Write on
notebooks_originals/** (a dir that does not exist) but does NOT yet protect the real
golden-master file codigo_de_chaima_3_fase6_lite.py. Treat that file as read-only by
convention; adding it to permissions.deny is a separate, user-approved change.