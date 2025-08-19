# streamlit_logger.py
import logging
import streamlit as st

class StreamlitLoggerHandler(logging.Handler):
    def emit(self, record):
        if "logs" not in st.session_state:
            st.session_state["logs"] = []
        msg = self.format(record)
        st.session_state["logs"].append(msg)

# Function to set up logger
def setup_streamlit_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Avoid adding multiple handlers
    if not any(isinstance(h, StreamlitLoggerHandler) for h in logger.handlers):
        handler = StreamlitLoggerHandler()
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
