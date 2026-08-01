from auth import get_access_token

access_token = get_access_token()
headers = {"Authorization": f"Bearer {access_token}"}