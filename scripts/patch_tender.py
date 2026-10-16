import requests
import json
import os
import argparse
import inspect
from datetime import datetime
import copy
import urllib.parse
import shutil


TENDER_DIR = os.getcwd()
CONFIG_FILE = os.path.join(TENDER_DIR, "tender_config.json")

BASE_URL_TEST = "https://lb-api-staging.prozorro.gov.ua"
BASE_URL_PROD = "https://public-api.prozorro.gov.ua"

HEADERS_TO = {
    "Authorization": "YOUR_TOKEN",
    "Content-Type": "application/json",
}

# TODO: implement the interface

def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading configuration from {CONFIG_FILE}: {e}")
        return None

def replace_document(url, format, path=None):
    if path is not None:
        filename = None
        download_response = None

        try:
            download_response = requests.get(url, timeout=15)
            if download_response.status_code == 200:
                # print(download_response.headers)
                temp_filename = "default_filename.p7s" if format == "application/pkcs7-signature" else "default_filename.docx"
                if 'Content-Disposition' in download_response.headers:
                    header = download_response.headers['Content-Disposition']
                    filename_part = [part for part in header.split(';') if 'filename=' in part]
                    if filename_part:
                        encoded_filename = filename_part[0].split('=')[1].strip('"')
                        temp_filename = urllib.parse.unquote(encoded_filename)
                
                documents_path = os.path.join(TENDER_DIR, "documents")
                filename = temp_filename

                # Create the directory if it does not exist
                if path:
                    documents_path = os.path.join(documents_path, path)
                os.makedirs(documents_path, exist_ok=True)
                with open(os.path.join(documents_path, filename), 'wb') as f:
                    f.write(download_response.content)
                
                # print(f"\nDocument successfully downloaded and saved as '{filename}'")
            else:
                print(f"\nFailed to download the document. The server returned status code: {download_response.status_code}")
                print("Response text:", download_response.text)

        except requests.exceptions.RequestException as e:
            print(f"\nAn error occurred while making the request: {e}")

        if filename and download_response and download_response.ok:
            doc_server_url = "https://upload-docs-staging.prozorro.gov.ua/upload"

            files_to_upload = [('file', (filename, open(os.path.join(documents_path, temp_filename), 'rb'), download_response.headers.get('Content-Type')))]
            # print("Preparing to upload:", files_to_upload)
            headers = {
                'Authorization': "YOUR_TOKEN",
            }

            upload_api_response = requests.post(doc_server_url, headers=headers, files=files_to_upload)

            print(f"Uploaded: 'documents/{path + '/' if path else ''}{temp_filename}'")
            # print("\nServer response to the upload:")
            return upload_api_response.json()["data"]["url"], upload_api_response.json()["data"]["hash"]
    else: 
        if format == "application/pkcs7-signature":
            url = "https://public-docs-staging.prozorro.gov.ua/get/647142191cfe428d887fb80e77186ecb?KeyID=f557937a&Signature=IMFGvThQpmUhQ%252BzdgwY6pWRS6BayPJ5rgvxIxZvQZwO4cb2enJWFWCIdlH7AUFot%2FhiC5CjEruOVwFGzP4v5Dw%253D%253D"
            hash = "md5:9caa9d0b766f29b7ab43403d21b93a8c"
            return url, hash
        else:
            url = "https://public-docs-staging.prozorro.gov.ua/get/49e07ef1ea2b4b31936154b7ee27e908?KeyID=f557937a&Signature=QZwC1Jp3cGZfqE%2FOSAM915vcdzAP0HNjSSukq5bemDwEiTHcISYQir97A29d2NNcU94CTKx9i0t2iijqJouyCQ%253D%253D"
            hash = "md5:37ba6f5ebd1ba42bcc40cb867fcc1d6d"
            return url, hash

def delete_documents_func(delete_documents):
    if delete_documents:
        print('=' * 70)
        print("Deleting documents")
        TENDER_DIR = os.path.dirname(os.path.abspath(__file__))
        documents_dir = os.path.join(TENDER_DIR, "documents")
        if os.path.exists(documents_dir):
            try:
                shutil.rmtree(documents_dir)
                print(f"Directory '{documents_dir}' and its contents have been successfully deleted.")
            except Exception as e:
                print(f"Error deleting directory '{documents_dir}': {e}")

