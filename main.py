"""Build a Spotify playlist with every song of an artist (albums + singles)."""

import random
import re
import time
from pathlib import Path

import requests

from auth import get_access_token

API = "https://api.spotify.com/v1"

# Filled in by main() after the login.
headers = {}


def spotify(method, url, **kwargs):
    """Call the Spotify Web API, waiting and retrying when rate limited (429)."""
    while True:
        response = requests.request(method, url, headers=headers, **kwargs)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            print(f"Rate limited, waiting {retry_after} seconds...")
            time.sleep(retry_after)
            continue
        if not response.ok:
            raise SystemExit(f"Error {response.status_code} on {url}: {response.text}")
        return response


def get_all_pages(url, params=None):
    """Yield every item of a paginated endpoint, following the "next" links."""
    while url:
        data = spotify("GET", url, params=params).json()
        yield from data["items"]
        url = data["next"]
        params = None  # the "next" URL already contains the query parameters


def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def base_title(track_name):
    """Title without versions/features: "Song (feat. X) - Remastered" -> "song"."""
    return re.split(r"\s-\s|\(|\[", track_name.lower())[0].strip()


def choose_artist():
    query = input("Enter the artist: ")
    # 10 is the maximum search limit.
    data = spotify("GET", f"{API}/search", params={"q": query, "type": "artist", "limit": 10}).json()
    artists = data["artists"]["items"]
    if not artists:
        raise SystemExit(f'No artist found for "{query}".')

    for number, artist in enumerate(artists):
        print(f"{number}: {artist['name']}")

    while True:
        try:
            choice = int(input("\nEnter the artist number: "))
        except ValueError:
            print("Please enter a number.")
            continue
        if 0 <= choice < len(artists):
            return artists[choice]
        print(f"Enter a number between 0 and {len(artists) - 1}.")


def fetch_track_uris(artist_id):
    """Return the URIs of all the artist's songs, one per title."""
    track_uris = set()
    seen_titles = set()

    albums = get_all_pages(
        f"{API}/artists/{artist_id}/albums",
        {"include_groups": "album,single", "limit": 10},  # 10 is the maximum
    )
    for album in albums:
        tracks = get_all_pages(f"{API}/albums/{album['id']}/tracks", {"limit": 50})  # 50 is the maximum
        for track in tracks:
            title = base_title(track["name"])
            if title in seen_titles:
                continue  # same song already added from another release
            seen_titles.add(title)
            track_uris.add(f"spotify:track:{track['id']}")

        # Pause between albums to avoid hitting the rate limit.
        time.sleep(random.uniform(0.5, 1))

    return track_uris


def load_or_fetch_track_uris(artist):
    """Read the track list from "<artist>.txt", or download it and save it there."""
    cache_file = Path(f"{artist['name']}.txt")

    if cache_file.exists():
        print(f"Using the saved track list in {cache_file}")
        return {uri.strip() for uri in cache_file.read_text().split(",") if uri.strip()}

    print("Downloading the discography, this can take a few minutes...")
    track_uris = fetch_track_uris(artist["id"])
    print(f"Unique songs found: {len(track_uris)}")
    cache_file.write_text(", ".join(track_uris))
    return track_uris


def find_my_playlists(name):
    """Return the ids of the current user's own playlists called `name`."""
    user_id = spotify("GET", f"{API}/me").json()["id"]
    return [
        playlist["id"]
        for playlist in get_all_pages(f"{API}/me/playlists", {"limit": 50})
        if playlist["name"] == name and playlist["owner"]["id"] == user_id
    ]


def confirm(question):
    while True:
        answer = input(f"{question} (y/n): ").strip().lower()
        if answer in ("y", "n"):
            return answer == "y"
        print("Please answer y or n.")


def remove_playlists(playlist_ids):
    """Remove playlists from the user's library (what "Delete" does in the Spotify app)."""
    uris = [f"spotify:playlist:{playlist_id}" for playlist_id in playlist_ids]
    for batch in chunks(uris, 40):  # at most 40 URIs per request
        spotify("DELETE", f"{API}/me/library", params={"uris": ",".join(batch)})


def create_playlist(name, track_uris):
    playlist_id = spotify(
        "POST", f"{API}/me/playlists", json={"name": name, "public": True}
    ).json()["id"]

    for batch in chunks(list(track_uris), 100):  # at most 100 tracks per request
        spotify("POST", f"{API}/playlists/{playlist_id}/items", json={"uris": batch})

    return playlist_id


def main():
    access_token = get_access_token()
    if not access_token:
        raise SystemExit("Spotify login failed: no access token received.")
    headers["Authorization"] = f"Bearer {access_token}"

    artist = choose_artist()
    name = artist["name"]
    track_uris = load_or_fetch_track_uris(artist)

    existing = find_my_playlists(name)
    if existing:
        print(f'You already have a playlist called "{name}" ({len(existing)} found).')
        if not confirm("Delete it and build it again from scratch?"):
            raise SystemExit("Nothing changed.")
        remove_playlists(existing)
        print("Old playlist deleted.")

    playlist_id = create_playlist(name, track_uris)
    print(f"Added {len(track_uris)} songs.")
    print(f"https://open.spotify.com/playlist/{playlist_id}")


if __name__ == "__main__":
    main()
