"""
Data fetcher to collect tweets from all accounts in the database
"""
from database import Database
from twitter_api import TwitterAPI
from datetime import datetime, timedelta, timezone
import time


class DataFetcher:
    """Fetch and store tweet data for all accounts"""
    
    def __init__(self, db, twitter_api):
        self.db = db
        self.twitter_api = twitter_api
    
    def fetch_account_data(self, username, months_back=3, update_existing=True, days_back=None):
        """
        Fetch tweets for a single account and store in database
        
        Args:
            username: Twitter username
            months_back: Number of months to fetch (1-6)
            update_existing: Whether to update existing tweets
            days_back: If specified, only fetch tweets from last N days (overrides months_back)
        
        Returns:
            Tuple of (success, tweets_fetched, error_message)
        """
        try:
            # Get or create account
            account = self.db.get_account(username)
            if not account:
                # Fetch user info first
                user_data = self.twitter_api.get_user_by_username(username)
                if not user_data:
                    return False, 0, f"Account @{username} not found"
                
                account = self.db.add_account(
                    username=username,
                    display_name=user_data.get('name'),
                    follower_count=user_data.get('followers_count', 0)
                )
            
            # Fetch tweets - use days_back if specified, otherwise use months_back
            if days_back:
                # Convert days to approximate months for API call
                months_back = max(1, days_back // 30)
            user_data, tweets = self.twitter_api.fetch_account_tweets(username, months_back)
            
            # If days_back is specified, filter tweets to that range
            if days_back:
                cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
                tweets = [t for t in tweets if self.twitter_api._parse_tweet_date(t) and 
                         self.twitter_api._parse_tweet_date(t) >= cutoff]
            
            if not tweets:
                return True, 0, None  # No tweets found, but not an error
            
            # Store tweets using bulk operation for better performance
            tweets_to_store = []
            for tweet_data in tweets:
                try:
                    metrics = self.twitter_api.parse_tweet_metrics(tweet_data)
                    # Only add if tweet_id is valid
                    tweet_id = metrics.get('tweet_id')
                    if tweet_id and str(tweet_id).strip():
                        # Ensure created_at is a datetime object
                        created_at = metrics.get('created_at')
                        if not isinstance(created_at, datetime):
                            created_at = datetime.utcnow()
                        
                        tweets_to_store.append({
                            'account_id': account.id,
                            'tweet_id': str(tweet_id).strip(),
                            'text': metrics.get('text', '') or '',
                            'created_at': created_at,
                            'likes': int(metrics.get('likes', 0) or 0),
                            'retweets': int(metrics.get('retweets', 0) or 0),
                            'replies': int(metrics.get('replies', 0) or 0),
                            'views': int(metrics.get('views', 0) or 0)
                        })
                except Exception as e:
                    # Skip tweets that can't be parsed
                    error_msg = str(e)
                    if len(error_msg) > 200:
                        error_msg = error_msg[:200] + "..."
                    print(f"Warning: Skipping tweet due to parse error: {error_msg}")
                    continue
            
            # Bulk insert/update tweets
            if tweets_to_store:
                try:
                    added, updated = self.db.bulk_add_tweets(tweets_to_store)
                    tweets_stored = added + updated
                except Exception as e:
                    # Fallback to individual inserts if bulk fails
                    error_msg = str(e)
                    # Truncate very long error messages
                    if len(error_msg) > 500:
                        error_msg = error_msg[:500] + "... (truncated)"
                    print(f"Warning: Bulk insert failed, falling back to individual inserts: {error_msg}")
                    tweets_stored = 0
                    for tweet_data in tweets_to_store:
                        try:
                            self.db.add_tweet(
                                account_id=tweet_data['account_id'],
                                tweet_id=tweet_data['tweet_id'],
                                text=tweet_data.get('text', ''),
                                created_at=tweet_data.get('created_at', datetime.utcnow()),
                                likes=tweet_data.get('likes', 0),
                                retweets=tweet_data.get('retweets', 0),
                                replies=tweet_data.get('replies', 0),
                                views=tweet_data.get('views', 0)
                            )
                            tweets_stored += 1
                        except Exception as e2:
                            error_msg2 = str(e2)
                            if len(error_msg2) > 200:
                                error_msg2 = error_msg2[:200] + "..."
                            print(f"Warning: Failed to add tweet {tweet_data.get('tweet_id', 'unknown')}: {error_msg2}")
                            continue
            else:
                tweets_stored = 0
            
            # Update account info
            if user_data:
                # Re-fetch account to get latest from DB
                account = self.db.get_account(username)
                if account:
                    session = self.db.get_session()
                    try:
                        from database import Account
                        account_obj = session.query(Account).filter_by(id=account.id).first()
                        if account_obj:
                            account_obj.display_name = user_data.get('name') or account_obj.display_name
                            account_obj.follower_count = user_data.get('followers_count', account_obj.follower_count)
                            account_obj.last_updated = datetime.utcnow()
                            account_obj.last_fetched_at = datetime.utcnow()
                            session.commit()
                    finally:
                        session.close()
            
            return True, tweets_stored, None
        
        except Exception as e:
            return False, 0, str(e)
    
    def fetch_all_accounts(self, months_back=3, delay_between_accounts=2, min_days_between_fetch=1, days_back=None):
        """
        Fetch tweets for all accounts in the database
        
        Args:
            months_back: Number of months to fetch (1-6)
            delay_between_accounts: Seconds to wait between accounts (to avoid rate limits)
            min_days_between_fetch: Minimum days since last fetch to skip
            days_back: If specified, only fetch tweets from last N days (overrides months_back for filtering)
        
        Returns:
            Dict with summary statistics
        """
        accounts = self.db.get_all_accounts()
        total_accounts = len(accounts)
        
        if total_accounts == 0:
            return {
                'total_accounts': 0,
                'successful': 0,
                'failed': 0,
                'total_tweets': 0,
                'errors': []
            }
        
        successful = 0
        failed = 0
        skipped = 0
        total_tweets = 0
        errors = []
        
        print(f"\nFetching data for {total_accounts} accounts...")
        print(f"Time range: Last {months_back} months\n")
        
        cutoff = datetime.utcnow() - timedelta(days=min_days_between_fetch) if min_days_between_fetch is not None else None

        for idx, account in enumerate(accounts, 1):
            print(f"[{idx}/{total_accounts}] Fetching @{account.username}...", end=' ', flush=True)

            # Skip if recently fetched
            if cutoff and account.last_fetched_at and account.last_fetched_at >= cutoff:
                skipped += 1
                print(f"[SKIP] fetched recently ({account.last_fetched_at})")
                continue
            
            success, tweets_count, error = self.fetch_account_data(
                account.username,
                months_back,
                update_existing=True,
                days_back=days_back
            )
            
            if success:
                successful += 1
                total_tweets += tweets_count
                print(f"[OK] {tweets_count} tweets")
            else:
                failed += 1
                errors.append(f"@{account.username}: {error}")
                print(f"[FAIL] {error}")
            
            # Delay to avoid rate limits (except for last account)
            if idx < total_accounts:
                time.sleep(delay_between_accounts)
        
        return {
            'total_accounts': total_accounts,
            'successful': successful,
            'failed': failed,
            'skipped': skipped,
            'total_tweets': total_tweets,
            'errors': errors
        }

