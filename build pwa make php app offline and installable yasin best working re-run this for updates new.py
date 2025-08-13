import os
import json
import re
import hashlib
from PIL import Image

# ===============================
# CONFIG
# ===============================
SOURCE_LOGO_PATH = r"logo.jpg"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

APP_NAME = "My Web App"
SHORT_NAME = "WebApp"
APP_DESCRIPTION = "A description of the web application."
BACKGROUND_COLOR = "#ffffff"
THEME_COLOR = "#007bff"
VERSION = "1.1.0"  # PHP support + no-destructive writes

# PHP caching behavior:
#   True  => cache .php pages for offline usage (like static HTML)
#   False => do NOT cache .php; show offline.html when offline
CACHE_PHP_FILES = False


# ===============================
# UTILITIES
# ===============================
def log(msg): print(msg)

def get_file_hash(path):
    hasher = hashlib.md5()
    try:
        with open(path, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()
    except Exception as e:
        log(f"   ❌ Could not hash file {os.path.basename(path)}: {e}")
        return None


# ===============================
# ICONS / FAVICON
# ===============================
def generate_pwa_icons(source_path, output_dir):
    log("--- 1. Generating PWA Icons ---")
    if not os.path.exists(source_path):
        log(f"❌ Error: Source logo not found at '{source_path}'.")
        return [], []

    icon_sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    generated_icons = []
    icon_metadata = []
    try:
        from PIL import Image  # ensure PIL is present
        with Image.open(source_path) as logo:
            logo = logo.convert("RGBA")
            for size in icon_sizes:
                filename = f"icon-{size}.png"
                output_path = os.path.join(output_dir, filename)

                canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                logo_copy = logo.copy()
                logo_copy.thumbnail((size, size))
                left = (size - logo_copy.width) // 2
                top = (size - logo_copy.height) // 2
                canvas.paste(logo_copy, (left, top))
                canvas.save(output_path, "PNG")

                log(f"✅ Created: {filename}")
                file_hash = get_file_hash(output_path)
                if file_hash:
                    generated_icons.append({"url": filename, "revision": file_hash})
                icon_metadata.append({"src": filename, "sizes": f"{size}x{size}", "type": "image/png"})
        return generated_icons, icon_metadata
    except Exception as e:
        log(f"❌ Error generating icons: {e}")
        return [], []


def generate_favicon(source_path, output_dir):
    log("\n--- Generating favicon.ico ---")
    try:
        if not os.path.exists(source_path):
            log(f"❌ Error: Source logo not found at '{source_path}'.")
            return None
        with Image.open(source_path) as logo:
            logo = logo.convert("RGBA")
            logo = logo.resize((48, 48))
            favicon_path = os.path.join(output_dir, "favicon.ico")
            logo.save(favicon_path, format='ICO')
            log("✅ Created: favicon.ico")
            return "favicon.ico"
    except Exception as e:
        log(f"❌ Error creating favicon.ico: {e}")
        return None


# ===============================
# DISCOVER & HASH
# ===============================
def discover_assets(project_dir, generated_icons):
    log(f"\n--- 2. Discovering App Files and Generating Hashes ---")
    precache_list = generated_icons[:]  # already include icons
    existing_urls = {entry['url'] for entry in precache_list}

    html_files = []
    php_files = []

    for root, _, files in os.walk(project_dir):
        # skip hidden folders like .git, .venv, etc.
        if any(part.startswith('.') for part in root.split(os.sep)):
            continue

        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, project_dir).replace("\\", "/")

            # avoid duplicate URLs
            if relative_path in existing_urls:
                continue

            # classify
            lower = file.lower()
            if lower.endswith(".html"):
                html_files.append(file_path)
            elif lower.endswith(".php"):
                php_files.append(file_path)

            # Decide if the file should be pre-cached:
            # - Always precache non-PHP files (css/js/images/fonts/etc.)
            # - Precache .html
            # - Precache .php only if CACHE_PHP_FILES is True
            should_precache = False
            if lower.endswith(".php"):
                should_precache = CACHE_PHP_FILES
            elif lower.endswith(".html"):
                should_precache = True
            else:
                should_precache = True

            if should_precache:
                file_hash = get_file_hash(file_path)
                if file_hash:
                    precache_list.append({"url": relative_path, "revision": file_hash})
                    existing_urls.add(relative_path)

    if not html_files and not php_files:
        log("❌ Error: No HTML or PHP files found.")
        return [], [], []

    log(f"✅ Discovered and hashed {len(precache_list)} local files (per caching rules).")
    return precache_list, html_files, php_files


