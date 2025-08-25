# Squarespace Catalog Builder

This repository generates a fully self-contained **HTML product catalog** from a CSV export like the one you provided. The resulting HTML works well inside a Squarespace **Code Block** or as a standalone page.

## Features
- Reads `data/inventory.csv` and normalizes common column names
- Filters out-of-stock items by default (configurable)
- Clean, responsive product cards
- Built‑in **search** and **filters** for Category and Manufacturer
- Optional image lookup by SKU from `out/assets/{SKU}.jpg` with graceful placeholder
- Outputs a single `out/index.html` that can be pasted into Squarespace

## Quick Start
1. Install Python 3.9+
2. `pip install -r requirements.txt`
3. Put your CSV at `data/inventory.csv` (already added from your upload)
4. Run:
   ```bash
   python build.py --title "Route 66 Guns & Ammo Catalog" --min_stock 1
   ```
5. Open `out/index.html` in a browser to preview.
6. To use in Squarespace, copy the **entire contents** of `out/index.html` and paste into a **Code Block** on your page.

## Images
If you have product images, place them at `out/assets/{SKU}.jpg` or `out/assets/{SKU}.png`. The catalog will automatically use them. When an image is missing, a neutral SVG placeholder will be shown.

## CSV Columns
This builder tries to auto-detect the following fields. Use these exact headers if possible for best results:
- `SKU` or `UPC`
- `PartNo` (optional)
- `Description` (product title)
- `Manufacturer`
- `Category`
- `store_price` or `Price`
- `Onhand New` or `OnHand New` or `Qty`

It also looks for `desc1`…`desc5` (and `desc1a`…`desc5a`) to show as bullet-point features when present.

If your columns differ, you can tweak the mapping near the top of `build.py`.

## Advanced
- Pass `--show_oos` to include out-of-stock items
- Pass `--category "AMMUNITION"` to filter by category at build time
- Pass `--max 500` to limit the number of products for testing
- The page is static and contains inline CSS/JS to remain portable

## License
MIT


---

## Deploy with GitHub Pages (Option A)

This project is ready to build and publish the catalog to **GitHub Pages** automatically on every push.

### Steps
1. Create a new repo on GitHub and push this folder:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```

2. The included workflow at `.github/workflows/deploy.yml` will:
   - Install Python
   - Build `out/index.html`
   - Publish the `out/` folder to GitHub Pages

3. Your catalog URL will look like:
   ```
   https://<your-username>.github.io/<your-repo>/
   ```

4. Squarespace embed:
   - Add a **Code** block and paste:
     ```html
     <iframe src="https://<your-username>.github.io/<your-repo>/" width="100%" height="2400" style="border:0;"></iframe>
     ```

### Product images
Place images at `out/assets/<SKU>.jpg` before pushing, or add them later and push again. Pages will serve them at:
```
https://<your-username>.github.io/<your-repo>/assets/<SKU>.jpg
```