# * TESTED patch_tender.py add_document --index 0 --object "contracts" --subindex 0 --doc_index 0 - subindex and subobject for contracts
# * TESTED patch_tender.py add_document --index 0 --doc_index 0
def add_document(test_tender_data, prod_tender_data, config, index=None, object=None, subindex=None, subobject=None, doc_index=None, copy_documents=False, doc_index_from=None, doc_index_to=None, doc_title=None):
    has_index = True
    if doc_index is None:
        has_index = False
        doc_index = 0
        if doc_title is None:
            print("Document index is not specified")
            return
    tender_id = config.get("tender_id")
    tender_token = config.get("tender_token")
    doc_index_from = doc_index_from or doc_index
    doc_index_to = doc_index_to or doc_index
    for i in range(doc_index_from, doc_index_to + 1):
        # i = doc_index
        if object == "contracts": # for contracts
            contract_data = requests.get(
                f"{BASE_URL_PROD}/api/2.5/contracts/{prod_tender_data['contracts'][index]['id']}"
            ).json()["data"]
            document_to_send = None
            if subobject == "changes": # for changes
                if has_index:
                    document_to_send = contract_data["changes"][subindex]["documents"][i]
                else:
                    for doc in contract_data["changes"][subindex]["documents"]:
                        if doc_title in doc["title"]:
                            document_to_send = doc
                            break
                endpoint = f'{BASE_URL_TEST}/api/0/contracts/{test_tender_data["contracts"][index]["id"]}/changes/{contract_data["changes"][subindex]["id"]}/documents?acc_token={tender_token}'
            else: # for the contract
                if has_index:
                    document_to_send = contract_data["documents"][i]
                else:
                    for doc in contract_data["documents"]:
                        if doc_title in doc["title"]:
                            document_to_send = doc
                            break
                endpoint = f'{BASE_URL_TEST}/api/0/contracts/{test_tender_data["contracts"][index]['id']}/documents?acc_token={tender_token}'
            if not document_to_send:
                print(f"Error: Document with index {i} was not found in contract {index}")
                return
        else:
            document_to_send = None
            if object is None: # for the tender
                if i >= len(prod_tender_data["documents"]):
                    print(f"Error: Document with index {i} was not found")
                    return
                if has_index:
                    document_to_send = prod_tender_data["documents"][i]
                else:
                    for doc in prod_tender_data["documents"]:
                        if doc_title in doc["title"]:
                            document_to_send = doc
                            break
                endpoint = f"{BASE_URL_TEST}/api/0/tenders/{tender_id}/documents?acc_token={tender_token}"
            else: # for bids, awards, etc.
                object_id = test_tender_data.get(object, [])[index].get("id")
                if subobject is not None:
                    if has_index:
                        document_to_send = prod_tender_data[object][index][subobject][subindex]["documents"][i]
                    else:
                        for doc in prod_tender_data[object][index][subobject][subindex]["documents"]:
                            if doc_title in doc["title"]:
                                document_to_send = doc
                                break
                    subobject_id = test_tender_data[object][index][subobject][subindex]["id"]
                    endpoint = f"{BASE_URL_TEST}/api/0/tenders/{tender_id}/{object}/{test_tender_data[object][index]['id']}/{subobject}/{subobject_id}/documents?acc_token={tender_token}"
                else:
                    if has_index:
                        document_to_send = prod_tender_data[object][index]["documents"][i]
                    else:
                        for doc in prod_tender_data[object][index]["documents"]:
                            if doc_title in doc["title"]:
                                document_to_send = doc
                                break
                    endpoint = f"{BASE_URL_TEST}/api/0/tenders/{tender_id}/{object}/{object_id}/documents?acc_token={tender_token}"
            if not document_to_send:
                print(f"Error: Document with index {i} was not found in {object}[{index}]")
                return
        path = f"{object + '/' if object else ''}{str(index) + '/' if index else ''}{subobject + '/' if subobject else ''}{str(subindex) + '/' if subindex else ''}" if copy_documents else None
        document_to_send["url"], document_to_send["hash"] = replace_document(document_to_send["url"], document_to_send["format"], path)
        response = requests.post(
            endpoint,
            json={"data": {key: value for key, value in document_to_send.items() if key != "author"}}, 
            headers=HEADERS_TO)
        print("Done") if response.ok else print(response.text)
 
