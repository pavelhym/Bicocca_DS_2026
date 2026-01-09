import os
import sys

current_file_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_file_dir)

if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


from dataclasses import field
from typing import List, TypedDict

from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, END, StateGraph
from src.logger_initialization import initialize_logger
from src.agents import company_metric_agent_with_websearch

logger = initialize_logger("websearch_tool_graph")
MAX_RETRIES = 1


## Creating graph
class One_metricsGraphState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        question: question
        generation: LLM generation
        documents: list of documents
        retry_count: retry count initialized to 0
    """

    company_name: str = ""
    metrics: str = ""

    generation: str = ""
    follow_up_question: str = ""
    documents: List[str] = field(default_factory=list)
    retry_count: int = 0
    parameters: List[str] = field(default_factory=list)
    web_results: List[str] = field(default_factory=list)


async def generate_structured_answer_node(state, config: RunnableConfig):
    """
    Generate answer

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, generation, that contains LLM generation
    """
    thread_id = config["configurable"]["thread_id"]
    logger.info(f"Thread: {thread_id} - Generate")
    company_name = state["company_name"]
    metrics = state["metrics"]
    question = f"Find {metrics} for {company_name}"

    # RAG generation
    input_prompt = f"Question: {question}"
    result = await company_metric_agent_with_websearch.run(input_prompt)
    generation = result.output.model_dump()
    logger.info(f"Thread: {thread_id} - Generation: {generation}")
    return {"generation": generation}


workflow = StateGraph(One_metricsGraphState)

workflow.add_node(
    "generate_structured_answer_node", generate_structured_answer_node
)  # Generate response


workflow.add_edge(START, "generate_structured_answer_node")

workflow.add_edge("generate_structured_answer_node", END)

checkpointer = InMemorySaver()

# Compile
one_metrics_graph_tool = workflow.compile(checkpointer=checkpointer)
