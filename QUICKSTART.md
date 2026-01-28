# Quick Start Guide

Get up and running with the Tweet Outlier Tool in 5 minutes!

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Get TwitterAPI.io API Key

1. Go to https://twitterapi.io
2. Sign up for an account
3. Get your API key from the dashboard
4. Copy the API key

## Step 3: Configure

Create a `.env` file in the project root:

```
TWITTER_API_KEY=your_api_key_here
```

## Step 4: Import Accounts

Create a text file `accounts.txt` with one username per line:

```
elonmusk
jack
naval
```

Or use a CSV file `accounts.csv`:

```csv
username,display_name
elonmusk,Elon Musk
jack,Jack Dorsey
```

Then import:

```bash
python main.py import-accounts accounts.txt
```

## Step 5: Fetch Data

This will fetch tweets for all accounts (may take a while):

```bash
python main.py fetch --months 3
```

## Step 6: Analyze

Find outliers:

```bash
python main.py analyze --months 3 --threshold 2.0
```

This shows tweets that performed 2x better than the account's average.

## Common Commands

```bash
# List all accounts
python main.py list-accounts

# View statistics
python main.py stats

# Analyze specific account
python main.py analyze --account elonmusk --months 3

# Fetch with different time range
python main.py fetch --months 6
```

## Tips

- Start with 1-2 months for faster results
- Use `--threshold 2.0` for 2x outliers, `--threshold 3.0` for 3x outliers
- The database saves everything, so you can analyze multiple times without refetching
- For 500+ accounts, fetching may take several hours due to API rate limits

