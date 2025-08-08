# modules/plot_registry.py
import plotly.express as px
import pandas as pd

def bar_plot(df: pd.DataFrame, x: str, y: str = None, color: str = None):
    """
    Creates a bar plot. If y is not provided, it defaults to count aggregation of x.
    """
    if y is None:
        # Group by x and count rows
        df_count = df[x].value_counts().reset_index()
        df_count.columns = [x, "Count"]
        return px.bar(df_count, x=x, y="Count", color=color, title=f"Bar Plot of Count by {x}")
    else:
        return px.bar(df, x=x, y=y, color=color, title=f"Bar Plot of {y} by {x}")

def scatter_plot(df: pd.DataFrame, x: str, y: str, color: str = None):
    return px.scatter(df, x=x, y=y, color=color, title=f"Scatter Plot of {y} vs {x}")

def histogram_plot(df: pd.DataFrame, x: str, color: str = None):
    return px.histogram(df, x=x, color=color, title=f"Histogram of {x}")

# Supported plot types
PLOT_FUNCTIONS = {
    "bar": bar_plot,
    "scatter": scatter_plot,
    "histogram": histogram_plot,
}

def get_plot_function(plot_type: str):
    return PLOT_FUNCTIONS.get(plot_type)
