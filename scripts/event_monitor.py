import requests
import json
import os
import argparse
from datetime import datetime, timezone

TENDER_DIR = os.getcwd()
CONFIG_FILE = os.path.join(TENDER_DIR, "tender_config.json")
LAST_TENDER_FILE = os.path.join(TENDER_DIR, "last_tender.json")
BASE_URL_TEST = "https://lb-api-staging.prozorro.gov.ua"
BASE_URL_PROD = "https://public-api.prozorro.gov.ua"

# UA-2025-06-13-012785-a
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)
prod_tender_id = config.get("prod_tender_id")
test_tender_id = config.get("tender_id")

# System fields to ignore when comparing data.
# These fields often change with every request or are unique to each tender.

IGNORE_KEYS = {
    # TODO: Add system fields to ignore
    "evidences",
    "lotValues",
    "status",
    "tender_id",
    "dateSigned",
    "procurementMethodDetails",
    "submissionMethodDetails",
    "mode",
    "title_en",
    "title_ru",
    "title",
    "id",
    "date",
    "dateModified",
    "dateCreated",
    "datePublished",
    "tenderID",
    # "contractID",
    "awardID",
    "bid_id",
    "dueDate",
    "documentType",
    "format",
    "startDate",
    "endDate",
    "submissionDate",
    "owner",
    "url",
    "hash",
    "next_check",
    "auctionPeriod",
    "complaintPeriod",
    "enquiryPeriod",
    "tenderPeriod",
    "auctionUrl",
    "noticePublicationDate"
}

def format_relative_time(event_date_str, start_date_str):
    """Converts an ISO date into a relative text format based on the procurement start date."""
    if not event_date_str or not start_date_str:
        return ""
    try:
        # fromisoformat handles time zones such as +03:00
        event_dt = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
        start_dt = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return ""

    event_dt_utc = event_dt.astimezone(timezone.utc)
    start_dt_utc = start_dt.astimezone(timezone.utc)
    delta = event_dt_utc - start_dt_utc
    seconds = delta.total_seconds()

    if seconds < 0:
        return "(before the procurement started)"
    if seconds < 60:
        return f"in {int(seconds)} sec."
    elif seconds < 3600:
        return f"in {int(seconds / 60)} min."
    elif seconds < 86400:
        return f"in {int(seconds / 3600)} hr."
    else:
        return f"on day {int(seconds / 86400) + 1}"

def _get_date_str(item, event_type, parent_item=None, procurement_start_date=None):
    """Generates a formatted date string for an event."""
    date_val = None
    prefix = ""

    if event_type == "created":
        prefix = "Created"
        if isinstance(item, dict):
            date_val = item.get("date") or item.get("dateCreated") or item.get("datePublished")
        if not date_val and isinstance(parent_item, dict):
            date_val = parent_item.get("dateModified")
            prefix = "Modified"  # This is a modification of the parent object
    elif event_type == "modified":
        prefix = "Modified"
        if isinstance(parent_item, dict):
            date_val = parent_item.get("dateModified")
    elif event_type == "removed":
        prefix = "Removed"
        if isinstance(parent_item, dict):
            date_val = parent_item.get("dateModified")
    
    if date_val:
        relative_time = format_relative_time(date_val, procurement_start_date)
        if relative_time:
            return f" ({prefix} {relative_time})"
    return ""

def compare_json(json1, json2, path="", ignore_keys=None, parent_json2=None, procurement_start_date=None):
    if ignore_keys is None:
        ignore_keys = set()

    differences = []
    if parent_json2 is None:
        parent_json2 = json2

    if isinstance(json1, dict) and isinstance(json2, dict):
        keys1 = set(json1.keys())
        keys2 = set(json2.keys())

        # Keys present only in the first file (removed)
        for key in keys1 - keys2:
            if key not in ignore_keys:
                date_str = _get_date_str(None, "removed", parent_item=json2, procurement_start_date=procurement_start_date)
                differences.append(f"{path}/{key} - present only in the test tender.{date_str}")

        # Keys present only in the second file (added)
        for key in keys2 - keys1:
            if key not in ignore_keys:
                value2 = json2[key]
                if isinstance(value2, list):
                    for i, item in enumerate(value2):
                        date_str = _get_date_str(item, "created", procurement_start_date=procurement_start_date)
                        differences.append(f"{path}/{key}[{i}] - present only in the production tender.{date_str}")
                else:
                    date_str = _get_date_str(value2, "created", parent_item=json2, procurement_start_date=procurement_start_date)
                    differences.append(f"{path}/{key} - present only in the production tender.{date_str}")

        for key in keys1 & keys2:
            if key not in ignore_keys:
                differences += compare_json(json1[key], json2[key], f"{path}/{key}", ignore_keys, parent_json2=json2, procurement_start_date=procurement_start_date)

    elif isinstance(json1, list) and isinstance(json2, list):
        min_len = min(len(json1), len(json2))
        for i in range(min_len):
            differences += compare_json(json1[i], json2[i], f"{path}[{i}]", ignore_keys, parent_json2=parent_json2, procurement_start_date=procurement_start_date)
        if len(json1) > len(json2):
            for i in range(min_len, len(json1)):
                date_str = _get_date_str(None, "removed", parent_item=parent_json2, procurement_start_date=procurement_start_date)
                differences.append(f"{path}[{i}] - element present only in the test tender.{date_str}")
        elif len(json2) > len(json1):
            for i in range(min_len, len(json2)):
                item2 = json2[i]
                date_str = _get_date_str(item2, "created", procurement_start_date=procurement_start_date)
                differences.append(f"{path}[{i}] - element present only in the production tender.{date_str}")
    else:
        if json1 != json2:
            date_str = _get_date_str(None, "modified", parent_item=parent_json2, procurement_start_date=procurement_start_date)
            differences.append(f"{path} - different values: {json1} != {json2}.{date_str}")

    return differences

