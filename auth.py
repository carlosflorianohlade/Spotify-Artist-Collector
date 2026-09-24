"""Spotify login using the Authorization Code with PKCE flow.

PKCE does not need a client secret: only the Client ID of your Spotify app.
See https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow
"""

import base64
import hashlib
import os
import secrets
import string
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests


def _load_env_file(path):
    """Load KEY=VALUE lines from a .env file into os.environ (real env vars win)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_env_file(Path(__file__).with_name(".env"))

# Client ID of your app on the Spotify Developer Dashboard.
# Put SPOTIFY_CLIENT_ID=... in the .env file next to this script.
CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")

# Must match exactly one of the Redirect URIs saved in the app settings.
REDIRECT_HOST = "127.0.0.1"
REDIRECT_PORT = 3000
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}"

SCOPES = " ".join([
    "user-read-private",       # GET /me
    "playlist-read-private",   # GET /me/playlists
    "playlist-modify-public",  # create playlist, add tracks, remove playlist
    "user-library-modify",     # DELETE /me/library (remove old playlist)
])


def _random_string(length: int) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _wait_for_auth_code() -> str | None:
    """Start a one-shot local server and return the ?code=... Spotify redirects to."""
    result = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            if "code" in query or "error" in query:
                result["code"] = query.get("code", [None])[0]
                result["error"] = query.get("error", [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Login complete, you can close this tab.")
            else:
                # e.g. the browser asking for /favicon.ico
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    server = HTTPServer((REDIRECT_HOST, REDIRECT_PORT), CallbackHandler)
    while "code" not in result:
        server.handle_request()
    server.server_close()

    if result["error"]:
        print(f"Spotify login refused: {result['error']}")
    return result["code"]


def get_access_token() -> str | None:
    """Open the Spotify login page in the browser and return an access token."""
    if not CLIENT_ID:
        raise SystemExit("SPOTIFY_CLIENT_ID is missing: add it to the .env file (see README).")

    code_verifier = _random_string(64)

    auth_url = "https://accounts.spotify.com/authorize?" + urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": _code_challenge(code_verifier),
        "redirect_uri": REDIRECT_URI,
    })

    print("Opening the Spotify login page in your browser...")
    print(f"If it does not open, visit this URL:\n{auth_url}\n")
    webbrowser.open(auth_url)

    auth_code = _wait_for_auth_code()
    if not auth_code:
        return None

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
        },
    )
    return response.json().get("access_token")
