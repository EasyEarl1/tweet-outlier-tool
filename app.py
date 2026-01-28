"""
Web UI for Tweet Outlier Tool
"""
from flask import Flask, render_template, jsonify, request
from database import Database
from twitter_api import TwitterAPI
from data_fetcher import DataFetcher
from analyzer import TweetAnalyzer
from persistence import AccountPersistence
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Initialize database with error handling for Vercel
try:
    # Database class will handle Vercel-specific path logic
    db = Database()
except Exception as e:
    # On Vercel, if database init fails, allow app to start anyway
    # This prevents the entire app from crashing
    import traceback
    error_msg = f"Warning: Database initialization failed: {e}"
    print(error_msg)
    # Print full traceback for debugging in Vercel logs
    traceback.print_exc()
    db = None

# Initialize persistent storage for accounts
persistence = AccountPersistence()


@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


@app.route('/api/outliers')
def get_outliers():
    """Get outlier tweets with filters"""
    if db is None:
        return jsonify({'success': True, 'outliers': [], 'count': 0})
    
    try:
        min_multiplier = request.args.get('min_multiplier', None)
        max_multiplier = request.args.get('max_multiplier', None)
        account_filter = request.args.get('account', None)
        limit = int(request.args.get('limit', 100))
        show_all = request.args.get('show_all', 'false').lower() == 'true'
        days_back = request.args.get('days_back', None)
        sort_by = request.args.get('sort_by', 'multiplier')  # 'multiplier' or 'date'
        
        # Parse days_back
        days = int(days_back) if days_back else None
        
        # Parse multipliers (allow negative/zero for negative outliers)
        min_mult = float(min_multiplier) if min_multiplier else None
        max_mult = float(max_multiplier) if max_multiplier else None
        
        # If no min_multiplier specified and not showing all, default to 2.0 for positive outliers
        if min_mult is None and not show_all:
            min_mult = 2.0
        
        # Get tweets - use get_all_tweets_with_multipliers to get all tweets with multipliers
        if show_all or min_mult is not None or max_mult is not None:
            # Get all tweets with multipliers (not just outliers)
            account_id = None
            if account_filter:
                try:
                    account = db.get_account(account_filter)
                    account_id = account.id if account else None
                except:
                    account_id = None
            
            try:
                tweets = db.get_all_tweets_with_multipliers(
                    account_id=account_id,
                    min_multiplier=min_mult,
                    max_multiplier=max_mult,
                    limit=limit,
                    days_back=days,
                    sort_by=sort_by
                )
            except Exception as e:
                print(f"Error getting tweets: {e}")
                return jsonify({'success': True, 'outliers': [], 'count': 0})
        else:
            # Legacy: get only outliers
            try:
                tweets = db.get_outlier_tweets(min_multiplier=min_mult or 2.0, limit=limit)
                if account_filter:
                    tweets = [t for t in tweets if t.account.username == account_filter]
                # Apply date filter if specified
                if days:
                    from datetime import datetime, timedelta
                    cutoff = datetime.utcnow() - timedelta(days=days)
                    tweets = [t for t in tweets if t.created_at >= cutoff]
                # Sort by date if requested
                if sort_by == 'date':
                    tweets = sorted(tweets, key=lambda t: t.created_at, reverse=True)
            except Exception as e:
                print(f"Error getting outlier tweets: {e}")
                return jsonify({'success': True, 'outliers': [], 'count': 0})
        
        # Format for JSON
        result = []
        for tweet in tweets:
            result.append({
                'id': tweet.id,
                'tweet_id': tweet.tweet_id,
                'account': tweet.account.username,
                'account_display': tweet.account.display_name or tweet.account.username,
                'text': tweet.text or '',
                'multiplier': round(tweet.outlier_multiplier, 2) if tweet.outlier_multiplier else 0.0,
                'likes': tweet.likes,
                'retweets': tweet.retweets,
                'replies': tweet.replies,
                'views': tweet.views,
                'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                'engagement_score': round(tweet.total_engagement, 2) if tweet.total_engagement else 0.0,
                'is_outlier': bool(tweet.is_outlier)
            })
        
        return jsonify({
            'success': True,
            'outliers': result,
            'count': len(result)
        })
    except Exception as e:
        print(f"Error in get_outliers: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': True, 'outliers': [], 'count': 0})


@app.route('/api/accounts')
def get_accounts():
    """Get all accounts - merge from database and persistent storage"""
    if db is None:
        # If database not available, return accounts from persistent storage only
        try:
            persisted_accounts = persistence.get_all_accounts()
            result = []
            for acc in persisted_accounts:
                result.append({
                    'username': acc['username'],
                    'display_name': acc.get('display_name') or acc['username'],
                    'follower_count': acc.get('follower_count', 0),
                    'tweet_count': 0,
                    'outlier_count': 0,
                    'last_fetched_at': None
                })
            return jsonify({'success': True, 'accounts': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e), 'accounts': []}), 500
    
    try:
        # Get accounts from persistent storage
        persisted_accounts = {acc['username']: acc for acc in persistence.get_all_accounts()}
        
        # Get accounts from database (if available) and merge
        db_accounts = []
        try:
            accounts = db.get_all_accounts()
            for account in accounts:
                # Count tweets and outliers for this account
                try:
                    tweets = db.get_tweets_by_account(account.id)
                    outlier_count = sum(1 for t in tweets if t.is_outlier)
                except:
                    tweets = []
                    outlier_count = 0
                
                db_accounts.append({
                    'username': account.username,
                    'display_name': account.display_name or account.username,
                    'follower_count': account.follower_count,
                    'tweet_count': len(tweets),
                    'outlier_count': outlier_count,
                    'last_fetched_at': account.last_fetched_at.isoformat() if account.last_fetched_at else None
                })
        except Exception as e:
            print(f"Error getting accounts from database: {e}")
        
        # Merge: use DB data if available, otherwise use persisted data
        result = []
        all_usernames = set(persisted_accounts.keys()) | {acc['username'] for acc in db_accounts}
        
        for username in all_usernames:
            if username in [acc['username'] for acc in db_accounts]:
                # Prefer DB data (has outlier counts)
                result.append(next(acc for acc in db_accounts if acc['username'] == username))
            elif username in persisted_accounts:
                # Use persisted data
                acc = persisted_accounts[username]
                result.append({
                    'username': acc['username'],
                    'display_name': acc.get('display_name') or acc['username'],
                    'follower_count': acc.get('follower_count', 0),
                    'tweet_count': 0,
                    'outlier_count': 0,
                    'last_fetched_at': None
                })
        
        return jsonify({'success': True, 'accounts': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'accounts': []}), 500


