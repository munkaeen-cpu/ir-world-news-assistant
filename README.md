# ir-world-news-assistant
## Free database setup with Supabase (optional but recommended for deployed apps)

This app supports two storage modes:
- Local SQLite (default, no setup required)
- Supabase Postgres (free tier, recommended for deployed apps)

### 1) Local mode (works immediately)
No secrets required. The app will create:
- data/data.db

This works well for local development and simple personal usage.

### 2) Supabase free-tier mode
1. Create a free Supabase project at https://supabase.com
2. Open Project Settings → Database
3. Copy the connection string
4. Create a file named .streamlit/secrets.toml in your project root:
   [db]
   database_url = "postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres"

Important:
- Do not commit .streamlit/secrets.toml to GitHub
- Add this to .gitignore:
  .streamlit/secrets.toml
  data/

Then deploy to Streamlit Cloud or another free host. The app will automatically use Postgres if the URL is available.

### Why this matters
- Streamlit Cloud containers are not a reliable long-term storage system for app data
- Local SQLite is fine for personal use
- Supabase is better for persistent notes, flashcards, and saved articles