# * TESTED patch_tender.py post_question --index 0
def post_question(test_tender_data, prod_tender_data, config, index):
    tender_id = config.get("tender_id")
    tender_token = config.get("tender_token")
    questions = prod_tender_data.get("questions", [])
    if not questions:
        print(f"Error: Question with index {index} was not found in tender {tender_id}")
        return None
    question = questions[index]
    question.pop('dateAnswered', None)
    question.pop('answer', None)

    question['author'] = {
        "address": {
            "countryName": "Україна",
            "locality": "м. Львів",
            "postalCode": "79013",
            "region": "Львівська область",
            "streetAddress": "вул. Тестова, 00"
        },
        "contactPoint": {
            "email": "Test@mail.com",
            "name": "Test",
            "telephone": "Test"
        },
        "identifier": {
            "scheme": "UA-EDR",
            "legalName": "Державна аудиторська служба України",
            "id": "40165856",
            "uri": "http://www.dasu.gov.ua/"
        },
        "name": "Test"
    }

    response = requests.post(
        f"{BASE_URL_TEST}/api/0/tenders/{tender_id}/questions",
        json={"data": question},
        headers=HEADERS_TO)
    print("Done") if response.ok else print(response.text)

# * TESTED patch_tender.py post_answer --index 0  
def post_answer(test_tender_data, prod_tender_data, config, index):
    tender_id = config.get("tender_id")
    tender_token = config.get("tender_token")
    questions = prod_tender_data.get("questions", [])
    if not questions:
        print(f"Error: Question with index {index} was not found")
        return None
    if "answer" not in questions[index]:
        print(f"Error: Answer to question with index {index} is missing")
        return None
    answer = questions[index]["answer"]
    question_id = test_tender_data["questions"][index]["id"]
    response = requests.patch(
        f"{BASE_URL_TEST}/api/0/tenders/{tender_id}/questions/{question_id}?acc_token={tender_token}",
        json={"data": {"answer": answer}},
        headers=HEADERS_TO
    )
    print("Done") if response.ok else print(response.text)

# * TESTED patch_tender.py post_complaint --index 0
# * TESTED patch_tender.py post_complaint --index 0 --award_index 0
def post_complaint(test_tender_data, prod_tender_data, config, index, award_index=None, copy_documents=False):
    tender_id = config.get("tender_id")
    tender_token = config.get("tender_token")
    if award_index is not None: # for an award
        if not prod_tender_data["awards"][award_index].get("complaints"):
            print("No complaints found; skipping")
            return
        endpoint = f"{BASE_URL_TEST}/api/0/tenders/{tender_id}/awards/{test_tender_data['awards'][award_index]['id']}/complaints"
        complaint_data = prod_tender_data["awards"][award_index]["complaints"][index]
        # Find the bid index by award ID
        bid_id, bid_token = None, None
        for bid in test_tender_data["bids"]:
            if bid["id"] == test_tender_data["awards"][award_index]["bid_id"]:
                bids_data = config.get("bids_data", [])
                for bid_data in bids_data:
                    if bid["id"] == bid_data["id"]:
                        bid_id = bid_data["id"]
                        bid_token = bid_data["token"]
                        break
        if bid_id is None:
            print("Error: Bid not found for award ID")
            return
    else: # for the tender
        if not prod_tender_data["data"].get("complaints"):
            print("No complaints found; skipping")
            return
        endpoint = f"{BASE_URL_TEST}/api/0/tenders/{tender_id}/complaints"
        complaint_data = prod_tender_data["complaints"][index]
    
    print("Creating complaint")
    complaint_data_copy = copy.deepcopy(complaint_data)
    
    for f in ["reviewPlace", "reviewDate", "tendererActionDate", "complaintID", "tendererAction", "value", "acceptance", "dateSubmitted", "dateAccepted", "dateDecision"]:
        complaint_data_copy.pop(f, None)

    complaint_data_copy["status"] = "draft"    
    
    for obj in complaint_data_copy["objections"]:
        if award_index is not None:
            obj["relatedItem"] = test_tender_data["awards"][award_index]["id"]
        else:
            obj["relatedItem"] = tender_id

    complaint_data_copy["documents"] = [
        {k: v for k, v in doc.items() if k != "author"}
        for doc in complaint_data_copy["documents"]
        if doc["author"] == "complaint_owner"
    ]
    
    for doc in complaint_data_copy["documents"]:
        path = f"{'awards/' + award_index + '/' if award_index is not None else ''}complaints/{str(index) if index else ''}" if copy_documents else None
        doc["url"], doc["hash"] = replace_document(doc["url"], doc["format"], path)
    
    response = requests.post(
        f"{endpoint}?acc_token={bid_token if award_index is not None else tender_token}",
        json={"data": complaint_data_copy},
        headers=HEADERS_TO,
    )
    print("Done") if response.ok else print(response.text)
    complaint_id = response.json()["data"]["id"]
    complaint_token = response.json()["access"]["token"]
    
    if complaint_data["status"] == "mistaken":
        print("Complaint marked as mistaken")
        response = requests.patch(
            f"{endpoint}/{complaint_id}?acc_token={complaint_token}",
            json={"data": {"status": "mistaken"}},
            headers=HEADERS_TO,
        )
    else:
        print("Submitting complaint")
        response = requests.patch(
            f"{endpoint}/{complaint_id}?acc_token={complaint_token}",
            json={"data": {"status": "pending"}},
            headers={
                "Authorization": "YOUR_TOKEN",
                "Content-Type": "application/json",
            },
        )
            
    if response.ok:
        print("Complaint submitted")
        key = "tender_complaints" if award_index is None else "award_complaints"
        if key not in config:
            config[key] = []
        config[key].append({"id": complaint_id, "token": complaint_token})
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    else:
        print(response.text)

