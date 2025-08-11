# app.py
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from modules import data_manager, ui_components, agent_manager, vector_store_manager
from sqlalchemy import inspect
import plotly.express as px


# Page config
st.set_page_config(page_title="🚀 Data Analyst Chatbot", layout="wide")

def ensure_session_state_defaults():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "generated_codes" not in st.session_state:
        st.session_state.generated_codes = []
    if "last_df" not in st.session_state:
        st.session_state.last_df = None
    if "theme" not in st.session_state:
        st.session_state.theme = "light"
    if "agent_executor" not in st.session_state:
        st.session_state.agent_executor = None
    if "engine" not in st.session_state:
        st.session_state.engine = None
    if "table_names" not in st.session_state:
        st.session_state.table_names = []

def main():
    ensure_session_state_defaults()

    # Sidebar - Controls
    with st.sidebar:
        st.title("Controls")
        st.markdown("### 1 — Data Source")
        source_type = st.radio("Select source:", ("Upload CSVs", "Connect to External Database"))

        engine = None
        table_names = []

        if source_type == "Upload CSVs":
            uploaded_files = st.file_uploader(
                "Upload CSV files", type=["csv"], accept_multiple_files=True
            )
            if uploaded_files:
                engine, table_names = data_manager.handle_csv_uploads(uploaded_files)
                st.success(f"Loaded {len(uploaded_files)} file(s).")
        else:
            st.markdown("**Connect to External DB**")
            with st.form("db_connect_form"):
                db_params = {
                    "type": st.selectbox("Database Type", ["PostgreSQL", "MySQL"]),
                    "host": st.text_input("Host", "localhost"),
                    "port": st.text_input("Port", "5432"),
                    "user": st.text_input("Username"),
                    "password": st.text_input("Password", type="password"),
                    "name": st.text_input("Database Name"),
                }
                if st.form_submit_button("Connect"):
                    engine, table_names = data_manager.handle_external_db_connection(db_params)
                    if engine:
                        st.success("Connected to database.")
                    else:
                        st.error("Connection failed. Check credentials and network.")

        # Theme toggle
        st.markdown("---")
        theme_choice = st.radio("Theme:", ("Light", "Dark"), index=0 if st.session_state.theme == "light" else 1)
        st.session_state.theme = "light" if theme_choice == "Light" else "dark"

    # If a new engine was created via upload/connect, initialize agent and persist
    if engine is not None and st.session_state.agent_executor is None:
        st.session_state.engine = engine
        st.session_state.table_names = table_names or []
        retriever_tool = vector_store_manager.create_vector_store_retriever(engine, st.session_state.table_names)
        if retriever_tool:
            with st.spinner("Initializing agent..."):
                st.session_state.agent_executor = agent_manager.initialize_agent(engine, retriever_tool)
        st.rerun()


    # Header
    title_html = """
    <h1 style="text-align:center; margin-bottom: 0.1rem;">🚀 Definitive Data Analyst Chatbot</h1>
    <p style="text-align:center; color:gray; margin-top:0.1rem;">Upload • Explore • Visualize • Query with natural language</p>
    <hr style="margin-top: 0.5rem; margin-bottom: 1.0rem;">
    """
    st.markdown(title_html, unsafe_allow_html=True)

    # If agent ready show tabs; otherwise prompt configuration
    if st.session_state.agent_executor:
        st.success("✅ Agent is Ready — ask questions or run EDA below.")

        tabs = st.tabs(["📊 Automated EDA", "📈 Visualizations", "💬 Chat", "⚙️ Settings"])
        with tabs[0]:
            ui_components.display_automated_eda(st.session_state.engine, st.session_state.table_names)
        with tabs[1]:
            ui_components.display_quick_visualizer(st.session_state.engine, st.session_state.table_names)
        with tabs[2]:
            ui_components.display_chat_interface()
        with tabs[3]:
            ui_components.display_settings()
    else:
        st.info("Select and configure a data source via the sidebar to get started.")
        # show a compact sample area so UI doesn't look empty
        st.markdown("### Quick start")
        st.markdown("- Upload one or more CSVs in the sidebar, or connect to Postgres/MySQL.")
        st.markdown("- After loading, the agent will initialize automatically.")

if __name__ == "__main__":
    main()