# ===============================
# TITLE / DESCRIPTION (NON-DESTRUCTIVE)
# ===============================
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]*content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL
)

def read_title_desc(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            title_m = TITLE_RE.search(content)
            desc_m = DESC_RE.search(content)
            title = title_m.group(1).strip() if title_m else None
            desc = desc_m.group(1).strip() if desc_m else None
            return title, desc
    except Exception as e:
        log(f"⚠️ Could not read title/description from {os.path.basename(file_path)}: {e}")
        return None, None


# ===============================
# MANIFEST
# ===============================
def create_manifest(output_dir, icon_metadata, start_url, title_from_file, desc_from_file):
    log("\n--- 3. Creating manifest.json ---")
    manifest = {
        "name": title_from_file or APP_NAME,
        "short_name": title_from_file or SHORT_NAME,
        "description": desc_from_file or APP_DESCRIPTION,
        "start_url": start_url,
        "display": "standalone",
        "background_color": BACKGROUND_COLOR,
        "theme_color": THEME_COLOR,
        "orientation": "portrait-primary",
        "icons": icon_metadata
    }
    with open(os.path.join(output_dir, "manifest.json"), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    log("✅ Created: manifest.json")


# ===============================
# SERVICE WORKER
# ===============================
def create_service_worker(output_dir, precache_list):
    log("\n--- 4. Creating sw.js (Service Worker) ---")

    # Build JS array text without Python dict repr leakage
    precache_json = json.dumps(precache_list, indent=4)

    # When CACHE_PHP_FILES is False, we still might precache other documents (.html) & assets,
    # and we explicitly avoid caching .php (handled above). The catch handler will serve offline.html.
    sw_template = f"""
// Auto-generated by PWA builder script v{VERSION}
importScripts('https://storage.googleapis.com/workbox-cdn/releases/7.0.0/workbox-sw.js');

if (workbox) {{
  console.log('Workbox is loaded.');

  self.addEventListener('message', (event) => {{
    if (event.data && event.data.type === 'SKIP_WAITING') {{
      console.log('Service Worker received SKIP_WAITING message, activating now.');
      self.skipWaiting();
    }}
  }});

  workbox.core.clientsClaim();

  // Precache (per discovered assets and PHP caching rule)
  workbox.precaching.precacheAndRoute({precache_json});

  // Runtime caching for CSS/JS
  workbox.routing.registerRoute(
    ({{request}}) => request.destination === 'style' || request.destination === 'script',
    new workbox.strategies.StaleWhileRevalidate({{ cacheName: 'asset-cache' }})
  );

  // Images cache
  workbox.routing.registerRoute(
    ({{request}}) => request.destination === 'image',
    new workbox.strategies.CacheFirst({{
      cacheName: 'image-cache',
      plugins: [ new workbox.expiration.ExpirationPlugin({{ maxEntries: 60, maxAgeSeconds: 30 * 24 * 60 * 60 }}) ],
    }})
  );

  {"// For PHP documents, use regular network; offline shows offline.html" if not CACHE_PHP_FILES else "// PHP pages are precached like other documents"}

  {"workbox.routing.registerRoute(( {request} ) => request.destination === 'document' && new URL(request.url).pathname.endsWith('.php'), new workbox.strategies.NetworkOnly());" if not CACHE_PHP_FILES else ""}

  // Generic offline fallback for documents (HTML/PHP)
  workbox.routing.setCatchHandler(async ({{event}}) => {{
    if (event.request && event.request.destination === 'document') {{
      const cached = await caches.match('offline.html');
      return cached || Response.error();
    }}
    return Response.error();
  }});

}} else {{
  console.log('Workbox failed to load.');
}}
""".strip()

    with open(os.path.join(output_dir, "sw.js"), 'w', encoding='utf-8') as f:
        f.write(sw_template)
    log("✅ Created: sw.js")


# ===============================
# UPDATE FILES (NON-DESTRUCTIVE INSERTS)
# ===============================

MANIFEST_LINK = '<link rel="manifest" href="manifest.json">'
FAVICON_LINK  = '<link rel="icon" type="image/x-icon" href="favicon.ico">'
SW_SCRIPT = """<script type="module">
  import { Workbox } from 'https://storage.googleapis.com/workbox-cdn/releases/7.0.0/workbox-window.prod.mjs';
  const swUrl = './sw.js';
  const wb = new Workbox(swUrl);

  wb.addEventListener('waiting', () => {
    console.log('A new service worker is waiting to activate.');
    wb.messageSW({ type: 'SKIP_WAITING' });
  });

  wb.addEventListener('controlling', () => {
    console.log('The new service worker is now in control. Reloading page for updates...');
    window.location.reload();
  });

  wb.register();
</script>
"""

def insert_before(tag_to_insert, content, closing_tag_pattern):
    """
    Insert tag_to_insert immediately before the first match of closing_tag_pattern.
    If not found, append at end.
    """
    m = re.search(closing_tag_pattern, content, flags=re.IGNORECASE)
    if not m:
        return content + "\n" + tag_to_insert + "\n"
    start = m.start()
    return content[:start] + tag_to_insert + "\n" + content[start:]


def ensure_in_head(content, snippet):
    if snippet in content:
        return content
    # Try to insert before </head>
    return insert_before(snippet, content, r"</head\s*>")


def ensure_before_body_end(content, snippet):
    if snippet in content:
        return content
    # Insert before </body>
    return insert_before(snippet, content, r"</body\s*>")


def update_text_file(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            original = f.read()

        updated = original

        # Add <link rel="manifest"> if missing
        if 'rel="manifest"' not in updated:
            updated = ensure_in_head(updated, MANIFEST_LINK)

        # Add favicon if missing
        if 'rel="icon"' not in updated and 'favicon.ico' not in updated:
            updated = ensure_in_head(updated, FAVICON_LINK)

        # Add SW registration if not already present
        if 'workbox-window.prod.mjs' not in updated and 'new Workbox(' not in updated:
            updated = ensure_before_body_end(updated, SW_SCRIPT)

        if updated != original:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(updated)
            log(f"   - Updated {os.path.basename(path)}")
        else:
            log(f"   - Skipped (already up-to-date): {os.path.basename(path)}")

    except Exception as e:
        log(f"   ❌ Could not update {os.path.basename(path)}: {e}")


def update_documents(html_files, php_files):
    log("\n--- 5. Updating HTML & PHP Files (non-destructive) ---")
    for fp in html_files + php_files:
        update_text_file(fp)
    log("✅ Files updated.")


# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    log(f"🚀 Starting PWA Build Script [v{VERSION}]...")
    log(f"    PHP caching mode: {'CACHE' if CACHE_PHP_FILES else 'OFFLINE_FALLBACK'}")

    # Ensure offline.html exists
    offline_page_path = os.path.join(PROJECT_DIR, 'offline.html')
    if not os.path.exists(offline_page_path):
        with open(offline_page_path, 'w', encoding='utf-8') as f:
            f.write(
                "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                "<title>Offline</title></head><body><h1>You are offline.</h1></body></html>"
            )
        log("✅ Created 'offline.html'.")

    # 1) Icons & favicon
    generated_icons, icon_metadata = generate_pwa_icons(SOURCE_LOGO_PATH, PROJECT_DIR)
    generate_favicon(SOURCE_LOGO_PATH, PROJECT_DIR)

    # 2) Discover & hash
    precache_list, html_files, php_files = discover_assets(PROJECT_DIR, generated_icons)

    if not (html_files or php_files):
        log("\n❌ Script stopped: No HTML/PHP files were found.")
        raise SystemExit(1)

    # Choose start file preference: index.html > index.php > first any
    candidates = []
    candidates += [p for p in html_files if os.path.basename(p).lower() == "index.html"]
    if not candidates:
        candidates += [p for p in php_files if os.path.basename(p).lower() == "index.php"]
    if not candidates:
        candidates += (html_files or php_files)

    start_file_path = candidates[0]
    start_url = os.path.relpath(start_file_path, PROJECT_DIR).replace("\\", "/")

    # Read title/description (non-destructive regex)
    title_from_file, desc_from_file = read_title_desc(start_file_path)

    # 3) Manifest
    create_manifest(PROJECT_DIR, icon_metadata, start_url, title_from_file, desc_from_file)

    # 4) Service worker (precache list already respects PHP caching flag)
    create_service_worker(PROJECT_DIR, precache_list)

    # 5) Update files (inject manifest, favicon, SW registration) — non-destructive
    update_documents(html_files, php_files)

    log(f"\n🎉 PWA setup is complete!")