# * TESTED patch_tender.py accept_complaint --index 0
# * TESTED patch_tender.py accept_complaint --index 0 --award_index 0
def accept_complaint(test_tender_data, prod_tender_data, config, index, award_index=None):
    if award_index is not None:
        complaint_id = config.get("award_complaints", [])[award_index]["id"]
        complaint_token = config.get("award_complaints", [])[award_index]["token"]
        complaint_data = prod_tender_data["awards"][award_index]["complaints"][index]
        endpoint_url = f"{BASE_URL_TEST}/api/0/tenders/{test_tender_data['id']}/awards/{test_tender_data['awards'][award_index]['id']}/complaints"
    else:
        complaint_id = config.get("tender_complaints", [])[index]["id"]
        complaint_token = config.get("tender_complaints", [])[index]["token"]
        complaint_data = prod_tender_data["complaints"][index]
        endpoint_url = f"{BASE_URL_TEST}/api/0/tenders/{test_tender_data['id']}/complaints"
    if complaint_data.get("status") == "invalid":   
        request_body = {
            "data": {
                "status": "invalid",
                "rejectReason": complaint_data.get("rejectReason")
            }
        }
    else:
        request_body = {
            "data": {
                "status": "accepted",
                "reviewDate": complaint_data['reviewDate'],
                "reviewPlace": complaint_data['reviewPlace']
            }
        }
    response = requests.patch(
        f"{endpoint_url}/{complaint_id}?acc_token={complaint_token}",
        json=request_body,
        headers={
            "Authorization": "YOUR_TOKEN",
            "Content-Type": "application/json",
        },
    )
    print("Done") if response.ok else print(response.text)
      
# * TESTED patch_tender.py decide_complaint --index 0
# * TESTED patch_tender.py decide_complaint --index 0 --award_index 0
def decide_complaint(test_tender_data, prod_tender_data, config, index, award_index=None, copy_documents=False):  
    # Add documents to the decision
    if award_index is not None:
        complaint_id = config.get("award_complaints", [])[award_index]["id"]
        complaint_token = config.get("award_complaints", [])[award_index]["token"]
        complaint_data = prod_tender_data["awards"][award_index]["complaints"][index]
        endpoint_url = f"{BASE_URL_TEST}/api/0/tenders/{test_tender_data['id']}/awards/{test_tender_data['awards'][award_index]['id']}/complaints"
    else:
        complaint_id = config.get("tender_complaints", [])[index]["id"]
        complaint_token = config.get("tender_complaints", [])[index]["token"]
        complaint_data = prod_tender_data["complaints"][index]
        endpoint_url = f"{BASE_URL_TEST}/api/0/tenders/{test_tender_data['id']}/complaints"
    decision_documents = [
        {k: v for k, v in doc.items() if k != "author"}
        for doc in complaint_data["documents"]
        if doc["author"] == "aboveThresholdReviewers"
    ]
    for doc in decision_documents:
        path = f"{'awards/' + award_index + '/' if award_index is not None else ''}complaints/{str(index) if index else ''}" if copy_documents else None
        doc["url"], doc["hash"] = replace_document(doc["url"], doc["format"], path)
    response = requests.post(
        f"{endpoint_url}/{complaint_id}/documents?acc_token={complaint_token}",
        json={"data": decision_documents},
        headers={
            "Authorization": "YOUR_TOKEN",
            "Content-Type": "application/json",
        },
    )
    print("Done") if response.ok else print(response.text)
    # Decide the complaint
    response = requests.patch(
        f"{endpoint_url}/{complaint_id}?acc_token={complaint_token}",
        json={
            "data": {
                # ! Check whether the process has been stopped
                "status": "satisfied" if complaint_data.get("status") == "resolved" else complaint_data.get("status"),
            }
        },
        headers={
            "Authorization": "YOUR_TOKEN",
            "Content-Type": "application/json",
        },
    )
    print("Done") if response.ok else print(response.text)

