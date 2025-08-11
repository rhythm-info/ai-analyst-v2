import streamlit as st
import pandas as pd
import re
import json
import plotly.graph_objects as go

# Import plotly express globally for all functions
try:
    import plotly.express as px
except ImportError:
    px = None
    st.error("Plotly Express is not installed. Please install with `pip install plotly`.")

# --- Helpers ---
def _plot_template():
    return "plotly_dark" if st.session_state.get("theme", "light") == "dark" else "plotly_white"

def render_plotly_from_marker(text: str):
    """Extract [PLOTLY_JSON] blocks and render them."""
    import plotly.io as pio
    pattern = r"\[PLOTLY_JSON\](.*?)\[/PLOTLY_JSON\]"
    matches = re.findall(pattern, text, re.DOTALL)
    cleaned = re.sub(pattern, "", text, flags=re.DOTALL).strip()
    if cleaned:
        st.markdown(cleaned)
    for block in matches:
        try:
            fig = pio.from_json(block)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Failed to render plot: {e}")

# --- EDA UI ---
def display_automated_eda(engine, table_names):
    st.header("📊 Automated EDA")
    if not table_names:
        st.info("No tables available. Upload a CSV or connect to a database in the sidebar.")
        return

    selected_table = st.selectbox("Select a table for EDA:", table_names)
    if not selected_table:
        return

    try:
        df = pd.read_sql_table(selected_table, con=engine)
    except Exception as e:
        st.error(f"Failed to read table `{selected_table}`: {e}")
        return

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rows", f"{len(df):,}")
    col2.metric("Columns", f"{len(df.columns):,}")
    col3.metric("Missing", f"{df.isna().sum().sum():,}")
    col4.metric("Unique (sample)", df.nunique().sum())

    # Expanders
    with st.expander("Preview — First 5 rows", expanded=True):
        st.dataframe(df.head(), use_container_width=True)

    with st.expander("Data Types & Missing"):
        st.dataframe(pd.DataFrame({"dtype": df.dtypes.astype(str), "missing": df.isnull().sum()}))

    with st.expander("Summary Statistics"):
        st.dataframe(df.describe(include="all").T, use_container_width=True)

    with st.expander("Quick Visualization"):
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        categorical_cols = df.select_dtypes(exclude="number").columns.tolist()

        if not px:
            st.error("Plotly Express not available for plotting.")
            return

        if not numeric_cols and not categorical_cols:
            st.info("No columns available to plot.")
        else:
            left, right = st.columns(2)
            with left:
                x_col = st.selectbox("X axis", df.columns, index=0)
            with right:
                y_col_options = ["count"] + numeric_cols
                y_col = st.selectbox("Y axis (or 'count')", y_col_options, index=0)

            if st.button("Generate Plot"):
                if y_col == "count":
                    plot_df = df.groupby(x_col).size().reset_index(name="count")
                    y = "count"
                else:
                    plot_df = df.copy()
                    y = y_col

                fig = px.bar(plot_df, x=x_col, y=y, title=f"{y} by {x_col}", template=_plot_template())
                st.plotly_chart(fig, use_container_width=True)

    # Generated code runner
    gen_codes = st.session_state.get("generated_codes", [])
    if gen_codes:
        with st.expander("Agent Generated Code — Ready to Run", expanded=False):
            for entry in gen_codes:
                st.code(entry["code"], language="python")
                run_key = f"run_{entry['id']}"
                if st.button("▶ Run this code", key=run_key):
                    last_df = st.session_state.get("last_df", df)
                    local_vars = {"df": last_df, "pd": pd, "st": st, "px": px}
                    try:
                        exec(entry["code"], {"__name__": "__main__"}, local_vars)
                    except Exception as e:
                        st.exception(e)

    # Download
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download table CSV", csv_bytes, file_name=f"{selected_table}.csv")


# --- Quick Visualizer Tab ---

def display_quick_visualizer(engine, table_names):
    st.header("📈 Quick Visualizer")
    if not table_names:
        st.info("No tables available. Upload a CSV or connect to a database in the sidebar.")
        return

    selected_table = st.selectbox("Select a table to visualize:", table_names, key="viz_table_select")
    try:
        df = pd.read_sql_table(selected_table, con=engine)
    except Exception as e:
        st.error(f"Failed to read table `{selected_table}`: {e}")
        return

    st.markdown("**Choose chart type and columns**")
    chart_type = st.selectbox("Chart type", ["bar", "line", "scatter", "histogram", "pie"])
    cols = df.columns.tolist()

    if chart_type == "histogram":
        x = st.selectbox("Column (x)", cols)
        if st.button("Plot histogram"):
            fig = px.histogram(df, x=x, title=f"Histogram of {x}", template=_plot_template())
            st.plotly_chart(fig, use_container_width=True)
    elif chart_type == "pie":
        names = st.selectbox("Names (categories)", cols)
        values = st.selectbox("Values (numeric)", df.select_dtypes(include="number").columns.tolist())
        if st.button("Plot pie"):
            fig = px.pie(df, names=names, values=values, title=f"{values} by {names}", template=_plot_template())
            st.plotly_chart(fig, use_container_width=True)
    else:
        x = st.selectbox("X", cols)
        y = st.selectbox("Y", df.select_dtypes(include="number").columns.tolist() or cols)
        if st.button("Generate plot"):
            if chart_type == "bar":
                fig = px.bar(df, x=x, y=y, title=f"{y} vs {x}", template=_plot_template())
            elif chart_type == "line":
                fig = px.line(df, x=x, y=y, title=f"{y} vs {x}", template=_plot_template())
            else:
                fig = px.scatter(df, x=x, y=y, title=f"{y} vs {x}", template=_plot_template())
            st.plotly_chart(fig, use_container_width=True)

# --- Chat UI ---

def display_chat_interface():
    st.header("💬 Chat with your Data")

    # Clear chat control in a sidebar-like layout within the tab
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.session_state.generated_codes = []
        st.rerun()

    # 1. Display all messages from the session state history
    # This loop is now the single source of truth for rendering.
    for msg in st.session_state.get("messages", []):
        with st.chat_message(msg["role"]):
            content = msg.get("content", "")
            # The helper function is called here for any assistant message containing a plot
            if msg["role"] == "assistant" and "[PLOTLY_JSON]" in content:
                render_plotly_from_marker(content)
            else:
                st.markdown(content)

    # 2. Handle new user input at the bottom
    if prompt := st.chat_input("Ask the agent to analyze, query or plot"):
        # Add user's message to state and display it immediately
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Get the agent's response
        with st.spinner("Thinking..."):
            try:
                agent_executor = st.session_state.agent_executor
                chat_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                
                # Invoke the agent
                response = agent_executor.invoke({"input": prompt, "chat_history": chat_history})
                answer = response.get("output") if isinstance(response, dict) else str(response)

                # 3. Add the agent's full response (including plot JSON) to the state
                st.session_state.messages.append({"role": "assistant", "content": answer})

            except Exception as e:
                error_message = f"An error occurred: {e}"
                st.session_state.messages.append({"role": "assistant", "content": error_message})

        # 4. Trigger a rerun to display the new messages
        # This will cause the script to run from the top, and the loop above will render the new messages.
        st.rerun()
# --- Settings tab ---

def display_settings():
    st.header("⚙️ Settings")
    st.markdown("Manage environment & safety settings")

    st.markdown("**Execution safety**")
    st.checkbox("Allow agent-generated code execution", value=True, key="allow_code_exec")
    st.markdown("**Note:** Executing arbitrary code can be dangerous — run only in trusted environments.")

