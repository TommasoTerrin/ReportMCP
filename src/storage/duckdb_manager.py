"""
DuckDB database manager for ReportMCP.

This module provides a thread-safe, session-isolated DuckDB manager
for storing and querying ingested data. Each session gets its own
schema namespace to prevent data conflicts.
"""

import logging
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Generator, Optional

import duckdb
import pandas as pd

from src.models.data import ColumnSchema, DataIngestionRequest, DataIngestionResponse
from src.models.exceptions import DataIngestionError, SessionNotFoundError

logger = logging.getLogger(__name__)


class DuckDBManager:
    """
    Thread-safe DuckDB database manager with session isolation.
    
    Each session creates a separate schema in DuckDB, providing
    multi-tenant data isolation. The manager supports both in-memory
    and persistent storage modes.
    
    Attributes:
        db_path: Path to the database file, or ":memory:" for in-memory.
        connection: The DuckDB connection object.
    
    Example:
        ```python
        manager = DuckDBManager()
        manager.ingest_data(request)
        df = manager.execute_query("session_id", "SELECT * FROM my_table")
        ```
    """
    
    def __init__(self, db_path: str = ":memory:") -> None:
        """
        Initialize the DuckDB manager.
        
        Args:
            db_path: Path to database file or ":memory:" for in-memory storage.
        """
        self._db_path = db_path
        self._lock = Lock()
        self._connection: Optional[duckdb.DuckDBPyConnection] = None
        self._sessions: set[str] = set()
        
        # Initialize connection
        self._connect()
        logger.info(f"DuckDB manager initialized with path: {db_path}")
    
    def _connect(self) -> None:
        """Establish database connection."""
        try:
            self._connection = duckdb.connect(self._db_path)
            logger.debug("DuckDB connection established")
        except Exception as e:
            logger.error(f"Failed to connect to DuckDB: {e}")
            raise DataIngestionError(
                message="Failed to initialize database connection",
                details={"error": str(e)},
            )
    
    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        """Get the database connection, reconnecting if necessary."""
        if self._connection is None:
            self._connect()
        return self._connection  # type: ignore
    
    @contextmanager
    def _get_cursor(self) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """
        Context manager for thread-safe cursor access.
        
        Yields:
            A DuckDB cursor for executing queries.
        """
        with self._lock:
            yield self.connection
    
    def _get_schema_name(self, session_id: str) -> str:
        """
        Get the schema name for a session.
        
        Args:
            session_id: The session identifier.
            
        Returns:
            The schema name (formatted as session_<id>).
        """
        # Sanitize session_id to be a valid SQL identifier
        safe_id = session_id.replace("-", "_").replace(" ", "_")
        return f"session_{safe_id}"
    
    def _ensure_schema(self, session_id: str) -> str:
        """
        Ensure the schema exists for a session.
        
        Args:
            session_id: The session identifier.
            
        Returns:
            The schema name.
        """
        schema_name = self._get_schema_name(session_id)
        
        with self._get_cursor() as conn:
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
        
        self._sessions.add(session_id)
        logger.debug(f"Ensured schema exists: {schema_name}")
        
        return schema_name
    
    def session_exists(self, session_id: str) -> bool:
        """
        Check if a session exists.
        
        Args:
            session_id: The session identifier.
            
        Returns:
            True if the session exists.
        """
        schema_name = self._get_schema_name(session_id)
        
        with self._get_cursor() as conn:
            result = conn.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name = ?",
                [schema_name],
            ).fetchone()
        
        return result is not None
    
    def get_tables(self, session_id: str) -> list[str]:
        """
        Get list of tables in a session.
        
        Args:
            session_id: The session identifier.
            
        Returns:
            List of table names.
            
        Raises:
            SessionNotFoundError: If session does not exist.
        """
        if not self.session_exists(session_id):
            raise SessionNotFoundError(session_id)
        
        schema_name = self._get_schema_name(session_id)
        
        with self._get_cursor() as conn:
            result = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = ?",
                [schema_name],
            ).fetchall()
        
        return [row[0] for row in result]
    
    def ingest_data(self, request: DataIngestionRequest) -> DataIngestionResponse:
        """
        Ingest data into DuckDB.
        
        Creates a table in the session schema with the specified data
        and schema definition.
        
        Args:
            request: The data ingestion request.
            
        Returns:
            Response with ingestion statistics.
            
        Raises:
            DataIngestionError: If ingestion fails.
        """
        session_id = request.session_id
        table_name = request.table_name
        
        try:
            # Ensure schema exists
            schema_name = self._ensure_schema(session_id)
            full_table_name = f"{schema_name}.{table_name}"
            
            logger.info(
                f"Ingesting data: session={session_id}, table={table_name}, "
                f"rows={len(request.data)}"
            )
            
            # Build CREATE TABLE statement
            column_defs = []
            for col in request.schema:
                col_type = col.type.to_duckdb_type()
                column_defs.append(f'"{col.name}" {col_type}')
            
            columns_sql = ", ".join(column_defs)
            
            with self._get_cursor() as conn:
                # Drop existing table to ensure fresh ingestion if replace is enabled
                if request.replace_if_exists:
                    conn.execute(f"DROP TABLE IF EXISTS {full_table_name}")
                
                # Create table
                create_sql = f"CREATE TABLE {full_table_name} ({columns_sql})"
                conn.execute(create_sql)
                logger.debug(f"Created table: {create_sql}")
                
                # Convert data to DataFrame for efficient insertion
                df = pd.DataFrame(request.data)
                
                # Ensure columns match schema order
                column_names = [col.name for col in request.schema]
                
                # Handle missing columns by adding them with None
                for col_name in column_names:
                    if col_name not in df.columns:
                        df[col_name] = None
                
                # Reorder columns to match schema
                df = df[column_names]
                
                # Insert data using efficient register + INSERT
                conn.register("temp_df", df)
                conn.execute(f"INSERT INTO {full_table_name} SELECT * FROM temp_df")
                conn.unregister("temp_df")
                
                # Get row count
                row_count = conn.execute(
                    f"SELECT COUNT(*) FROM {full_table_name}"
                ).fetchone()[0]
            
            logger.info(f"Successfully ingested {row_count} rows into {full_table_name}")
            
            return DataIngestionResponse(
                success=True,
                session_id=session_id,
                table_name=table_name,
                row_count=row_count,
                column_count=len(request.schema),
                message=f"Successfully ingested {row_count} rows into {table_name}",
            )
            
        except Exception as e:
            logger.error(f"Data ingestion failed: {e}", exc_info=True)
            raise DataIngestionError(
                message=f"Failed to ingest data: {str(e)}",
                session_id=session_id,
                details={"table_name": table_name, "error": str(e)},
            )
    
    def execute_query(
        self,
        session_id: str,
        query: str,
        params: Optional[list[Any]] = None,
    ) -> pd.DataFrame:
        """
        Execute a SQL query within a session context.
        
        The query is executed with the session schema set as the default,
        so table names don't need to be schema-qualified.
        
        Args:
            session_id: The session identifier.
            query: SQL query to execute.
            params: Optional query parameters.
            
        Returns:
            Query results as a pandas DataFrame.
            
        Raises:
            SessionNotFoundError: If session does not exist.
            DataIngestionError: If query execution fails.
        """
        if not self.session_exists(session_id):
            raise SessionNotFoundError(session_id)
        
        schema_name = self._get_schema_name(session_id)
        
        try:
            with self._get_cursor() as conn:
                # Set search path to session schema
                conn.execute(f"SET search_path = '{schema_name}'")
                
                # Execute query
                if params:
                    result = conn.execute(query, params)
                else:
                    result = conn.execute(query)
                
                # Fetch as DataFrame
                df = result.fetchdf()
                
                # Reset search path
                conn.execute("SET search_path = 'main'")
            
            logger.debug(f"Query executed: {query[:100]}... ({len(df)} rows)")
            return df
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}", exc_info=True)
            raise DataIngestionError(
                message=f"Query execution failed: {str(e)}",
                session_id=session_id,
                details={"query": query[:200], "error": str(e)},
            )
    
    def get_table_stats(self, session_id: str, table_name: str) -> dict[str, Any]:
        """
        Get statistics for a table.
        
        Args:
            session_id: The session identifier.
            table_name: The table name.
            
        Returns:
            Dictionary with table statistics.
        """
        if not self.session_exists(session_id):
            raise SessionNotFoundError(session_id)
        
        schema_name = self._get_schema_name(session_id)
        full_table_name = f"{schema_name}.{table_name}"
        
        with self._get_cursor() as conn:
            # Get row count
            row_count = conn.execute(
                f"SELECT COUNT(*) FROM {full_table_name}"
            ).fetchone()[0]
            
            # Get column info
            columns = conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = ? AND table_name = ?",
                [schema_name, table_name],
            ).fetchall()
        
        return {
            "table_name": table_name,
            "row_count": row_count,
            "column_count": len(columns),
            "columns": [{"name": c[0], "type": c[1]} for c in columns],
        }
    
    def get_data_summary(self, session_id: str) -> dict[str, Any]:
        """
        Get a summary of all data in a session.
        
        Args:
            session_id: The session identifier.
            
        Returns:
            Dictionary with session data summary.
        """
        if not self.session_exists(session_id):
            raise SessionNotFoundError(session_id)
        
        tables = self.get_tables(session_id)
        table_stats = []
        
        for table_name in tables:
            stats = self.get_table_stats(session_id, table_name)
            table_stats.append(stats)
        
        return {
            "session_id": session_id,
            "table_count": len(tables),
            "tables": table_stats,
            "total_rows": sum(t["row_count"] for t in table_stats),
        }
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its data.
        
        Args:
            session_id: The session identifier.
            
        Returns:
            True if session was deleted.
        """
        if not self.session_exists(session_id):
            return False
        
        schema_name = self._get_schema_name(session_id)
        
        with self._get_cursor() as conn:
            conn.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
        
        self._sessions.discard(session_id)
        logger.info(f"Deleted session: {session_id}")
        
        return True
    
    def save_blueprint(self, session_id: str, blueprint_json: str) -> None:
        """
        Save a dashboard blueprint to the system table.
        """
        with self._get_cursor() as conn:
            conn.execute("CREATE SCHEMA IF NOT EXISTS _system")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS _system.blueprints ("
                "session_id VARCHAR PRIMARY KEY, "
                "blueprint_json JSON, "
                "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
            conn.execute(
                "INSERT OR REPLACE INTO _system.blueprints (session_id, blueprint_json) "
                "VALUES (?, ?)",
                [session_id, blueprint_json]
            )
        logger.info(f"Saved blueprint for session: {session_id}")

    def get_blueprint(self, session_id: str) -> Optional[str]:
        """
        Retrieve a dashboard blueprint from the system table.
        """
        try:
            with self._get_cursor() as conn:
                result = conn.execute(
                    "SELECT blueprint_json FROM _system.blueprints WHERE session_id = ?",
                    [session_id]
                ).fetchone()
                return result[0] if result else None
        except Exception:
            # Table might not exist yet
            return None

    def list_blueprints(self) -> list[tuple[str, str]]:
        """
        List all saved blueprints.
        """
        try:
            with self._get_cursor() as conn:
                result = conn.execute(
                    "SELECT session_id, blueprint_json FROM _system.blueprints"
                ).fetchall()
                return result
        except Exception:
            return []

    def reset_database(self) -> bool:
        """
        Hard reset of the database: closes connection, deletes the file, and reconnects.
        """
        try:
            # 1. Close current connection
            self.close()
            
            # 2. Delete the file if it's not in-memory
            if self._db_path != ":memory:" and os.path.exists(self._db_path):
                logger.warning(f"Deleting database file: {self._db_path}")
                os.remove(self._db_path)
            
            # 3. Reconnect (this will create a fresh new file)
            self._connect()
            
            # 4. Re-initialize system tables if needed
            with self._get_cursor() as conn:
                conn.execute("CREATE SCHEMA IF NOT EXISTS _system")
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS _system.blueprints ("
                    "session_id VARCHAR PRIMARY KEY, "
                    "blueprint_json JSON, "
                    "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            
            logger.info("Database hard reset completed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reset database: {e}")
            # Try to reconnect anyway to avoid leaving the app in a broken state
            try:
                self._connect()
            except:
                pass
            return False

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.info("DuckDB connection closed")