# * TESTED patch_tender.py confirm_resolution --index 0
# * TESTED patch_tender.py confirm_resolution --index 0 --award_index 0
def confirm_resolution(test_tender_data, prod_tender_data, config, index, award_index=None, copy_documents=False):
    # Add documents to the resolution
    if award_index is not None:
        complaint_id = config.get("award_complaints", [])[award_index]["id"]
        complaint_data = prod_tender_data["awards"][award_index]["complaints"][index]
        endpoint_url = f"{BASE_URL_TEST}/api/0/tenders/{test_tender_data['id']}/awards/{test_tender_data['awards'][award_index]['id']}/complaints"
    else:
        complaint_id = config.get("tender_complaints", [])[index]["id"]
        complaint_data = prod_tender_data["complaints"][index]
        endpoint_url = f"{BASE_URL_TEST}/api/0/tenders/{test_tender_data['id']}/complaints"
    tender_token = config.get("tender_token")
    resolution_documents = [
        {k: v for k, v in doc.items() if k != "author"}
        for doc in complaint_data["documents"]
        if doc["author"] in ["tenderer", "complaint_owner"]
    ]
    for doc in resolution_documents:
        path = f"{'awards/' + award_index + '/' if award_index is not None else ''}complaints/{str(index) if index else ''}" if copy_documents else None
        doc["url"], doc["hash"] = replace_document(doc["url"], doc["format"], path)
    response = requests.post(
        f"{endpoint_url}/{complaint_id}/documents?acc_token={tender_token}",
        json={"data": resolution_documents},
        headers=HEADERS_TO,
    )
    print("Done") if response.ok else print(response.text)
    # Confirm the resolution
    response = requests.patch(
        f"{endpoint_url}/{complaint_id}?acc_token={tender_token}",
        json={
            "data": {
                "tendererAction": complaint_data.get("tendererAction"),
                "status": "resolved"
            }
        },
        headers=HEADERS_TO,
    )
    print("Done") if response.ok else print(response.text)

