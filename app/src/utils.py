from tqdm.asyncio import tqdm
from src.logger_initialization import initialize_logger
import pandas as pd
import io

logger = initialize_logger("utils")


async def process_item_async(item, one_metrics_graph, config):
    """Async function to process each (company, metric) pair using one_comp_metric_graph.ainvoke."""
    company, metric = item
    try:
        result_graph = await one_metrics_graph.ainvoke(
            input={"company_name": company, "metrics": metric}, config=config
        )

        return {
            "company_name": result_graph.get("company_name", company),
            "generation": result_graph.get("generation", {}),
            "metrics": result_graph.get("parameter", metric),
        }
    except Exception as e:
        logger.error(f"Error processing {company} with {metric}: {e}")
        return {
            "company_name": company,
            "generation": {"error": str(e)},
            "metrics": metric,
        }


async def process_combinations_async(combinations_list, one_metrics_graph, configs):
    """Process all combinations asynchronously."""
    tasks = [
        process_item_async(item, one_metrics_graph, config)
        for item, config in zip(combinations_list, configs)
    ]

    results = []
    for coro in tqdm.as_completed(tasks, desc="Processing documents"):
        result = await coro
        results.append(result)

    return results


async def process_lists(companies_list, metrics_list, one_metrics_graph):
    """Main entry point that creates combinations and processes them asynchronously."""
    combinations_list = [
        (company, metric) for company in companies_list for metric in metrics_list
    ]
    configs = [
        {"configurable": {"thread_id": item[0] + item[1]}} for item in combinations_list
    ]

    processed_results = await process_combinations_async(
        combinations_list, one_metrics_graph, configs
    )

    return processed_results


def create_table(data):
    company_names = set()
    parameters = set()

    # Extract unique company names and parameters with exception handling
    for item in data:
        try:
            company_name = item["company_name"]
            parameter = item["metrics"]

            # Add to the sets if both company_name and parameter exist
            if company_name and parameter:
                company_names.add(company_name)
                parameters.add(parameter)
        except KeyError as e:
            # Log the error or just skip this item if there is a missing key
            logger.error(f"Skipping item due to missing key: {e}")
            continue
        except Exception as e:
            # Catch any other exceptions and skip the problematic item
            logger.error(f"Skipping item due to error: {e}")
            continue

    # Convert sets to lists
    company_names = list(company_names)
    parameters = list(parameters)

    # Initialize the DataFrame with company names as the first column
    df = pd.DataFrame(company_names, columns=["company_name"])

    # Add columns for each parameter's value and comment
    for parameter in parameters:
        df[parameter + " value"] = None
        df[parameter + " comment"] = None

    # Populate the DataFrame with values and comments
    for item in data:
        try:
            # Extract necessary information from new format
            company_name = item["company_name"]
            parameter = item["metrics"]  # Changed from "parameter" to "metrics"
            generation = item.get("generation", {})  # Get generation dict
            value = generation.get("value", None)  # Changed from retrieved_info
            comment = generation.get("comment", None)  # Changed from retrieved_info

            # Skip if any of the necessary information is missing or malformed
            if not company_name or not parameter or value is None or comment is None:
                continue  # Skip this observation

            # Update the DataFrame
            df.loc[df["company_name"] == company_name, parameter + " value"] = value
            df.loc[df["company_name"] == company_name, parameter + " comment"] = comment

        except KeyError as e:
            # Log the error or just skip this item if there is a missing key
            logger.error(f"Skipping observation due to missing key: {e}")
            continue
        except Exception as e:
            # Catch any other exceptions and skip the problematic item
            logger.error(f"Skipping observation due to error: {e}")
            continue

    return df


def create_documents_dict(documents):
    documents_dict = {}
    for doc in documents:
        key = doc.metadata.get("url")
        documents_dict[key] = {
            "company": doc.metadata.get("company", "Unknown"),
            "title": doc.metadata.get("title", "Unknown"),
            "date": doc.metadata.get("date", "Unknown"),
        }

    return documents_dict


def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    processed_data = output.getvalue()
    return processed_data
