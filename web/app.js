"use strict";

// Browser version of main.py + auth.py: same Spotify endpoints, same logic.

const API = "https://api.spotify.com/v1";
const ACCOUNTS = "https://accounts.spotify.com";

const SCOPES = [
  "user-read-private",       // GET /me
  "playlist-read-private",   // GET /me/playlists
  "playlist-modify-public",  // create playlist, add tracks, remove playlist
  "user-library-modify",     // DELETE /me/library (remove old playlist)
].join(" ");

const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ---------------------------------------------------------------- storage

// localStorage can be missing or throw (private mode, blocked storage).
function storageGet(store, key) {
  try { return store.getItem(key); } catch { return null; }
}
function storageSet(store, key, value) {
  try { store.setItem(key, value); } catch { /* not saved, the page still works */ }
}
function storageRemove(store, key) {
  try { store.removeItem(key); } catch { /* ignore */ }
}

function getClientId() {
  return (window.SPOTIFY_CLIENT_ID || storageGet(localStorage, "clientId") || "").trim();
}

// Must match one of the Redirect URIs saved in the app settings.
// On http://127.0.0.1:3000/ this is "http://127.0.0.1:3000", like the Python version.
function redirectUri() {
  const path = location.pathname === "/" ? "" : location.pathname.replace(/index\.html$/, "");
  return location.origin + path;
}

// ---------------------------------------------------------------- login (PKCE)

function randomString(length) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  const values = crypto.getRandomValues(new Uint8Array(length));
  return Array.from(values, (v) => alphabet[v % alphabet.length]).join("");
}

async function codeChallenge(verifier) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function login() {
  const verifier = randomString(64);
  const state = randomString(16);
  storageSet(sessionStorage, "codeVerifier", verifier);
  storageSet(sessionStorage, "authState", state);

  location.href = `${ACCOUNTS}/authorize?` + new URLSearchParams({
    response_type: "code",
    client_id: getClientId(),
    scope: SCOPES,
    code_challenge_method: "S256",
    code_challenge: await codeChallenge(verifier),
    redirect_uri: redirectUri(),
    state,
  });
}

/** Handle the ?code=... Spotify redirects to after the login. */
async function handleLoginRedirect() {
  const params = new URLSearchParams(location.search);
  if (!params.has("code") && !params.has("error")) return;
  history.replaceState(null, "", location.pathname);  // clean the URL

  if (params.get("error")) {
    throw new Error(`Spotify login refused: ${params.get("error")}.`);
  }
  if (params.get("state") !== storageGet(sessionStorage, "authState")) {
    throw new Error("The login did not start from this page. Log in again.");
  }

  const response = await fetch(`${ACCOUNTS}/api/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: getClientId(),
      grant_type: "authorization_code",
      code: params.get("code"),
      redirect_uri: redirectUri(),
      code_verifier: storageGet(sessionStorage, "codeVerifier") || "",
    }),
  });
  const data = await response.json();
  storageRemove(sessionStorage, "codeVerifier");
  storageRemove(sessionStorage, "authState");
  if (!data.access_token) {
    throw new Error(`Spotify login failed: ${data.error_description || data.error || "no access token received"}.`);
  }
  saveToken(data.access_token, data.expires_in);
}

function saveToken(token, expiresIn) {
  storageSet(sessionStorage, "token", JSON.stringify({ token, expiresAt: Date.now() + expiresIn * 1000 }));
}

function getToken() {
  try {
    const saved = JSON.parse(storageGet(sessionStorage, "token"));
    // Keep a minute of margin: an expired token makes every call fail with 401.
    return saved && saved.expiresAt - 60_000 > Date.now() ? saved.token : null;
  } catch {
    return null;
  }
}

function logout() {
  storageRemove(sessionStorage, "token");
  $("user").hidden = true;
  show("login");
}

// ---------------------------------------------------------------- Spotify API

class SpotifyError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

/** Call the Spotify Web API, waiting and retrying when rate limited (429). */
async function spotify(method, url, { params, body } = {}) {
  if (!url.startsWith("http")) url = API + url;
  if (params) url += "?" + new URLSearchParams(params);

  while (true) {
    const response = await fetch(url, {
      method,
      headers: {
        Authorization: `Bearer ${getToken()}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status === 429) {
      const retryAfter = Number(response.headers.get("Retry-After")) || 5;
      setStatus(`Spotify asked to slow down, waiting ${retryAfter} seconds…`);
      await sleep(retryAfter * 1000);
      continue;
    }
    if (!response.ok) {
      let message = "";
      try { message = (await response.json()).error?.message || ""; } catch { /* no JSON body */ }
      throw new SpotifyError(response.status, message);
    }
    const text = await response.text();
    return text ? JSON.parse(text) : null;
  }
}

