# Artist Collector: web version

The same thing as `main.py`, but as a website: log in, pick an artist, get a playlist.
Everything runs in the browser. There is no server code: the login uses PKCE, which needs only the Client ID, not the secret.

## Run it on your computer

From the project folder:

```bash
python -m http.server 3000 --bind 127.0.0.1 -d web
```

Open **http://127.0.0.1:3000** (not `localhost`: Spotify refuses it as a Redirect URI).

- The Redirect URI on the Dashboard stays `http://127.0.0.1:3000`, the same as the Python version.
- The first time, the page asks for your **Client ID** and remembers it in the browser.
  You can also write it in `config.js` instead.

Python is used only as a quick local web server here; any static server works.

## Differences from the Python version

| Python | Web |
| --- | --- |
| `<Artist>.txt` cache | saved in the browser (`localStorage`); the site asks whether to use it or download again, and lets you download the `.txt` at the end |
| terminal questions | search results with photos, a dialog for the duplicate playlist |
| `.env` | the page asks for the Client ID, or `config.js` |

The Spotify endpoints, scopes and duplicate-by-title rule are the same.

## Publishing it

The `web/` folder is a static site: upload it to any static host (GitHub Pages, Netlify, Cloudflare Pages…).
Then add the site's address as a Redirect URI on the Dashboard, for example
`https://<user>.github.io/Spotify-Artist-Collector/web/`, exactly as the setup screen of the page shows it.
The Development Mode limits still apply: at most 5 users, each added in **User Management**.
