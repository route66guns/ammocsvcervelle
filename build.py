import argparse, os, re, pandas as pd, math, datetime as dt
from jinja2 import Environment, FileSystemLoader, select_autoescape

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).strip().lower())

def coalesce(d, keys):
    for k in keys:
        if k in d and pd.notna(d[k]):
            return d[k]
    return None

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
    return ap.parse_args()

def main():
    args = parse_args()
    df = pd.read_csv(args.csv)

    # Normalize column names for easier handling
    cols = {c: c for c in df.columns}
    lower = {c.lower().strip(): c for c in df.columns}

    # Common aliases
    alias = {
        "sku": ["sku", "upc", "barcode"],
        "partno": ["partno", "part_no", "mpn"],
        "title": ["description", "title", "name"],
        "manufacturer": ["manufacturer", "brand", "mfg"],
        "category": ["category", "dept", "department"],
        "price": ["store_price", "price", "msrp"],
        "onhand_new": ["onhand new", "onhand_new", "qty", "quantity", "stock", "onhand"],
        "onhand_used": ["onhand used", "onhand_used"],
    }

    def find_col(*keys):
        for k in keys:
            k = k.lower().strip()
            if k in lower:
                return lower[k]
        return None

    col = {k: None for k in alias}
    for key, options in alias.items():
        for opt in options:
            c = find_col(opt)
            if c:
                col[key] = c
                break

    # Detect desc columns
    desc_cols = []
    for c in df.columns:
        lc = c.lower().strip()
        if re.match(r"^desc\d+a?$", lc):
            desc_cols.append(c)

    # Compute stock and filter
    def row_instock(row):
        v = 0
        if col["onhand_new"] and pd.notna(row[col["onhand_new"]]):
            try: v += int(float(row[col["onhand_new"]]))
            except: pass
        if col["onhand_used"] and pd.notna(row[col["onhand_used"]]):
            try: v += int(float(row[col["onhand_used"]]))
            except: pass
        return v

    # Apply base filters (category + stock)
    if args.category and col["category"]:
        df = df[df[col["category"]].astype(str).str.strip().str.lower() == args.category.strip().lower()]

    if not args.show_oos:
        df["_stock"] = df.apply(row_instock, axis=1)
        df = df[df["_stock"] >= args.min_stock]
    else:
        df["_stock"] = df.apply(row_instock, axis=1)

    if args.max:
        df = df.head(args.max)

    # Transform rows
    products = []
    for _, r in df.iterrows():
        sku = coalesce(r, [col["sku"]]) if col["sku"] else None
        title = coalesce(r, [col["title"]]) or f"SKU {sku}" if sku else "Untitled"
        manufacturer = coalesce(r, [col["manufacturer"]])
        category = coalesce(r, [col["category"]])
        partno = coalesce(r, [col["partno"]])
        price_str = as_price(coalesce(r, [col["price"]])) if col["price"] else None
        stock = int(row_instock(r))
        in_stock = stock >= args.min_stock
        stock_note = f"In stock: {stock}" if stock > 0 else "Out of stock"

        # Collect features from desc* columns
        feats = []
        for dc in desc_cols:
            val = r.get(dc, None)
            if pd.notna(val) and str(val).strip():
                feats.append(str(val).strip())
        # Deduplicate while preserving order
        seen = set(); features = []
        for f in feats:
            key = f.lower()
            if key not in seen:
                seen.add(key); features.append(f)

        # Keywords for search
        kws = " ".join(features + list(filter(None, [sku, partno, manufacturer, category])))

        products.append({
            "sku": str(sku) if pd.notna(sku) else "",
            "title": str(title),
            "manufacturer": manufacturer or "",
            "category": category or "",
            "partno": partno or "",
            "price_str": price_str or "",
            "in_stock": in_stock,
            "stock_note": stock_note,
            "features": features[:8],  # keep cards compact
            "keywords": kws
        })

    # Sort by category then title
    products.sort(key=lambda p: (p["category"].lower(), p["title"].lower()))

    # Distinct picklists
    cats = sorted({p["category"] for p in products if p["category"]})
    mfgs = sorted({p["manufacturer"] for p in products if p["manufacturer"]})

    # Render
    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(["html", "xml"]),
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
