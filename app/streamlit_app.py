import sys
from io import BytesIO

import asyncio
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from st_on_hover_tabs import on_hover_tabs

sys.stdout.reconfigure(line_buffering=True)
import time
import uuid

from src.logger_initialization import initialize_logger
from src.utils import (
    create_documents_dict,
    create_table,
    process_lists,
)
from graphs.metrics_graph import websearch_graph
from graphs.table_graph import one_metrics_graph
from graphs.websearch_tool_graph import one_metrics_graph_tool

load_dotenv()

logger = initialize_logger("streamlit_app")


def run_async(coro):
    """Helper function to run async code in Streamlit."""
    # Create a new event loop for each call (Streamlit runs in a new thread per request)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


st.set_page_config(layout="wide", page_title="Company Researcher")
# change tab fontsize
css_tabs = """
<style>
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
    font-size:2rem;
    }
</style>
"""

st.markdown(css_tabs, unsafe_allow_html=True)


# change fontsize
css = """
<style>
    .st-emotion-cache-q8sbsg p {
        font-size: 25px;
    }
</style>
"""

st.markdown(css, unsafe_allow_html=True)

# change font
css = """
<style>
    .st-emotion-cache-q8sbsg {
        font-family: Pragmatica;
    }
</style>
"""
st.markdown(css, unsafe_allow_html=True)


# change sidebar color
st.markdown(
    """
<style>
    [data-testid=stSidebar] {
        background-color: #111;
    }
</style>
""",
    unsafe_allow_html=True,
)

# hide made by streamlit
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)


@st.cache_data
def to_excel(df):
    """Convert DataFrame to Excel with formatting."""
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine="xlsxwriter")
    df.to_excel(writer, index=False, sheet_name="Sheet1")
    workbook = writer.book
    worksheet = writer.sheets["Sheet1"]
    format1 = workbook.add_format({"num_format": "0.00"})
    worksheet.set_column("A:A", None, format1)
    writer.close()
    processed_data = output.getvalue()
    return processed_data


################################################ STREAMLIT APP ################################################

if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())


with st.sidebar:
    selected = on_hover_tabs(
        tabName=["Full search", "Table format"],
        iconName=["saved_search", "table"],
        default_choice=0,
    )


if selected == "Full search":
    st.header("Full search")

    with st.expander("What is full search?"):
        st.info(
            "Full search ALWAYS combines web search and local storage. It is designed to return a comprehensive answer to a question, but takes longer to complete."
        )

    config = {
        "configurable": {
            "thread_id": str(st.session_state.session_id) + str(int(time.time()))
        }
    }

    question = st.text_input("Enter your query:", autocomplete="off")

    if st.button("Search"):
        logger.info("--------------------------------")
        logger.info(f"TRACK: {selected}")

        with st.spinner("Searching...", show_time=True):
            try:
                final_state = run_async(
                    websearch_graph.ainvoke(input={"question": question}, config=config)
                )
            except Exception as e:
                logger.error(f"error in invoke: {e}")
                final_state = {}

            generation = final_state.get("generation")
            documents_raw = final_state.get("documents", [])
            documents = create_documents_dict(documents_raw)
            if generation:
                st.write(generation)
            else:
                st.error("No information found, an error occurred")


if selected == "Table format":
    st.header("Table format")

    with st.expander("What is the input format?"):
        st.info(
            "The input file should include a table, where the first column is filled with company names, and the rest of the column names are the metrics."
        )

    uploaded_metrics = st.file_uploader("Upload metrics file")

    # Initialize session state variables
    if "init_table" not in st.session_state:
        st.session_state["init_table"] = None
    if "init_table_companies" not in st.session_state:
        st.session_state["init_table_companies"] = ""
    if "init_table_metrics" not in st.session_state:
        st.session_state["init_table_metrics"] = ""
    if "selected_graph" not in st.session_state:
        st.session_state["selected_graph"] = "one_metrics_graph"

    if uploaded_metrics is not None:
        try:
            st.session_state["init_table"] = pd.read_excel(uploaded_metrics)
            st.session_state["init_table"].columns = ["company"] + st.session_state[
                "init_table"
            ].columns.tolist()[1:]
        except Exception as e:
            st.warning(f"Error reading file: {e}")
    else:
        st.session_state["init_table_companies"] = st.text_input(
            "Enter companies for analysis: (separated by '++')",
            value=st.session_state["init_table_companies"],
            autocomplete="off",
        )

        companies_list = [
            company.strip()
            for company in st.session_state["init_table_companies"].split("++")
            if company.strip()
        ]

        st.session_state["init_table_metrics"] = st.text_input(
            "Enter metrics: (separated by '++')",
            value=st.session_state["init_table_metrics"],
            autocomplete="off",
        )
        metrics_list = [
            metric.strip()
            for metric in st.session_state["init_table_metrics"].split("++")
            if metric.strip()
        ]

        if companies_list and metrics_list:
            data = {metric: [""] * len(companies_list) for metric in metrics_list}
            data["company"] = companies_list
            st.session_state["init_table"] = pd.DataFrame(data)
            st.session_state["init_table"] = st.session_state["init_table"][
                ["company"]
                + [
                    col
                    for col in st.session_state["init_table"].columns
                    if col != "company"
                ]
            ]
        elif st.session_state["init_table"] is None:
            st.session_state["init_table"] = None

    project_name = st.text_input("Enter project name", autocomplete="off")

    # Graph selector
    graph_options = {
        "one_metrics_graph": one_metrics_graph,
        "one_metrics_graph_tool": one_metrics_graph_tool,
    }
    graph_option_keys = list(graph_options.keys())
    current_index = (
        graph_option_keys.index(st.session_state["selected_graph"])
        if st.session_state["selected_graph"] in graph_option_keys
        else 0
    )
    selected_graph_name = st.selectbox(
        "Select graph to use:",
        options=graph_option_keys,
        index=current_index,
        help="Choose which graph implementation to use for processing",
    )
    st.session_state["selected_graph"] = selected_graph_name
    selected_graph = graph_options[selected_graph_name]

    if st.session_state.get("init_table") is not None:
        st.write("")
        st.write("")
        st.write("")
        st.write("")

        st.info("Your current dataframe is:")
        st.write(st.session_state["init_table"])

        st.write("")
        st.write("")
        st.write("")
        st.write("")

        if st.button("Fill table"):
            companies_for_analysis = st.session_state["init_table"]["company"].tolist()
            metrics_for_analysis = st.session_state["init_table"].columns.tolist()[1:]

            with st.spinner("Processing...", show_time=True):
                try:
                    result_list = run_async(
                        process_lists(
                            companies_for_analysis,
                            metrics_for_analysis,
                            selected_graph,
                        )
                    )
                except Exception as e:
                    logger.error(f"error in process_lists: {e}")
                    st.error(f"Error processing table: {e}")
                    result_list = []

                result_df = create_table(result_list)
                st.dataframe(result_df)
                excel_data = to_excel(result_df)
                _, main_col, _ = st.columns(3)
                with main_col:
                    st.download_button(
                        label="📥 Download Excel",
                        data=excel_data,
                        file_name=f"table_filled_{project_name}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        on_click=lambda: st.session_state.update(
                            {"download_triggered": True}
                        ),
                    )
                if st.session_state.get("download_triggered"):
                    st.session_state["download_triggered"] = False

    else:
        st.warning("Please upload/create a table to fill")
