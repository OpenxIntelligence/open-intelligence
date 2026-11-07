"""Session-auth helper for HTTP tests after the transitional header removal.

W1 (auth slice 2) removed the X-Fictional-Actor header path: case routes
require a live session. Tests that used to send the header now sign in as
the seeded demo clinician instead. seed() creates the demo account
passwordless by design, so this helper sets its password first, then signs
in over HTTP and returns the session cookie.
"""

import json
from urllib.request import Request, urlopen

from open_intelligence import CaseStore

PASSWORD = "fictional-demo-1"
DEMO_ACTOR = "FICTIONAL-NAVIGATOR-A"


def signin_cookie(port, account_id, password=PASSWORD):
    """POST /api/auth/sign-in; return the `oi_session=...` cookie value."""
    req = Request(
        f"http://127.0.0.1:{port}/api/auth/sign-in",
        data=json.dumps({"account_id": account_id, "password": password}).encode(),
        headers={"Content-Type": "application/json",
                 "Origin": f"http://127.0.0.1:{port}"})
    with urlopen(req, timeout=5) as response:
        body = json.loads(response.read())
        assert response.status == 200, body
        return response.headers.get("Set-Cookie").split(";", 1)[0]


def signin_demo(port, db_path):
    """Set the seeded demo clinician's password, sign in, return the cookie.

    Opens the store briefly to set the password; the live server is not
    serving requests yet at setUpClass time, so there is no contention.
    """
    store = CaseStore(db_path)
    try:
        assert store.get_account(DEMO_ACTOR) is not None, "seed() did not create the demo account"
        store.set_account_password(DEMO_ACTOR, PASSWORD)
    finally:
        store.close()
    return signin_cookie(port, DEMO_ACTOR)