/** Yield every item of a paginated endpoint, following the "next" links. */
async function* getAllPages(url, params) {
  while (url) {
    const data = await spotify("GET", url, { params });
    yield* data.items;
    url = data.next;
    params = undefined;  // the "next" URL already contains the query parameters
  }
}

function* chunks(items, size) {
  for (let i = 0; i < items.length; i += size) yield items.slice(i, i + size);
}

/** Title without versions/features: "Song (feat. X) - Remastered" -> "song". */
function baseTitle(trackName) {
  return trackName.toLowerCase().split(/\s-\s|\(|\[/)[0].trim();
}

function smallestImage(images, minSize = 64) {
  if (!images || !images.length) return "";
  const fitting = images.filter((image) => (image.width || 0) >= minSize);
  return (fitting.length ? fitting[fitting.length - 1] : images[0]).url;
}

// ---------------------------------------------------------------- the steps of main.py

async function searchArtists(query) {
  // 10 is the maximum search limit.
  const data = await spotify("GET", "/search", { params: { q: query, type: "artist", limit: 10 } });
  return data.artists.items;
}

/** Return the URIs of all the artist's songs, one per title. */
async function fetchTrackUris(artist) {
  const albums = [];
  for await (const album of getAllPages(`/artists/${artist.id}/albums`,
    { include_groups: "album,single", limit: 10 })) {  // 10 is the maximum
    albums.push(album);
    setStatus(`Finding releases… ${albums.length} so far`);
  }

  const trackUris = new Set();
  const seenTitles = new Set();

  for (const [index, album] of albums.entries()) {
    setStatus(`Reading ${album.name}`);
    for await (const track of getAllPages(`/albums/${album.id}/tracks`, { limit: 50 })) {  // 50 is the maximum
      const title = baseTitle(track.name);
      if (seenTitles.has(title)) continue;  // same song already added from another release
      seenTitles.add(title);
      trackUris.add(`spotify:track:${track.id}`);
    }
    addToWall(album);
    setProgress(index + 1, albums.length, trackUris.size);

    // Pause between albums to avoid hitting the rate limit.
    await sleep(500 + Math.random() * 500);
  }
  return [...trackUris];
}

/** The ids of the current user's own playlists called `name`. */
async function findMyPlaylists(name, userId) {
  const ids = [];
  for await (const playlist of getAllPages("/me/playlists", { limit: 50 })) {
    if (playlist && playlist.name === name && playlist.owner.id === userId) ids.push(playlist.id);
  }
  return ids;
}

/** Remove playlists from the user's library (what "Delete" does in the Spotify app). */
async function removePlaylists(playlistIds) {
  const uris = playlistIds.map((id) => `spotify:playlist:${id}`);
  for (const batch of chunks(uris, 40)) {  // at most 40 URIs per request
    await spotify("DELETE", "/me/library", { params: { uris: batch.join(",") } });
  }
}

async function createPlaylist(name, trackUris) {
  const playlist = await spotify("POST", "/me/playlists", { body: { name, public: true } });
  let added = 0;
  for (const batch of chunks(trackUris, 100)) {  // at most 100 tracks per request
    await spotify("POST", `/playlists/${playlist.id}/items`, { body: { uris: batch } });
    added += batch.length;
    setStatus(`Adding songs… ${added} of ${trackUris.length}`);
  }
  return playlist.id;
}

// ---------------------------------------------------------------- cache (<Artist>.txt in the Python version)

function loadCache(artistId) {
  try { return JSON.parse(storageGet(localStorage, `tracks:${artistId}`)); } catch { return null; }
}
function saveCache(artist, uris) {
  storageSet(localStorage, `tracks:${artist.id}`, JSON.stringify({ name: artist.name, uris, savedAt: Date.now() }));
}

// ---------------------------------------------------------------- UI

let me = null;             // the logged-in user (/me)
let chosenArtist = null;

function show(screen) {
  for (const section of document.querySelectorAll("[data-screen]")) {
    section.hidden = section.dataset.screen !== screen;
  }
  const heading = document.querySelector(`[data-screen="${screen}"] h1`);
  if (heading) { heading.tabIndex = -1; heading.focus({ preventScroll: true }); }
}

function showError(error) {
  console.error(error);
  let message = error.message || String(error);
  if (error instanceof SpotifyError) {
    if (error.status === 401) {
      logout();
      message = "Your Spotify session expired. Log in again.";
    } else if (error.status === 403) {
      message = "Spotify refused the request (403). Check that your account is in the app’s User Management list "
        + "on the Developer Dashboard and that the app owner has Premium."
        + (error.message ? ` Spotify said: “${error.message}”.` : "");
    } else {
      message = `Spotify answered with error ${error.status}${error.message ? `: ${error.message}` : ""}.`;
    }
  }
  $("alert-text").textContent = message;
  $("alert").hidden = false;
}

function clearError() {
  $("alert").hidden = true;
}

function setStatus(text) {
  $("status").textContent = text;
}

function setProgress(done, total, songs) {
  const percent = total ? Math.round((done / total) * 100) : 0;
  $("progress-bar").style.width = `${percent}%`;
  $("progress").setAttribute("aria-valuenow", percent);
  $("counts").textContent = `${done} of ${total} releases read, ${songs} unique songs so far.`;
}

function addToWall(album) {
  const item = document.createElement("li");
  const src = smallestImage(album.images, 150);
  if (src) {
    const img = document.createElement("img");
    img.src = src;
    img.alt = "";
    img.loading = "lazy";
    item.append(img);
  }
  item.title = `${album.name} (${(album.release_date || "").slice(0, 4)})`;
  $("wall").append(item);
}

function renderArtists(artists) {
  const list = $("artists");
  list.replaceChildren();
  if (!artists.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No artist with that name. Check the spelling or try a shorter name.";
    list.append(empty);
    return;
  }
  for (const artist of artists) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "artist";

    const img = document.createElement("span");
    img.className = "portrait";
    const src = smallestImage(artist.images, 160);
    if (src) img.style.backgroundImage = `url("${src}")`;
    else img.textContent = artist.name.charAt(0);

    const text = document.createElement("span");
    text.className = "artist-text";
    const name = document.createElement("strong");
    name.textContent = artist.name;
    const meta = document.createElement("span");
    meta.className = "meta";
    const details = [];
    if (artist.followers?.total != null) details.push(`${artist.followers.total.toLocaleString()} followers`);
    if (artist.genres?.length) details.push(artist.genres.slice(0, 2).join(", "));
    meta.textContent = details.join(", ");
    text.append(name, meta);
    if (loadCache(artist.id)) {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = "List saved";
      text.append(badge);
    }

    button.append(img, text);
    button.addEventListener("click", () => chooseArtist(artist));
    item.append(button);
    list.append(item);
  }
}

function chooseArtist(artist) {
  chosenArtist = artist;
  const cached = loadCache(artist.id);
  if (!cached) {
    build(artist, false);
    return;
  }
  const date = new Date(cached.savedAt).toLocaleDateString();
  $("cached-text").textContent = `You already downloaded ${artist.name}’s discography on ${date} `
    + `(${cached.uris.length} songs). Download it again if they released new music since then.`;
  $("artists").replaceChildren();
  $("cached").hidden = false;
  $("use-cache").focus();
}

function askConfirm(title, text) {
  const dialog = $("confirm-dialog");
  $("confirm-title").textContent = title;
  $("confirm-text").textContent = text;
  dialog.returnValue = "";
  dialog.showModal();
  return new Promise((resolve) => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "yes"), { once: true });
  });
}

