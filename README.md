# Spotify Artist Collector

Create a Spotify playlist that contains **every song of an artist**: all the albums and all the singles, each song only once.

## Why this project exists

I wanted a single playlist with an artist's complete discography. It all started with Dave: I wanted every song of his in one place. Spotify has no button for that. The usual workaround is to search for a public playlist made by someone else, but those are often incomplete, out of date or full of duplicates.

So I wrote this script. You type the artist's name, and it reads the whole discography from the Spotify Web API. Then it builds the playlist in your account for you.

## What it does

1. You log in with your Spotify account in the browser.
2. You type an artist name and choose the right artist from the search results.
3. The script reads every **album** and **single** of the artist, and every track in them.
4. It removes duplicates by title. The same song often appears on an album, as a single and as a deluxe version, but it is added only once. Titles are compared without the part in brackets or after ` - `, so `Song`, `Song (feat. X)` and `Song - Remastered` count as the same song.
5. The list of songs is saved in `<Artist>.txt`, so the next run does not need to download everything again.
6. It creates a public playlist named after the artist and adds all the songs.
7. If you already have a playlist with that name, it asks if you want to delete it and build it again from scratch. The new playlist then contains only the songs in `<Artist>.txt`.

Songs where the artist only *appears on* someone else's album (`appears_on`) are not included.

## Requirements

- **Python 3.10 or newer**
- The **`requests`** library
- A **Spotify Premium** account. Spotify says that *"the app owner must have a Spotify Premium account for apps in development mode to function"*.
- A **Spotify app** created on the Spotify Developer Dashboard. It is free, see below.

## Setup

### 1. Create a Spotify app

