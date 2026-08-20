"""Cover art search (SteamGridDB-style), from several sources:

1. Steam Store (no key required) — good coverage for PC games.
2. SteamGridDB (optional free API key) — community-uploaded cover art in the
   exact portrait "grid" dimensions Steam itself uses, often higher quality
   than the Steam Store asset and available for non-Steam games too.
3. RAWG.io (optional free API key, set in Settings) — covers almost every
   platform (consoles, retro, indies...), so much broader than Steam alone.
4. Giant Bomb (optional free API key) — strong console/retro coverage,
   community-curated database.
5. TheGamesDB (optional free API key) — open, community-maintained database
   with strong console/retro box-art coverage (often the best source for
   older Nintendo/Sony/Sega titles).
6. Wikipedia (no key required) — last-resort fallback if nothing else was
   found (very old or obscure game).

The searched title is first cleaned up (parentheses, DLC/edition suffixes,
subtitles) to generate several search phrasings, and results from every
active source are merged then re-ranked by similarity to the original title
— rather than settling for the first raw result returned by a single API,
which isn't always the right game."""
import os
import re
import io
import time
import difflib
import ipaddress
import socket
import threading
import requests
from pathlib import Path
from urllib.parse import quote, urlparse
from . import applog, sequel_guard

STORE_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
STEAM_COVER_TEMPLATE = "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900.jpg"
STEAM_HEADER_TEMPLATE = "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"
RAWG_SEARCH_URL = "https://api.rawg.io/api/games"
WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

# SteamGridDB — community-uploaded cover art. Requires a free API key,
# sent as a Bearer token in the Authorization header.
STEAMGRIDDB_BASE_URL = "https://www.steamgriddb.com/api/v2"
# Portrait cover dimensions Steam (and this app's grid) use: 600x900 (and the
# smaller 342x482). We request the largest portrait grid available.
STEAMGRIDDB_GRID_DIMENSIONS = "600x900,342x482"

# TheGamesDB — open database of game artwork (boxart). Requires a free API
# key passed as the `apikey` query parameter.
THEGAMESDB_BASE_URL = "https://api.thegamesdb.net/v1"

TIMEOUT = 6
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")

# Folder where the user can drop their own cover art (at the project root,
# like backup_backlog, so it's easy to find and fill in).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
COVER_ART_DIR = Path(os.environ.get("BACKLOG_COVER_ART_DIR", PROJECT_ROOT / "cover_art"))
COVER_ART_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_filename(s: str) -> str:
    """Normalizes a name (game title or filename without extension) for a
    loose comparison: case, spaces, hyphens, underscores are all ignored."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def safe_title_filename(title: str, game_id: int, ext: str) -> str:
    """Builds a recognizable filename from the game title (rather than an
    opaque identifier), while staying unique thanks to the id."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", (title or "game").strip()).strip("_") or "game"
    return f"{slug}_{game_id}{ext}"


def build_local_cover_index():
    """Builds a {normalized_name: Path} index of the cover_art/ folder once,
    to avoid rescanning the disk for every game during a bulk fill
    (optimization)."""
    index = {}
    try:
        candidates = list(COVER_ART_DIR.iterdir())
    except FileNotFoundError:
        return index
    for f in candidates:
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
            index[_normalize_filename(f.stem)] = f
    return index


def find_local_cover(title: str, index: dict = None):
    """Looks in cover_art/ for a file whose name matches the game title
    (ignoring spacing/underscores/case). Returns the Path found, or None. A
    pre-built `index` from build_local_cover_index() can be passed in to
    avoid rescanning the folder on every call (useful when processing many
    games in a row)."""
    if not title:
        return None
    target = _normalize_filename(title)
    if not target:
        return None
    if index is not None:
        return index.get(target)
    try:
        candidates = list(COVER_ART_DIR.iterdir())
    except FileNotFoundError:
        return None
    for f in candidates:
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
            if _normalize_filename(f.stem) == target:
                return f
    return None


