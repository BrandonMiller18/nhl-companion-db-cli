from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from datetime import datetime, time as dt_time
import logging
import requests

logger = logging.getLogger(__name__)

from ..clients.nhl_web_client import (
    fetch_game_boxscore,
    fetch_game_landing,
    fetch_game_pbp,
    fetch_schedule_for_date,
    get_configured_session,
)
from ..db import get_db_connection
from ..mappers.games import derive_game_fields_from_gamecenter, to_game_rows_from_schedule
from ..mappers.plays import map_play
from ..repositories.games_repo import (
    upsert_games_with_conn,
    update_game_fields_with_conn,
)
from ..repositories.plays_repo import upsert_plays_with_conn


def update_live_once(game_id: int) -> int:
    session = get_configured_session()
    landing = fetch_game_landing(game_id, session=session)
    box = fetch_game_boxscore(game_id, session=session)
    pbp = fetch_game_pbp(game_id, session=session)

    game_state, period, clock, home_score, away_score, home_sog, away_sog = derive_game_fields_from_gamecenter(landing, box)
    conn = get_db_connection()
    try:
        update_game_fields_with_conn(conn, game_id, game_state, period, clock, home_score, away_score, home_sog, away_sog)

        plays = pbp.get("plays") or []
        rows = [map_play(game_id, p) for p in plays]
        count = upsert_plays_with_conn(conn, rows)
        return count
    finally:
        conn.close()


def _list_live_games_today(session: Optional[requests.Session] = None) -> List[int]:
    session = session or get_configured_session()
    # Today's schedule only; can be extended to inch back/forward if desired

    today = datetime.now().strftime("%Y-%m-%d")
    games = fetch_schedule_for_date(today, session=session)
    rows = to_game_rows_from_schedule(games)
    # Ensure rows exist minimally (id and basic fields)
    conn = get_db_connection()
    try:
        upsert_games_with_conn(conn, rows)
    finally:
        conn.close()

    ids: List[int] = []
    for g in games:
        try:
            if str(g.get("gameState") or "").upper() in ["LIVE", "CRIT"]:
                ids.append(int(g.get("id")))
        except Exception:
            continue
    return ids


def watch_live_games(poll_seconds: int = 5) -> None:
    """
    Continuously watch live games and update the database.
    
    Args:
        poll_seconds: Polling interval when there ARE live games (in seconds).
                     Default is 5 seconds. Set to 0 to use config default.
    
    The function will run indefinitely:
    - When live games exist: polls every `poll_seconds` (default: 5 seconds)
    - When no live games: polls every 5 minutes (300 seconds)
    """
    from ..config import NO_GAMES_POLL_SECONDS, LIVE_GAMES_POLL_SECONDS
    
    # Use config default if poll_seconds is 0 or negative
    if poll_seconds <= 0:
        poll_seconds = LIVE_GAMES_POLL_SECONDS
    
    session = get_configured_session()
    i = 0
    SESSION_REFRESH_INTERVAL = 50  # Recreate session every N iterations
    
    print(f"Starting watch-live service...")
    print(f"Live games polling: {poll_seconds}s | No games polling: {NO_GAMES_POLL_SECONDS}s")
    
    while True:
        # Periodically refresh the session to prevent long-lived connection issues
        if i > 0 and i % SESSION_REFRESH_INTERVAL == 0:
            print(f"Refreshing session after {i} iterations...")
            session = get_configured_session()
        
        try:
            live_ids = _list_live_games_today(session=session)
            current_time = datetime.now().strftime("%H:%M:%S")
            
            if not live_ids:
                print(f"[{current_time}] No LIVE games found.")
            else:
                print(f"[{current_time}] Found {len(live_ids)} live game(s)")
            
            conn = get_db_connection()
            try:
                for game_id in live_ids:
                    try:
                        print(f"  Watching game: {game_id}")
                        landing = fetch_game_landing(game_id, session=session)
                        box = fetch_game_boxscore(game_id, session=session)
                        pbp = fetch_game_pbp(game_id, session=session)

                        game_state, period, clock, home_score, away_score, home_sog, away_sog = derive_game_fields_from_gamecenter(landing, box)
                        update_game_fields_with_conn(conn, game_id, game_state, period, clock, home_score, away_score, home_sog, away_sog)

                        plays = pbp.get("plays") or []
                        rows = [map_play(game_id, p) for p in plays]
                        count = upsert_plays_with_conn(conn, rows)
                        print(f"    → Updated {count} plays for game {game_id}")
                    except requests.exceptions.RequestException as e:
                        logger.error(f"Request error for game {game_id}: {e}", exc_info=True)
                        print(f"  Request error for game {game_id}: {e}")
                        print("  Continuing to next game...")
                        continue
                    except Exception as e:
                        logger.error(f"Unexpected error for game {game_id}: {e}", exc_info=True)
                        print(f"  Unexpected error for game {game_id}: {e}")
                        print("  Continuing to next game...")
                        continue
            finally:
                conn.close()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error while fetching live games: {e}", exc_info=True)
            print(f"Request error while fetching live games: {e}")
            print("Retrying in next iteration...")
        except Exception as e:
            logger.error(f"Unexpected error in watch loop: {e}", exc_info=True)
            print(f"Unexpected error in watch loop: {e}")
            print("Retrying in next iteration...")

        from time import sleep as _sleep
        if not live_ids:
            print(f"Sleeping for {NO_GAMES_POLL_SECONDS}s (no games)...\n")
            _sleep(NO_GAMES_POLL_SECONDS)
        else:
            print(f"Sleeping for {poll_seconds}s (live games active)...\n")
            _sleep(max(1, int(poll_seconds)))
        i += 1


