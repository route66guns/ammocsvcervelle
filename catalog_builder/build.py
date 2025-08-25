import argparse, os, re, pandas as pd, math, datetime as dt
from jinja2 import Environment, FileSystemLoader, select_autoescape

ACRONYMS = {"CCI","FMJ","JHP","JSP","TMJ","HST","PSP","LR","WMR","ACP","NATO","HP","SP","HMR","V-MAX","Vmax"}
REPLACEMENTS = [
    (r"\s+", " "),              # collapse whitespace
    (r"\s{2,}", " "),
]

def smart_title(s):
    # Title-case but preserve acronyms and measurements like 9mm, .308, 6.5
    def fix_token(tok):
        t = tok
        if t.upper() in ACRONYMS: return t.upper()
        if re.match(r"^\d+mm$", t.lower()): return t.lower()
        if re.match(r"^\.\d+", t): return t  # .308
        if re.match(r"^\d+(\.\d+)?(gr|grain|in)$", t.lower()): return t.lower()
        return t.capitalize()
    toks = re.split(r"(\s+|-|/)", s)
    return "".join(fix_token(t) if t.strip() and not re.match(r"(\s+|-|/)", t) else t for t in toks)

def clean_title(raw, manufacturer=None):
    if not isinstance(raw, str): raw = str(raw or "")
    s = raw.strip()
    for pat, rep in REPLACEMENTS:
        s = re.sub(pat, rep, s)
    # Remove packaging tails like 50/10, 20/10 etc
    s = re.sub(r"\b\d{2,3}/\d{1,3}\b", "", s).strip()
    # Remove duplicate manufacturer prefix if present
    if manufacturer and s.upper().startswith(str(manufacturer).upper()):
        s = s[len(manufacturer):].strip(" -")
    # Compact uppercase noise
    if s.isupper() or sum(1 for c in s if c.isupper()) > sum(1 for c in s if c.islower()):
        s = smart_title(s.lower())
    # Normalize calibers
    s = re.sub(r"\b(\d{2,3})\s*MM\b", r"\1mm", s, flags=re.I)
    s = re.sub(r"\b(\d{2,3})\s*GR\b", r"\1gr", s, flags=re.I)
    # Final trim
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s if s else "Untitled"

def clean_feature(s):
    if not isinstance(s, str): s = str(s or "")
    s = s.strip()
    s = re.sub(r"\s{2,}", " ", s)
    # Simple title-case while preserving acronyms
    return smart_title(s)

def detect_columns(df: pd.DataFrame):
    lower = {c.lower().strip(): c for c in df.columns}
    alias = {
        "sku": ["sku","upc","barcode"],
        "partno": ["partno","part_no","mpn"],
        "title": ["description","title","name"],
        "manufacturer": ["manufacturer","brand","mfg"],
        "category": ["category","dept","department"],
        "price": ["store_price","price","msrp"],
        "onhand_new": ["onhand new","onhand_new","qty","quantity","stock","onhand"],
        "onhand_used": ["onhand used","onhand_used"],
    }
    def find_col(key):
        k = key.lower().strip()
        return lower.get(k)
    col = {k: None for k in alias}
    for key, options in alias.items():
        for opt in options:
            c = find_col(opt)
            if c:
                col[key] = c
                break
    return col

def row_instock(row, col):
    v = 0
    if col["onhand_new"] and pd.notna(row[col["onhand_new"]]):
        try: v += int(float(row[col["onhand_new"]]))
        except: pass
    if col["onhand_used"] and pd.notna(row[col["onhand_used"]]):
        try: v += int(float(row[col["onhand_used"]]))
        except: pass
    return v

def as_price(v):
    try:
        x = float(v)
        return f"${x:,.2f}"
    except Exception:
        return None