def is_valid_image(path_or_bytes) -> bool:
    """Checks that the content is really an image (not an executable or any
    other file simply renamed with an image extension)."""
    try:
        from PIL import Image
        if isinstance(path_or_bytes, (bytes, bytearray)):
            img = Image.open(io.BytesIO(path_or_bytes))
        else:
            img = Image.open(path_or_bytes)
        img.verify()
        return True
    except Exception:
        return False


_SUFFIX_PATTERN = re.compile(
    r"\b(dlc|hd|remastered?|definitive edition|goty edition|"
    r"game of the year edition|director'?s cut|complete edition|"
    r"enhanced edition)\b",
    re.IGNORECASE,
)


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _similarity(a, b):
    """Plain fuzzy ratio, penalized when the two titles carry different
    sequel/entry numbers (e.g. "Dark Souls II" vs "Dark Souls III" are one
    character apart and would otherwise score deceptively high) — see
    sequel_guard for why this can't just be left to raw text similarity."""
    norm_a, norm_b = _norm(a), _norm(b)
    ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()
    if sequel_guard.sequel_conflict(norm_a, norm_b):
        ratio *= 0.25
    return ratio


def _query_variants(title: str):
    """Generates several search phrasings from a sometimes cluttered title
    (parentheses, DLC/edition suffixes, subtitle after ':' or '-'), to
    maximize the chances of finding the right game. E.g. 'Nier Automata (A)'
    -> ['Nier Automata'] ; 'Castlevania Lords of Shadow - Mirror of Fate HD'
    -> ['Castlevania Lords of Shadow - Mirror of Fate', ..., 'Castlevania Lords of Shadow']."""
    title = (title or "").strip()
    if not title:
        return []
    variants = []

    cleaned = re.sub(r"\([^)]*\)", "", title).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    if cleaned:
        variants.append(cleaned)

    stripped = _SUFFIX_PATTERN.sub("", cleaned).strip()
    stripped = re.sub(r"\s{2,}", " ", stripped)
    if stripped and stripped.lower() != cleaned.lower():
        variants.append(stripped)

    base = re.split(r"\s+-\s+|:\s+", cleaned)[0].strip()
    if base and base.lower() not in (v.lower() for v in variants):
        variants.append(base)

    seen, ordered = set(), []
    for v in variants + [title]:
        k = v.lower()
        if v and k not in seen:
            seen.add(k)
            ordered.append(v)
    return ordered


def _log_source_failure(source: str, query: str, exc_or_resp=None, note: str = None):
    """Every keyed source below is wrapped in a broad except that returns
    [] on any failure — deliberately, so one misbehaving source never
    breaks the others or the whole search. But that used to mean a bad or
    expired API key, a rate limit, or a malformed request failed completely
    silently: the source would just always contribute zero results, with
    no way to tell that apart from "this source genuinely has no cover for
    this game". Steam needs no key and basically never fails this way, so
    the visible symptom was always the same: every result badge says
    Steam, even with other keys configured, and nothing in the UI explains
    why. This logs the real reason to the terminal/console MyBacklog is
    running in, so a source that looks configured but never returns
    anything is actually diagnosable."""
    if isinstance(exc_or_resp, requests.Response):
        detail = f"HTTP {exc_or_resp.status_code}"
        if exc_or_resp.status_code in (401, 403):
            detail += " (check that the API key is valid)"
        elif exc_or_resp.status_code == 429:
            detail += " (rate limited)"
    elif isinstance(exc_or_resp, Exception):
        detail = f"{type(exc_or_resp).__name__}: {exc_or_resp}"
    else:
        detail = note or "unknown error"
    applog.warn(f"Cover search [{source}] failed for {query!r}: {detail}")


