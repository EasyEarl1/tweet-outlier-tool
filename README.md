# Tweet Outlier Tool

A powerful tool to identify tweets that significantly outperformed the average engagement for Twitter accounts. Perfect for analyzing what content resonates most with your audience.

## Features

- **Bulk Account Import**: Import 500+ Twitter accounts from CSV or TXT files
- **Persistent Database**: SQLite database saves all data so you don't need to refetch every time
- **Comprehensive Engagement Analysis**: Considers likes, retweets, replies, and views
- **Outlier Multiplier**: Calculates how many times better a tweet performed than the account's average
- **Flexible Time Frames**: Analyze tweets from 1-6 months back
- **Relative Comparison**: Compares against each account's own average, not global averages
- **Web UI**: Beautiful, interactive dashboard to view and filter outliers

## Installation

1. **Clone or download this repository**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Twitter API credentials**:
   - Get an API key from [TwitterAPI.io](https://twitterapi.io)
   - Copy `env_example.txt` to `.env`
   - Add your API key to `.env`:
     ```
     TWITTER_API_KEY=your_actual_api_key_here
     ```

## Usage

### 1. Import Accounts

Import accounts from a CSV or text file:

**CSV Format** (`accounts.csv`):
```csv
username,display_name,follower_count
elonmusk,Elon Musk,150000000
jack,Jack Dorsey,5000000
```

**Text Format** (`accounts.txt`):
```
elonmusk
jack
@naval
```

**Command**:
```bash
python main.py import-accounts accounts.csv
# or
python main.py import-accounts accounts.txt
```

### 2. Fetch Tweet Data

Fetch tweets for all accounts in your database:

```bash
python main.py fetch --months 3
```

Options:
- `--months`: Number of months to fetch (1-6, default: 3)
- `--delay`: Delay between accounts in seconds (default: 2)

### 3. Analyze Tweets

Analyze all accounts and find outliers:

```bash
python main.py analyze --months 3 --threshold 2.0
```

Options:
- `--months`: Number of months to analyze (1-6, default: 3)
- `--threshold`: Minimum multiplier to be considered an outlier (default: 2.0)
- `--account`: Analyze specific account only (e.g., `--account elonmusk`)

### 4. View Results

**List all accounts**:
```bash
python main.py list-accounts
```

**View database statistics**:
```bash
python main.py stats
```

### 5. View in Web UI

Launch the web interface for a better viewing experience:

```bash
python main.py web
# or directly:
python app.py
```

Then open your browser to `http://localhost:5000` to see:
- Interactive dashboard with statistics
- Filterable table of outliers
- Filter by account, minimum multiplier, and more
- Click through to view tweets on Twitter
- Beautiful, modern interface

## How It Works

1. **Engagement Score Calculation**: 
   - Each tweet gets a weighted engagement score
   - Weights: Likes (1x), Retweets (2x), Replies (3x), Views (0.1x per 1000)
   - This balances different engagement types appropriately

2. **Average Calculation**:
   - For each account, calculates the average engagement score across all tweets in the time period
   - Uses both mean and median for robust analysis

3. **Outlier Multiplier**:
   - Compares each tweet's engagement to the account's average
   - A multiplier of 2.5 means the tweet performed 2.5x better than average
   - Only tweets above the threshold are marked as outliers

4. **Relative Analysis**:
   - Each account is compared against its own average
   - This ensures fair comparison regardless of account size
   - A small account's 2x outlier is just as significant as a large account's 2x outlier

## Example Workflow

```bash
# 1. Import accounts
python main.py import-accounts my_accounts.csv

# 2. Fetch data (this may take a while for 500+ accounts)
python main.py fetch --months 3

# 3. Analyze and find outliers
python main.py analyze --months 3 --threshold 2.0

# 4. View top outliers
python main.py analyze  # Shows top outliers across all accounts
```

## Database

The tool uses SQLite and stores data in `tweet_outlier.db`. This file contains:
- All imported accounts
- All fetched tweets with engagement metrics
- Calculated outlier multipliers
- Analysis results

You can safely delete this file to start fresh, or keep it to build up historical data over time.

## Rate Limits and Pricing

TwitterAPI.io has generous rate limits (1000+ requests per second). The tool includes delays between requests to be respectful. For large account lists (500+), fetching may take some time. Pricing:
- $0.15 per 1,000 tweets
- $0.18 per 1,000 user profiles

The tool will:
- Automatically handle rate limits if encountered
- Add delays between account fetches
- Resume from where it left off if interrupted

## Tips

- Start with a smaller time frame (1-2 months) for faster initial analysis
- Use `--threshold 2.0` to find tweets that performed 2x better than average
- Lower thresholds (1.5x) will show more outliers but may include less significant ones
- Higher thresholds (3.0x+) will show only the most exceptional tweets
- The database persists, so you can fetch data once and analyze multiple times with different parameters

## Troubleshooting

**"TWITTER_API_KEY not found"**
- Make sure you've created a `.env` file with your API key from TwitterAPI.io

**"Account not found"**
- Check that the username is correct (without @)
- Some accounts may be private or suspended

**Rate limit errors**
- The tool handles this automatically, but you may need to wait
- Consider reducing the number of accounts or using longer delays

## License

MIT License - Feel free to use and modify as needed.