/** main() of the Python version. */
async function build(artist, useCache) {
  clearError();
  $("cached").hidden = true;
  $("working-title").textContent = artist.name;
  $("wall").replaceChildren();
  $("counts").textContent = "";
  setProgress(0, 0, 0);
  show("working");

  try {
    let trackUris;
    const cached = useCache && loadCache(artist.id);
    if (cached) {
      trackUris = cached.uris;
      setProgress(1, 1, trackUris.length);
      $("counts").textContent = `${trackUris.length} unique songs from the saved list`;
    } else {
      trackUris = await fetchTrackUris(artist);
      saveCache(artist, trackUris);
    }
    if (!trackUris.length) throw new Error(`Spotify has no albums or singles for ${artist.name}.`);

    setStatus("Looking for an existing playlist with the same name…");
    const existing = await findMyPlaylists(artist.name, me.id);
    if (existing.length) {
      const rebuild = await askConfirm(
        `You already have a playlist called “${artist.name}”`,
        "Delete it and build it again with the current list of songs? The new playlist gets a different link.",
      );
      if (!rebuild) {
        show("search");
        return;
      }
      setStatus("Deleting the old playlist…");
      await removePlaylists(existing);
    }

    setStatus("Creating the playlist…");
    const playlistId = await createPlaylist(artist.name, trackUris);
    showDone(artist, playlistId, trackUris);
  } catch (error) {
    if (getToken()) show("search");
    showError(error);
  }
}