def _search_steam(query):
    try:
        resp = requests.get(
            STORE_SEARCH_URL,
            params={"term": query, "cc": "us", "l": "english"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []
    results = []
    for it in data.get("items", []):
        appid = it.get("id")
        if not appid:
            continue
        results.append({
            "name": it.get("name"),
            "source": "steam",
            "appid": appid,
            "cover_url": STEAM_COVER_TEMPLATE.format(appid=appid),
            "fallback_url": STEAM_HEADER_TEMPLATE.format(appid=appid),
        })
    return results


def _search_rawg(query, api_key):
    if not api_key:
        return []
    try:
        resp = requests.get(
            RAWG_SEARCH_URL,
            params={"key": api_key, "search": query, "page_size": 6},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as exc:
        _log_source_failure("rawg", query, exc.response)
        return []
    except (requests.RequestException, ValueError) as exc:
        _log_source_failure("rawg", query, exc)
        return []
    results = []
    for it in data.get("results", []):
        image = it.get("background_image")
        if not image:
            continue
        results.append({
            "name": it.get("name"),
            "source": "rawg",
            "cover_url": image,
            "fallback_url": None,  # no distinct 2nd URL for this source
        })
    return results


GIANTBOMB_SEARCH_URL = "https://www.giantbomb.com/api/search/"
GIANTBOMB_HEADERS = {"User-Agent": "MyBacklog/1.0 (personal game backlog tracker)"}


def _search_giantbomb(query, api_key):
    """Giant Bomb — community-curated database with strong console/retro
    coverage. Requires a free API key (set in Settings). Giant Bomb blocks
    requests without a real User-Agent header, hence GIANTBOMB_HEADERS."""
    if not api_key:
        return []
    try:
        resp = requests.get(
            GIANTBOMB_SEARCH_URL,
            params={"api_key": api_key, "format": "json", "query": query,
                    "resources": "game", "limit": 6},
            headers=GIANTBOMB_HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as exc:
        _log_source_failure("giantbomb", query, exc.response)
        return []
    except (requests.RequestException, ValueError) as exc:
        _log_source_failure("giantbomb", query, exc)
        return []
    if data.get("error") != "OK":
        _log_source_failure(
            "giantbomb", query,
            note=f"API returned error={data.get('error')!r} (often means an invalid API key)",
        )
        return []
    results = []
    for it in data.get("results", []):
        image = it.get("image") or {}
        cover_url = image.get("super_url") or image.get("medium_url")
        if not cover_url:
            continue
        results.append({
            "name": it.get("name"),
            "source": "giantbomb",
            "cover_url": cover_url,
            "fallback_url": image.get("medium_url") if cover_url != image.get("medium_url") else None,
        })
    return results


def _search_steamgriddb(query, api_key):
    """SteamGridDB \u2014 community-uploaded cover art in the exact portrait
    "grid" dimensions Steam itself uses (600x900). Two-step flow like Giant
    Bomb: search games by name, then fetch the portrait grids for each match.
    Requires a free API key, sent as a Bearer token in the Authorization
    header. We restrict to static (non-animated) grids so the saved cover is a
    real, validatable image file once downloaded."""
    if not api_key:
        return []
    headers = {"Authorization": f"Bearer {api_key}"}
    # Step 1: resolve the searched name to SteamGridDB game ids. Unlike every
    # other source here, the search term is part of the URL *path* rather
    # than a query parameter, so it must be percent-encoded explicitly —
    # `requests` only auto-encodes values passed via `params=`. Left
    # unencoded, a title with a "/" (splits the path into extra segments),
    # "?"/"#" (truncates the path early), or "&" would silently mis-fire or
    # 404 instead of erroring loudly.
    try:
        resp = requests.get(
            f"{STEAMGRIDDB_BASE_URL}/search/autocomplete/{quote(query, safe='')}",
            headers=headers,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as exc:
        _log_source_failure("steamgriddb", query, exc.response)
        return []
    except (requests.RequestException, ValueError) as exc:
        _log_source_failure("steamgriddb", query, exc)
        return []
    if not data.get("success"):
        _log_source_failure(
            "steamgriddb", query,
            note=f"API returned success=false: {data.get('errors')}",
        )
        return []
    games = data.get("data") or []
    if not games:
        return []

    results = []
    # Step 2: for each matched game, fetch its portrait grids. Capped to the
    # first few games so a broad search doesn't fan out into many requests.
    for game in games[:4]:
        gid = game.get("id")
        name = game.get("name")
        if gid is None:
            continue
        try:
            gresp = requests.get(
                f"{STEAMGRIDDB_BASE_URL}/grids/game/{gid}",
                params={"dimensions": STEAMGRIDDB_GRID_DIMENSIONS,
                        "types": "static", "nsfw": "false", "humor": "false",
                        "epilepsy": "false", "limit": 6},
                headers=headers,
                timeout=TIMEOUT,
            )
            gresp.raise_for_status()
            gdata = gresp.json()
        except (requests.RequestException, ValueError):
            continue
        if not gdata.get("success"):
            continue
        for grid in gdata.get("data") or []:
            url = grid.get("url")
            thumb = grid.get("thumb")
            if not url:
                continue
            results.append({
                "name": name,
                "source": "steamgriddb",
                "cover_url": url,
                "fallback_url": thumb if thumb and thumb != url else None,
            })
    return results


def _search_thegamesdb(query, api_key):
    """TheGamesDB \u2014 open, community-maintained database with strong
    console/retro box-art coverage. Two-step flow like SteamGridDB: search
    games by name, then fetch front boxart for each match. Requires a free
    API key passed as the `apikey` query parameter. Only the front boxart is
    returned (the back of a box is rarely useful as a cover) and the original
    (full-res) base URL is preferred so the editor can crop cleanly."""
    if not api_key:
        return []
    try:
        resp = requests.get(
            f"{THEGAMESDB_BASE_URL}/Games/ByGameName",
            params={"name": query, "apikey": api_key, "fields": "id"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as exc:
        _log_source_failure("thegamesdb", query, exc.response)
        return []
    except (requests.RequestException, ValueError) as exc:
        _log_source_failure("thegamesdb", query, exc)
        return []
    if data.get("code") != 200:
        _log_source_failure(
            "thegamesdb", query,
            note=f"API returned code={data.get('code')!r}: {data.get('status')} "
                 f"(often means an invalid API key)",
        )
        return []
    games = (data.get("data") or {}).get("games") or []
    if not games:
        return []

    results = []
    for game in games[:6]:
        gid = game.get("id")
        name = game.get("game_title")
        if gid is None:
            continue
        try:
            iresp = requests.get(
                f"{THEGAMESDB_BASE_URL}/Games/Images",
                params={"games_id": gid, "apikey": api_key,
                        "filter": "boxart"},
                timeout=TIMEOUT,
            )
            iresp.raise_for_status()
            idata = iresp.json()
        except (requests.RequestException, ValueError):
            continue
        if idata.get("code") != 200:
            continue
        base = ((idata.get("data") or {}).get("base_url") or {}).get("original")
        if not base:
            continue
        for art in ((idata.get("data") or {}).get("boxart") or {}).get(str(gid), []):
            if art.get("type") != "boxart" or art.get("side") != "front":
                continue
            filename = art.get("filename")
            if not filename:
                continue
            url = base + filename
            results.append({
                "name": name,
                "source": "thegamesdb",
                "cover_url": url,
                "fallback_url": None,  # no distinct 2nd URL for this source
            })
    return results


def _search_wikipedia(query):
    """No-API-key fallback: searches Wikipedia and grabs the page's cover
    image via a single combined query (generator=search + pageimages), which
    is both more reliable than a plain text search — it pulls the actual
    infobox/lead image MediaWiki associates with the page, rather than
    depending on the REST summary endpoint having one — and cheaper (one
    request covers every candidate page instead of one search + N
    per-article follow-ups)."""
    try:
        resp = requests.get(
            WIKI_SEARCH_URL,
            params={
                "action": "query", "format": "json",
                "generator": "search", "gsrsearch": f"{query} video game", "gsrlimit": 4,
                "prop": "pageimages", "piprop": "original|thumbnail", "pithumbsize": 800,
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
    except (requests.RequestException, ValueError):
        return []

    results = []
    for page in pages.values():
        image = (page.get("original") or page.get("thumbnail") or {}).get("source")
        if not image:
            continue
        results.append({
            "name": page.get("title"),
            "source": "wikipedia",
            "cover_url": image,
            "fallback_url": None,  # no distinct 2nd URL for this source
        })
    return results


PLACEHOLDER_COLORS = [
    (0x3b, 0x5c, 0x9e), (0x9e, 0x3b, 0x5c), (0x3b, 0x9e, 0x6a),
    (0x9e, 0x7a, 0x3b), (0x6a, 0x3b, 0x9e), (0x3b, 0x8f, 0x9e),
]


def generate_placeholder_cover(title: str, dest_path):
    """Reliable last-resort fallback when no source (Steam/RAWG/Giant
    Bomb/Wikipedia) has a usable image for this game: generates a simple
    cover locally (colored background + title), deterministic from the
    title so the same game always gets the same placeholder. This is what
    guarantees every game ends up with *something* instead of a permanently
    broken/missing cover."""
    from PIL import Image, ImageDraw, ImageFont

    title = (title or "Unknown title").strip()
    color = PLACEHOLDER_COLORS[sum(ord(c) for c in title) % len(PLACEHOLDER_COLORS)]

    w, h = 600, 900
    img = Image.new("RGB", (w, h), color)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 42)
    except OSError:
        font = ImageFont.load_default()

    # Simple manual word-wrap so the title stays inside the cover.
    words = title.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) > w - 80:
            if current:
                lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    lines = lines[:6]

    line_height = 54
    total_height = len(lines) * line_height
    y = (h - total_height) // 2
    for line in lines:
        line_w = draw.textlength(line, font=font)
        draw.text(((w - line_w) / 2, y), line, font=font, fill=(255, 255, 255))
        y += line_height

    img.save(dest_path, "PNG")
    return True


def search_cover_candidates(title: str, max_results: int = 8, rawg_api_key: str = None,
                             giantbomb_api_key: str = None, steamgriddb_api_key: str = None,
                             thegamesdb_api_key: str = None):
    """Searches for cover art across several sources and returns the best
    candidates, ranked by similarity to the searched title — rather than in
    the raw order returned by a single API."""
    if not title or not title.strip():
        return []

    variants = _query_variants(title)
    merged = []
    seen = set()

    def _add_all(items):
        for it in items:
            key = (it.get("source"), _norm(it.get("name")), it.get("cover_url"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(it)

    for variant in variants:
        _add_all(_search_steam(variant))
        if steamgriddb_api_key:
            _add_all(_search_steamgriddb(variant, steamgriddb_api_key))
        if rawg_api_key:
            _add_all(_search_rawg(variant, rawg_api_key))
        if giantbomb_api_key:
            _add_all(_search_giantbomb(variant, giantbomb_api_key))
        if thegamesdb_api_key:
            _add_all(_search_thegamesdb(variant, thegamesdb_api_key))
        if len(merged) >= max_results:
            # Enough candidates found: no need to query the remaining
            # search variants (reduces latency and network calls).
            break

    if not merged:
        # Nothing found on any keyed source (very obscure game, no keys
        # configured...): last resort, less precise but broader coverage.
        _add_all(_search_wikipedia(variants[0]))

    # Rank each source's own matches by similarity, then interleave them
    # round-robin (best Steam match, best SteamGridDB match, best RAWG
    # match, ..., then each source's 2nd-best, and so on) instead of
    # sorting the whole merged pool by similarity and truncating. Steam
    # needs no key and tends to return many close string matches on its
    # own, so a flat sort-then-truncate could silently fill every one of
    # the `max_results` slots with Steam hits — even with several other
    # sources configured and returning perfectly good candidates — simply
    # because Steam happened to have more near-exact name matches. This
    # guarantees every source that found *something* gets a fair shot at
    # showing up in what the user actually sees.
    by_source = {}
    for it in merged:
        by_source.setdefault(it.get("source"), []).append(it)
    for items in by_source.values():
        items.sort(key=lambda it: _similarity(title, it.get("name") or ""), reverse=True)

    sources_in_order = list(by_source.keys())
    interleaved = []
    rank = 0
    while len(interleaved) < len(merged):
        added = False
        for src in sources_in_order:
            bucket = by_source[src]
            if rank < len(bucket):
                interleaved.append(bucket[rank])
                added = True
        rank += 1
        if not added:
            break

    return interleaved[:max_results]


def search_with_local(title: str, max_results: int = 8, rawg_api_key: str = None,
                       giantbomb_api_key: str = None, steamgriddb_api_key: str = None,
                       thegamesdb_api_key: str = None):
    """For interactive search (one game at a time): returns both a possible
    local match (cover_art/ folder) and the online candidates, so the user
    can choose between them if both exist."""
    local = find_local_cover(title)
    local_match = None
    if local and is_valid_image(local):
        local_match = {"filename": local.name, "preview_url": f"/api/cover-art-preview/{local.name}"}
    online = search_cover_candidates(title, max_results=max_results, rawg_api_key=rawg_api_key,
                                      giantbomb_api_key=giantbomb_api_key,
                                      steamgriddb_api_key=steamgriddb_api_key,
                                      thegamesdb_api_key=thegamesdb_api_key)
    return {"local_match": local_match, "online": online}


def _detect_image_ext(content: bytes) -> str:
    """Determines a file extension from actual image content rather than
    trusting the source URL, so a GIF or PNG cover doesn't get mislabeled as
    .jpg — which would break animation/transparency once served back with
    the wrong Content-Type."""
    try:
        from PIL import Image
        fmt = (Image.open(io.BytesIO(content)).format or "JPEG").upper()
    except Exception:
        return ".jpg"
    return {"JPEG": ".jpg", "PNG": ".png", "GIF": ".gif", "WEBP": ".webp"}.get(fmt, ".jpg")


# Minimum byte size for a plausible cover image. Anything smaller is almost
# certainly an error page, a tracking pixel, or a truncated response — not a
# real cover — so it's rejected before the (costlier) image-validation step.
MIN_IMAGE_BYTES = 500


def _is_safe_remote_url(url: str) -> bool:
    """SSRF guard for every outbound cover-art fetch (search results, a
    manually pasted URL, or the cover-proxy route the crop editor uses).

    Without this, any of those code paths — all reachable from the browser
    with a caller-supplied URL — would let someone make this server issue
    an arbitrary HTTP request: probing other services on the local network,
    a cloud metadata endpoint, etc. Only allows http(s) URLs whose hostname
    resolves exclusively to public IP addresses; private/loopback/
    link-local/reserved ranges are rejected outright.

    This is a best-effort check performed before the real request, so it
    doesn't close a DNS-rebinding race (the hostname could resolve
    differently by the time `requests` connects) — but it stops the
    straightforward case of someone pasting or forging an internal URL,
    which is the realistic threat here for a local single-user app."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local or
                ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            return False
    return True


def _fetch_valid_image_bytes(url: str, want_content_type: bool = False):
    """Shared download + validation core for every cover fetch.

    Fetches `url`, rejects non-image Content-Types, and verifies the bytes
    really decode as an image (defends against executables renamed .jpg, error
    pages, etc.). Returns the validated image bytes, or None on any failure
    — or, with want_content_type=True, an (bytes, content_type) tuple so a
    single request can serve both a save-to-disk caller and a stream-back-
    to-the-browser caller (see fetch_proxied_image below) without fetching
    the same URL twice. Both download_image() and
    download_image_with_detected_ext() build on this so the fetch/validate
    logic lives in exactly one place.

        +-----------+     GET url      +---------------+
        |  caller   | ----------------> |  requests.get |
        +-----------+                    +-------+-------+
                                               |  resp.content
                                               v
                                  +--------------------+
                                  | url host is public? |--- no --> None
                                  | status==200 ?      |--- no --> None
                                  | bytes >= MIN ?     |
                                  | content-type img?  |
                                  | is_valid_image ?   |
                                  +---------+----------+
                                            | yes
                                            v
                                  return content (bytes)
    """
    empty = (None, None) if want_content_type else None
    if not _is_safe_remote_url(url):
        return empty
    try:
        resp = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException:
        return empty
    if resp.status_code != 200 or len(resp.content) < MIN_IMAGE_BYTES:
        return empty
    content_type = resp.headers.get("content-type", "")
    if content_type and not content_type.startswith("image/"):
        return empty
    if not is_valid_image(resp.content):
        return empty
    if want_content_type:
        return resp.content, (content_type or "image/jpeg")
    return resp.content


def download_image(url: str, dest_path) -> bool:
    """Downloads an image to dest_path (fixed extension). Checks the content
    is really an image before writing it (protection against an executable or
    any other file disguised with an image extension). Returns True on
    success. Used when the destination extension is already known."""
    content = _fetch_valid_image_bytes(url)
    if content is None:
        return False
    with open(dest_path, "wb") as f:
        f.write(content)
    return True


def download_image_with_detected_ext(url: str, base_path):
    """Like download_image, but the caller passes a path without extension
    (or an ignored one) and gets back the real destination Path, with the
    extension matching the actual downloaded content (jpg/png/gif/webp).
    Used wherever the source format isn't known ahead of time — a manually
    pasted cover URL, or an auto-search result — so GIF covers keep working
    once saved. Returns None on failure."""
    content = _fetch_valid_image_bytes(url)
    if content is None:
        return None
    dest = Path(base_path).with_suffix(_detect_image_ext(content))
    with open(dest, "wb") as f:
        f.write(content)
    return dest


def fetch_proxied_image(url: str):
    """Used by the /api/cover-proxy route: fetches an external URL through
    the exact same SSRF guard and validation as every other cover download
    (_fetch_valid_image_bytes / _is_safe_remote_url above), and returns
    (content_bytes, content_type) for streaming back to the browser same-
    origin — the cover editor loads candidates into a <canvas> for cropping,
    and a canvas fed directly from a cross-origin image without permissive
    CORS headers becomes "tainted" and silently refuses to export, so every
    source the editor can open has to come back through our own origin
    first. Returns None if the URL is unsafe or the fetch/validation
    fails."""
    content, content_type = _fetch_valid_image_bytes(url, want_content_type=True)
    if content is None:
        return None
    return content, content_type


# --------------------------------------------------------------------------
# Bulk-fill of missing cover art ("quick search" button).
# Runs in a background thread so it doesn't block HTTP requests; progress is
# exposed via get_bulk_status() so the frontend can show a progress bar by
# polling the API regularly.
# --------------------------------------------------------------------------

_bulk_state = {
    "running": False, "total": 0, "done": 0, "found": 0, "skipped": 0,
    "current": None, "cancel": False,
}
_bulk_lock = threading.Lock()
BULK_FILL_DELAY_SECONDS = 0.25  # courtesy delay towards the public APIs used


def get_bulk_status():
    with _bulk_lock:
        return dict(_bulk_state)


def cancel_bulk_fill():
    with _bulk_lock:
        _bulk_state["cancel"] = True


def _bulk_worker():
    from .db import get_conn, COVERS_DIR, load_config

    cfg = load_config()
    rawg_key = cfg.get("rawg_api_key") or None
    giantbomb_key = cfg.get("giantbomb_api_key") or None
    steamgriddb_key = cfg.get("steamgriddb_api_key") or None
    thegamesdb_key = cfg.get("thegamesdb_api_key") or None

    # One connection for the read, kept open for writes too: opening a SQLite
    # connection per row (the old behaviour) is wasteful and can hit the
    # per-connection WAL/checkpoint overhead hundreds of times per batch.
    _write_conn = get_conn()
    rows = _write_conn.execute(
        "SELECT id, title FROM games WHERE cover_path IS NULL OR cover_path = ''"
    ).fetchall()

    # Index built once rather than rescanned for every game.
    local_index = build_local_cover_index()

    with _bulk_lock:
        # "running" and "cancel" were already set by start_bulk_fill()
        # before the thread started, to avoid any race window where a status
        # poll could arrive before the thread has done anything.
        _bulk_state.update({
            "total": len(rows), "done": 0, "found": 0, "skipped": 0, "current": None,
        })

    for row in rows:
        with _bulk_lock:
            if _bulk_state["cancel"]:
                break
            _bulk_state["current"] = row["title"]

        found = False
        try:
            local = find_local_cover(row["title"], index=local_index)
            if local:
                dest = COVERS_DIR / safe_title_filename(row["title"], row["id"], local.suffix.lower())
                if is_valid_image(local):
                    dest.write_bytes(local.read_bytes())
                    found = True
            if not found:
                candidates = search_cover_candidates(
                    row["title"], max_results=1, rawg_api_key=rawg_key,
                    giantbomb_api_key=giantbomb_key, steamgriddb_api_key=steamgriddb_key,
                    thegamesdb_api_key=thegamesdb_key,
                )
                if candidates:
                    base = COVERS_DIR / safe_title_filename(row["title"], row["id"], "")
                    dest = download_image_with_detected_ext(candidates[0]["cover_url"], base)
                    if not dest and candidates[0].get("fallback_url"):
                        dest = download_image_with_detected_ext(candidates[0]["fallback_url"], base)
                    if dest:
                        found = True
                if not found:
                    # Reliable fallback: nothing found anywhere, generate a
                    # placeholder rather than leaving the game with no cover.
                    dest = COVERS_DIR / safe_title_filename(row["title"], row["id"], ".png")
                    if generate_placeholder_cover(row["title"], dest):
                        found = True
            if found:
                # Persist the cover path. Reuse the single batch connection
                # rather than opening one per game (the old code opened, wrote,
                # and closed a fresh SQLite connection on every row — fine for
                # 10 games, painful for 500).
                _write_conn.execute(
                    "UPDATE games SET cover_path = ? WHERE id = ?",
                    (f"/api/covers/{dest.name}?v={int(time.time() * 1000)}", row["id"]),
                )
                _write_conn.commit()
        except Exception:
            # An error on one game must never block the whole batch: log it
            # silently and move on to the next one.
            found = False

        with _bulk_lock:
            _bulk_state["done"] += 1
            _bulk_state["found" if found else "skipped"] += 1

        time.sleep(BULK_FILL_DELAY_SECONDS)

    try:
        _write_conn.close()
    except Exception:
        pass

    with _bulk_lock:
        _bulk_state["running"] = False
        _bulk_state["current"] = None


def start_bulk_fill() -> bool:
    """Starts the bulk fill. Returns False if one is already running.
    Immediately marks the state as "running" before starting the thread, so
    a status poll right after this call can never read a stale "not
    running" state while a job has just started."""
    with _bulk_lock:
        if _bulk_state["running"]:
            return False
        _bulk_state.update({"running": True, "cancel": False, "total": 0, "done": 0,
                             "found": 0, "skipped": 0, "current": None})
    t = threading.Thread(target=_bulk_worker, daemon=True)
    t.start()
    return True
