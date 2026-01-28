"""
Account import functionality for bulk importing Twitter accounts
"""
import csv
import os
from database import Database


class AccountImporter:
    """Handle importing accounts from various file formats"""
    
    def __init__(self, db):
        self.db = db
    
    def import_from_csv(self, csv_path, username_column='username'):
        """
        Import accounts from CSV file
        
        CSV format should have at least a username column.
        Optional columns: display_name, follower_count
        """
        imported = 0
        errors = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                    try:
                        username = row.get(username_column, '').strip()
                        if not username:
                            errors.append(f"Row {row_num}: Missing username")
                            continue
                        
                        # Remove @ if present
                        username = username.lstrip('@')
                        
                        display_name = row.get('display_name', '').strip() or None
                        follower_count = None
                        if 'follower_count' in row and row['follower_count']:
                            try:
                                follower_count = int(row['follower_count'])
                            except ValueError:
                                pass
                        
                        self.db.add_account(username, display_name, follower_count)
                        imported += 1
                        
                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")
        
        except FileNotFoundError:
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        except Exception as e:
            raise Exception(f"Error reading CSV file: {str(e)}")
        
        return imported, errors
    
    def import_from_txt(self, txt_path):
        """
        Import accounts from text file (one username per line)
        """
        imported = 0
        errors = []
        
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, start=1):
                    username = line.strip()
                    if not username or username.startswith('#'):
                        continue  # Skip empty lines and comments
                    
                    try:
                        # Remove @ if present
                        username = username.lstrip('@')
                        self.db.add_account(username)
                        imported += 1
                    except Exception as e:
                        errors.append(f"Line {line_num}: {str(e)}")
        
        except FileNotFoundError:
            raise FileNotFoundError(f"Text file not found: {txt_path}")
        except Exception as e:
            raise Exception(f"Error reading text file: {str(e)}")
        
        return imported, errors
    
    def import_accounts(self, file_path, file_type='auto', username_column='username'):
        """
        Import accounts from a file
        
        Args:
            file_path: Path to the file
            file_type: 'csv', 'txt', or 'auto' (detect from extension)
            username_column: Column name for username in CSV
        
        Returns:
            Tuple of (imported_count, errors_list)
        """
        if file_type == 'auto':
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.csv':
                file_type = 'csv'
            elif ext in ['.txt', '.list']:
                file_type = 'txt'
            else:
                raise ValueError(f"Unknown file type: {ext}. Use .csv or .txt")
        
        if file_type == 'csv':
            return self.import_from_csv(file_path, username_column)
        elif file_type == 'txt':
            return self.import_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

