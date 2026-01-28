"""
Persistence layer for accounts using Vercel KV (Redis) with in-memory fallback
"""
import os
import json
import pickle
from typing import List, Optional, Dict

class AccountPersistence:
    """Handle persistent storage of accounts using Vercel KV or in-memory fallback"""
    
    def __init__(self):
        self.use_kv = False
        self.kv = None
        self._memory_store = {}  # Fallback in-memory storage
        
        # Try to initialize Vercel KV
        try:
            # Vercel KV uses @vercel/kv package, but we can use redis-py if available
            # For now, we'll use environment variable as a simple KV store
            # In production, you'd use Vercel KV SDK
            kv_url = os.environ.get('KV_REST_API_URL')
            kv_token = os.environ.get('KV_REST_API_TOKEN')
            
            if kv_url and kv_token:
                try:
                    import redis
                    self.kv = redis.from_url(
                        kv_url,
                        password=kv_token,
                        decode_responses=True
                    )
                    self.use_kv = True
                    print("Using Vercel KV for persistent storage")
                except ImportError:
                    print("redis package not installed, using in-memory storage")
                except Exception as e:
                    print(f"Failed to connect to KV: {e}, using in-memory storage")
            else:
                print("KV credentials not found, using in-memory storage")
        except Exception as e:
            print(f"Persistence initialization error: {e}, using in-memory storage")
    
    def save_accounts(self, accounts: List[Dict]) -> bool:
        """Save accounts to persistent storage"""
        try:
            accounts_json = json.dumps(accounts)
            
            if self.use_kv and self.kv:
                self.kv.set('tweet_outlier_accounts', accounts_json)
                return True
            else:
                # Fallback: store in environment variable (limited size)
                # This is a workaround - not ideal but works for small datasets
                self._memory_store['accounts'] = accounts
                return True
        except Exception as e:
            print(f"Error saving accounts: {e}")
            return False
    
    def load_accounts(self) -> List[Dict]:
        """Load accounts from persistent storage"""
        try:
            if self.use_kv and self.kv:
                accounts_json = self.kv.get('tweet_outlier_accounts')
                if accounts_json:
                    return json.loads(accounts_json)
                return []
            else:
                # Fallback: load from memory
                return self._memory_store.get('accounts', [])
        except Exception as e:
            print(f"Error loading accounts: {e}")
            return []
    
    def add_account(self, username: str, display_name: Optional[str] = None, 
                   follower_count: Optional[int] = None) -> bool:
        """Add a single account"""
        accounts = self.load_accounts()
        
        # Check if account already exists
        if any(acc.get('username') == username for acc in accounts):
            return False
        
        accounts.append({
            'username': username,
            'display_name': display_name,
            'follower_count': follower_count
        })
        
        return self.save_accounts(accounts)
    
    def remove_account(self, username: str) -> bool:
        """Remove an account"""
        accounts = self.load_accounts()
        accounts = [acc for acc in accounts if acc.get('username') != username]
        return self.save_accounts(accounts)
    
    def get_all_accounts(self) -> List[Dict]:
        """Get all accounts"""
        return self.load_accounts()