# * TESTED patch_tender.py add_bids
def add_bids(test_tender_data, prod_tender_data, config, copy_documents=False):
    tender_status = requests.get(f"{BASE_URL_TEST}/api/0/tenders/{test_tender_data['id']}").json()["data"]["status"]
    if tender_status != "active.tendering":
        print(f"Cannot add bids while the tender is in status '{test_tender_data['status']}'")
        return
    bids_data = copy.deepcopy(prod_tender_data["bids"])
    for i, bid in enumerate(bids_data):
        print(f"Adding bid {i+1}")
        bid["status"] = "draft" # pending
        bid.pop("date", None)
        bid.pop("submissionDate", None)

        if bid.get("requirementResponses", None):
            for rr in bid["requirementResponses"]:
                rr.pop("classification", None)
                rr["requirement"].pop("title", None)
                rr.pop("unit", None)
                
                #! CHECK THE DOCUMENTATION
                rr.pop("evidences", None)
                # Added during the qualification stage

        if "items" not in bid:
            bid["items"] = []
            for item in prod_tender_data["items"]:
                if item["relatedLot"] in [lv["relatedLot"] for lv in bid["lotValues"]]:
                    item.pop("classification", None)
                    item.pop("deliveryAddress", None)
                    item.pop("deliveryDate", None)
                    bid["items"].append(item)
            
        rr_data = [
            {
                "value": 90,
                "requirement": {
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                }
            },
            {
                "value": True,
                "requirement": {
                    "id": "9895853717754ff2a2003bfc722bdcb9",
                }
            }
        ]
        # bid["requirementResponses"].extend(rr_data)

        for lv in bid["lotValues"]:
            lv.pop("date", None)
            lv.pop("status", None)
            lv.pop("initialValue", None)
            
        # for key, value in bid.items():
        #     if key in ["documents", "eligibilityDocuments", "financialDocuments"] and isinstance(value, list):
        #         for doc in value:
        #             if datetime.fromisoformat(doc["datePublished"]) < datetime.fromisoformat(prod_tender_data["tenderPeriod"]["endDate"]):
        #                 path = f"bids/{i}" if copy_documents else None
        #                 doc["url"], doc["hash"] = replace_document(doc["url"], doc["format"], path)
        #                 # url, hash = replace_document(doc["url"], doc["format"], path)
        #                 # doc = {
        #                 #     "url": url,
        #                 #     "hash": hash,
        #                 #     "format": doc["format"],
        #                 #     "title": doc["title"]
        #                 # }
                        
        bid.pop("documents", None)
        bid.pop("eligibilityDocuments", None)
        bid.pop("financialDocuments", None)

        response = requests.post(
            f"{BASE_URL_TEST}/api/0/tenders/{config.get('tender_id')}/bids",
            json={"data": bid},
            headers=HEADERS_TO
        )
        if response.ok:
            bid_id = response.json()["data"]["id"]
            bid_token = response.json()["access"]["token"]
            if "bids_data" not in config:
                config["bids_data"] = []
            config["bids_data"].append({"id": bid_id, "token": bid_token})
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print(f"Bid {i+1} added; data saved.")
        else:
            print(response.text)
            
        print("Adding signature")
        response = requests.post(
            f"{BASE_URL_TEST}/api/0/tenders/{config.get('tender_id')}/bids/{bid_id}/documents?acc_token={bid_token}",
            json={"data": {
                "url": "https://public-docs-staging.prozorro.gov.ua/get/3a62f1b834ab4068a4208772bc53be73?KeyID=f557937a&Signature=%252Bgnylq8bJ4awopeCOnL8igSelQJ%252BKVqrPhRweiBllg99Dmp%252B62I6gnv1OGtMrnLdyt2kgMRJTAVuprp0kVByCA%253D%253D",
                "title": "sign.p7s",
                "documentType": "proposal",
                "hash": "md5:4183fa034803f77d4937317634bd06d0",
                "format": "application/pkcs7-signature"
            }},
            headers=HEADERS_TO
        )
        print("Done") if response.ok else print(response.text)
        
        print("Adding documents")
        for key in ["documents", "eligibilityDocuments", "financialDocuments"]:
            if key not in prod_tender_data["bids"][i]: continue
            for doc in prod_tender_data["bids"][i][key]: # [:n]
                if doc.get("documentType", None) == "proposal": continue
                path = f"bids/{i}" if copy_documents else None
                doc["url"], doc["hash"] = replace_document(doc["url"], doc["format"], path)
                response = requests.post(
                    f"{BASE_URL_TEST}/api/0/tenders/{config.get('tender_id')}/bids/{bid_id}/documents?acc_token={bid_token}",
                    json={"data": doc},
                    headers=HEADERS_TO
                )
                print(doc["title"], "Done") if response.ok else print(response.text)
        
        print("Confirming bid")
        response = requests.patch(
            f"{BASE_URL_TEST}/api/0/tenders/{config.get('tender_id')}/bids/{bid_id}?acc_token={bid_token}",
            json={"data": {"status": "pending"}},
            headers=HEADERS_TO
        )
        print("Done") if response.ok else print(response.text)


# ! TESTED - FIX
def post_evidences(test_tender_data, prod_tender_data, config, index):
    tender_id = config.get("tender_id")
    tender_token = config.get("tender_token")
    bid_id = config["bids_data"][index]["id"]
    bid_token = config["bids_data"][index]["token"]
    request_body = [rr for rr in prod_tender_data["bids"][index]["requirementResponses"] if rr.get("evidences", [])]
    for rr in request_body:
        rr.pop("classification", None)
        rr["requirement"].pop("title", None)
        rr.pop("unit", None)
    print(request_body)
    response = requests.post(
        f"{BASE_URL_TEST}/api/0/tenders/{tender_id}/bids/{bid_id}/requirement_responses?acc_token={bid_token}",
        json={"data": request_body[0]
        },
        headers=HEADERS_TO
    )
    print("Done") if response.ok else print(response.text)

