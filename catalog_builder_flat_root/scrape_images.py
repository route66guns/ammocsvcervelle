import argparse, os, re, time, io, sys, math, hashlib, mimetypes
from urllib.parse import urlparse
import requests
from PIL import Image
from duckduckgo_search import DDGS

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
}

ALLOW_DOMAINS = {
    "midwayusa.com","ammoseek.com","palmettostatearmory.com","sportsmans.com",
    "images-na.ssl-images-amazon.com","m.media-amazon.com","targetsportsusa.com",
    "brownells.com","academysports.com","basspro.com","cabelas.com","cheaperthandirt.com",
    "sgammo.com","gunmagwarehouse.com","sportsmansguide.com","natchezss.com","opticsplanet.com"
}

VALID_EXTS = {".jpg",".jpeg",".png",".webp",".gif"}

def safe_filename(s):
    return re.sub(r"[^a-zA-Z0-9_.-]+","_", s).strip("_")

def is_valid_image_url(u):
    try:
        ext = os.path.splitext(urlparse(u).path)[1].lower()
        return ext in VALID_EXTS
    except Exception:
        return False

def choose_candidates(query, max_results=12):
    # Prefer DDG images for simplicity and reliability in CI
    with DDGS() as ddg:
        results = ddg.images(keywords=query, max_results=max_results, safesearch="off")
    # Keep those from allowed domains first, then others
    allowed, other = [], []
    for r in results:
        u = r.get("image") or r.get("thumbnail") or ""
        if not u: 
            continue
        host = urlparse(u).netloc.lower()
        if any(host.endswith(d) for d in ALLOW_DOMAINS) and is_valid_image_url(u):
            allowed.append(u)
        elif is_valid_image_url(u):
            other.append(u)
    return allowed + other

def download_image(url, timeout=15):
    r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, stream=True)
    r.raise_for_status()
    content = r.content
    return content

def normalize_to_jpg(raw_bytes, max_px=1200, quality=88):
    im = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    w,h = im.size
    if max(w,h) > max_px:
        scale = max_px / float(max(w,h))
        im = im.resize((int(w*scale), int(h*scale)))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

def default_query(title, manufacturer, sku):
    parts = []
    if manufacturer: parts.append(str(manufacturer))
    if title: parts.append(str(title))
    if sku: parts.append(str(sku))
    return " ".join(parts)

def main():
    ap = argparse.ArgumentParser(description="Fetch product images by query and save as out/assets/<SKU>.jpg")
    ap.add_argument("--csv", default="data/inventory.csv", help="Path to CSV processed by build.py mappings")
    ap.add_argument("--outdir", default="out/assets", help="Where to save images")
    ap.add_argument("--limit", type=int, default=150, help="Max products to attempt per run")
    ap.add_argument("--overwrite", action="store_true", help="Redownload existing images")
    ap.add_argument("--sleep", type=float, default=1.0, help="Delay between downloads to be polite")
    args = ap.parse_args()

    import pandas as pd
    from build import detect_columns, clean_title
    
    os.makedirs(args.outdir, exist_ok=True)
    df = pd.read_csv(args.csv)
    col = detect_columns(df)

    attempted = 0
    saved = 0
    for _, r in df.iterrows():
        if args.limit and attempted >= args.limit:
            break
        sku = str(r[col["sku"]]) if col["sku"] and pd.notna(r[col["sku"]]) else None
        if not sku: 
            continue
        dest = os.path.join(args.outdir, f"{sku}.jpg")
        if os.path.exists(dest) and not args.overwrite:
            continue

        title_raw = str(r[col["title"]]) if col["title"] else ""
        manufacturer = str(r[col["manufacturer"]]) if col["manufacturer"] else ""
        title = clean_title(title_raw, manufacturer=manufacturer)
        query = default_query(title, manufacturer, sku)

        attempted += 1
        candidates = choose_candidates(query, max_results=14)
        ok = False
        for u in candidates:
            try:
                raw = download_image(u)
                jpg = normalize_to_jpg(raw)
                with open(dest, "wb") as f:
                    f.write(jpg)
                saved += 1
                ok = True
                break
            except Exception as e:
                continue
        time.sleep(args.sleep)
    print(f"Attempted: {attempted}, saved: {saved}, outdir: {args.outdir}")

if __name__ == "__main__":
    main()
