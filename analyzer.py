"""
Analysis engine for calculating outlier multipliers
"""
from datetime import datetime, timedelta
from database import Database
import statistics


class TweetAnalyzer:
    """Analyze tweets and calculate outlier multipliers"""
    
    def __init__(self, db):
        self.db = db
    
    def calculate_engagement_score(self, likes, retweets, replies, views, weights=None):
        """
        Calculate weighted engagement score
        
        Args:
            likes: Number of likes
            retweets: Number of retweets
            replies: Number of replies
            views: Number of views
            weights: Dict with weights for each metric (default: equal weights)
        
        Returns:
            Engagement score
        """
        if weights is None:
            weights = {
                'likes': 1.0,
                'retweets': 2.0,  # Retweets are more valuable
                'replies': 3.0,   # Replies are most valuable
                'views': 0.1      # Views are less valuable
            }
        
        # Normalize views (divide by 1000 to scale it down)
        normalized_views = views / 1000.0 if views > 0 else 0
        
        score = (
            likes * weights['likes'] +
            retweets * weights['retweets'] +
            replies * weights['replies'] +
            normalized_views * weights['views']
        )
        
        return score
    
    def calculate_account_average(self, account_id, months_back=3):
        """
        Calculate average engagement for an account over the specified period
        
        Returns:
            Dict with average metrics and average engagement score
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months_back * 30)
        
        tweets = self.db.get_tweets_by_account(account_id, start_date, end_date)
        
        if not tweets or len(tweets) == 0:
            return None
        
        # Calculate engagement scores for all tweets
        engagement_scores = []
        total_likes = 0
        total_retweets = 0
        total_replies = 0
        total_views = 0
        
        for tweet in tweets:
            score = self.calculate_engagement_score(
                tweet.likes,
                tweet.retweets,
                tweet.replies,
                tweet.views
            )
            engagement_scores.append(score)
            total_likes += tweet.likes
            total_retweets += tweet.retweets
            total_replies += tweet.replies
            total_views += tweet.views
        
        # Calculate averages
        avg_engagement = statistics.mean(engagement_scores) if engagement_scores else 0
        median_engagement = statistics.median(engagement_scores) if engagement_scores else 0
        
        # Ensure avg_engagement is never exactly 0 if there are tweets with engagement
        # This handles edge cases where most tweets have 0 engagement but some don't
        if avg_engagement == 0 and any(score > 0 for score in engagement_scores):
            # Use median instead, or minimum non-zero engagement
            non_zero_scores = [s for s in engagement_scores if s > 0]
            if non_zero_scores:
                avg_engagement = statistics.mean(non_zero_scores)
        
        return {
            'avg_engagement': avg_engagement,
            'median_engagement': median_engagement,
            'avg_likes': total_likes / len(tweets) if len(tweets) > 0 else 0,
            'avg_retweets': total_retweets / len(tweets) if len(tweets) > 0 else 0,
            'avg_replies': total_replies / len(tweets) if len(tweets) > 0 else 0,
            'avg_views': total_views / len(tweets) if len(tweets) > 0 else 0,
            'tweet_count': len(tweets)
        }
    
    def calculate_outlier_multiplier(self, tweet, account_avg):
        """
        Calculate how many times better a tweet performed than the account average
        
        Args:
            tweet: Tweet object
            account_avg: Average engagement dict from calculate_account_average
        
        Returns:
            Outlier multiplier (e.g., 2.5 means 2.5x better than average)
        """
        if not account_avg:
            return 0.0
        
        tweet_engagement = self.calculate_engagement_score(
            tweet.likes,
            tweet.retweets,
            tweet.replies,
            tweet.views
        )
        
        # If average is 0, but tweet has engagement, return a high multiplier
        # This handles edge cases where account just started or has very low engagement
        if account_avg['avg_engagement'] == 0:
            if tweet_engagement > 0:
                # If this is the only tweet or all others have 0 engagement, return 1.0x
                return 1.0
            else:
                return 0.0
        
        multiplier = tweet_engagement / account_avg['avg_engagement']
        return multiplier
    
    def analyze_account(self, account_id, months_back=3, outlier_threshold=2.0):
        """
        Analyze all tweets for an account and calculate outlier multipliers
        
        Args:
            account_id: Account ID to analyze
            months_back: Number of months to analyze
            outlier_threshold: Minimum multiplier to be considered an outlier
        
        Returns:
            Dict with analysis results
        """
        # Calculate account average
        account_avg = self.calculate_account_average(account_id, months_back)
        
        if not account_avg:
            return {
                'account_id': account_id,
                'error': 'No tweets found for this account',
                'outliers': []
            }
        
        # Get all tweets in the period
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months_back * 30)
        tweets = self.db.get_tweets_by_account(account_id, start_date, end_date)
        
        outliers = []
        updates = []  # Batch updates for better performance
        
        for tweet in tweets:
            # Calculate total engagement first
            total_engagement = self.calculate_engagement_score(
                tweet.likes, tweet.retweets, tweet.replies, tweet.views
            )
            
            # Calculate multiplier
            multiplier = self.calculate_outlier_multiplier(tweet, account_avg)
            
            # is_outlier flag is still used for filtering, but all tweets get multipliers
            is_outlier = multiplier >= outlier_threshold
            
            # Collect updates for bulk processing
            updates.append({
                'tweet_id': tweet.tweet_id,
                'outlier_multiplier': multiplier,
                'is_outlier': is_outlier,
                'total_engagement': total_engagement
            })
            
            if is_outlier:
                outliers.append({
                    'tweet_id': tweet.tweet_id,
                    'text': tweet.text[:100] + '...' if len(tweet.text) > 100 else tweet.text,
                    'multiplier': multiplier,
                    'likes': tweet.likes,
                    'retweets': tweet.retweets,
                    'replies': tweet.replies,
                    'views': tweet.views,
                    'created_at': tweet.created_at
                })
        
        # Bulk update all tweets at once
        if updates:
            self.db.bulk_update_outliers(updates)
        
        return {
            'account_id': account_id,
            'account_avg': account_avg,
            'outliers': sorted(outliers, key=lambda x: x['multiplier'], reverse=True),
            'total_tweets': len(tweets),
            'outlier_count': len(outliers)
        }
    
    def analyze_all_accounts(self, months_back=3, outlier_threshold=2.0):
        """
        Analyze all accounts in the database
        
        Returns:
            List of analysis results for each account
        """
        accounts = self.db.get_all_accounts()
        results = []
        
        for account in accounts:
            print(f"Analyzing @{account.username}...")
            result = self.analyze_account(account.id, months_back, outlier_threshold)
            result['username'] = account.username
            results.append(result)
        
        return results