def parse_args():
    ap = argparse.ArgumentParser(description="Build Squarespace-ready catalog HTML from CSV")
    ap.add_argument("--csv", default="data/inventory.csv", help="Path to CSV")
    ap.add_argument("--out", default="out/index.html", help="Output HTML path")
    ap.add_argument("--title", default="Product Catalog", help="Page title")
    ap.add_argument("--min_stock", type=int, default=1, help="Minimum in-stock qty to include")
    ap.add_argument("--show_oos", action="store_true", help="Include out-of-stock items too")
    ap.add_argument("--category", default=None, help="Filter by category at build time")
    ap.add_argument("--max", type=int, default=None, help="Limit number of rows for testing")
    ap.add_argument("--no_clean_names", action="store_true", help="Disable product name cleanup")
    return ap.parse_args()

def main():
    args = parse_args()
    df = pd.read_csv(args.csv)
    col = detect_columns(df)

    # Detect desc columns
    desc_cols = []
    for c in df.columns:
        lc = c.lower().strip()
        if re.match(r"^desc\d+a?$", lc):
            desc_cols.append(c)

    # Apply base filters (category + stock)
    if args.category and col["category"]:
        df = df[df[col["category"]].astype(str).str.strip().str.lower() == args.category.strip().lower()]

    df["_stock"] = df.apply(lambda r: row_instock(r, col), axis=1)
    if not args.show_oos:
        df = df[df["_stock"] >= args.min_stock]

    if args.max:
        df = df.head(args.max)

    products = []
    for _, r in df.iterrows():
        raw_title = (str(r[col["title"]]) if col["title"] else "") if col["title"] in r else ""
        manufacturer = str(r[col["manufacturer"]]) if col["manufacturer"] and pd.notna(r[col["manufacturer"]]) else ""
        title = clean_title(raw_title, manufacturer) if not args.no_clean_names else (raw_title or "Untitled")
        sku = str(r[col["sku"]]) if col["sku"] and pd.notna(r[col["sku"]]) else ""
        category = str(r[col["category"]]) if col["category"] and pd.notna(r[col["category"]]) else ""
        partno = str(r[col["partno"]]) if col["partno"] and pd.notna(r[col["partno"]]) else ""
        price_str = as_price(r[col["price"]]) if col["price"] and pd.notna(r[col["price"]]) else ""
        stock = int(r["_stock"]) if "_stock" in r else 0
        in_stock = stock >= args.min_stock
        stock_note = f"In stock: {stock}" if stock > 0 else "Out of stock"

        # Collect features from desc* columns
        feats = []
        for dc in desc_cols:
            val = r.get(dc, None)
            if pd.notna(val) and str(val).strip():
                feats.append(clean_feature(str(val).strip()))
        # Dedup preserve order
        seen = set(); features = []
        for f in feats:
            key = f.lower()
            if key not in seen:
                seen.add(key); features.append(f)

        # Keywords for search
        kws = " ".join(features + list(filter(None, [sku, partno, manufacturer, category])))

        products.append({
            "sku": sku,
            "title": title,
            "manufacturer": manufacturer or "",
            "category": category or "",
            "partno": partno or "",
            "price_str": price_str or "",
            "in_stock": in_stock,
            "stock_note": stock_note,
            "features": features[:8],
            "keywords": kws
        })

    # Sort
    products.sort(key=lambda p: (p["category"].lower(), p["title"].lower()))

    cats = sorted({p["category"] for p in products if p["category"]})
    mfgs = sorted({p["manufacturer"] for p in products if p["manufacturer"]})

    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(["html","xml"]),
        trim_blocks=True, lstrip_blocks=True
    )
    tpl = env.get_template("catalog.html.j2")
    html = tpl.render(
        title=args.title,
        total=len(products),
        products=products,
        categories=cats,
        manufacturers=mfgs,
        generated_at=dt.datetime.now().strftime("%b %d, %Y %I:%M %p"),
        filtered_note=None if args.show_oos else f"showing items with stock ≥ {args.min_stock}"
    )

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {args.out} ({len(products)} products)")

if __name__ == "__main__":
    main()
