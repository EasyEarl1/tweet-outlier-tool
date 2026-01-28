"""
Twitter API integration using twitterapi.io for fetching tweets and engagement metrics
"""
import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import time

load_dotenv()


class TwitterAPI:
    """Twitter API client wrapper using twitterapi.io"""
    
    BASE_URL = "https://api.twitterapi.io"
    
    def __init__(self):
        self.api_key = os.getenv('TWITTER_API_KEY')
        if not self.api_key:
            raise ValueError("TWITTER_API_KEY not found in environment variables")
        
        self.headers = {
            'X-API-Key': self.api_key
        }
    
    def get_user_by_username(self, username):
        """
        Get user information by username using twitterapi.io
        
        Args:
            username: Twitter username (with or without @)
        
        Returns:
            User data dict or None
        """
        try:
            # Remove @ if present
            username = username.lstrip('@')
            
            url = f"{self.BASE_URL}/twitter/user_about"
            params = {'userName': username}
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success' and 'data' in data:
                    user_data = data['data']
                    # Convert to a format similar to what we expect
                    return {
                        'id': user_data.get('id'),
                        'username': user_data.get('userName'),
                        'name': user_data.get('name'),
                        'followers_count': 0  # Not available in this endpoint
                    }
                else:
                    return None
            elif response.status_code == 404:
                return None
            else:
                print(f"Error fetching user {username}: HTTP {response.status_code}")
                return None
        
        except requests.exceptions.RequestException as e:
            print(f"Error fetching user {username}: {e}")
            return None
        except Exception as e:
            print(f"Error fetching user {username}: {e}")
            return None
    
    def get_user_tweets(self, username, max_results=100):
        """
        Get tweets for a user using twitterapi.io
        
        Args:
            username: Twitter username (with or without @)
            max_results: Maximum number of tweets to fetch
        
        Returns:
            List of tweet dicts
        """
        tweets = []
        
        try:
            # Remove @ if present
            username = username.lstrip('@')
            
            url = f"{self.BASE_URL}/twitter/user/last_tweets"
            params = {'userName': username}
            # Request more tweets - try count parameter
            params['count'] = min(max_results, 100)  # Request up to 100 per API call
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success' and 'data' in data:
                    data_obj = data['data']
                    # The API returns data as a dict with 'tweets' key containing the list
                    if isinstance(data_obj, dict) and 'tweets' in data_obj:
                        tweet_list = data_obj['tweets']
                        if isinstance(tweet_list, list):
                            tweets = tweet_list[:max_results]
                            
                            # Check if there's pagination available
                            has_next = data.get('has_next_page', False)
                            next_cursor = data.get('next_cursor')
                            
                            # If we need more tweets and pagination is available, fetch more pages
                            page_count = 1
                            while len(tweets) < max_results and has_next and next_cursor and page_count < 10:  # Limit to 10 pages
                                params['cursor'] = next_cursor
                                next_response = requests.get(url, headers=self.headers, params=params, timeout=30)
                                if next_response.status_code == 200:
                                    next_data = next_response.json()
                                    if next_data.get('status') == 'success' and 'data' in next_data:
                                        next_data_obj = next_data['data']
                                        if isinstance(next_data_obj, dict) and 'tweets' in next_data_obj:
                                            next_tweet_list = next_data_obj['tweets']
                                            if isinstance(next_tweet_list, list) and len(next_tweet_list) > 0:
                                                remaining = max_results - len(tweets)
                                                tweets.extend(next_tweet_list[:remaining])
                                                has_next = next_data.get('has_next_page', False)
                                                next_cursor = next_data.get('next_cursor')
                                                page_count += 1
                                            else:
                                                break
                                        else:
                                            break
                                    else:
                                        break
                                else:
                                    break
                        else:
                            tweets = []
                    elif isinstance(data_obj, list):
                        # Fallback: if data is directly a list
                        tweets = data_obj[:max_results]
                    else:
                        tweets = []
                else:
                    print(f"No tweets found for {username} (response: {data.get('msg', 'unknown')})")
            elif response.status_code == 404:
                print(f"User {username} not found")
            else:
                print(f"Error fetching tweets for {username}: HTTP {response.status_code}")
                if response.status_code == 429:
                    print("Rate limit exceeded. Waiting 60 seconds...")
                    time.sleep(60)
        
        except requests.exceptions.RequestException as e:
            print(f"Error fetching tweets for {username}: {e}")
        except Exception as e:
            print(f"Error fetching tweets for {username}: {e}")
        
        return tweets
    
    def fetch_account_tweets(self, username, months_back=3):
        """
        Fetch tweets for an account over the specified number of months
        
        Args:
            username: Twitter username (with or without @)
            months_back: Number of months to look back (1-6)
        
        Returns:
            Tuple of (user_data, list_of_tweets)
        """
        # Get user info
        user = self.get_user_by_username(username)
        if not user:
            return None, []
        
        # Fetch tweets - default to 100 per account
        tweets = self.get_user_tweets(username, max_results=100)
        
        # Filter tweets by date range
        # Make end_time timezone-aware for comparison
        from datetime import timezone
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=months_back * 30)
        
        filtered_tweets = []
        for tweet in tweets:
            tweet_date = self._parse_tweet_date(tweet)
            if tweet_date:
                # Make sure tweet_date is timezone-aware
                if tweet_date.tzinfo is None:
                    tweet_date = tweet_date.replace(tzinfo=timezone.utc)
                # Convert to UTC if it has a timezone
                if tweet_date.tzinfo is not None:
                    tweet_date = tweet_date.astimezone(timezone.utc)
                
                if start_time <= tweet_date <= end_time:
                    filtered_tweets.append(tweet)
        
        return user, filtered_tweets
    
    def _parse_tweet_date(self, tweet):
        """Parse tweet date from various possible formats"""
        try:
            # Try different date field names
            date_str = tweet.get('createdAt') or tweet.get('created_at') or tweet.get('date')
            if not date_str:
                return None
            
            # Try parsing ISO format first
            try:
                # Handle ISO format with Z
                if date_str.endswith('Z'):
                    date_str = date_str.replace('Z', '+00:00')
                return datetime.fromisoformat(date_str)
            except:
                pass
            
            # Try parsing Twitter format: "Mon Dec 29 04:31:10 +0000 2025"
            try:
                return datetime.strptime(date_str, '%a %b %d %H:%M:%S %z %Y')
            except:
                pass
            
            # Try other formats
            formats = [
                '%Y-%m-%dT%H:%M:%S.%fZ',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%d %H:%M:%S',
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
            
            return None
        except:
            return None
    
    def parse_tweet_metrics(self, tweet):
        """
        Extract engagement metrics from a tweet dict
        
        Args:
            tweet: Tweet dict from twitterapi.io
        
        Returns:
            Dict with tweet metrics
        """
        # Handle different possible field names in the response
        tweet_id = tweet.get('id') or tweet.get('tweetId') or tweet.get('tweet_id')
        text = tweet.get('text') or tweet.get('content') or tweet.get('fullText') or ''
        
        # Engagement metrics - TwitterAPI.io uses camelCase
        likes = tweet.get('likeCount') or tweet.get('likes') or tweet.get('favorite_count') or 0
        retweets = tweet.get('retweetCount') or tweet.get('retweets') or tweet.get('retweet_count') or 0
        replies = tweet.get('replyCount') or tweet.get('replies') or tweet.get('reply_count') or 0
        views = tweet.get('viewCount') or tweet.get('views') or tweet.get('impression_count') or 0
        
        # Parse date
        created_at = self._parse_tweet_date(tweet)
        if not created_at:
            # Default to now if we can't parse
            created_at = datetime.utcnow()
        
        return {
            'tweet_id': str(tweet_id) if tweet_id else '',
            'text': text,
            'created_at': created_at,
            'likes': int(likes) if likes else 0,
            'retweets': int(retweets) if retweets else 0,
            'replies': int(replies) if replies else 0,
            'views': int(views) if views else 0
        }
