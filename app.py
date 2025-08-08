# app.py

import streamlit as st
from modules import data_manager, ui_components, agent_manager, vector_store_manager
from sqlalchemy import inspect
import pandas as pd

def main():
    """
    Main function to run the Streamlit application.
    Orchestrates the UI, data loading from multiple sources, and agent initialization.
    """
    st.set_page_config(page_title="Data Analyst Chatbot", layout="wide")
    st.title("🚀 The Definitive Data Analyst Chatbot")

    st.sidebar.title("Controls")
    
    # --- Data Source Selection ---
    st.sidebar.header("1. Choose Data Source")
    source_type = st.sidebar.radio("Select source:", ("Upload CSVs", "Connect to External Database"))

    engine = None
    table_names = []

    if source_type == "Upload CSVs":
        st.sidebar.subheader("Upload Files")
        uploaded_files = st.sidebar.file_uploader("Upload one or more CSV files", type=["csv"], accept_multiple_files=True)
        if uploaded_files:
            engine, table_names = data_manager.handle_csv_uploads(uploaded_files)
    
    elif source_type == "Connect to External Database":
        st.sidebar.subheader("Database Credentials")
        with st.sidebar.form("db_connect_form"):
            db_params = {
                'type': st.selectbox("Database Type", ["PostgreSQL", "MySQL"]),
                'host': st.text_input("Host", "localhost"),
                'port': st.text_input("Port", "5432"),
                'user': st.text_input("Username"),
                'password': st.text_input("Password", type="password"),
                'name': st.text_input("Database Name"),
            }
            if st.form_submit_button("Connect"):
                engine, table_names = data_manager.handle_external_db_connection(db_params)

    # --- Agent Initialization and UI Display ---
    if engine is not None and 'agent_executor' not in st.session_state:
        st.session_state.engine = engine
        st.session_state.table_names = table_names
        
        retriever_tool = vector_store_manager.create_vector_store_retriever(engine, table_names)
        
        if retriever_tool:
            with st.spinner("Initializing agent... This may take a moment."):
                st.session_state.agent_executor = agent_manager.initialize_agent(engine, retriever_tool)
        st.rerun()

    if 'agent_executor' in st.session_state and st.session_state.agent_executor:
        st.header("✅ Agent is Ready")
        st.info("You can now ask questions about your data in the chat window below.")
        
        ui_components.display_automated_eda(st.session_state.engine, st.session_state.table_names)
        ui_components.display_chat_interface()
    else:
        st.info("Select and configure a data source via the sidebar to get started.")

if __name__ == "__main__":
    main()