This is a one-time setup. It gives you a **Client ID**, which is how Spotify knows which app is asking for access to your account.

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in with your Spotify account. The first time, you need to accept the Developer Terms.
2. Click **Create app** and fill in the form:
   - **App name**: anything, for example `Artist Collector`.
   - **App description**: anything, for example `Playlist with all the songs of an artist`.
   - **Redirect URI**: `http://127.0.0.1:3000`. Click **Add**. It must be exactly this value, because it is the address the script listens on after the login.
   - If you are asked which APIs/SDKs you plan to use, choose **Web API**.
   - Accept the **Developer Terms of Service** and click **Save**/**Create**.
3. Open the app and go to **Settings**. Copy the **Client ID**. You do **not** need the Client Secret: the script uses the [Authorization Code with PKCE](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow) flow, which works without a secret.

About the Redirect URI, Spotify's rules are:
- `localhost` is **not** allowed. You must use the IP address `127.0.0.1`.
- Plain `http` is allowed only for loopback addresses like `127.0.0.1`.

### 2. (Optional) Add other users

New apps start in **Development Mode**. In this mode:
- up to **5 Spotify users** can use the app;
- every user must be added to the app's allowlist first.

If you are the only user, skip this step: the app owner can always use it. To let a friend use *your* app:

1. Open the app on the Dashboard and go to **Settings → User Management**.
2. Click **Add new user** and enter their name and the email of their Spotify account.

A user who is not on the list can log in, but every API request fails with **403**.

See the official docs: [Apps](https://developer.spotify.com/documentation/web-api/concepts/apps), [Quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes), [Redirect URIs](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri).

### 3. Download the project and install the dependencies

```bash
git clone https://github.com/carlosflorianohlade/Spotify-Artist-Collector.git
cd Spotify-Artist-Collector
pip install requests
```

### 4. Set your Client ID

Create a file called `.env` in the project folder, next to `auth.py`, with this line:

```
SPOTIFY_CLIENT_ID=your-client-id
```

Replace `your-client-id` with the value you copied from the Dashboard. `auth.py` reads this file when it starts, so you don't need any extra library. `.env` is listed in `.gitignore`, so it is never committed.

You can also set `SPOTIFY_CLIENT_ID` as a normal environment variable, for example `export SPOTIFY_CLIENT_ID=...`. If you do both, the environment variable wins over `.env`.

## Usage

```bash
python main.py
```

1. The browser opens the Spotify login page. Log in and click **Agree**. The page then says *"Login complete, you can close this tab."*
2. Type the artist name and choose the number of the right artist:
   ```
   Enter the artist: dave
   0: Dave
   1: Dave East
   ...
   Enter the artist number: 0
   ```
3. Wait while the discography is downloaded. This can take a few minutes for big discographies, because the script pauses between albums so that Spotify does not block it.
4. If a playlist with the same name already exists in your library, answer `y` to delete it and build it again, or `n` to stop without changing anything.
5. At the end the script prints the link to the new playlist.

### Updating a playlist

The track list is saved in `<Artist>.txt` (for example `Dave.txt`). On the next run for the same artist, the script uses this file and does not download the discography again.

When the artist releases new music:
1. Delete `<Artist>.txt`.
2. Run the script again.
3. Answer `y` to rebuild the playlist.

You can also edit the file yourself: it is a comma-separated list of `spotify:track:...` URIs. When you rebuild the playlist, it will contain exactly the songs in the file.

Deleting a playlist gives the new one a **different link**. The old link stops working.

## How it works

| File | What it does |
| --- | --- |
| `auth.py` | Login with the PKCE flow. It opens the browser and starts a small local server on `127.0.0.1:3000` to receive the login code. Then it exchanges the code for an access token. |
| `main.py` | Searches for the artist, downloads the discography, removes duplicates, saves `<Artist>.txt` and creates the playlist. |

**Spotify Web API endpoints used**

| Endpoint | Purpose |
| --- | --- |
| `GET /search` | Find the artist (max 10 results) |
| `GET /artists/{id}/albums` | Albums and singles of the artist (max 10 per page) |
| `GET /albums/{id}/tracks` | Tracks of each release (max 50 per page) |
| `GET /me` | Your user id, to recognise your own playlists |
| `GET /me/playlists` | Look for an existing playlist with the same name |
| `DELETE /me/library` | Delete the old playlist (the same as *Delete* in the app) |
| `POST /me/playlists` | Create the playlist |
| `POST /playlists/{id}/items` | Add the tracks (max 100 per request) |

**Scopes (permissions) requested at login**

| Scope | Why |
| --- | --- |
| `user-read-private` | read your profile (`/me`) |
| `playlist-read-private` | read your playlists |
| `playlist-modify-public` | create the playlist, add tracks and delete it |
| `user-library-modify` | remove the old playlist from your library |

Every request goes through the `spotify()` function in `main.py`. If Spotify answers **429 Too Many Requests**, the function waits the number of seconds in the `Retry-After` header and tries again. On any other error it stops and prints Spotify's message.

## Limitations

- **Duplicates are found by title.** Only the part in brackets or after ` - ` is ignored. A title like `Song Remix (feat. X)` still counts as a different song, because "Remix" is outside the brackets.
- Two *different* songs with the same title would count as one, and only one of them would be added.
- Which version of a song ends up in the playlist (album, single or deluxe) depends on the order in which Spotify returns the releases.
- Songs appear in random order, not by release date.
- Because of Development Mode, the app works for at most 5 users, and you must add each of them yourself.

## Troubleshooting

| Problem | Solution |
| --- | --- |
| `INVALID_CLIENT: Invalid redirect URI` in the browser | The Redirect URI in the Dashboard must be exactly `http://127.0.0.1:3000`. |
| `SPOTIFY_CLIENT_ID is missing` | The `.env` file is missing, is in the wrong folder, or does not contain `SPOTIFY_CLIENT_ID=...`. |
| `INVALID_CLIENT: Invalid client` | The Client ID is wrong. Check the value in `.env`. |
| `Error 403 ... Insufficient client scope` | The login was done with fewer scopes. Run the script again and accept the new permissions. |
| `Error 403` on every request | Your account is not in the app's **User Management** list, or the app owner does not have Premium. |
| `OSError: [Errno 98] Address already in use` | Port 3000 is in use by another program. Close that program, or change `REDIRECT_PORT` in `auth.py` **and** the Redirect URI on the Dashboard. |
| The browser does not open | Copy the login URL printed in the terminal into your browser. |
