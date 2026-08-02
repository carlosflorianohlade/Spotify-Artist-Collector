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

