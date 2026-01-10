# NHL Companion DB CLI

Command-line interface for syncing NHL data from external APIs to MySQL database.

## Overview

This service is responsible for:
- Fetching team and player data from NHL APIs
- Syncing game schedules
- Monitoring live games and updating play-by-play data
- Managing database schema and migrations

## Architecture

The DB CLI service includes:
- **CLI application** (`app.py`) - Main entry point with command structure
- **Database package** (`nhl_db/`) - Core functionality
  - `commands/` - CLI command implementations (teams, players, schedule, live)
  - `clients/` - External API clients (NHL Web API, Records API)
  - `repositories/` - Database access layer
  - `mappers/` - Data transformation layer
  - `services/` - Business logic layer
  - `config.py` - Environment configuration
  - `db.py` - Database connection management

## Local Development Setup

### Prerequisites

- Python 3.11+
- MySQL database (local or remote)
- Git

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd nhl-companion-db-cli
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp env.example .env
# Edit .env with your database credentials
```

### Database Setup

1. Create the MySQL database:
```sql
CREATE DATABASE nhl;
```

2. Run the schema script:
```bash
mysql -u root -p nhl < test/schema.sql
```

## Usage

### Available Commands

#### Teams
```bash
# Sync all teams from NHL API
python app.py teams sync

# Sync active teams only
python app.py teams sync --active-only
```

#### Players
```bash
# Sync players for a specific team
python app.py players sync --team-id 1

# Sync players for all teams
python app.py players sync-all
```

#### Schedule
```bash
# Sync schedule for a specific date
python app.py schedule sync --date 2024-01-15

# Sync schedule for a date range
python app.py schedule sync --start-date 2024-01-01 --end-date 2024-01-31
```

#### Live Games
```bash
# Update a single game once
python app.py update-live 2023020001

# Continuously watch all live games (5s when live, 5min when no games)
python app.py watch-live

# Watch live games with custom polling interval
python app.py watch-live --poll-seconds 10
```

## Deployment to Heroku

### Prerequisites

- Heroku account
- Heroku CLI installed
- Git repository
- MySQL database (shared with API service or separate)

### Deployment Steps

1. Create a Heroku app:
```bash
heroku create your-db-cli-app-name
```

2. Set database credentials (use same as API service):
```bash
heroku config:set DB_HOST=<host>
heroku config:set DB_PORT=3306
heroku config:set DB_USER=<user>
heroku config:set DB_PASSWORD=<password>
heroku config:set DB_NAME=<database>
```

3. Deploy:
```bash
git push heroku main
```

4. **Start the worker dyno** (continuously watches live games):
```bash
heroku ps:scale worker=1
```

The worker dyno runs `watch-live` continuously, automatically adjusting polling based on game activity. This is the core of the application and should always be running.

5. (Optional) Install Heroku Scheduler add-on for additional commands:
```bash
heroku addons:create scheduler:standard
```

6. (Optional) Configure scheduled jobs:
```bash
heroku addons:open scheduler
```

Add jobs in the Heroku Scheduler dashboard:
- **Daily schedule sync**: `python app.py sync-schedule --date $(date +%Y-%m-%d)`
- **Weekly team sync**: `python app.py sync-teams`
- **Weekly player sync**: `python app.py sync-players --team-id <id>` (or sync-all)

### Managing the Worker Dyno

The worker dyno continuously monitors live games and should always be running:

```bash
# Check dyno status
heroku ps

# Start the worker (if not running)
heroku ps:scale worker=1

# Stop the worker (for maintenance)
heroku ps:scale worker=0

# View worker logs
heroku logs --tail --dyno worker
```

### Running One-Off Commands

```bash
# Run any command on Heroku
heroku run python app.py sync-teams
heroku run python app.py sync-schedule --date 2024-01-15
heroku run python app.py update-live 2023020001
```

## Polling Configuration

The `watch-live` command uses a simple, efficient polling strategy based on whether live games are detected:

| Condition | Polling Interval | Configuration |
|-----------|------------------|---------------|
| Live games detected | 5 seconds | `LIVE_GAMES_POLL_SECONDS` |
| No live games | 5 minutes (300 seconds) | `NO_GAMES_POLL_SECONDS` |

This approach optimizes API usage by polling frequently during active games and conserving resources when no games are live.

### Customizing Polling Intervals

Edit `nhl_db/config.py` to adjust the polling intervals:

```python
# Poll every 5 seconds when there are live games
LIVE_GAMES_POLL_SECONDS = 5

