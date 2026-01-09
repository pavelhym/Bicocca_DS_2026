import os

import aiohttp
import pdfplumber
from .logger_initialization import initialize_logger
import asyncio
from urllib.parse import quote

from bs4 import BeautifulSoup
from exa_py import AsyncExa
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
from datetime import datetime
from io import BytesIO
from tqdm.asyncio import tqdm
from .agents import web_credibility_grader_agent

load_dotenv()

logger = initialize_logger("parsing_utils")

embd = OpenAIEmbeddings(model="text-embedding-3-small")
selected_keys_metadata = ["company", "status", "last_update", "url"]


# Exa API call function with retry logic (async)
async def exacall(query, num_results=15, max_retries=10, backoff_factor=1.5):
    retry_count = 0  # Counter for the number of retries

    while retry_count < max_retries:
        try:
            # Once rate limit is available, make the API call
            exa = AsyncExa(api_key=os.getenv("EXA_API_KEY"))

            results = await exa.search_and_contents(
                query,
                text=True,
                summary=True,
                type="auto",
                num_results=num_results,
            )
            return results  # Return the results if the call is successful

        except Exception as e:
            # If there's an error (e.g., network issues or API errors), handle retry logic
            retry_count += 1
            if retry_count < max_retries:
                # Exponential backoff strategy
                backoff_time = backoff_factor**retry_count
                logger.info(
                    f"EXA -- Attempt {retry_count} failed {e}. Retrying in {backoff_time} seconds..."
                )
                await asyncio.sleep(backoff_time)  # Wait before retrying (async sleep)
            else:
                # If retries are exhausted, raise the exception
                logger.info(f"EXA -- Failed after {max_retries} attempts. Error: {e}")
                raise e
    return None  # Return None if max retries are reached without success


# HTML parsing functions (async - runs CPU-bound work in thread pool)
async def parse_url_soup_html(html):
    """Parse HTML asynchronously by running CPU-bound BeautifulSoup work in a thread pool."""

    def _parse_sync(html_content):
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove unwanted elements
            for element in soup.find_all(
                ["header", "footer", "nav", "script", "style"]
            ):
                element.decompose()

            # Try to find main content container - common class/id names
            main_content = soup.find(
                ["main", "article", "div"],
                class_=[
                    "content",
                    "main-content",
                    "article-content",
                    "post-content",
                    "entry-content",
                ],
            )

            if main_content:
                # Extract text from main content
                return main_content.get_text(separator=" ", strip=True)
            # Fallback to body content if no main container found
            body = soup.find("body")
            if body:
                return body.get_text(separator=" ", strip=True)
            return soup.get_text(separator=" ", strip=True)

        except Exception as e:
            logger.info(f"parse_url_soup_html --Error parsing HTML with API: {e}")
            return None

    # Run CPU-bound parsing in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _parse_sync, html)


async def parse_url_text_scrapingant(url):
    """Scrape a URL using ScrapingAnt API (async with aiohttp)"""
    api_key = os.getenv("SCRAPER_ANT_API_KEY")

    # URL encode the target URL
    encoded_url = quote(url)

    # Construct the request URL
    request_url = f"https://api.scrapingant.com/v2/general?url={encoded_url}&x-api-key={api_key}&return_page_source=true"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(request_url) as response:
                if response.status == 200:
                    data = await response.text()
                    return await parse_url_soup_html(data)
                else:
                    logger.info(f"scrapingant -- HTTP {response.status} for URL {url}")
                    return None
    except Exception as e:
        logger.info(f"scrapingant -- Error scraping URL {url}: {e}")
        return None


# PDF handling functions
def is_pdf(response):
    """Checks if the response contains a PDF by looking at the Content-Type header."""
    content_type = response.headers.get("Content-Type", "")
    return "application/pdf" in content_type


def extract_text_from_pdf_url(response):
    if response.status_code == 200:
        with pdfplumber.open(BytesIO(response.content)) as pdf:
            if len(pdf.pages) > 50:
                return None
            text = "\n".join(
                page.extract_text() for page in pdf.pages if page.extract_text()
            )
            return text
    else:
        return None  # Not a PDF or error in request


# Main function to get full text from URL (async)
async def get_full_text_url(document):
    url = document.url
    logger.info(f"Getting full text url {url}")

    timeout = aiohttp.ClientTimeout(total=1)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Check content length with HEAD request
            async with session.head(url, allow_redirects=True) as head_response:
                content_length = head_response.headers.get("Content-Length")
                if content_length and int(content_length) > 50_000_000:  # 50 MB limit
                    logger.info(f"File too large, skipping parsing. -- {url}")
                    return document.text.replace("\n", " ")
    except Exception as e:
        logger.info(f"Head request error: {e} -- {url}")

    text = None
    try:
        logger.info(f"Request -- {url}")
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, allow_redirects=False) as response:
                content_type = response.headers.get("Content-Type", "")

                if ("application/pdf" in content_type) and (response.status == 200):
                    logger.info(f"Getting full text --pdf url -- {url}")
                    # For PDF, we need to read the content and use the sync extract function
                    # Run CPU-bound PDF extraction in thread pool
                    pdf_content = await response.read()
                    loop = asyncio.get_event_loop()

                    # Create a mock response object for extract_text_from_pdf_url
                    class MockResponse:
                        def __init__(self, content, status_code, headers):
                            self.content = content
                            self.status_code = status_code
                            self.headers = headers

                    mock_response = MockResponse(
                        pdf_content, 200, {"Content-Type": content_type}
                    )
                    text = await loop.run_in_executor(
                        None, extract_text_from_pdf_url, mock_response
                    )
                elif url.endswith(".html") or url.endswith(".htm"):
                    logger.info(f"Getting full text --html url -- {url}")
                    html_content = await response.text()
                    text = await parse_url_soup_html(html_content)
                else:
                    logger.info(f"Getting full text -- using scraperAPI -- {url}")
                    text = await parse_url_text_scrapingant(url)
    except Exception as e:
        logger.info(f"request error {e}, go to SearchEngine text -- {url}")
        text = None

    if text is None:
        text = document.text.replace("\n", " ")
        text = " ".join(text.split())
        return text
    else:
        text = " ".join(text.split())
        return text


