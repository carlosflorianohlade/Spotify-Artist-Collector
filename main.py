from auth import get_access_token
import requests
import time
import random

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
    search_result.append(artista['id'])

while True:
    try:
        choice = int(input("\nInserisci il ""Codice"" dell'artista: "))
        if 0 <= choice < len(search_result):
            break
        else:
            print(f"Inserisci un numero tra 0 e {len(search_result) - 1}.")
    except ValueError:
        print("Devi inserire un numero.")

id_artista = search_result[choice]

url = f"https://api.spotify.com/v1/artists/{id_artista}/albums"
params = {
    "limit": 10,
    "include_groups": "album,single"
}

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
