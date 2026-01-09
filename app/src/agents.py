import os

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from dotenv import load_dotenv
from typing import Optional
from typing import Union
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai import WebSearchTool

load_dotenv()

model_mini = OpenAIChatModel(
    "gpt-4o-mini", provider=OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY"))
)
model_4o = OpenAIChatModel(
    "gpt-4o", provider=OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY"))
)
model_5 = OpenAIChatModel(
    "gpt-5", provider=OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY"))
)
model_5_responses = OpenAIResponsesModel(
    "gpt-5", provider=OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY"))
)


class GradeDocuments(BaseModel):
    """Binary score for relevance check on retrieved documents."""

    binary_score: str = Field(
        description="Documents are relevant to the question, 'yes' or 'no'"
    )


system_prompt_retrieval = """You are a grader assessing relevance of a retrieved document to a user question. 
If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. 
It does not need to be a stringent test. The goal is to filter out erroneous retrievals. 
Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question."""

retrieval_grader_agent = Agent(
    model_mini,
    model_settings={"temperature": 0.0},
    system_prompt=system_prompt_retrieval,
    output_type=GradeDocuments,
)

system_prompt_rag = """
## Role
You are expert in analysis of financial statements and annual reports.
Generate a direct and well-structured answer to the question, using only the provided sources.

### Guidelines:
1. **Synthesize** details if multiple sources agree.
2. **Prioritize higher credibility scores** if sources conflict.
3. **Prioritize official sources, such as official websites, annual reports, etc.**
4. **Cite sources explicitly** using *(According to [Title]( URL ))*.
5. **Ensure clarity, accuracy, and neutrality.**

Now generate the answer."""

rag_chain_agent = Agent(
    model_5, model_settings={"temperature": 0.0}, system_prompt=system_prompt_rag
)


class GradeHallucinations(BaseModel):
    """Binary score for hallucination present in generation answer."""

    binary_score: bool = Field(
        description="True if the answer is grounded in / supported by the set of facts, False otherwise"
    )


system_prompt_hallucination = """You are a grader assessing whether an LLM generation is grounded in / supported by a set of retrieved facts. 
Return True if the answer is grounded in / supported by the set of facts, False otherwise."""

hallucination_grader_agent = Agent(
    model_mini,
    model_settings={"temperature": 0.0},
    system_prompt=system_prompt_hallucination,
    output_type=GradeHallucinations,
)


class GradeAnswer(BaseModel):
    """Binary score to assess answer addresses question."""

    binary_score: bool = Field(
        description="True if the answer addresses/resolves the question, False otherwise"
    )


system_prompt_answer = """You are a grader assessing whether an answer addresses / resolves a question. 
Return True if the answer addresses/resolves the question, False otherwise."""

answer_grader_agent = Agent(
    model_5,
    model_settings={"temperature": 0.0},
    system_prompt=system_prompt_answer,
    output_type=GradeAnswer,
)


class GradeAnswerFullInfo(BaseModel):
    """Binary score to assess answer addresses question."""

    binary_score: bool = Field(
        description="True if the answer fully addresses the question, False otherwise"
    )
    follow_up_question: Optional[str] = Field(
        None,
        description="Follow-up question if more details are needed (only when binary_score is False)",
    )


system_prompt_full_info = """You are a grader assessing whether the provided answer fully addresses the question, including details and accuracy.
If the answer is sufficient, return True. If not, return False and provide a specific follow-up question to the web to fill missing information."""

full_information_grader_agent = Agent(
    model_5,
    model_settings={"temperature": 0.0},
    system_prompt=system_prompt_full_info,
    output_type=GradeAnswerFullInfo,
)


class Updated_Query(BaseModel):
    """Updated query for web search."""

    updated_query: str = Field(description="Updated query for web search")


system_prompt_rewriter = """
##ROLE
You are expert in company research and analysis.

Based on provided documents and question with follow-up question - refine the question to be more informative and specific.
Also translate question to the language of the documents.
"""

question_rewriter_agent = Agent(
    model_5,
    model_settings={"temperature": 0.0},
    system_prompt=system_prompt_rewriter,
    output_type=Updated_Query,
)


class WebCredibilityGrader(BaseModel):
    credibility_score: float = Field(
        description="Web search result score, based on source credibility and time of publication"
    )


system_prompt_web_credibility = """You are an expert fact-checker and researcher. You will be given a URL as well as some URL metadata.
Your task is to evaluate the credibility of the content of the given URL.

**Instructions:**
**Credibility Score (`credibility_score`)**:  
    - Base this score (0.0 to 1.0) on:  
        - Domain reliability (peer-reviewed, official, or trusted news source).  
        - Author expertise (e.g., known expert vs. anonymous).  
        - Recency (fresher content gets a higher score unless older info is more authoritative)."""

web_credibility_grader_agent = Agent(
    model_4o,
    model_settings={"temperature": 0.0},
    system_prompt=system_prompt_web_credibility,
    output_type=WebCredibilityGrader,
)


class CompanyMetric(BaseModel):
    """Company metrics with value and explanation."""

    comment: str = Field(description="Sources and explanation")
    value: Union[int, str, float] = Field(description="The value of the metric")


system_prompt_company_metric = """Generate a direct and well-structured answer to the question, using only the provided sources. Put full answer in the comment field.
Put the extracted particular value in the value field. For numeric values write them in the full numeric form (120 000 000 but not 120 million).

### Guidelines:
1. **Synthesize** details if multiple sources agree.
2. **Prioritize higher credibility scores** if sources conflict.
3. **Prioritize official sources, such as official websites, annual reports, etc.**
4. **Cite sources explicitly** using *(According to [Title]( URL ))*.
5. **Ensure clarity, accuracy, and neutrality.**
"""

company_metric_agent = Agent(
    model_5,
    model_settings={"temperature": 0.0},
    system_prompt=system_prompt_company_metric,
    output_type=CompanyMetric,
)

company_metric_agent_with_websearch = Agent(
    model_5_responses,
    builtin_tools=[WebSearchTool()],
    model_settings={"temperature": 0.0},
    system_prompt=system_prompt_company_metric,
    output_type=CompanyMetric,
)


system_prompt_websearch = """
## Role
You are expert in analysis of financial statements and annual reports.
Generate a direct and well-structured answer to the question, using only found in web search results.

### Guidelines:
1. **Synthesize** details if multiple sources agree.
2. **Prioritize higher credibility scores** if sources conflict.
3. **Prioritize official sources, such as official websites, annual reports, etc.**
4. **Cite sources explicitly** using *(According to [Title]( URL ))*.
5. **Ensure clarity, accuracy, and neutrality.**

Now generate the answer."""

agent_with_websearch = Agent(
    model_5_responses,
    builtin_tools=[WebSearchTool()],
    model_settings={"temperature": 0.0},
    system_prompt=system_prompt_websearch,
)
