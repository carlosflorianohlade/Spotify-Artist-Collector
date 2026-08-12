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
            album_id = album['id']
            tracks_resp = requests.get(
                f"https://api.spotify.com/v1/albums/{album_id}/tracks",
                headers=headers,
                params={"limit": 50}
            )
            tracks_data = tracks_resp.json()

            for track in tracks_data["items"]:
                response_ids.add(f"spotify:track:{track['id']}")
            time.sleep(random.uniform(0.5, 1))
        
        url = data["next"]
        params = None
        time.sleep(random.uniform(1.5, 3))

    print(f"Totale ID unici: {len(response_ids)}")
    # print(response_ids)

    with open(f"{nome_artista}.txt", "w") as f:
        f.write(str(", ".join(response_ids)))

else:
    with open(f"{nome_artista}.txt", "r") as f:
        contenuto = f.read()
        response_ids = {x.strip() for x in contenuto.split(",")}
        
        


response = requests.post(
    "https://api.spotify.com/v1/me/playlists", headers=headers, json={
        "name": nome_artista,
        "public": True
    }   
)

playlist_id = response.json()['id']
uris = list(response_ids)

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

for batch in chunks(uris, 100):
    while True:
        response = requests.post(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/items",
            headers=headers,
            json={"uris": batch}
        )
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 5))
            print(f"Rate limited, aspetto {retry_after} secondi...")
            time.sleep(retry_after)
            continue
        break
    print(response.status_code)

check = requests.get(
    f"https://api.spotify.com/v1/playlists/{playlist_id}/items",
    headers=headers
)