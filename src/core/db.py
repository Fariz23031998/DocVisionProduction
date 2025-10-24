import aiosqlite
from typing import Any, Dict, List, Optional, Tuple, Union
from fastapi import HTTPException
import logging

from src.core.conf import DATABASE_URL

logger = logging.getLogger("DocVision")

# Database setup
class DatabaseConnection:
    """Unified core connection class with all core operations as methods"""

    def __init__(self, db_path: str = DATABASE_URL):
        self.db_path = db_path
        self.connection = None

    async def __aenter__(self):
        try:
            self.connection = await aiosqlite.connect(self.db_path)
            self.connection.row_factory = aiosqlite.Row  # Enable dict-like row access
            logger.info(f"Connected to core: {self.db_path}")
            return self
        except Exception as e:
            logger.error(f"Failed to connect to core {self.db_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Database connection failed: {e}")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            await self.connection.close()
            logger.info(f"Closed core connection: {self.db_path}")

    def _ensure_connection(self):
        """Ensure connection is available"""
        if not self.connection:
            raise HTTPException(status_code=500,
                                detail="No active core connection. Use within async context manager.")

    async def init_db(self):
        """Initialize core tables"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")

            # Create users table
            await db.execute("""
                  CREATE TABLE IF NOT EXISTS users (
                      id TEXT PRIMARY KEY,
                      email TEXT UNIQUE NOT NULL,
                      full_name TEXT NOT NULL,
                      password_hash TEXT NOT NULL,
                      is_active BOOLEAN DEFAULT TRUE,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                  )
              """)

            # Create sessions table
            await db.execute("""
                  CREATE TABLE IF NOT EXISTS sessions (
                      session_id TEXT PRIMARY KEY,
                      user_id TEXT NOT NULL,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      expires_at TIMESTAMP NOT NULL,
                      FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                  )
              """)

            # Create keys table
            await db.execute("""
                  CREATE TABLE IF NOT EXISTS regos_tokens (
                      token_id INTEGER PRIMARY KEY,
                      user_id TEXT UNIQUE NOT NULL,
                      integration_token TEXT NOT NULL,
                      FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                  )
              """)

            # Create subscriptions table
            await db.execute("""
                  CREATE TABLE IF NOT EXISTS subscriptions (
                      id TEXT PRIMARY KEY,
                      user_id TEXT UNIQUE NOT NULL,
                      plan TEXT NOT NULL CHECK(plan IN ('free-trial', 'standard', 'pro')),
                      status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'cancelled', 'expired')),
                      ai_processing INTEGER DEFAULT 0,
                      last_monthly_regen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      last_daily_regen TIMESTAMP,
                      started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      expires_at TIMESTAMP,
                      cancelled_at TIMESTAMP,
                      FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                  )
              """)

            # Create orders table
            await db.execute("""
                  CREATE TABLE IF NOT EXISTS orders (
                      id TEXT PRIMARY KEY,
                      user_id TEXT NOT NULL,
                      plan TEXT NOT NULL CHECK(plan IN ('standard', 'pro')),
                      months INTEGER NOT NULL CHECK(months >= 1 AND months <= 24),
                      amount REAL NOT NULL,
                      currency TEXT DEFAULT 'UZS',
                      status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'paid', 'failed', 'cancelled', 'expired')),
                      payment_provider TEXT,
                      payment_transaction_id TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      paid_at TIMESTAMP,
                      expires_at TIMESTAMP,
                      metadata TEXT,
                      FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                  )
              """)

            # Create payments table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INT PRIMARY KEY,
                    amount REAL NOT NULL,
                    provider TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    subscription_id TEXT NOT NULL,
                    is_cancelled BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    FOREIGN KEY (subscription_id) REFERENCES subscriptions (id) ON DELETE CASCADE
                )
            """)

            # Create ai_usage_operations
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ai_processing_operations (
                    id INTEGER PRIMARY KEY,
                    subscription_id TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    is_positive BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
                )
            """)

            # Create verification code table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS verification_codes (
                    id INTEGER PRIMARY KEY,
                    recipient TEXT NOT NULL,
                    code TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for better performance
            await db.execute("""
                  CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)
              """)

            await db.execute("""
                  CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id)
              """)

            await db.execute("""
                  CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions (last_activity)
              """)

            await db.execute("""
                  CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions (user_id)
              """)

            await db.execute("""
                  CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions (status)
              """)

            await db.execute("""
                  CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id)
              """)

            await db.execute("""
                  CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status)
              """)

            await db.execute("""
                  CREATE INDEX IF NOT EXISTS idx_orders_payment_transaction_id ON orders (payment_transaction_id)
              """)

            await db.execute("""
                 CREATE INDEX IF NOT EXISTS idx_verification_codes_recipient ON verification_codes (recipient)
             """)

            await db.commit()

    async def fetch_one(
            self,
            query: str,
            params: Optional[Union[Tuple, Dict]] = None,
            allow_none: bool = False,
            raise_http: bool = True
    ) -> Optional[aiosqlite.Row]:
        """
        Execute a SQL query and retrieve a single row from the core.

        Args:
            query (str): The SQL query string to be executed.
            params (Optional[Union[Tuple, Dict]]): Optional query parameters.
            allow_none (bool): If True, returns None when no data found instead of raising an exception.
            raise_http (bool): If False, catches and logs exceptions instead of raising HTTPException.
                               Use False in background or scheduler contexts.

        Returns:
            aiosqlite.Row | None: The fetched row, or None if allow_none=True or if an error occurred
                                  and raise_http=False.

        Raises:
            HTTPException: 404 if no data found (when allow_none=False and raise_http=True),
                           400 for SQLite errors, 500 for other unexpected errors.
        """
        self._ensure_connection()

        try:
            logger.info(f"[DB] Executing fetch_one query: {query}")
            logger.info(f"[DB] Parameters: {params}")

            cursor = await self.connection.execute(query, params or ())
            result = await cursor.fetchone()

            if result is None:
                if allow_none:
                    return None
                if raise_http:
                    raise HTTPException(status_code=404, detail="No data was found")
                logger.info("[DB] No data found (scheduler-safe mode).")
                return None

            logger.info(f"[DB] fetch_one result: {dict(result)}")
            return result

        except HTTPException:
            if raise_http:
                raise
            logger.error("[DB] HTTPException caught in fetch_one (scheduler context).")
            return None

        except aiosqlite.Error as e:
            error_msg = f"SQLite error in fetch_one: {e}"
            logger.error(error_msg)
            if raise_http:
                raise HTTPException(status_code=400, detail=error_msg)
            return None

        except Exception as e:
            error_msg = f"Unexpected error in fetch_one: {e}"
            logger.error(error_msg)
            if raise_http:
                raise HTTPException(status_code=500, detail=error_msg)
            return None

    async def fetch_all(
            self,
            query: str,
            params: Optional[Union[Tuple, Dict]] = None,
            raise_http: bool = True,  # add this flag
    ) -> List[aiosqlite.Row]:
        """
        Execute a SQL query and fetch all matching rows.
        Args:
            query (str): The SQL query string to execute.
            params (Optional[Union[Tuple, Dict]]): Parameters for the query.
            raise_http (bool): Raises http Exception if True, otherwise returns empty list.

        Returns:
            List[aiosqlite.Row]: List of fetched rows.

        Raises:
            HTTPException: 404 if no data found, 400 for SQLite errors, 500 for other errors.
        """
        self._ensure_connection()

        try:
            logger.info(f"Executing fetch_all query: {query}")
            logger.info(f"Parameters: {params}")

            cursor = await self.connection.execute(query, params or ())
            results = await cursor.fetchall()

            if len(results) == 0 and raise_http:
                raise HTTPException(status_code=404, detail="No data was found")

            return results

        except HTTPException:
            if raise_http:
                raise
            logger.error("HTTPException caught in fetch_all (scheduler context)")
            return []

        except aiosqlite.Error as e:
            error_msg = f"SQLite error in fetch_all: {e}"
            logger.error(error_msg)
            if raise_http:
                raise HTTPException(status_code=400, detail=error_msg)
            return []

        except Exception as e:
            error_msg = f"Unexpected error in fetch_all: {e}"
            logger.error(error_msg)
            if raise_http:
                raise HTTPException(status_code=500, detail=error_msg)
            return []

    async def execute_one(
            self,
            query: str,
            params: Optional[Union[Tuple, Dict]] = None,
            commit: bool = True,
            raise_http: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a single SQL statement (INSERT, UPDATE, or DELETE).

        Args:
            query (str): The SQL statement to execute.
            params (Optional[Union[Tuple, Dict]]): Parameters for the statement.
            commit (bool): Whether to commit the transaction.
            raise_http (bool): If False, catches exceptions and logs them instead of raising HTTPException
                               (useful for background/scheduled tasks).

        Returns:
            Dict[str, Any]: Dictionary with rows_affected and inserted_row_id.
                            Returns {'rows_affected': 0, 'inserted_row_id': None} on failure if raise_http=False.
        """
        self._ensure_connection()

        try:
            logger.info(f"[DB] Executing execute_one query: {query}")
            logger.info(f"[DB] Parameters: {params}")

            cursor = await self.connection.execute(query, params or ())

            if commit:
                await self.connection.commit()

            rows_affected = cursor.rowcount or 0
            last_row_id = cursor.lastrowid
            logger.info(f"[DB] execute_one affected {rows_affected} rows")

            return {
                "rows_affected": rows_affected,
                "inserted_row_id": last_row_id
            }

        except aiosqlite.Error as e:
            error_msg = f"SQLite error in execute_one: {e}"
            logger.error(error_msg)

            # Only rollback if we were managing the transaction
            if commit:
                await self.connection.rollback()

            if raise_http:
                raise HTTPException(status_code=400, detail=error_msg)
            return {"rows_affected": 0, "inserted_row_id": None}

        except Exception as e:
            error_msg = f"Unexpected error in execute_one: {e}"
            logger.error(error_msg)

            # Rollback on unexpected errors too
            if commit:
                await self.connection.rollback()

            if raise_http:
                raise HTTPException(status_code=500, detail=error_msg)
            return {"rows_affected": 0, "inserted_row_id": None}

    async def execute_many(
            self,
            query: str,
            params_list: List[Union[Tuple, Dict]],
            commit: bool = True,
            raise_http: bool = True
    ) -> int:
        """
        Execute a SQL statement multiple times with different parameters.

        Args:
            query (str): The SQL statement to execute.
            params_list (List[Union[Tuple, Dict]]): List of parameters for each execution.
            commit (bool): Whether to commit the transaction.
            raise_http (bool): If False, logs errors instead of raising HTTPException
                               (recommended for background/scheduled tasks).

        Returns:
            int: Total number of rows affected. Returns 0 on failure if raise_http=False.

        Raises:
            HTTPException: 400 for SQLite errors, 500 for other errors (when raise_http=True).
        """
        self._ensure_connection()

        if not params_list:
            logger.info("[DB] execute_many called with empty params_list")
            return 0

        try:
            logger.info(f"[DB] Executing execute_many query: {query}")
            logger.info(f"[DB] Parameter count: {len(params_list)}")

            cursor = await self.connection.executemany(query, params_list)

            if commit:
                await self.connection.commit()

            # Some SQLite drivers may return -1 for rowcount when unknown
            rows_affected = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else len(params_list)
            logger.info(f"[DB] execute_many affected {rows_affected} rows")

            return rows_affected

        except aiosqlite.Error as e:
            error_msg = f"SQLite error in execute_many: {e}"
            logger.error(error_msg)

            if commit:
                await self.connection.rollback()

            if raise_http:
                raise HTTPException(status_code=400, detail=error_msg)
            return 0

        except Exception as e:
            error_msg = f"Unexpected error in execute_many: {e}"
            logger.error(error_msg)

            if commit:
                await self.connection.rollback()

            if raise_http:
                raise HTTPException(status_code=500, detail=error_msg)
            return 0

    async def execute_transaction(
            self,
            operations: List[Tuple[str, Optional[Union[Tuple, Dict]]]]
    ) -> List[int]:
        """
        Execute multiple SQL statements in a single transaction.

        Args:
            operations (List[Tuple[str, Optional[Union[Tuple, Dict]]]]):
                List of tuples containing (query, params) for each operation.

        Returns:
            List[int]: Number of rows affected by each operation.

        Raises:
            HTTPException: 400 for SQLite errors, 404 if no operations, 500 for other errors.
        """
        self._ensure_connection()

        if not operations:
            raise HTTPException(status_code=400, detail="No operations provided")

        try:
            results = []

            # Start transaction
            await self.connection.execute("BEGIN")

            try:
                for query, params in operations:
                    logger.info(f"Transaction operation: {query}")
                    cursor = await self.connection.execute(query, params or ())
                    results.append(cursor.rowcount)

                # Commit transaction
                await self.connection.commit()
                logger.info(f"Transaction completed successfully with {len(operations)} operations")

                return results

            except Exception as e:
                # Rollback on any error
                await self.connection.rollback()
                error_msg = f"Transaction operation failed: {e}"
                logger.error(error_msg)
                raise HTTPException(status_code=500, detail=error_msg)

        except HTTPException:
            raise
        except aiosqlite.Error as e:
            error_msg = f"SQLite error in execute_transaction: {e}"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        except Exception as e:
            error_msg = f"Unexpected error in execute_transaction: {e}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

    async def get_last_insert_id(
            self,
            query: str,
            params: Optional[Union[Tuple, Dict]] = None
    ) -> int:
        """
        Execute an INSERT statement and return the last inserted row ID.

        Args:
            query (str): The INSERT SQL statement to execute.
            params (Optional[Union[Tuple, Dict]]): Parameters for the statement.

        Returns:
            int: The ID of the newly inserted row.

        Raises:
            HTTPException: 400 for SQLite errors, 500 for other errors.
        """
        self._ensure_connection()

        try:
            cursor = await self.connection.execute(query, params or ())
            await self.connection.commit()

            last_id = cursor.lastrowid
            logger.info(f"Last inserted ID: {last_id}")

            return last_id

        except aiosqlite.Error as e:
            error_msg = f"SQLite error in get_last_insert_id: {e}"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        except Exception as e:
            error_msg = f"Unexpected error in get_last_insert_id: {e}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

    async def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the core.

        Args:
            table_name (str): Name of the table to check

        Returns:
            bool: True if table exists, False otherwise
        """
        try:
            await self.fetch_one(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            return True
        except HTTPException as e:
            if e.status_code == 404:
                return False
            raise

    async def get_table_info(self, table_name: str) -> List[aiosqlite.Row]:
        """
        Retrieve schema information about a core table.

        Args:
            table_name (str): The name of the table whose schema information should be retrieved.

        Returns:
            List[aiosqlite.Row]: List of rows with column metadata.

        Raises:
            HTTPException: 404 if table not found, 400 for SQLite errors, 500 for other errors.
        """
        return await self.fetch_all(f"PRAGMA table_info({table_name})")

    async def get_row_count(self, table_name: str, where_clause: str = "",
                            params: Optional[Union[Tuple, Dict]] = None) -> int:
        """
        Get the number of rows in a core table.

        Args:
            table_name (str): The name of the table to count rows from.
            where_clause (str): Optional SQL WHERE clause (without the `WHERE` keyword).
            params (Optional[Union[Tuple, Dict]]): Parameters for the WHERE clause.

        Returns:
            int: The number of rows matching the condition.

        Raises:
            HTTPException: 400 for SQLite errors, 500 for other errors.
        """
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"

        try:
            result = await self.fetch_one(query, params)
            return result["count"]
        except HTTPException as e:
            if e.status_code == 404:
                return 0
            raise

    async def close(self):
        """Manually close the core connection"""
        if self.connection:
            await self.connection.close()
            self.connection = None
            logger.info(f"Manually closed core connection: {self.db_path}")