# Simple async function for web credibility grading
async def grade_web_credibility(
    question: str, date: str, author: str, snippet: str, url: str
) -> float:
    """Grade the credibility of a web document."""
    prompt = f"""Query: '{question}'
Publication Date: '{date}'
Author: '{author}'
Snippet: '{snippet}'
URL: {url}"""
    result = await web_credibility_grader_agent.run(prompt)
    return result.output.credibility_score


# Async function to add credibility scores to web search documents
async def add_credibility_web_search(documents, question):
    """Determines whether the web results are credible."""
    logger.info("---ADD CREDIBILITY TO DOCUMENTS---")

    # Score each doc in parallel
    tasks = []
    doc_indices = []

    for i, d in enumerate(documents):
        if d.metadata.get("url") is not None:
            logger.info(
                f"Adding credibility to web document -- {d.metadata.get('url')}"
            )
            tasks.append(
                grade_web_credibility(
                    question=question,
                    url=d.metadata.get("url", ""),
                    date=d.metadata.get("date", ""),
                    author=d.metadata.get("author", ""),
                    snippet=d.page_content[:5000],
                )
            )
            doc_indices.append(i)

    # Run all credibility checks in parallel
    if tasks:
        credibility_scores = await asyncio.gather(*tasks, return_exceptions=True)

        # Update documents with credibility scores
        for idx, score in zip(doc_indices, credibility_scores):
            if isinstance(score, Exception):
                logger.info(f"Error grading credibility for document {idx}: {score}")
                documents[idx].metadata["credibility"] = 0.0
            else:
                documents[idx].metadata["credibility"] = score

    return documents


# Main Exa search function
async def exa_search_results(
    query: str,
    vectorstore=None,  # Not used for in-memory stores, kept for compatibility
    num_results: int = 15,
) -> list[Document]:
    logger.info(f"Start exa search with query: {query}")

    results = await exacall(query, num_results)
    logger.info(f"Exa search completed with {len(results.results)} results")

    # For in-memory store, we don't track existing docs across sessions
    # All results will be processed
    existing_docs = []
    new_docs = [doc for doc in results.results if doc.url not in existing_docs]

    logger.info(f"Found {len(new_docs)} new documents: {[d.url for d in new_docs]}")
    logger.info(f"Async websearch started with {len(new_docs)} tasks")

    # Use asyncio.gather to parallelize async tasks
    tasks_list = [get_full_text_url(doc) for doc in new_docs]
    texts = await asyncio.gather(*tasks_list, return_exceptions=True)

    # Update documents with retrieved text
    for i, text in enumerate(tqdm(texts, desc="Processing documents")):
        if isinstance(text, Exception):
            logger.info(f"Error processing document {i}: {text}")
            text = new_docs[i].text.replace("\n", " ")
            text = " ".join(text.split())
        new_docs[i].text = text

    logger.info(f"Processed {len(new_docs)} documents")

    web_documents = [
        Document(
            page_content=d.text,  # Main content
            metadata={
                "title": d.title if d.title else "None",
                "url": d.url if d.url else "None",
                "date": d.published_date if d.published_date else "None",
                "author": d.author if d.author else "None",
                "highlights": d.highlights if d.highlights else "None",
                "source": "web",
                "date_parsed": datetime.now().strftime("%Y-%m-%d"),
            },
        )
        for d in new_docs
    ]

    return web_documents


def clean_metadata_from_docs(doc):
    if doc.metadata:
        doc.metadata = {k: v for k, v in doc.metadata.items() if v is not None}
    return doc


def create_retriever_in_memory(docs):
    docs = [clean_metadata_from_docs(doc) for doc in docs]

    vector_store_inmemory = InMemoryVectorStore.from_documents(docs, embedding=embd)

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=50)
    docs = text_splitter.split_documents(docs)

    if len(docs) > 0:
        logger.info("Adding documents to the inmemory vectorstore")
        vector_store_inmemory.add_documents(documents=docs)
        logger.info("Documents added to the inmemory vectorstore")

    else:
        return None

    return vector_store_inmemory


def retrieve_with_credibility(
    vectorstore, query, k_init=30, k_final=15, min_credibility=0.5, alpha=0.5
):
    docs_with_scores = vectorstore.similarity_search_with_score(query, k=k_init)

    # Step 2: Filter documents by minimum credibility
    for doc, score in docs_with_scores:
        # If document is not from web, set credibility to 0.9
        if doc.metadata.get("source") != "web":
            doc.metadata["credibility"] = 0.9

    # Then filter as before
    filtered_docs = [
        (doc, score)
        for doc, score in docs_with_scores
        if doc.metadata.get("credibility", 0) >= min_credibility
    ]

    # Step 3: Compute hybrid score (weighted sum of similarity & credibility)
    ranked_docs = sorted(
        filtered_docs,
        key=lambda d: (1 - alpha) * (d[0].metadata.get("credibility", 0) / 5)
        + (alpha * (1 - d[1])),
        reverse=True,
    )[: min(k_final, len(filtered_docs))]

    return [doc for doc, _ in ranked_docs]
