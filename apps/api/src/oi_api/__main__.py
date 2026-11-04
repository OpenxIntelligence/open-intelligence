"""Run the synthetic shell on loopback. Container launch has an explicit command."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("oi_api.app:create_app", factory=True, host="127.0.0.1", port=8000,
                access_log=False, proxy_headers=False)
