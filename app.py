# app.py

import streamlit as st
import os
import io
import sys
import pandas as pd
from contextlib import contextmanager
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

# LangChain imports
from langchain_community.utilities import SQLDatabase
from langchain_groq import ChatGroq
from langchain_community.agent_toolkits import create_sql_agent # Removed SQL_FUNCTIONS_AGENT_PROMPT from import
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


# --- IMPORTANT: Groq API Key ---
# For a production app, this should ideally be managed via Streamlit secrets
# (st.secrets.GROQ_API_KEY) or environment variables, not hardcoded.

if "GROQ_API_KEY" not in os.environ:
    st.error("GROQ_API_KEY environment variable not set.")
    st.info("Please set it in your terminal before running Streamlit, or hardcode it for this demo.")
    st.stop()

# --- Streamlit UI Setup ---
st.set_page_config(page_title="Versatile Data Analyst Chatbot", layout="centered")
st.title("📊 Versatile Data Analyst Chatbot")
st.markdown("Choose your data source: upload CSVs or connect to an external database. Ask questions in natural language!")

# --- Cache & Session State Clearing Function ---
# This button helps clear Streamlit's cache and session state for a clean reset.
def clear_all_state():
    st.cache_resource.clear() # Clears cached database engines/agents
    st.session_state.clear()  # Clears all session state variables
    st.success("App state reset! Please re-select your data source and re-upload/re-connect.")

st.sidebar.button("Clear App State & Reset", on_click=clear_all_state)

# --- Data Source Selection ---
st.sidebar.markdown("---")
st.sidebar.markdown("### Choose Data Source")
data_source_option = st.sidebar.radio(
    "Select your data source type:",
    ("Upload CSVs", "Connect to External Database"),
    key="data_source_option" # Use a key for the radio button state
)

# --- Function to initialize agent from CSVs ---
def initialize_agent_from_csvs(files):
    """Initializes the database and LangChain agent from uploaded CSV files."""
    try:
        engine = create_engine("sqlite:///:memory:")
        
        created_table_names = []
        for uploaded_file in files:
            csv_data = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
            df = pd.read_csv(csv_data)
            
            # Sanitize filename to create a valid SQL table name
            table_name = os.path.splitext(uploaded_file.name)[0]
            table_name = ''.join(c if c.isalnum() else '_' for c in table_name).lower()
            
            # Ensure table name is valid and unique if necessary
            if not table_name or table_name[0].isdigit():
                table_name = "csv_data_" + table_name
            if len(table_name) > 60: # SQLite max identifier length can be around 64
                table_name = table_name[:60]
            
            # Add a numerical suffix if table name already exists (simple uniqueness)
            original_table_name = table_name
            counter = 1
            while table_name in created_table_names:
                table_name = f"{original_table_name}_{counter}"
                counter += 1

            try:
                df.to_sql(table_name, engine, index=False, if_exists="replace")
                created_table_names.append(table_name)
            except SQLAlchemyError as sqla_err:
                st.error(f"Failed to create SQL table from '{uploaded_file.name}': {sqla_err}")
                return None, None
            except Exception as e:
                st.error(f"An unexpected error occurred while writing '{uploaded_file.name}' to SQL: {e}")
                return None, None
        
        if not created_table_names:
            st.warning("No valid CSV files were processed into tables.")
            return None, None

        st.info(f"CSV data loaded into in-memory tables: **`{', '.join(created_table_names)}`**.")
        st.session_state['current_table_names'] = created_table_names

        # SQLDatabase object automatically gets schema (columns, types)
        # and sample rows from the tables specified in include_tables.
        db = SQLDatabase(
            engine,
            include_tables=st.session_state['current_table_names'],
            sample_rows_in_table_info=3 # Provides some sample data for the LLM
        )
        llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)
        
        # The agent's default prompt will incorporate db.get_table_info()
        agent_executor = create_sql_agent(llm=llm, db=db, agent_type="openai-tools", verbose=True)

        return db, agent_executor
    except Exception as e:
        st.error(f"An overall error occurred during CSV processing: {e}")
        st.error("Please ensure your CSV files are valid and well-formatted.")
        return None, None

