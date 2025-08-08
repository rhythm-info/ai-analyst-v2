# modules/ui_components.py

import streamlit as st
import pandas as pd
from sqlalchemy import inspect
import re
import json
import plotly.graph_objects as go


def display_chat_interface():
    """
    Displays the chat interface and handles the agent interaction loop,
    including rendering of interactive Plotly charts.
    """
    st.subheader("💬 Chat with your Data")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display previous messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("plot_json"):
                try:
                    fig = go.Figure(json.loads(message["plot_json"]))
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Error rendering plot: {e}")

    # New user input
    if prompt := st.chat_input("Ask for analysis, plots, or insights..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    agent_executor = st.session_state.agent_executor
                    chat_history = [
                        {"role": msg["role"], "content": msg["content"]}
                        for msg in st.session_state.messages
                    ]

                    response = agent_executor.invoke({
                        "input": prompt,
                        "chat_history": chat_history
                    })

                    answer = response.get("output", "I couldn't find an answer.")
                    plot_json = None

                    # Extract Plotly JSON
                    plot_match = re.search(r"\[PLOTLY_JSON\](.*?)\[/PLOTLY_JSON\]", answer, re.DOTALL)
                    if plot_match:
                        plot_json_str = plot_match.group(1).strip()
                        plot_json = json.loads(plot_json_str)
                        answer = re.sub(r"\[PLOTLY_JSON\].*?\[/PLOTLY_JSON\]", "", answer, flags=re.DOTALL).strip()

                    st.markdown(answer)
                    if plot_json:
                        fig = go.Figure(plot_json)
                        st.plotly_chart(fig, use_container_width=True)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "plot_json": json.dumps(plot_json) if plot_json else None
                    })

                except Exception as e:
                    error_message = f"An error occurred: {e}"
                    st.error(error_message)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_message
                    })


def display_automated_eda(engine, table_names):
    """
    Displays expandable EDA summaries for each table.
    """
    st.subheader("🤖 Automated Data Insights (EDA)")
    inspector = inspect(engine)
    for table_name in table_names:
        with st.expander(f"Insights for table: `{table_name}`"):
            try:
                df = pd.read_sql_table(table_name, engine)
                st.markdown("#### Basic Information")
                st.write(f"- **Total Rows:** {len(df)}")
                st.write(f"- **Columns:** {', '.join([f'`{col}`' for col in df.columns])}")

                st.markdown("#### Descriptive Statistics (Numerical Columns)")
                stats = df.describe()
                if not stats.empty:
                    st.dataframe(stats)
                else:
                    st.info("No numerical columns found.")
            except Exception as e:
                st.warning(f"Could not run EDA for `{table_name}`: {e}")
