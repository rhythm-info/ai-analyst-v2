# plot_generator.py
import pandas as pd
import plotly.express as px
from modules.plot_registry import get_plot_function

def generate_plot(plot_type: str, data: pd.DataFrame, x: str, y: str = None, color: str = None, title: str = "") -> str:
    """
    Generates a plot based on the specified type and data,
    and returns it as a serialized Plotly JSON string.
    """
    try:
        plot_func = get_plot_function(plot_type)
        if not plot_func:
            return f"Unsupported plot type: {plot_type}"

        # Call the plot function with the available arguments
        fig = plot_func(data, x=x, y=y, color=color)

        return f"[PLOTLY_JSON]{fig.to_json()}[/PLOTLY_JSON]"
    except Exception as e:
        return f"Error generating plot: {e}"