# --- Function to initialize agent from external DB ---
def initialize_agent_from_external_db(db_type, db_host, db_port, db_user, db_password, db_name):
    """Initializes the database connection and the LangChain agent for an external DB."""
    try:
        if db_type == "PostgreSQL":
            driver = "psycopg2"
            conn_string = f"postgresql+{driver}://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        elif db_type == "MySQL":
            driver = "pymysql"
            conn_string = f"mysql+{driver}://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        elif db_type == "SQL Server":
            driver = "pyodbc"
            conn_string = f"mssql+{driver}://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?trusted_connection=yes&driver=ODBC+Driver+17+for+SQL+Server"
        else:
            st.error("Unsupported database type selected.")
            return None, None

        st.info(f"Attempting to connect to {db_type} at {db_host}:{db_port}...")
        engine = create_engine(conn_string)

        # Test the connection and get table names dynamically
        inspector = inspect(engine)
        table_names_from_db = inspector.get_table_names() # This gets ALL table names dynamically
        
        if not table_names_from_db:
            st.warning("No tables found in the connected database. Please ensure your database has data.")
            return None, None

        st.success("Connection to external database successful!")
        st.info(f"Connected to tables: **`{', '.join(table_names_from_db)}`**.")
        st.session_state['current_table_names'] = sorted(table_names_from_db) # Store sorted list

        # --- DYNAMIC SCHEMA: SQLDatabase object automatically gets schema ---
        # The SQLDatabase object will inspect the connected 'engine'
        # and retrieve table names, column names, data types, and sample rows.
        db = SQLDatabase(
            engine,
            include_tables=st.session_state['current_table_names'], # Dynamically include all found tables
            sample_rows_in_table_info=3 # Provides some sample data for the LLM
        )
        
        llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

        # --- DYNAMIC PROMPT: Agent automatically incorporates schema ---
        # The `create_sql_agent` is designed to automatically inject the
        # database schema information (from the `db` object) into its prompt.
        # A simple, direct system message often works best here.
        SYSTEM_PROMPT = """
        You are an expert at writing and executing SQL queries for data analysis.
        Your goal is to answer user questions by generating correct, efficient, and safe SQL queries.
        Always execute the query and provide the final result in a clear, concise natural language sentence.
        If you cannot answer the question with the provided tables, state that you cannot.
        """

        # LangChain's create_sql_agent implicitly builds a prompt that includes
        # table names and schema information from the `db` object.
        # We provide a simple system message and let the agent handle the rest.
        agent_executor = create_sql_agent(
            llm=llm,
            db=db,
            agent_type="openai-tools",
            verbose=True,
            handle_parsing_errors=True,
            # We explicitly pass the system message to the prompt.
            # The agent will then add its own context (table info, tools) around this.
            prompt=ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
                ("user", "{input}"),
            ])
        )
        
        return db, agent_executor
    except SQLAlchemyError as e:
        st.error(f"A database connection error occurred: {e}")
        st.error("Please check your credentials, database host/port, and ensure the database is running and accessible.")
        return None, None
    except Exception as e:
        st.error(f"An unexpected error occurred during agent initialization: {e}")
        return None, None

# --- Context manager to capture stdout (for verbose agent output) ---
@contextmanager
def st_stdout_redirect(item):
    old_stdout = sys.stdout
    sys.stdout = captured_output = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old_stdout
        item.code(captured_output.getvalue())

# --- Main Application Logic ---
# Initialize db and agent_executor to None at the start of each Streamlit run
# They will be populated based on user interaction and session state.
db, agent_executor = None, None

# Handle data source selection and agent initialization
if data_source_option == "Upload CSVs":
    uploaded_files = st.file_uploader("Upload your CSV (.csv) files", type=["csv"], accept_multiple_files=True)
    if uploaded_files:
        # Check if CSVs have changed or if agent needs re-initialization
        current_file_hashes = hash(tuple(f.name for f in uploaded_files))
        if 'db_csv_initialized' not in st.session_state or st.session_state.get('uploaded_file_hashes') != current_file_hashes:
            st.session_state['db_csv_initialized'] = True
            st.session_state['uploaded_file_hashes'] = current_file_hashes
            db, agent_executor = initialize_agent_from_csvs(uploaded_files)
            st.session_state['db'] = db
            st.session_state['agent_executor'] = agent_executor
        else:
            # Retrieve from session state if already initialized
            db = st.session_state.get('db')
            agent_executor = st.session_state.get('agent_executor')
            if db and agent_executor:
                st.success("Using previously loaded CSV data.")
                st.info(f"Connected to tables: **`{', '.join(st.session_state.get('current_table_names', []))}`**.")

elif data_source_option == "Connect to External Database":
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Database Credentials")
    with st.sidebar.form("db_connect_form"):
        db_type = st.selectbox("Database Type", ["PostgreSQL", "MySQL", "SQL Server"], index=0, key="db_type_select")
        db_host = st.text_input("Host", "localhost", key="db_host_input")
        db_port = st.text_input("Port", "5433", key="db_port_input")
        db_user = st.text_input("Username", "my_app_user", key="db_user_input")
        db_password = st.text_input("Password", type="password", key="db_password_input")
        db_name = st.text_input("Database Name", "my_app_db", key="db_name_input")
        
        connect_button = st.form_submit_button("Connect to Database")

    if connect_button:
        # Re-initialize on connect button click
        db, agent_executor = initialize_agent_from_external_db(db_type, db_host, db_port, db_user, db_password, db_name)
        st.session_state['db'] = db
        st.session_state['agent_executor'] = agent_executor
        st.session_state['db_external_initialized'] = True
    elif st.session_state.get('db_external_initialized') and st.session_state.get('db') and st.session_state.get('agent_executor'):
        # If already connected from a previous run, retrieve from session_state
        db = st.session_state['db']
        agent_executor = st.session_state['agent_executor']
        st.success("Using previously connected external database.")
        st.info(f"Connected to tables: **`{', '.join(st.session_state.get('current_table_names', []))}`**.")

if st.session_state.get('db') and st.session_state.get('agent_executor'):
    db = st.session_state['db']
    agent_executor = st.session_state['agent_executor']

    st.subheader("Database Schema:")
    try:
        st.code(db.get_table_info()) # This dynamically gets and displays the schema
    except Exception as e:
        st.warning(f"Could not retrieve schema info: {e}")
        st.info("Ensure your database is accessible and has tables.")

    st.subheader("Ask your question:")
    user_question = st.text_area("Enter your natural language query here:", height=100)

    if st.button("Get Answer"):
        if user_question:
            with st.spinner("Thinking..."):
                with st.expander("Agent's Thought Process (Verbose Output)"):
                    with st_stdout_redirect(st):
                        try:
                            response = agent_executor.invoke({"input": user_question})
                            st.subheader("Agent's Final Answer:")
                            st.success(response["output"])
                        except Exception as e:
                            st.error(f"An error occurred during query execution: {e}")
                            st.info("Please check your question or the database schema/connection.")
        else:
            st.warning("Please enter a question.")
else:
    st.info("Please select a data source option and follow the instructions to get started.")