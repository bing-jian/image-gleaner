# image-gleaner

A CLI tool to download images from Bing Image Search by keyword.

## Requirements

- Python 3.10+
- Google Chrome installed
- [Playwright](https://playwright.dev/python/)

```bash
pip install playwright
python -m playwright install chromium
```

## Usage

```bash
python gleaner.py "search term" [--count N] [--out DIR] [--no-headless]
```

### Arguments

| Argument | Default | Description |
|---|---|---|
| `keyword` | *(required)* | Search keyword(s) |
| `--count`, `-n` | `20` | Number of images to download |
| `--out`, `-o` | `downloads/` | Output base directory |
| `--no-headless` | | Show browser window while running |

### Examples

```bash
# Download 20 images (default)
python gleaner.py "golden retriever"

# Download 100 images to a custom folder
python gleaner.py "mountain landscape" --count 100 --out ~/datasets

# Watch the browser while it runs
python gleaner.py "abstract art" --count 50 --no-headless
```

## Output

Images are saved to `<out>/<keyword>/` with filenames like `0001_a3f2c1b0.jpg`.
The tool tries to download the original full-resolution image from the source
site, and falls back to Bing's cached thumbnail if that fails.