# * TESTED patch_tender.py prolong_award --index 0 --subindex 0
def prolong_award(test_tender_data, prod_tender_data, config, index, subindex=None):
    # Get the award ID
    tender_id = config.get("tender_id")
    tender_token = config.get("tender_token")
    response = requests.get(
        f"{BASE_URL_TEST}/api/0/tenders/{tender_id}/awards", headers=HEADERS_TO
    )
    if response.json()["data"] == []:
        print("No awards found")
        return

    award_id = response.json()["data"][index]["id"]
    award_data = prod_tender_data["awards"][index]
    # Prolong the award review period
    if subindex is not None:
        print("Prolonging the award review period")
        if "milestones" in award_data:
            response = requests.post(
                f"{BASE_URL_TEST}/api/0/tenders/{tender_id}/awards/{award_id}/milestones?acc_token={tender_token}",
                json={"data": award_data["milestones"][subindex]},
                headers=HEADERS_TO,
            )
            print("Done") if response.ok else print(response.text)
        else:
            print("No milestones available for prolongation.")

# * TESTED patch_tender.py sign_award --index 0
def sign_award(test_tender_data, prod_tender_data, config, index, copy_documents=False):
    tender_id = config.get("tender_id")
    tender_token = config.get("tender_token")
    if test_tender_data.get("awards", []):
        award_id = test_tender_data["awards"][index]["id"]
        for doc in prod_tender_data["awards"][index]["documents"]:
            if doc.get("documentType") == "notice":
                signature_doc = {key: value for key, value in doc.items() if key != "author"}
                break
        path = f"awards/{str(index)}" if copy_documents else None
        signature_doc["url"], signature_doc["hash"] = replace_document(doc["url"], doc["format"], path)
        response = requests.post(
            f"{BASE_URL_TEST}/api/0/tenders/{tender_id}/awards/{award_id}/documents?acc_token={tender_token}",
            json={"data": signature_doc},
            headers=HEADERS_TO)
        print("Done") if response.ok else print(response.text)      
    else:
        print("The bid review period has not started yet")
        return

# * TESTED patch_tender.py decide_award --index 0
def decide_award(test_tender_data, prod_tender_data, config, index):
    # Decide the award
    award_data = prod_tender_data["awards"][index]
    award_id = test_tender_data.get("awards", [])[index].get("id")
    tender_id = config.get("tender_id")
    tender_token = config.get("tender_token")
    print("Deciding the award")
    request_body = {
        "data": {
            "status": "active" if (award_data.get("qualified") == True or award_data.get("eligible") == True) else "unsuccessful",
            "title": award_data.get("title"),
            "description": award_data.get("description")
        }
    }
    if award_data.get("qualified") is not None:
        request_body["data"]["qualified"] = award_data.get("qualified")
    if award_data.get("eligible") is not None:
        request_body["data"]["eligible"] = award_data.get("eligible")
    response = requests.patch(
        f"{BASE_URL_TEST}/api/0/tenders/{tender_id}/awards/{award_id}?acc_token={tender_token}",
        json=request_body,
        headers=HEADERS_TO,
    )
    print("Done") if response.ok else print(response.text)

# * TESTED patch_tender.py activate_contract --index 0
def activate_contract(test_tender_data, prod_tender_data, config, index):
    # Get the contract ID
    tender_id = config.get("tender_id")
    tender_token = config.get("tender_token")
    contract_data = requests.get(
        f"https://public-api.prozorro.gov.ua/api/2.5/contracts/{prod_tender_data['contracts'][index]['id']}"
    ).json()["data"]
    if contract_data['status'] not in ["active", "terminated"]:
        return
    contract_id = requests.get(
        f"{BASE_URL_TEST}/api/0/tenders/{tender_id}/contracts"
    ).json()["data"][index]["id"]

    request_body = contract_data
    for key in ["dateSigned", "owner", "suppliers", "amountPaid", "id", "changes", "dateCreated", "date", "awardID", "tender_id", "documents", "contractID", "dateModified", "buyer", "buyerID"]:
        request_body.pop(key, None)
    
    # Activate the contract
    response = requests.patch(
        f"{BASE_URL_TEST}/api/0/contracts/{contract_id}?acc_token={tender_token}",
        json={"data": request_body},
        headers=HEADERS_TO
    )
    print("Done") if response.ok else print(response.text)

