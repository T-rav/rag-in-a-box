import logging
import os
import psycopg2
from psycopg2.extras import execute_values
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SlackPostgresService:
    """Service for handling PostgreSQL operations for Slack data."""
    
    def __init__(self):
        self.conn_string = os.getenv(
            "POSTGRES_CONNECTION_STRING", 
            "postgresql://postgres:postgres@localhost:5432/insight_mesh"
        )
        self.logger = logging.getLogger(__name__)
        self._ensure_tables()
    
    def _get_connection(self):
        """Get a connection to the PostgreSQL database."""
        return psycopg2.connect(self.conn_string)
    
    def _ensure_tables(self):
        """Ensure that all required tables exist."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Create users table
                    cur.execute("""
                    CREATE TABLE IF NOT EXISTS slack_users (
                        id VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(255),
                        real_name VARCHAR(255),
                        display_name VARCHAR(255),
                        email VARCHAR(255) UNIQUE,
                        is_admin BOOLEAN,
                        is_owner BOOLEAN,
                        is_bot BOOLEAN,
                        deleted BOOLEAN,
                        team_id VARCHAR(255),
                        data JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                    """)
                    
                    # Create index on email for faster lookups
                    cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_slack_users_email ON slack_users(email);
                    """)
                    
                    conn.commit()
                    self.logger.info("Ensured PostgreSQL tables for Slack data")
        except Exception as e:
            self.logger.error(f"Error ensuring PostgreSQL tables: {e}")
            raise
    
    def store_users(self, users: List[Dict[str, Any]]):
        """Store multiple Slack users in PostgreSQL."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Prepare data for batch insert
                    columns = [
                        'id', 'name', 'real_name', 'display_name', 'email', 
                        'is_admin', 'is_owner', 'is_bot', 'deleted', 'team_id', 'data'
                    ]
                    
                    values = []
                    for user in users:
                        values.append((
                            user.get('id'),
                            user.get('name'),
                            user.get('real_name'),
                            user.get('display_name'),
                            user.get('email'),
                            user.get('is_admin', False),
                            user.get('is_owner', False),
                            user.get('is_bot', False),
                            user.get('deleted', False),
                            user.get('team_id'),
                            psycopg2.extras.Json(user)
                        ))
                    
                    # Perform upsert - update existing users, insert new ones
                    query = f"""
                    INSERT INTO slack_users ({', '.join(columns)})
                    VALUES %s
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        real_name = EXCLUDED.real_name,
                        display_name = EXCLUDED.display_name,
                        email = EXCLUDED.email,
                        is_admin = EXCLUDED.is_admin,
                        is_owner = EXCLUDED.is_owner,
                        is_bot = EXCLUDED.is_bot,
                        deleted = EXCLUDED.deleted,
                        team_id = EXCLUDED.team_id,
                        data = EXCLUDED.data,
                        updated_at = CURRENT_TIMESTAMP
                    """
                    
                    execute_values(cur, query, values)
                    conn.commit()
                    self.logger.info(f"Stored {len(users)} users in PostgreSQL")
        except Exception as e:
            self.logger.error(f"Error storing users in PostgreSQL: {e}")
            raise
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get a user by email."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT data FROM slack_users WHERE email = %s",
                        (email,)
                    )
                    result = cur.fetchone()
                    return result[0] if result else None
        except Exception as e:
            self.logger.error(f"Error getting user by email from PostgreSQL: {e}")
            raise
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT data FROM slack_users")
                    results = cur.fetchall()
                    return [row[0] for row in results]
        except Exception as e:
            self.logger.error(f"Error getting all users from PostgreSQL: {e}")
            raise 