function showDone(artist, playlistId, trackUris) {
  $("done-title").textContent = `${artist.name} is ready`;
  $("done-text").textContent = `${trackUris.length} songs, each one only once, now in a public playlist in your library.`;
  $("open-playlist").href = `https://open.spotify.com/playlist/${playlistId}`;
  $("embed").src = `https://open.spotify.com/embed/playlist/${playlistId}`;

  const link = $("download-list");
  if (link.href.startsWith("blob:")) URL.revokeObjectURL(link.href);
  link.href = URL.createObjectURL(new Blob([trackUris.join(", ")], { type: "text/plain" }));
  link.download = `${artist.name}.txt`;
  show("done");
}

async function showUser() {
  me = await spotify("GET", "/me");
  $("user-name").textContent = me.display_name || me.id;
  const avatar = smallestImage(me.images, 0);
  $("user-avatar").hidden = !avatar;
  if (avatar) $("user-avatar").src = avatar;
  $("user").hidden = false;
}

// ---------------------------------------------------------------- events

$("setup-form").addEventListener("submit", (event) => {
  event.preventDefault();
  storageSet(localStorage, "clientId", $("client-id").value.trim());
  window.SPOTIFY_CLIENT_ID = window.SPOTIFY_CLIENT_ID || $("client-id").value.trim();
  show("login");
});

$("change-client-id").addEventListener("click", () => {
  storageRemove(localStorage, "clientId");
  window.SPOTIFY_CLIENT_ID = "";
  $("client-id").value = "";
  show("setup");
});

$("login").addEventListener("click", () => login().catch(showError));
$("logout").addEventListener("click", logout);
$("alert-close").addEventListener("click", clearError);

$("search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  $("cached").hidden = true;
  const button = event.submitter || event.target.querySelector("button");
  button.disabled = true;
  try {
    renderArtists(await searchArtists($("query").value.trim()));
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
  }
});

$("use-cache").addEventListener("click", () => build(chosenArtist, true));
$("refresh-cache").addEventListener("click", () => build(chosenArtist, false));

$("again").addEventListener("click", () => {
  $("embed").removeAttribute("src");
  $("artists").replaceChildren();
  $("query").value = "";
  show("search");
  $("query").focus();
});

// ---------------------------------------------------------------- start

async function start() {
  $("redirect-uri").textContent = redirectUri();
  if (!getClientId()) {
    show("setup");
    return;
  }
  try {
    await handleLoginRedirect();
  } catch (error) {
    show("login");
    showError(error);
    return;
  }
  if (!getToken()) {
    show("login");
    return;
  }
  try {
    await showUser();
    show("search");
    $("query").focus();
  } catch (error) {
    show("login");
    showError(error);
  }
}

start();
