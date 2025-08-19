import logging
from langchain.tools import BaseTool
from pydantic import Field
from langchain_community.utilities import SQLDatabase
import pandas as pd
import streamlit as st
import time
import uuid
import re
from typing import Any, Optional

# ---------- Configure Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

# ---------- Helper to log AI query events ----------
def log_ai_event(message: str):
    timestamp = time.strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    if "logs" not in st.session_state:
        st.session_state["logs"] = []
    st.session_state["logs"].append(log_entry)
    logging.info(message)

class SmartSQLQueryTool(BaseTool):
    """
    Tool for executing SQL queries against a connected database
    and storing Python code for later execution in the UI.
    """

    name: str = "smart_sql_query"
    description: str = (
        "Executes SQL queries against a database and displays results, "
        "or stores Python code for later execution."
    )

    db: SQLDatabase = Field(..., description="Connected SQLDatabase instance")
    max_rows: int = 10000
    safe_preview_rows: int = 100

    # ---------- Utility Methods ----------
    def _is_sql(self, text: str) -> bool:
        log_ai_event("Entered _is_sql()")
        if not text:
            return False
        t = text.strip().lower()
        sql_starts = ("select", "with", "show", "describe", "pragma", "insert", "update", "delete")
        result = t.startswith(sql_starts) or " from " in t
        log_ai_event(f"_is_sql() result: {result}")
        return result

    def _get_engine(self) -> Optional[Any]:
        log_ai_event("Entered _get_engine()")
        for attr in ("_engine", "engine", "conn", "connection"):
            if hasattr(self.db, attr):
                log_ai_event(f"_get_engine(): found engine via '{attr}'")
                return getattr(self.db, attr)
        if hasattr(self.db, "get_engine") and callable(self.db.get_engine):
            log_ai_event("_get_engine(): found engine via get_engine()")
            return self.db.get_engine()
        log_ai_event("_get_engine(): no engine found")
        return None

    def _clean_sql(self, sql: str) -> str:
        log_ai_event("Entered _clean_sql()")
        cleaned = re.sub(r"LIMIT annotation=.*$", "", sql, flags=re.IGNORECASE).strip()
        log_ai_event(f"_clean_sql() result: {cleaned}")
        return cleaned

    def _execute_sql(self, sql: str):
        log_ai_event("Entered _execute_sql()")
        try:
            engine = self._get_engine()
            if engine is None:
                raise RuntimeError("Could not obtain SQL engine from SQLDatabase.")

            clean_sql = self._clean_sql(sql)
            lower_sql = clean_sql.lower()
            if lower_sql.startswith("select") and " limit " not in lower_sql:
                clean_sql += f" LIMIT {self.max_rows}"

            st.session_state["last_sql"] = clean_sql
            log_ai_event(f"Executing SQL:\n{clean_sql}")

            df = pd.read_sql_query(clean_sql, con=engine)
            st.session_state["last_df"] = df

            # Render in UI
            st.write("### Executed SQL Result")
            st.dataframe(df, use_container_width=True)
            st.code(clean_sql, language="sql")

            log_ai_event(f"SQL executed successfully, {len(df)} row(s) returned.")

            return {
                "status": "success",
                "rows": len(df),
                "columns": list(df.columns),
                "query": clean_sql,
                "data": df.to_dict(orient="records")  # actual data for chat output
            }

        except Exception as e:
            log_ai_event(f"Error in _execute_sql(): {e}")
            st.error(f"Error executing SQL: {e}")
            return {"status": "error", "message": str(e)}

    def _store_python_code(self, code: str):
        log_ai_event("Entered _store_python_code()")
        if "generated_codes" not in st.session_state:
            st.session_state["generated_codes"] = []

        code_id = f"code_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        st.session_state["generated_codes"].append({"id": code_id, "code": code})

        st.write("### Agent-generated Python code (stored)")
        st.code(code, language="python")
        st.info("You can run this code manually in the UI.")

        return {"status": "stored", "id": code_id}

    # ---------- Main Execution ----------
    def _run(self, query_or_code: str):
        log_ai_event("Entered _run()")
        text = (query_or_code or "").strip()
        if not text:
            log_ai_event("No SQL or Python code provided.")
            return {"status": "error", "message": "No SQL or Python code provided."}

        if self._is_sql(text):
            return self._execute_sql(text)
        else:
            return self._store_python_code(text)

    async def _arun(self, query_or_code: str):
        raise NotImplementedError("Async execution not supported.")
