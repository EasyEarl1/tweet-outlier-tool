"""
Database models and operations for the Tweet Outlier Tool
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta
import os

Base = declarative_base()


class Account(Base):
    """Twitter account to monitor"""
    __tablename__ = 'accounts'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(200))
    follower_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)
    last_fetched_at = Column(DateTime, nullable=True)
    
    tweets = relationship("Tweet", back_populates="account", cascade="all, delete-orphan")


class Tweet(Base):
    """Individual tweet data"""
    __tablename__ = 'tweets'
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False, index=True)
    tweet_id = Column(String(50), unique=True, nullable=False, index=True)
    text = Column(Text)
    created_at = Column(DateTime, nullable=False, index=True)
    
    # Engagement metrics
    likes = Column(Integer, default=0)
    retweets = Column(Integer, default=0)
    replies = Column(Integer, default=0)
    views = Column(Integer, default=0)
    
    # Calculated fields
    total_engagement = Column(Float, default=0.0)
    outlier_multiplier = Column(Float, default=0.0)
    is_outlier = Column(Integer, default=0)  # 0 = no, 1 = yes
    
    # Metadata
    fetched_at = Column(DateTime, default=datetime.utcnow)
    
    account = relationship("Account", back_populates="tweets")


class Database:
    """Database manager"""
    
    def __init__(self, db_path='tweet_outlier.db'):
        self.db_path = db_path
        # Check if we're on Vercel (multiple ways to detect)
        # Vercel uses /var/task for serverless functions - check both file path and cwd
        try:
            file_path = os.path.abspath(__file__) if '__file__' in globals() else ''
        except:
            file_path = ''
        cwd = os.getcwd()
        
        is_vercel = (
            os.environ.get('VERCEL') == '1' or 
            os.environ.get('VERCEL_ENV') or 
            os.environ.get('NOW_REGION') or
            '/var/task' in file_path or
            '/var/task' in cwd
        )
        
        # On Vercel, use in-memory database by default (file-based SQLite doesn't work reliably)
        if is_vercel:
            connection_string = 'sqlite:///:memory:'
            print("Using in-memory database on Vercel (data won't persist between requests)")
            self.engine = create_engine(connection_string, echo=False, connect_args={'check_same_thread': False})
            Base.metadata.create_all(self.engine)
            self._ensure_columns()
            self.Session = sessionmaker(bind=self.engine)
        else:
            # Local development - try file-based database first, fall back to in-memory if it fails
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.getcwd(), db_path)
            connection_string = f'sqlite:///{db_path}'
            
            try:
                self.engine = create_engine(connection_string, echo=False, connect_args={'check_same_thread': False})
                Base.metadata.create_all(self.engine)
                self._ensure_columns()
                self.Session = sessionmaker(bind=self.engine)
            except Exception as e:
                # If file-based fails (e.g., on Vercel or read-only filesystem), use in-memory
                print(f"File-based database failed ({e}), falling back to in-memory database")
                connection_string = 'sqlite:///:memory:'
                self.engine = create_engine(connection_string, echo=False, connect_args={'check_same_thread': False})
                Base.metadata.create_all(self.engine)
                self._ensure_columns()
                self.Session = sessionmaker(bind=self.engine)

    def _ensure_columns(self):
        """
        Ensure new columns exist in existing databases.
        Currently adds last_fetched_at to accounts if missing.
        """
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(self.engine)
            # Check if accounts table exists
            if 'accounts' in inspector.get_table_names():
                account_columns = [col['name'] for col in inspector.get_columns('accounts')]
                if 'last_fetched_at' not in account_columns:
                    with self.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE accounts ADD COLUMN last_fetched_at DATETIME'))
                        conn.commit()
        except Exception as e:
            # If table doesn't exist yet, that's fine - it will be created by Base.metadata.create_all
            # Just log and continue
            pass
    
    def get_session(self):
        """Get a new database session"""
        return self.Session()
    
    def add_account(self, username, display_name=None, follower_count=0):
        """Add or update an account"""
        session = self.get_session()
        try:
            account = session.query(Account).filter_by(username=username).first()
            if account:
                account.display_name = display_name or account.display_name
                account.follower_count = follower_count or account.follower_count
                account.last_updated = datetime.utcnow()
            else:
                account = Account(
                    username=username,
                    display_name=display_name,
                    follower_count=follower_count
                )
                session.add(account)
            session.commit()
            return account
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_all_accounts(self):
        """Get all accounts"""
        session = self.get_session()
        try:
            return session.query(Account).all()
        finally:
            session.close()
    
    def get_account(self, username):
        """Get account by username"""
        session = self.get_session()
        try:
            return session.query(Account).filter_by(username=username).first()
        finally:
            session.close()
    
    def add_tweet(self, account_id, tweet_id, text, created_at, likes=0, retweets=0, replies=0, views=0):
        """Add or update a tweet"""
        session = self.get_session()
        try:
            tweet = session.query(Tweet).filter_by(tweet_id=tweet_id).first()
            if tweet:
                tweet.likes = likes
                tweet.retweets = retweets
                tweet.replies = replies
                tweet.views = views
                tweet.text = text
                tweet.fetched_at = datetime.utcnow()
            else:
                tweet = Tweet(
                    account_id=account_id,
                    tweet_id=tweet_id,
                    text=text,
                    created_at=created_at,
                    likes=likes,
                    retweets=retweets,
                    replies=replies,
                    views=views
                )
                session.add(tweet)
            session.commit()
            return tweet
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def bulk_add_tweets(self, tweets_data):
        """
        Bulk add/update tweets for better performance
        
        Args:
            tweets_data: List of dicts with tweet data
        """
        if not tweets_data:
            return 0, 0
        
        session = self.get_session()
        try:
            # Filter out tweets with invalid tweet_ids
            valid_tweets = [t for t in tweets_data if t.get('tweet_id') and str(t['tweet_id']).strip()]
            
            if not valid_tweets:
                return 0, 0
            
            # Get existing tweet IDs
            tweet_ids = [t['tweet_id'] for t in valid_tweets]
            existing_tweets = {}
            if tweet_ids:
                existing_tweets = {t.tweet_id: t for t in session.query(Tweet).filter(Tweet.tweet_id.in_(tweet_ids)).all()}
            
            tweets_to_add = []
            tweets_to_update = []
            
            for tweet_data in valid_tweets:
                tweet_id = str(tweet_data['tweet_id']).strip()
                if not tweet_id:
                    continue
                    
                if tweet_id in existing_tweets:
                    # Update existing
                    tweet = existing_tweets[tweet_id]
                    tweet.likes = tweet_data.get('likes', 0)
                    tweet.retweets = tweet_data.get('retweets', 0)
                    tweet.replies = tweet_data.get('replies', 0)
                    tweet.views = tweet_data.get('views', 0)
                    tweet.text = tweet_data.get('text', '')
                    tweet.fetched_at = datetime.utcnow()
                    tweets_to_update.append(tweet)
                else:
                    # Add new
                    tweets_to_add.append(Tweet(
                        account_id=tweet_data['account_id'],
                        tweet_id=tweet_id,
                        text=tweet_data.get('text', ''),
                        created_at=tweet_data.get('created_at', datetime.utcnow()),
                        likes=tweet_data.get('likes', 0),
                        retweets=tweet_data.get('retweets', 0),
                        replies=tweet_data.get('replies', 0),
                        views=tweet_data.get('views', 0)
                    ))
            
            if tweets_to_add:
                # Use add_all instead of bulk_save_objects for better error handling and relationship support
                session.add_all(tweets_to_add)
            if tweets_to_update:
                # Updates are already tracked by the session, just need to commit
                pass
            session.commit()
            return len(tweets_to_add), len(tweets_to_update)
        except Exception as e:
            session.rollback()
            # Log the error with full traceback for debugging
            import traceback
            error_msg = f"Bulk add tweets error: {str(e)}"
            # Only print full traceback if it's not too long
            full_traceback = traceback.format_exc()
            if len(full_traceback) < 2000:
                print(f"{error_msg}\n{full_traceback}")
            else:
                print(f"{error_msg}\n{traceback.format_exc()[:2000]}... (truncated)")
            # Re-raise with a cleaner message
            raise Exception(f"Failed to bulk add tweets: {str(e)[:200]}") from e
        finally:
            session.close()
    
    def bulk_update_outliers(self, updates):
        """
        Bulk update outlier calculations for better performance
        
        Args:
            updates: List of dicts with tweet_id, outlier_multiplier, is_outlier, total_engagement
        """
        session = self.get_session()
        try:
            tweet_ids = [u['tweet_id'] for u in updates]
            tweets = {t.tweet_id: t for t in session.query(Tweet).filter(Tweet.tweet_id.in_(tweet_ids)).all()}
            
            for update in updates:
                tweet_id = update['tweet_id']
                if tweet_id in tweets:
                    tweet = tweets[tweet_id]
                    tweet.outlier_multiplier = update.get('outlier_multiplier', 0.0)
                    tweet.is_outlier = 1 if update.get('is_outlier', False) else 0
                    if 'total_engagement' in update:
                        tweet.total_engagement = update['total_engagement']
            
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_tweets_by_account(self, account_id, start_date=None, end_date=None):
        """Get tweets for an account within date range"""
        session = self.get_session()
        try:
            query = session.query(Tweet).filter_by(account_id=account_id)
            if start_date:
                query = query.filter(Tweet.created_at >= start_date)
            if end_date:
                query = query.filter(Tweet.created_at <= end_date)
            return query.order_by(Tweet.created_at.desc()).all()
        finally:
            session.close()
    
    def update_tweet_outlier(self, tweet_id, outlier_multiplier, is_outlier, total_engagement=None):
        """Update outlier calculation for a tweet"""
        session = self.get_session()
        try:
            tweet = session.query(Tweet).filter_by(tweet_id=tweet_id).first()
            if tweet:
                tweet.outlier_multiplier = outlier_multiplier
                tweet.is_outlier = 1 if is_outlier else 0
                if total_engagement is not None:
                    tweet.total_engagement = total_engagement
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_outlier_tweets(self, min_multiplier=2.0, limit=100, include_all=False):
        """
        Get outlier tweets sorted by multiplier
        
        Args:
            min_multiplier: Minimum multiplier threshold
            limit: Maximum number of results
            include_all: If True, return all tweets (not just outliers)
        """
        from sqlalchemy.orm import joinedload
        session = self.get_session()
        try:
            query = session.query(Tweet).options(joinedload(Tweet.account))
            
            if include_all:
                # Get all tweets, not just outliers
                query = query.filter(Tweet.outlier_multiplier >= min_multiplier)
            else:
                # Only get tweets marked as outliers
                query = query.filter(
                    Tweet.is_outlier == 1,
                    Tweet.outlier_multiplier >= min_multiplier
                )
            
            return query.order_by(Tweet.outlier_multiplier.desc()).limit(limit).all()
        finally:
            session.close()
    
    def get_all_tweets_with_multipliers(self, account_id=None, min_multiplier=None, max_multiplier=None, limit=500, days_back=None, sort_by='multiplier'):
        """
        Get all tweets with their multipliers, optionally filtered
        
        Args:
            account_id: Filter by account ID
            min_multiplier: Minimum multiplier threshold
            max_multiplier: Maximum multiplier threshold
            limit: Maximum number of results
            days_back: Filter tweets from last N days (None = all time)
            sort_by: Sort by 'multiplier' (default) or 'date' (newest first)
        """
        from sqlalchemy.orm import joinedload
        session = self.get_session()
        try:
            query = session.query(Tweet).options(joinedload(Tweet.account))
            
            if account_id:
                query = query.filter(Tweet.account_id == account_id)
            
            if min_multiplier is not None:
                query = query.filter(Tweet.outlier_multiplier >= min_multiplier)
            
            if max_multiplier is not None:
                query = query.filter(Tweet.outlier_multiplier <= max_multiplier)
            
            # Filter by date range
            if days_back is not None:
                cutoff_date = datetime.utcnow() - timedelta(days=days_back)
                query = query.filter(Tweet.created_at >= cutoff_date)
            
            # Sort by multiplier or date
            if sort_by == 'date':
                query = query.order_by(Tweet.created_at.desc())
            else:
                query = query.order_by(Tweet.outlier_multiplier.desc())
            
            return query.limit(limit).all()
        finally:
            session.close()
    
    def get_newest_tweets(self, account_id=None, limit=500, days_back=None):
        """Get newest tweets across all accounts, optionally filtered by account and date"""
        from sqlalchemy.orm import joinedload
        session = self.get_session()
        try:
            query = session.query(Tweet).options(joinedload(Tweet.account))
            
            if account_id:
                query = query.filter(Tweet.account_id == account_id)
            
            if days_back is not None:
                cutoff_date = datetime.utcnow() - timedelta(days=days_back)
                query = query.filter(Tweet.created_at >= cutoff_date)
            
            return query.order_by(Tweet.created_at.desc()).limit(limit).all()
        finally:
            session.close()

