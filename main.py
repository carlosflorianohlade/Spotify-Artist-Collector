from auth import get_access_token
import requests

access_token = get_access_token()
headers = {"Authorization": f"Bearer {access_token}"}

artist = input("Inserisci l'artista: ")

params = {
    "q": artist,
    "type": "artist",
    "limit": 10
}

id_artista = requests.get(
    "https://api.spotify.com/v1/search",
    headers= headers,
    params= params
)

data = id_artista.json()
items = data["artists"]["items"]

for artista in items:
    print(artista["name"])