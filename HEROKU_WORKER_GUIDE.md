# Heroku Worker Deployment Guide

## Overview

This guide explains how to deploy the NHL Companion DB CLI as a **continuously running worker dyno** on Heroku. The worker dyno monitors live NHL games 24/7 and automatically updates your database with real-time play-by-play data.

## What is a Worker Dyno?

Unlike web dynos that handle HTTP requests, worker dynos run background processes continuously. For this application:

- **Worker dyno** runs `python app.py watch-live` indefinitely
- Automatically detects all live games each day
- Updates game state and play-by-play data in real-time
- Uses dynamic time-based polling to optimize API usage
- Restarts automatically if it crashes

## Quick Start

### 1. Deploy to Heroku

```bash
# Create Heroku app (if not already created)
heroku create your-app-name

# Set database credentials
heroku config:set DB_HOST=your-db-host
heroku config:set DB_PORT=3306
heroku config:set DB_USER=your-db-user
heroku config:set DB_PASSWORD=your-db-password
heroku config:set DB_NAME=your-db-name

# Deploy
git push heroku main
```

### 2. Start the Worker

```bash
# Scale worker dyno to 1 instance
heroku ps:scale worker=1
```

That's it! The worker is now running continuously.

### 3. Verify It's Running

```bash
# Check dyno status
heroku ps

# Expected output:
# === worker (Basic): python app.py watch-live (1)
# worker.1: up 2024/01/15 12:00:00 (~ 1h ago)

# View live logs
heroku logs --tail --dyno worker
```

## Dynamic Polling Schedule

The worker automatically adjusts its polling frequency based on the time of day:

| Time Window | Interval | Purpose |
|-------------|----------|---------|
| 7 PM - 11 PM | 5 sec | Peak game time |
| 5 PM - 7 PM | 10 sec | Early games |
| 11 PM - 1 AM | 10 sec | Late games |
| 1 AM - 5 PM | 30 sec | Off-peak |

When no games are live, it polls every 60 seconds.

### Customizing the Schedule

Edit `nhl_db/config.py` and modify `POLLING_SCHEDULE`:

```python
POLLING_SCHEDULE: List[Tuple[time, time, int]] = [
    (time(19, 0), time(23, 0), 5),   # 7 PM - 11 PM: 5 seconds
    (time(17, 0), time(19, 0), 10),  # 5 PM - 7 PM: 10 seconds
    # Add your custom windows here
]
```

Then redeploy:
```bash
git add nhl_db/config.py
git commit -m "Update polling schedule"
git push heroku main
heroku restart worker
```

## Managing the Worker

### Start/Stop the Worker

```bash
# Start worker (scale to 1)
heroku ps:scale worker=1

# Stop worker (scale to 0)
heroku ps:scale worker=0

# Restart worker
heroku restart worker
```

### View Logs

```bash
# Tail worker logs in real-time
heroku logs --tail --dyno worker

# View last 200 lines
heroku logs -n 200 --dyno worker

# Filter for errors
heroku logs --tail --dyno worker | grep ERROR
```

### Check Status

```bash
# View all dynos
heroku ps

# View worker metrics (if available)
heroku ps:type worker
```

## Cost Considerations

### Dyno Hours

- **Free tier**: 550 dyno hours/month (not enough for 24/7)
- **Hobby tier**: $7/month for 24/7 operation
- **Basic tier**: $25/month with better performance

### Recommendations

1. **Development**: Use free tier, manually start/stop worker as needed
2. **Production**: Use Hobby or Basic tier for 24/7 operation

```bash
# Upgrade to Hobby
heroku ps:type worker=hobby

# Upgrade to Basic
heroku ps:type worker=basic
```

## Monitoring

### What to Watch For

1. **Worker uptime**: Should show "up" status
2. **Log output**: Should see "Watching game: XXXXX" messages
3. **Database updates**: Verify plays table is being updated
4. **Error patterns**: Watch for repeated API errors

### Sample Log Output (Healthy)

```
[12:34:56] Using dynamic polling interval: 5s
Watching game: 2024020123
  → Updated 45 plays for game 2024020123
Watching game: 2024020124
  → Updated 38 plays for game 2024020124
Sleeping for 5s...
```

### Sample Log Output (No Games)

```
[03:15:22] Using dynamic polling interval: 30s
No LIVE games found.
Sleeping for 60s (no games)...
```

## Troubleshooting

### Worker Not Starting

```bash
# Check logs for errors
heroku logs --tail --dyno worker

# Common issues:
# - Database connection failed: Check DB credentials
# - Import errors: Check requirements.txt and redeploy
# - Command not found: Verify Procfile syntax
```

### Worker Keeps Crashing

```bash
# View crash logs
heroku logs --tail --dyno worker

# Check for:
# - Database connection issues
# - API rate limiting (429 errors)
# - Memory issues (R14 errors)

# Restart worker
heroku restart worker
```

### High API Error Rate

The worker includes error handling and will continue running even if individual API calls fail. However, if you see persistent errors:

1. Check NHL API status
2. Verify network connectivity
3. Consider increasing polling intervals
4. Check for rate limiting

### Database Connection Issues

```bash
# Test database connection
heroku run python -c "from nhl_db.db import get_db_connection; conn = get_db_connection(); print('Connected!'); conn.close()"

# Verify credentials
heroku config | grep DB_
```

## Additional Commands (via Scheduler)

While the worker handles live games, you can use Heroku Scheduler for other tasks:

```bash
# Install scheduler
heroku addons:create scheduler:standard

# Open scheduler dashboard
heroku addons:open scheduler
```

Add these jobs:

1. **Daily schedule sync** (12:00 AM)
   ```
   python app.py sync-schedule --date $(date +%Y-%m-%d)
   ```

2. **Weekly team sync** (Monday 3:00 AM)
   ```
   python app.py sync-teams
   ```

## Best Practices

1. **Always monitor logs** after deployment
2. **Set up alerts** for worker crashes (use Heroku add-ons)
3. **Test locally** before deploying changes
4. **Keep polling intervals reasonable** to avoid API rate limits
5. **Use dynamic polling** to optimize resource usage
6. **Scale to 0 during off-season** to save costs

## Testing Locally

Before deploying, test the worker locally:

```bash
# Activate virtual environment
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Set environment variables
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=your-password
export DB_NAME=nhl

# Run worker
python app.py watch-live

# Test with fixed interval
python app.py watch-live --poll-seconds 10
```

Press `Ctrl+C` to stop.

## Support

For issues or questions:
1. Check Heroku logs first
2. Review this guide
3. Check the main README.md
4. Verify NHL API status

## Summary

✅ **Deploy once, runs forever**  
✅ **Automatic live game detection**  
✅ **Dynamic time-based polling**  
✅ **Resilient error handling**  
✅ **Easy to monitor and manage**  

The worker dyno approach is ideal for continuous monitoring tasks like live game tracking, eliminating the need for complex cron jobs or scheduled tasks.