# Poll every 5 minutes (300 seconds) when there are no live games
NO_GAMES_POLL_SECONDS = 300
```

You can also override the live games interval via command line:
```bash
# Use default (5 seconds for live games)
python app.py watch-live

# Custom interval for live games (10 seconds)
python app.py watch-live --poll-seconds 10
```

## Environment Variables

Required environment variables:

- `DB_HOST` - MySQL host
- `DB_PORT` - MySQL port (usually 3306)
- `DB_USER` - MySQL username
- `DB_PASSWORD` - MySQL password
- `DB_NAME` - MySQL database name

Optional:
- `LOG_TO_FILE` - Set to "true" for file logging (default: false, uses stdout)

## Data Sources

This service fetches data from:
- **NHL Web API**: `https://api-web.nhle.com/v1`
  - Current season data
  - Live game data
  - Player information
- **NHL Records API**: `https://records.nhl.com/site/api`
  - Historical data
  - Franchise information

## Database Schema

The service manages the following tables:

### teams
- Team information (id, name, abbreviation, etc.)

### players
- Player information (id, name, position, team, etc.)

### games
- Game schedule and results
- Includes scores, state, period, clock

### plays
- Play-by-play data for games
- Includes event type, time, players involved, description

See `test/schema.sql` for complete schema definition.

## Scheduled Job Recommendations

### Production Schedule

**Core Service (Always Running):**
- **Worker Dyno**: Runs `watch-live` continuously
  - Automatically monitors all live games
  - Polls every 5 seconds when games are live
  - Polls every 5 minutes when no games are active
  - No scheduler needed - runs 24/7

**Optional Scheduled Jobs (via Heroku Scheduler):**

1. **Daily Schedule Sync** (Run at 12:00 AM ET)
```bash
python app.py sync-schedule-dates $(date +%Y-%m-%d) $(date +%Y-%m-%d)
```

2. **Team Sync** (Run weekly on Monday at 3:00 AM ET)
```bash
python app.py sync-teams-records
```

3. **Player Sync** (Run weekly on Monday at 4:00 AM ET)
```bash
python app.py sync-players-roster --team-id <id>
```

Note: The worker dyno handles all live game monitoring automatically, so you don't need scheduled jobs for that.

## Monitoring and Logs

### Heroku Logs
```bash
# View all logs
heroku logs --tail --app your-db-cli-app-name

# View worker dyno logs specifically
heroku logs --tail --dyno worker

# View recent logs
heroku logs --tail --source app
```

### Worker Health Monitoring
```bash
# Check if worker is running
heroku ps

# Expected output:
# === worker (Basic): python app.py watch-live (1)
# worker.1: up 2024/01/15 12:00:00 (~ 1h ago)
```

### Database Verification
```bash
# Connect to database
heroku run mysql -h $DB_HOST -u $DB_USER -p$DB_PASSWORD $DB_NAME

# Check record counts
SELECT COUNT(*) FROM teams;
SELECT COUNT(*) FROM players;
SELECT COUNT(*) FROM games;
SELECT COUNT(*) FROM plays;
```

## Troubleshooting

### Database Connection Issues
- Verify database credentials in Heroku config vars
- Check if database is accessible from Heroku
- Test connection: `heroku run python -c "from nhl_db.db import get_db_connection; get_db_connection()"`

### API Rate Limiting
- NHL APIs may rate limit requests
- Add delays between bulk operations if needed
- Monitor logs for HTTP 429 errors

### Missing Data
- Check if NHL APIs are returning data
- Verify date formats (YYYY-MM-DD)
- Check logs for API errors

## Development Tips

### Testing Commands Locally

```bash
# Test with a specific date
python app.py schedule sync --date 2024-01-15

# Test with a known game ID
python app.py update-live 2023020001

# Test team sync
python app.py sync-teams-records --active-only
```

### Debugging

Enable verbose logging by setting environment variable:
```bash
export LOG_TO_FILE=true
python app.py <command>
# Check logs/nhl_companion.log
```

## Related Repositories

- **API**: NHL Companion API (FastAPI on Heroku)
- **Frontend**: NHL Companion Frontend (Next.js on Vercel)

## License

MIT
