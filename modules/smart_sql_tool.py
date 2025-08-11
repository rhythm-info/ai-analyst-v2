# modules/smart_sql_tool.py
from langchain.tools import BaseTool
from pydantic import Field
from langchain_community.utilities import SQLDatabase
import pandas as pd
import streamlit as st
import time
import uuid
import re
from typing import Any, Optional


class SmartSQLQueryTool(BaseTool):
    """
    Tool that can:
      - Execute SQL queries against a connected SQLDatabase and display results in Streamlit.
      - Store agent-generated Python code blocks (for plotting/EDA) so the UI can display them
        with a Run button (execution happens in the UI context, not automatically here).

    Usage:
        db = SQLDatabase.from_uri("postgresql+psycopg2://user:pass@host/db")
        tool = SmartSQLQueryTool(db=db)
    """

    name: str = "smart_sql_query"
    description: str = (
        "Executes SQL queries or stores agent-generated Python plotting code. "
        "SQL is executed immediately and results are stored in `st.session_state['last_df']`. "
        "Non-SQL text is treated as Python code and stored for manual execution via the UI."
    )

    db: SQLDatabase = Field(..., description="Connected SQLDatabase instance")
    # safety limits (can be tuned)
    max_rows: int = 10000
    safe_preview_rows: int = 100


    def _is_sql(self, text: str) -> bool:
        """
        Heuristic to decide whether `text` is SQL.
        """
        if not text:
            return False
        t = text.strip().lower()
        sql_starts = ("select", "with", "show", "describe", "pragma")
        if t.startswith(sql_starts) or " from " in t:
            return True
        return False

    def _get_engine(self) -> Optional[Any]:
        """
        Try to obtain a SQLAlchemy engine from the SQLDatabase wrapper.
        """
        db = self.db
        for attr in ("_engine", "engine", "conn", "connection"):
            if hasattr(db, attr):
                return getattr(db, attr)
        if hasattr(db, "get_engine") and callable(getattr(db, "get_engine")):
            return db.get_engine()
        return None

    def _clean_sql(self, sql: str) -> str:
        """
        Remove trailing unwanted annotation or metadata from the SQL query.
        Example: Remove 'LIMIT annotation=...' text if it appears.
        """
        # Remove any 'LIMIT annotation=...' or similar appended metadata
        cleaned_sql = re.sub(r"LIMIT annotation=.*$", "", sql, flags=re.IGNORECASE).strip()
        return cleaned_sql

    def _run(self, query_or_code: str):
        """
        Execute SQL (if detected) or store Python code to session_state for execution via UI.
        Returns a compact summary for the agent.
        """
        text = (query_or_code or "").strip()
        if not text:
            return "No SQL or code provided."

        try:
            if self._is_sql(text):
                engine = self._get_engine()
                if engine is None:
                    return "Error: could not obtain SQL engine from the provided SQLDatabase (db)."

                # Clean the SQL query from invalid appended annotations
                clean_text = self._clean_sql(text)

                lower = clean_text.lower()
                text_limited = clean_text
                if lower.startswith("select") and " limit " not in lower and self.max_rows:
                    text_limited = f"{clean_text} LIMIT {self.max_rows}"

                df = pd.read_sql_query(text_limited, con=engine)

                st.session_state["last_df"] = df

                st.write("### Executed SQL")
                st.code(clean_text, language="sql")
                st.write(f"Returned **{len(df):,}** row(s). Showing first {min(self.safe_preview_rows, len(df))} rows.")
                pd.set_option("display.max_columns", None)
                pd.set_option("display.max_colwidth", None)
                st.dataframe(df.head(self.safe_preview_rows), use_container_width=True)

                return {"rows": len(df), "columns": list(df.columns)}

            else:
                if "generated_codes" not in st.session_state:
                    st.session_state["generated_codes"] = []

                code_id = f"code_{int(time.time())}_{uuid.uuid4().hex[:6]}"
                entry = {"id": code_id, "code": text}
                st.session_state["generated_codes"].append(entry)

                st.write("### Agent-generated Python code (stored)")
                st.code(text, language="python")
                st.info("This code is stored and can be executed by clicking Run in the UI. The variable `df` (last query result) will be available when you run it.")

                return {"status": "stored", "id": code_id}

        except Exception as e:
            st.error(f"Error executing tool: {e}")
            return f"Error executing tool: {e}"


    async def _arun(self, query_or_code: str):
        raise NotImplementedError("Async execution is not supported by SmartSQLQueryTool.")
