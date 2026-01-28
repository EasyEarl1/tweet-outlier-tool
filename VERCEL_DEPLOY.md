# Deploying to Vercel

## Important Notes

⚠️ **Database Limitation**: SQLite databases (`*.db` files) don't persist on Vercel because the filesystem is ephemeral. Each deployment resets the database.

**Solutions:**
1. Use a cloud database (PostgreSQL, MySQL, etc.) - Recommended
2. Use Vercel KV (Redis) for data storage
3. Use an external database service (Supabase, PlanetScale, etc.)

## Deployment Steps

### 1. Set Up Environment Variables in Vercel

1. Go to your Vercel project dashboard
2. Navigate to **Settings** → **Environment Variables**
3. Add your Twitter API key:
   - **Key**: `TWITTER_API_KEY`
   - **Value**: Your actual API key from twitterapi.io
   - **Environment**: Production, Preview, Development (select all)

### 2. Update Database Configuration (If Using Cloud DB)

If you want to use a cloud database instead of SQLite, update `database.py`:

```python
# Example for PostgreSQL with SQLAlchemy
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:pass@host/dbname')
self.engine = create_engine(DATABASE_URL)
```

Then add `DATABASE_URL` to Vercel environment variables.

### 3. Deploy to Vercel

**Option A: Using Vercel CLI**
```bash
# Install Vercel CLI
npm i -g vercel

# Login to Vercel
vercel login

# Deploy
vercel

# For production
vercel --prod
```

**Option B: Using GitHub Integration**
1. Connect your GitHub repository to Vercel
2. Vercel will automatically deploy on every push
3. Make sure environment variables are set in Vercel dashboard

### 4. Update Requirements (if needed)

Make sure `requirements.txt` includes all dependencies. You may need to add:

```
gunicorn
```

### 5. Current Limitations

- **SQLite won't persist**: Database resets on each deployment
- **File uploads**: Not recommended for production on Vercel
- **Long-running tasks**: Vercel has timeout limits (10s for Hobby, 60s for Pro)

### 6. Recommended Architecture for Production

1. **Database**: Use Supabase (PostgreSQL) or PlanetScale (MySQL)
2. **File Storage**: Use Vercel Blob or AWS S3
3. **Background Jobs**: Use Vercel Cron or external service for scheduled fetches

## Quick Start with Cloud Database

1. Sign up for a free PostgreSQL database (Supabase, Neon, etc.)
2. Get your connection string
3. Update `database.py` to use PostgreSQL
4. Add `DATABASE_URL` to Vercel environment variables
5. Deploy!

## Troubleshooting

- **Import errors**: Make sure all dependencies are in `requirements.txt`
- **Environment variables**: Double-check they're set in Vercel dashboard
- **Database errors**: SQLite won't work - use a cloud database
- **Timeout errors**: Consider using background jobs for long operations

