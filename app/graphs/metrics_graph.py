import os
import sys

current_file_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_file_dir)

if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


from dataclasses import field
from typing import List, TypedDict

from langchain_core.messages import AnyMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command
from src.agents import (
    full_information_grader_agent,
    question_rewriter_agent,
    rag_chain_agent,
)
from src.logger_initialization import initialize_logger
from src.parsing_utils import (
    add_credibility_web_search,
    create_retriever_in_memory,
    exa_search_results,
    retrieve_with_credibility,
)
from typing_extensions import Annotated, Literal

logger = initialize_logger("main_graph")
MAX_RETRIES = 1


## Creating graph
class GraphState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        question: question
        generation: LLM generation
        documents: list of documents
        retry_count: retry count initialized to 0
    """

    messages_list: Annotated[list[AnyMessage], add_messages]
    company_name: str = ""
    question: str = ""

    generation: str = ""
    follow_up_question: str = ""
    documents: List[str] = field(default_factory=list)
    retry_count: int = 0
    test_count: int = 0
    parameters: List[str] = field(default_factory=list)
    web_results: List[str] = field(default_factory=list)


async def retries_increment_node(
    state, config: RunnableConfig
) -> Command[Literal["question_rewriter_node", END]]:
    thread_id = config["configurable"]["thread_id"]

    retry_count = state.get("retry_count", 0)
    incremented_retry_count = retry_count + 1

    logger.info(
        f"Thread: {thread_id} - Retry count increment {incremented_retry_count}"
    )
    logger.info(f"---RETRY COUNT INCREMENT {incremented_retry_count}---")

    if incremented_retry_count >= MAX_RETRIES:
        logger.info(f"Thread: {thread_id} - Reached maximum number of retries, stop")
        return Command(
            # state update
            update={"retry_count": incremented_retry_count},
            # control flow
            goto=END,
        )
    else:
        logger.info(f"Thread: {thread_id} - Proceed to web search")
        return Command(
            # state update
            update={"retry_count": incremented_retry_count},
            # control flow
            goto="question_rewriter_node",
        )


async def full_answer_check_node(
    state, config: RunnableConfig
) -> Command[Literal[END, "retries_increment_node"]]:
    thread_id = config["configurable"]["thread_id"]
    logger.info(f"Thread: {thread_id} - Full answer check")
    question = state["question"]
    generation = state["generation"]

    # Invoke the grading function
    input_prompt = f"User question: \n\n {question} \n\n LLM generation: {generation}"
    result = await full_information_grader_agent.run(input_prompt)
    binary_score = result.output.binary_score
    logger.info(f"Thread: {thread_id} - Full answer check result: {binary_score}")
    if binary_score:
        return Command(goto=END)

    else:
        logger.info(
            f"Thread: {thread_id} - New question: {result.output.follow_up_question}"
        )

        return Command(
            # state update
            update={"follow_up_question": result.output.follow_up_question},
            goto="retries_increment_node",
        )


async def generate_answer_node(state, config: RunnableConfig):
    """
    Generate answer

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, generation, that contains LLM generation
    """
    thread_id = config["configurable"]["thread_id"]
    logger.info(f"Thread: {thread_id} - Generate")
    question = state["question"]
    documents = state["documents"]

    # RAG generation
    input_prompt = f"Question: {question}\nDocuments: {documents}"
    result = await rag_chain_agent.run(input_prompt)
    generation = result.output
    logger.info(f"Thread: {thread_id} - Generation: {generation}")
    return {"generation": generation}


async def question_rewriter_node(state, config: RunnableConfig):
    thread_id = config["configurable"]["thread_id"]
    logger.info(f"Thread: {thread_id} - Generate")
    question = state["question"]
    follow_up_question = state["follow_up_question"]
    documents = state["documents"]

    # RAG generation
    input_prompt = f"Question: {question} \nFollow-up question: {follow_up_question} \nDocument: {documents[:1]}"
    result = await question_rewriter_agent.run(input_prompt)
    new_question = result.output.updated_query
    logger.info(f"Thread: {thread_id} - New question: {new_question}")
    return {"question": new_question}


async def web_search_node(state, config: RunnableConfig):
    """
    Web search based on the re-phrased question.

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Updates documents key with appended web results
    """

    thread_id = config["configurable"]["thread_id"]
    logger.info(f"Thread: {thread_id} - Web search")
    question = state["question"]
    # Web search

    web_results = await exa_search_results(question)
    logger.info(f"Thread: {thread_id} - Exa search done")
    web_results = await add_credibility_web_search(web_results, question)
    logger.info(f"Thread: {thread_id} - Credibility done")

    if web_results:
        logger.info(f"Thread: {thread_id} - Creating retriever in memory...")
        vector_store = create_retriever_in_memory(web_results)

        if vector_store is not None:
            logger.info(
                f"Thread: {thread_id} - Retrieving documents from the vectorstore..."
            )
            documents_web = retrieve_with_credibility(vector_store, question)

        else:
            documents_web = []

    else:
        documents_web = []

    return {"documents": documents_web, "web_results": web_results}


workflow = StateGraph(GraphState)

# Define the nodes
workflow.add_node("web_search_node", web_search_node)  # Web search if needed

workflow.add_node("generate_answer_node", generate_answer_node)  # Generate response
workflow.add_node("retries_increment_node", retries_increment_node)
workflow.add_node("full_answer_check_node", full_answer_check_node)
workflow.add_node("question_rewriter_node", question_rewriter_node)


workflow.add_edge(START, "web_search_node")

workflow.add_edge("web_search_node", "generate_answer_node")
workflow.add_edge("generate_answer_node", "full_answer_check_node")

workflow.add_edge("question_rewriter_node", "web_search_node")

checkpointer = InMemorySaver()

# Compile
websearch_graph = workflow.compile(checkpointer=checkpointer)
