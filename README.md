## Getting Started

You'll need Python 3.10 or higher.

```bash
# Get the code
git clone
cd vault-network-scraper

# Get dependencies
pip install -r requirements.txt
playwright install chromium
```

## Running it

Run the main script from your terminal:

```bash
python scraper.py
```

Once it's finished, it'll save an `output.json` file in the project folder and print a quick summary of the rows it found.

## How it works 

I found that standard scraping doesn't really work on QuickSight because it uses virtualized tables (meaning rows don't actually exist in the HTML until you scroll them into view).

The script handles the standard AWS auth flow. I've left the credentials in the script for now to keep things simple for the review.

QuickSight has a habit of throwing "What's New" or "Welcome" popups that block the screen. I added a helper that swats those away using raw JS clicks so the script doesn't hang.

Since normal scroll commands didn't trigger the data load, I'm injecting a JS snippet that finds every scrollable container and forces them down. This tricks React into fetching the next batch of rows.

It grabs text directly from the DOM, looks for affiliate codes (like `AFF001`), and maps out the five columns. It then deduplicates everything and sorts it by date.

## If things go wrong

If it's timing out, you might need to bump the timeout variables at the top of `scraper.py`.

In case it's not grabbing data, I set it up to take a screenshot (`failed_extraction.png`) if it can't find the table. Usually, this happens if a new popup appeared that I didn't account for.

I left the browser visible (`headless=False`). If you want to run it in the background, just flip that setting to `True` in the `main()` function.