@app.route('/api/stats')
def get_stats():
    """Get database statistics"""
    accounts = db.get_all_accounts()
    total_tweets = 0
    total_outliers = 0
    
    for account in accounts:
        tweets = db.get_tweets_by_account(account.id)
        total_tweets += len(tweets)
        total_outliers += sum(1 for t in tweets if t.is_outlier)
    
    return jsonify({
        'total_accounts': len(accounts),
        'total_tweets': total_tweets,
        'total_outliers': total_outliers
    })


@app.route('/api/accounts/add', methods=['POST'])
def add_accounts():
    """Add accounts from text input or file upload"""
    try:
        data = request.json
        accounts_text = data.get('accounts', '').strip()
        file_content = data.get('file_content', '')
        
        if not accounts_text and not file_content:
            return jsonify({'success': False, 'error': 'No accounts provided'}), 400
        
        # Use file content if provided, otherwise use text input
        content = file_content if file_content else accounts_text
        
        # Parse accounts (one per line, remove @, ignore empty lines and comments)
        accounts_to_add = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                username = line.lstrip('@')
                if username:
                    accounts_to_add.append(username)
        
        if not accounts_to_add:
            return jsonify({'success': False, 'error': 'No valid accounts found'}), 400
        
        # Add accounts
        added = 0
        errors = []
        for username in accounts_to_add:
            try:
                db.add_account(username)
                added += 1
            except Exception as e:
                errors.append(f"@{username}: {str(e)}")
        
        return jsonify({
            'success': True,
            'added': added,
            'errors': errors,
            'message': f'Successfully added {added} account(s)'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accounts/<username>', methods=['DELETE'])
def delete_account(username):
    """Delete an account"""
    try:
        # Remove from database if available
        if db is not None:
            try:
                account = db.get_account(username)
                if account:
                    session = db.get_session()
                    try:
                        session.delete(account)
                        session.commit()
                    finally:
                        session.close()
            except:
                pass  # Account might not exist in DB
        
        # Remove from persistent storage
        if persistence.remove_account(username):
            return jsonify({'success': True, 'message': f'Account @{username} deleted'})
        else:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accounts/list')
def list_persisted_accounts():
    """Get all accounts from persistent storage"""
    try:
        accounts = persistence.get_all_accounts()
        return jsonify({
            'success': True,
            'accounts': accounts,
            'count': len(accounts)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/settings/api-key', methods=['GET'])
def api_key_settings():
    """API key management - show instructions or check if set"""
    # Check if API key is set (don't expose the actual key)
    api_key_set = bool(os.environ.get('TWITTER_API_KEY'))
    return jsonify({
        'success': True,
        'api_key_set': api_key_set,
        'instructions': {
            'title': 'How to Add Your Twitter API Key',
            'steps': [
                '1. Go to your Vercel project dashboard',
                '2. Navigate to Settings → Environment Variables',
                '3. Click "Add New"',
                '4. Add variable:',
                '   - Key: TWITTER_API_KEY',
                '   - Value: Your API key from twitterapi.io',
                '   - Environment: Production, Preview, Development (select all)',
                '5. Click "Save"',
                '6. Redeploy your application'
            ],
            'note': 'Your API key is stored securely and never exposed in the code.'
        }
    })


@app.route('/api/fetch', methods=['POST'])
def fetch_tweets():
    """Fetch tweets for accounts"""
    try:
        data = request.json or {}
        months_back = int(data.get('months', 3))
        days_back = data.get('days', None)  # Optional: fetch only last N days (faster)
        account_filter = data.get('account', None)  # Optional: fetch for specific account
        min_days = data.get('min_days', 1)
        try:
            min_days = int(min_days) if min_days is not None else None
        except ValueError:
            min_days = 1
        
        # Convert days to int if provided
        if days_back is not None:
            try:
                days_back = int(days_back)
            except ValueError:
                days_back = None
        
        twitter_api = TwitterAPI()
        fetcher = DataFetcher(db, twitter_api)
        
        if account_filter:
            # Fetch for single account
            success, tweets_count, error = fetcher.fetch_account_data(
                account_filter, 
                months_back=months_back,
                days_back=days_back
            )
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Fetched {tweets_count} tweets for @{account_filter}',
                    'tweets_count': tweets_count
                })
            else:
                return jsonify({'success': False, 'error': error}), 400
        else:
            # Fetch for all accounts
            # If days_back is specified, use it for faster fetching
            if days_back:
                # For quick fetch, set months_back to approximate days (but we'll filter by days_back)
                months_back = max(1, days_back // 30)
            
            results = fetcher.fetch_all_accounts(
                months_back=months_back,
                delay_between_accounts=2,
                min_days_between_fetch=min_days,
                days_back=days_back
            )
            
            # If days_back was specified, filter results message
            if days_back:
                message = f'Quick fetched {results["total_tweets"]} tweets from last {days_back} days from {results["successful"]} accounts (skipped {results.get("skipped",0)})'
            else:
                message = f'Fetched {results["total_tweets"]} tweets from {results["successful"]} accounts (skipped {results.get("skipped",0)})'
            
            return jsonify({
                'success': True,
                'message': message,
                'total_tweets': results['total_tweets'],
                'successful': results['successful'],
                'failed': results['failed'],
                'skipped': results.get('skipped', 0),
                'errors': results['errors']
            })
    
    except ValueError as e:
        error_msg = str(e)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "... (error truncated)"
        return jsonify({'success': False, 'error': f'Configuration error: {error_msg}'}), 500
    except Exception as e:
        error_msg = str(e)
        # Truncate very long error messages to prevent huge responses
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "... (error truncated - check server logs for full details)"
        import traceback
        # Log full traceback to console but don't send it to client
        print(f"Error in fetch_tweets: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': error_msg}), 500


@app.route('/api/analyze', methods=['POST'])
def analyze_tweets():
    """Analyze tweets and calculate outliers"""
    try:
        data = request.json or {}
        months_back = int(data.get('months', 3))
        outlier_threshold = float(data.get('threshold', 2.0))
        account_filter = data.get('account', None)  # Optional: analyze specific account
        
        analyzer = TweetAnalyzer(db)
        
        if account_filter:
            # Analyze single account
            account = db.get_account(account_filter)
            if not account:
                return jsonify({'success': False, 'error': f'Account @{account_filter} not found'}), 404
            
            result = analyzer.analyze_account(account.id, months_back, outlier_threshold)
            
            return jsonify({
                'success': True,
                'message': f'Analyzed @{account_filter}: {result["outlier_count"]} outliers found',
                'outlier_count': result['outlier_count'],
                'total_tweets': result['total_tweets']
            })
        else:
            # Analyze all accounts
            results = analyzer.analyze_all_accounts(months_back, outlier_threshold)
            total_outliers = sum(r.get('outlier_count', 0) for r in results)
            total_tweets = sum(r.get('total_tweets', 0) for r in results)
            
            return jsonify({
                'success': True,
                'message': f'Analysis complete: {total_outliers} outliers found across {len(results)} accounts',
                'total_outliers': total_outliers,
                'total_tweets': total_tweets,
                'accounts_analyzed': len(results)
            })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/new-tweets')
def get_new_tweets():
    """Get newest tweets from all accounts - quick scan feature"""
    account_filter = request.args.get('account', None)
    limit = int(request.args.get('limit', 100))
    days_back = request.args.get('days_back', None)
    
    # Parse days_back
    days = int(days_back) if days_back else None
    
    # Get account ID if filtering
    account_id = None
    if account_filter:
        account = db.get_account(account_filter)
        account_id = account.id if account else None
    
    # Get newest tweets
    tweets = db.get_newest_tweets(account_id=account_id, limit=limit, days_back=days)
    
    # Format for JSON
    result = []
    for tweet in tweets:
        result.append({
            'id': tweet.id,
            'tweet_id': tweet.tweet_id,
            'account': tweet.account.username,
            'account_display': tweet.account.display_name or tweet.account.username,
            'text': tweet.text or '',
            'multiplier': round(tweet.outlier_multiplier, 2) if tweet.outlier_multiplier else 0.0,
            'likes': tweet.likes,
            'retweets': tweet.retweets,
            'replies': tweet.replies,
            'views': tweet.views,
            'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
            'engagement_score': round(tweet.total_engagement, 2) if tweet.total_engagement else 0.0,
            'is_outlier': bool(tweet.is_outlier)
        })
    
    return jsonify({
        'tweets': result,
        'count': len(result)
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

