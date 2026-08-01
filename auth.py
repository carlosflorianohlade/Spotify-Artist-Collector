import secrets
import string
import hashlib
import base64
import requests
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs

def get_access_token() -> str:
    def generate_random_string(length: int) -> str:
        possible = string.ascii_letters + string.digits
        return ''.join(secrets.choice(possible) for _ in range(length))

    code_verifier = generate_random_string(43)

    def generate_code_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode('ascii')).digest()
        challange = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')
        return challange

    code_challenge = generate_code_challenge(code_verifier)

    CLIENT_ID = "30dff565e47f4528adbfce8cac0569d0"
    REDIRECT_URI = "http://127.0.0.1:3000"
    SCOPE = "user-read-private playlist-modify-public"

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": SCOPE,
        "code_challenge_method": 'S256',
        "code_challenge": code_challenge,
        "redirect_uri": REDIRECT_URI
    }


    auth_url = "https://accounts.spotify.com/authorize?" + urlencode(params)


    auth_code = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            try:
                parsed_query = urlparse(self.path)
                query_params = parse_qs(parsed_query.query)
                auth_code = query_params.get('code', [None])[0]
                self.send_response(200)
                self.end_headers()
            except Exception:
                self.send_response(404)
                self.end_headers()

    server = HTTPServer(('127.0.0.1', 3000), CallbackHandler)
    webbrowser.open(auth_url)
    server.handle_request()


    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier, 
        }
    )

    token_data = response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    print(response.status_code)
    print(token_data)
    return access_token