# modules/data_manager.py

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError
import os

DB_FILE_PATH = "temp_csv_db.sqlite"

def handle_csv_uploads(uploaded_files):
    """
    Processes multiple uploaded CSV files, creates a unified SQLite database,
    and returns the database engine and table names.
    """
    if not uploaded_files:
        st.info("Please upload one or more CSV files to begin.")
        return None, None

    if os.path.exists(DB_FILE_PATH):
        os.remove(DB_FILE_PATH)
    
    engine = create_engine(f"sqlite:///{DB_FILE_PATH}")
    
    created_table_names = []
    with st.spinner("Processing CSV files..."):
        for uploaded_file in uploaded_files:
            try:
                table_name = os.path.splitext(uploaded_file.name)[0]
                table_name = ''.join(e for e in table_name if e.isalnum() or e == '_').lower()

                df = pd.read_csv(uploaded_file)
                df.to_sql(table_name, engine, index=False, if_exists="replace")
                created_table_names.append(table_name)
                st.success(f"Successfully loaded '{uploaded_file.name}' into table `{table_name}`.")
            
            except Exception as e:
                st.error(f"An error occurred while processing '{uploaded_file.name}': {e}")
                return None, None

    if not created_table_names:
        st.warning("No tables were created. Please check your CSV files.")
        return None, None

    return engine, created_table_names

def handle_external_db_connection(db_params):
    """
    Connects to an external database using provided credentials.

    Args:
        db_params (dict): A dictionary containing database connection details.

    Returns:
        tuple: A tuple containing the SQLAlchemy engine and a list of table names,
               or (None, None) if an error occurs.
    """
    try:
        db_type = db_params['type']
        if db_type == "PostgreSQL":
            driver = "psycopg2"
            conn_str = f"postgresql+{driver}://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{db_params['name']}"
        elif db_type == "MySQL":
            driver = "pymysql"
            conn_str = f"mysql+{driver}://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{db_params['name']}"
        else:
            st.error(f"Database type '{db_type}' is not currently supported.")
            return None, None

        with st.spinner(f"Attempting to connect to {db_type}..."):
            engine = create_engine(conn_str)
            with engine.connect():
                st.success("Connection to external database successful!")
            
            inspector = inspect(engine)
            table_names = inspector.get_table_names()
            
            if not table_names:
                st.warning("No tables were found in the connected database.")
                return None, None
        
        return engine, sorted(table_names)
        
    except SQLAlchemyError as e:
        st.error(f"Database connection error: {e}")
        st.error("Please check your credentials, host/port, firewall rules, and ensure the database is running.")
        return None, None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None, None
