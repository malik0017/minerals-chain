"""
app/modules/public/pwa_routes.py
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.core.templates import templates

router = APIRouter(tags=["pwa"])
CACHE_VERSION = "mc-v1"
THEME = "#0e6e5c"


@router.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return JSONResponse({
        "name": "Minerals Chain",
        "short_name": "Minerals Chain",
        "description": "Saudi B2B minerals marketplace — RFQs, orders, shipments and compliance.",
        "id": "/home",
        "start_url": "/home?source=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#ffffff",
        "theme_color": THEME,
        "lang": "en",
        "dir": "auto",
        "categories": ["business", "productivity"],
        "icons": [
            {"src": "/static/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/img/logo-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/static/img/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "Orders", "url": "/home?go=orders", "icons": [{"src": "/static/img/icon-192.png", "sizes": "192x192"}]},
            {"name": "Notifications", "url": "/notifications", "icons": [{"src": "/static/img/icon-192.png", "sizes": "192x192"}]},
        ],
    }, media_type="application/manifest+json", headers={"Cache-Control": "public, max-age=3600"})


SW = """
const CACHE = '%(v)s';
const OFFLINE = '/offline';
const PRECACHE = [OFFLINE, '/static/css/app.css', '/static/css/theme-mineral.css', '/static/css/design_system.css',
  '/static/css/mc-components.css', '/static/img/logo-512.png', '/static/img/icon-192.png', '/static/img/favicon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin || url.pathname.startsWith('/api/')) return;
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).catch(() => caches.match(OFFLINE)));
    return;
  }
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    })));
  }
});
""" % {"v": CACHE_VERSION}


@router.get("/sw.js", include_in_schema=False)
def service_worker():
    return Response(SW.strip() + "\n", media_type="application/javascript",
                    headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@router.get("/offline", name="offline", include_in_schema=False)
def offline(request: Request):
    return templates.TemplateResponse(request, "public/offline.html", {"lang": request.cookies.get("mc_lang", "en")})
