# Decision and state rules

- Upstream changes invalidate dependent downstream nodes only.
- `APPROVED` means current proposal accepted; it can become STALE after upstream change.
- `LOCKED` means automatic mutation prohibited.
- `STALE_LOCKED` means upstream truth and a locked result conflict; ask the user what to do.
- Keep prior versions; do not rewrite history.
- User override > approved AI decision > new AI proposal > default.