# * TESTED patch_tender.py add_contract_change --index 0 --subindex 0
def add_contract_change(test_tender_data, prod_tender_data, config, index, subindex, copy_documents=False):
    contract_data = requests.get(
        f"https://public-api.prozorro.gov.ua/api/2.5/contracts/{prod_tender_data['contracts'][index]['id']}"
    ).json()["data"]
    contract_id = test_tender_data["contracts"][index]["id"]
    change_data = contract_data["changes"][subindex]
    tender_token = config.get("tender_token")
    change_data.pop('dateSigned', None)
    
    response = requests.post(
        f"{BASE_URL_TEST}/api/0/contracts/{contract_id}/changes?acc_token={tender_token}",
        json={"data": change_data},
        headers=HEADERS_TO
    )
    print("Change added") if response.ok else print(response.text)
    change_old_id = change_data['id']
    change_new_id = response.json()['data']['id']
    
    print("Uploading documents")
    for doc in contract_data['documents']:
        if doc['documentOf'] == 'change' and doc['relatedItem'] == change_old_id:
            doc['relatedItem'] = change_new_id
            path = f"contracts/{str(index)}/changes/{str(subindex)}" if copy_documents else None
            doc["url"], doc["hash"] = replace_document(doc["url"], doc["format"], path)
            response = requests.post(
                f"{BASE_URL_TEST}/api/0/contracts/{contract_id}/documents?acc_token={tender_token}",
                json={"data": doc},
                headers=HEADERS_TO
            )
            print("Document added") if response.ok else print(response.text)
        
    # Activate the change
    print("Activating the change")
    # time.sleep(10)
    response = requests.patch(
        f"{BASE_URL_TEST}/api/0/contracts/{contract_id}/changes/{change_new_id}?acc_token={tender_token}",
        json={
            "data": {
                "status": "active",
                "dateSigned": (datetime.now()).replace(microsecond=0).isoformat() + "+03:00"
            }
        },
        headers=HEADERS_TO
    )
    print("Change activated") if response.ok else print(response.text)

def main():
    parser = argparse.ArgumentParser()
    functions = [f for f in globals().keys() if callable(globals()[f]) and f not in ["main", "load_config", "get_tender_data", "delete_documents_func"]]
    # TODO: add arguments for other modules if needed
    parser.add_argument("module", choices=functions)
    parser.add_argument("--index", type=int, required=False)
    parser.add_argument("--subindex", type=int, required=False)
    parser.add_argument("--doc_index", type=int, required=False) 
    parser.add_argument("--doc_title", type=str, required=False) 
    parser.add_argument("--doc_index_from", type=int, required=False)
    parser.add_argument("--doc_index_to", type=int, required=False)
    parser.add_argument("--object", type=str, required=False)
    parser.add_argument("--subobject", type=str, required=False)
    parser.add_argument("--award_index", type=int, required=False)
    parser.add_argument("-copy_documents", action="store_true", help="Copy documents")
    parser.add_argument("-delete_documents", action="store_true", help="Delete documents")
    
    args = parser.parse_args()
    
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
    delete_documents = args.delete_documents or False

    prod_tender_id = CONFIG.get("prod_tender_id")
    tender_id = CONFIG.get("tender_id")

    test_tender_data = requests.get(f"{BASE_URL_TEST}/api/0/tenders/{tender_id}").json()["data"]
    prod_tender_data = requests.get(f"https://public-api.prozorro.gov.ua/api/2.5/tenders/{prod_tender_id}").json()["data"]
    
    for module in functions:
        if args.module == module:
            target_func = globals()[module]
            # Get the target function's signature to pass only the expected arguments
            sig = inspect.signature(target_func)
            func_params = sig.parameters.keys()

            # Dictionary of all command-line arguments
            all_args = vars(args)

            # Filter the arguments, keeping only those present in the function signature
            args_for_func = {
                k: v for k, v in all_args.items() if k in func_params and v is not None
            }
            target_func(test_tender_data, prod_tender_data, CONFIG, **args_for_func)
            break

    if delete_documents:
        delete_documents_func(delete_documents)

if __name__ == "__main__":
    main()