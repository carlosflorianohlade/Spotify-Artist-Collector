from auth import get_access_token
import requests
import time
import random
import json
from pathlib import Path

access_token = get_access_token()
headers = {"Authorization": f"Bearer {access_token}"}

artist = input("Inserisci l'artista: ")

params = {
    "q": artist,
    "type": "artist",
    "limit": 10
}

artista = requests.get(
    "https://api.spotify.com/v1/search",
    headers= headers,
    params= params
)

data = artista.json()
items = data["artists"]["items"]

search_result = []

for codice, artista in enumerate(items):
    print(f"Risultati ricerca:{artista['name']} -- Codice: {codice}")
    search_result.append({
        "id": artista['id'],
        "name": artista['name']
    })

while True:
    try:
        choice = int(input("\nInserisci il ""Codice"" dell'artista: "))
        if 0 <= choice < len(search_result):
            break
        else:
            print(f"Inserisci un numero tra 0 e {len(search_result) - 1}.")
    except ValueError:
        print("Devi inserire un numero.")

scelto = search_result[choice]
id_artista = scelto["id"]
nome_artista = scelto["name"]

url = f"https://api.spotify.com/v1/artists/{id_artista}/albums"
params = {
    "limit": 10,
    "include_groups": "album,single"
}

file = Path(nome_artista)
if not file.exists():
    response_ids = set()

    while url:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 429:
            print(response.json())
            retry_after = int(response.headers.get('Retry-After', 5))
            print(f"Rate limited, aspetto {retry_after} secondi...")
            time.sleep(retry_after)
            continue

        data = response.json()

        for album in data["items"]:
            response_ids.add(album["id"])


        url = data["next"]
        params = None
        time.sleep(random.uniform(1.5, 3))

    print(f"Totale ID unici: {len(response_ids)}")
    print(response_ids)

    with open(nome_artista, "w") as f:
        f.write(str(response_ids))

response = requests.post(
    "https://api.spotify.com/v1/me/playlists", headers=headers, data={
        "name": nome_artista,
        "description": f"Playlist of {nome_artista}",
        "public": True ,
    }   
)

print(response.status_code)
