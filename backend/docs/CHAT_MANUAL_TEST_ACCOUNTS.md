# Chat manual test accounts

Two throwaway accounts created via the real signup API (not seed data) to manually
verify chat in a browser. Already matched with each other — you can log in as
either one in two separate browser windows (or one normal + one incognito) and
chat between them live.

Created and verified end-to-end (message send/receive both directions, read
receipts, emoji reactions, delete-within-15-minutes, and search) via a one-off
script before handing these off — see the commit history around
`chat_manager.py` reconnect fix for what that surfaced.

## Accounts

| | Email | Password | Pet |
|---|---|---|---|
| A | `e2e-test-a-1784888707@example.com` | `TestPass123!` | Rex (dog) |
| B | `e2e-test-b-1784888707@example.com` | `TestPass123!` | Bella (dog) |

- match id: `0afde0c2-332f-438b-8235-50a42b8c7838`
- Both accounts are unverified emails (verification is a console-print stub in
  dev, not a hard gate on anything — no need to verify to use the app).

## How to check it

1. Start the frontend (`npm run dev` in `frontend/`) and backend
   (`fastapi dev app/main.py` in `backend/`, or use the one already running).
2. Log in as **A** in one browser window, **B** in another (incognito/private
   window works well for the second).
3. Go to **Chat** in the nav on either side — the match with Rex/Bella should
   already be there (no need to swipe/match again).
4. Send a message from A, confirm it appears live on B's side without a
   refresh, and vice versa.
5. Things worth poking at:
   - Read receipts: open the conversation on B's side, check A sees the
     double-check "seen" mark update.
   - Reactions: hover a message bubble, click the emoji-face icon, pick a
     reaction — should show up on both sides.
   - Delete: hover your own message within 15 minutes of sending, trash icon
     should be there; after 15 minutes it should disappear (soft-deletes
     server-side either way — the button is a client-side affordance, the
     server enforces the real window).
   - Search: the search icon in the conversation header, type a word from an
     earlier message, click a result to jump to it in the thread.
   - Typing indicator: type in one window, should show "..." on the other.

## Cleanup

These are real rows in the dev database (Neon) — harmless throwaway test data,
but delete whenever convenient:

```sql
-- Run in the dev DB. Cascades will clean up pets/messages/matches/etc.
delete from users where email in (
  'e2e-test-a-1784888707@example.com',
  'e2e-test-b-1784888707@example.com'
);
```
