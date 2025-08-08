import io
import pandas as pd
import plotly.express as px
from sqlalchemy import Engine
from langchain_groq import ChatGroq
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import StructuredTool
from pydantic import BaseModel
from typing import Optional
from modules.plot_registry import get_plot_function

# --- Pydantic Schemas ---

class TableOnlyInput(BaseModel):
    table_name: str

class CountCategoricalInput(BaseModel):
    table_name: str
    column_name: str

class CreateInteractivePlotInput(BaseModel):
    table_name: str
    plot_type: str
    x: str
    y: Optional[str] = None
    color: Optional[str] = None

class YearlyPlotInput(BaseModel):
    table_name: str
    date_column: str

# --- Core Analytics ---

def get_data_summary(engine: Engine, table_name: str) -> str:
    try:
        df = pd.read_sql_table(table_name, con=engine)
        info_buf = io.StringIO()
        df.info(verbose=False, buf=info_buf)
        info_str = info_buf.getvalue()
        desc_str = df.describe().to_string()
        missing_values = df.isnull().sum()
        missing_df = missing_values[missing_values > 0].reset_index()
        missing_str = "No missing values found."
        if not missing_df.empty:
            missing_df.columns = ['Column', 'Missing Count']
            missing_str = f"Missing Values:\n{missing_df.to_string(index=False)}"
        return (
            f"Data Summary for table `{table_name}`:\n\n"
            f"--- Data Types and Info ---\n{info_str}\n\n"
            f"--- Descriptive Statistics ---\n{desc_str}\n\n"
            f"--- Missing Values ---\n{missing_str}"
        )
    except Exception as e:
        return f"Error during analysis: {e}"

def count_categorical_variable(engine: Engine, table_name: str, column_name: str) -> str:
    try:
        df = pd.read_sql_table(table_name, con=engine)
        if column_name not in df.columns:
            return f"Error: Column '{column_name}' not found in table '{table_name}'."
        counts = df[column_name].value_counts()
        return f"Counts for column '{column_name}' in table '{table_name}':\n{counts.to_string()}"
    except Exception as e:
        return f"Error counting categories: {e}"

def create_interactive_plot(table_name: str, plot_type: str, x: str, y: Optional[str] = None, color: Optional[str] = None, engine: Engine = None) -> str:
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", engine)

        if y == "count" or y is None:
            df = df.groupby(x).size().reset_index(name="count")
            y = "count"

        plot_func = get_plot_function(plot_type)
        if not plot_func:
            raise ValueError(f"Unsupported plot type: {plot_type}")

        # Determine parameters for plotting
        kwargs = {"x": x, "y": y}
        if color:
            kwargs["color"] = color

        fig = plot_func(df, **kwargs)
        return f"[PLOTLY_JSON]{fig.to_json()}[/PLOTLY_JSON]"
    except Exception as e:
        return f"Error creating plot: {e}"

def create_yearly_summary_plot(engine: Engine, table_name: str, date_column: str) -> str:
    try:
        df = pd.read_sql_table(table_name, con=engine)
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        df.dropna(subset=[date_column], inplace=True)
        df['year'] = df[date_column].dt.year
        yearly_counts = df['year'].value_counts().reset_index()
        yearly_counts.columns = ['Year', 'Count']
        yearly_counts = yearly_counts.sort_values('Year')
        fig = get_plot_function("bar")(yearly_counts, x='Year', y='Count')
        fig.update_layout(title=f"Total Count per Year from '{table_name}'")
        return f"[PLOTLY_JSON]{fig.to_json()}[/PLOTLY_JSON]"
    except Exception as e:
        return f"Error creating yearly summary plot: {e}"

# --- Agent Initialization ---

def initialize_agent(engine, retriever_tool):
    llm = ChatGroq(
        model_name="llama3-70b-8192",
        temperature=0,
        groq_api_key = os.getenv("GROQ_API_KEY")
    )

    tools = [
        retriever_tool,

        StructuredTool.from_function(
            name="analyze_data_summary",
            func=lambda table_name: get_data_summary(engine=engine, table_name=table_name),
            description="Get summary statistics, data types, and missing values of a data table.",
            args_schema=TableOnlyInput
        ),

        StructuredTool.from_function(
            name="count_categorical_variable",
            func=lambda table_name, column_name: count_categorical_variable(
                engine=engine, table_name=table_name, column_name=column_name
            ),
            description="Count occurrences in a categorical column.",
            args_schema=CountCategoricalInput
        ),

        StructuredTool.from_function(
            name="create_interactive_plot",
            func=lambda table_name, plot_type, x, y=None, color=None: create_interactive_plot(
                engine=engine, table_name=table_name, plot_type=plot_type, x=x, y=y, color=color
            ),
            description="Create visualizations: bar, scatter, histogram. Requires columns.",
            args_schema=CreateInteractivePlotInput
        ),

        StructuredTool.from_function(
            name="create_yearly_summary_plot",
            func=lambda table_name, date_column: create_yearly_summary_plot(
                engine=engine, table_name=table_name, date_column=date_column
            ),
            description="Create a bar plot showing yearly counts using a date column.",
            args_schema=YearlyPlotInput
        ),
    ]

    system_prompt = """
    You are an expert AI data analyst. You answer questions using only the tools provided to you.

    🔁 WORKFLOW:
    1. Use `schema_and_relationship_retriever` to understand tables and columns.
    2. Use `count_categorical_variable` for any question about counts, totals, or breakdowns.
    3. Use `create_yearly_summary_plot` to visualize trends over years.
    4. Use `create_interactive_plot` for visualizations like bar, scatter, histogram.
    5. Use `analyze_data_summary` to summarize a table.

    🔒 DO NOT write Python code manually.
    ✅ ALWAYS return a final answer after using a tool.
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    return executor