def get_tender_data(base_url, tender_id):
    try:
        response = requests.get(f"{base_url}/api/2.5/tenders/{tender_id}")
        response.raise_for_status()  # Check for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error loading tender {tender_id} data from {base_url}: {e}")
        return None

def get_contract_data(base_url, contract_id):
    try:
        response = requests.get(f"{base_url}/api/2.5/contracts/{contract_id}")
        response.raise_for_status()
        return response.json().get('data')
    except requests.exceptions.RequestException as e:
        print(f"Error loading contract {contract_id} data from {base_url}: {e}")
        return None

def save_test_data(tender_id):
    data_to_save = get_tender_data(BASE_URL_TEST, tender_id)
    if data_to_save:
        try:
            with open(LAST_TENDER_FILE, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            print(f"Test tender {tender_id} data saved to {LAST_TENDER_FILE}")
        except IOError as e:
            print(f"Error writing to file {LAST_TENDER_FILE}: {e}")

def main(from_file=False, save=False, contract_index=None):
    if save:
        save_test_data(test_tender_id)
        return

    procurement_start_date = None
    # Load the production tender first to obtain its creation date
    prod_tender_json = get_tender_data(BASE_URL_PROD, prod_tender_id)
    if not prod_tender_json or not prod_tender_json.get("data"):
        print("Error: Failed to load production tender data.")
        return
    
    procurement_start_date = prod_tender_json.get("data", {}).get("dateCreated")
    if not procurement_start_date:
        print("Error: Failed to retrieve the tender creation date. Relative time will not be calculated.")

    if contract_index is not None:
        print("Checking contract data...")
        prod_contracts = prod_tender_json.get("data", {}).get("contracts", [])
        if not prod_contracts or contract_index >= len(prod_contracts):
            print(f"Error: Contract with index {contract_index} was not found in the production tender.")
            return
        prod_contract_id = prod_contracts[contract_index]["id"]
        prod_contract_info = get_contract_data(BASE_URL_PROD, prod_contract_id)
        if not prod_contract_info: return

        test_tender_json = get_tender_data(BASE_URL_TEST, test_tender_id)
        if not test_tender_json: return
        test_contracts = test_tender_json.get("data", {}).get("contracts", [])
        if not test_contracts or contract_index >= len(test_contracts):
            print(f"Error: Contract with index {contract_index} was not found in the test tender.")
            return
        test_contract_id = test_contracts[contract_index]["id"]
        test_contract_info = get_contract_data(BASE_URL_TEST, test_contract_id)
        if not test_contract_info: return
        
        creation_date = prod_contract_info.get("dateCreated")
        modified_date = prod_contract_info.get("dateModified")
        print(f"Tender creation date: {procurement_start_date}")
        if creation_date:
            print(f"Contract creation date: {creation_date} ({format_relative_time(creation_date, procurement_start_date)})")
        if modified_date and modified_date != creation_date:
            print(f"Last modification date: {modified_date} ({format_relative_time(modified_date, procurement_start_date)})")

        diffs = compare_json(test_contract_info, prod_contract_info, ignore_keys=IGNORE_KEYS, procurement_start_date=procurement_start_date)

    else: # Tender comparison
        if from_file:
            print(f"Loading test data from file {LAST_TENDER_FILE}...")
            try:
                with open(LAST_TENDER_FILE, "r", encoding="utf-8") as f:
                    test_tender_data = json.load(f)
            except FileNotFoundError:
                print(f"Error: File {LAST_TENDER_FILE} was not found.")
                return
            except json.JSONDecodeError:
                print(f"Error: Invalid JSON format in file {LAST_TENDER_FILE}.")
                return
        else:
            print(f"Loading test data from the API for tender {test_tender_id}...")
            test_tender_data = get_tender_data(BASE_URL_TEST, test_tender_id)
            if not test_tender_data: return

        test_data_part = test_tender_data.get("data", {})
        prod_data_part = prod_tender_json.get("data", {})

        modified_date = prod_data_part.get("dateModified")
        if procurement_start_date:
            print(f"Tender creation date: {procurement_start_date}")
        if modified_date and modified_date != procurement_start_date:
            print(f"Last modification date: {modified_date} ({format_relative_time(modified_date, procurement_start_date)})")

        diffs = compare_json(test_data_part, prod_data_part, ignore_keys=IGNORE_KEYS, procurement_start_date=procurement_start_date)

    if diffs:
        print("\nDifferences found:")
        for diff in diffs:
            print(diff)
    else:
        print("\nNo differences found (excluding ignored fields).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare tender/contract data between production and staging.")
    parser.add_argument("--from_file", action="store_true", help="Load test data from the last_tender.json file.")
    parser.add_argument("--save", action="store_true", help="Save the current test data to the last_tender.json file.")
    parser.add_argument("--contract_index", type=int, help="Index of the contract to compare.")
    args = parser.parse_args()

    main(from_file=args.from_file, save=args.save, contract_index=args.contract_index)