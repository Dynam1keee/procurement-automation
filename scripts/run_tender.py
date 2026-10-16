import unittest
import requests
import time
import copy
from datetime import datetime, timedelta
import json
import os
import argparse
import shutil
import urllib.parse

TENDER_DIR = os.getcwd()
CONFIG_FILE = os.path.join(TENDER_DIR, "tender_config.json")
LAST_TENDER_FILE = os.path.join(TENDER_DIR, "last_tender.json")

class TestAPI(unittest.TestCase):
    BASE_URL = "https://lb-api-staging.prozorro.gov.ua"
    BASE_URL_PROD = "https://public-api.prozorro.gov.ua"
    HEADERS = {
        "Authorization": "YOUR_TOKEN",
        "Content-Type": "application/json",
    }
    
    prod_tender_id = None
    tender_data = {}
    plan_data = {}
    bids_data = []
    minutes_to_days = 0
    ignore_documents = False
    copy_documents = False
    delete_documents = False
    from_file = False
    no_bids = False
    
    @classmethod
    def setUpClass(cls):
        if TestAPI.copy_documents:
            print("Cleaning the documents folder...")
            documents_dir = os.path.join(TENDER_DIR, "documents")
            if os.path.exists(documents_dir):
                try:
                    shutil.rmtree(documents_dir)
                    print(f"Folder '{documents_dir}' and its contents have been successfully deleted for the new upload.")
                except Exception as e:
                    print(f"Error while cleaning folder '{documents_dir}': {e}")
            print("Processing documents")
        if cls.from_file:
            try:
                with open(os.path.join(TENDER_DIR, "tender_data.json"), "r", encoding="utf-8") as f:
                    cls.tender_data = json.load(f)
            except FileNotFoundError:
                print("File 'tender_data.json' was not found.")
                exit(1)
            except json.JSONDecodeError:
                print("Error decoding JSON from file 'tender_data.json'.")
                exit(1)
        else:
            cls.tender_data = requests.get(f"{cls.BASE_URL_PROD}/api/2.5/tenders/{cls.prod_tender_id}").json()
        if cls.tender_data.get("data", {}).get("plans"):
            cls.plan_data = requests.get(f"{cls.BASE_URL_PROD}/api/2.5/plans/{cls.tender_data['data']['plans'][0]['id']}").json()["data"]
            cls.replace_documents(cls.plan_data)
        
        cls.replace_documents(cls.tender_data["data"])
    
    @classmethod
    def tearDownClass(cls):
        if cls.delete_documents:
            print('=' * 70)
            print("Deleting documents")
            documents_dir = os.path.join(TENDER_DIR, "documents")
            if os.path.exists(documents_dir):
                try:
                    shutil.rmtree(documents_dir)
                    print(f"Folder '{documents_dir}' and its contents have been successfully deleted.")
                except Exception as e:
                    print(f"Error while deleting folder '{documents_dir}': {e}")

    ### DOCUMENTS PROCESSING
    @staticmethod
    def upload_document(url, format, path=None):
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

                if path:
                    documents_path = os.path.join(documents_path, path)
                os.makedirs(documents_path, exist_ok=True)
                with open(os.path.join(documents_path, filename), 'wb') as f:
                    f.write(download_response.content)
                
                # print(f"\nDocument successfully downloaded and saved as '{filename}'")
            else:
                print(f"\nFailed to download the document. The server returned status code: {download_response.status_code}")
                print("Response text:", download_response.text)
                return None, None

        except requests.exceptions.RequestException as e:
            print(f"\nAn error occurred while making the request: {e}")
            return None, None

        if filename and download_response and download_response.ok:
            doc_server_url = "https://upload-docs-staging.prozorro.gov.ua/upload"

            files_to_upload = [('file', (filename, open(os.path.join(documents_path, filename), 'rb'), download_response.headers.get('Content-Type')))]
            # print("Preparing for upload:", files_to_upload)
            headers = {
                'Authorization': "YOUR_TOKEN",
            }

            upload_api_response = requests.post(doc_server_url, headers=headers, files=files_to_upload)

            display_path = f"documents/{path + '/' if path else ''}{filename}"
            print(f"Uploaded: '{display_path}'")
            # print("\nServer response to the upload:")
            return upload_api_response.json()["data"]["url"], upload_api_response.json()["data"]["hash"]
        return None, None

    @staticmethod
    def replace_documents(data):
        for doc in data.get("documents", []):
            if TestAPI.copy_documents:
                doc["url"], doc["hash"] = TestAPI.upload_document(doc["url"], doc["format"])
            else:
                if doc["format"] == "application/pkcs7-signature":
                    doc["url"] = "https://public-docs-staging.prozorro.gov.ua/get/9224fbc9a855460ab02e025bfa30f3ef?KeyID=f557937a&Signature=jJWwOItYENH2ehq7PIaPN5santPlcaVDTwkmdWTeOXKboSIS05pBPbda9QWJXjpu9J6i8EwLSThFLWLMm18%252BDw%253D%253D"
                    doc["hash"] = "md5:72d399ffb75c2f122a942ac3236907d6"
                else:
                    doc["url"] = "https://public-docs-staging.prozorro.gov.ua/get/da42cdf067904d2084373bec23c911c2?KeyID=f557937a&Signature=nGixPjN33pi872X9B4FJdqgU5IyloBjsPzfzr18bxbtp1bRmZVhKb1CcCpDsJdBEPtBPFFnfCHa957mz7qOqDg%253D%253D"
                    doc["hash"] = "md5:37ba6f5ebd1ba42bcc40cb867fcc1d6d"

    @staticmethod
    def _add_business_days(start_date, delta):
        end_date = start_date
        days_to_add = delta.days
        while days_to_add > 0:
            end_date += timedelta(days=1)
            if end_date.weekday() < 5:  # Monday is 0, Sunday is 6
                days_to_add -= 1
        # Add the time component of the delta
        end_date += timedelta(seconds=delta.seconds, microseconds=delta.microseconds)
        return end_date
 
    def setUp(self):
        print("=" * 70)
        self.start_time = time.time()

    def tearDown(self):
        exec_time = time.time() - self.start_time
        print(f"Completed in {exec_time:.3f} seconds")

    def create_plan(self):
        if not self.tender_data["data"].get("plans"):
            print("No plan found, skipping")
            return
        print("Creating plan")
        for key in ["status", "datePublished", "planID", "owner", "dateCreated", "dateModified", "tender_id", "milestones"]:
            self.plan_data.pop(key, None)
        
        response = requests.post(
            f"{self.BASE_URL}/api/0/plans",
            json={"data": self.plan_data},
            headers=self.HEADERS,
        )
        if "is required for local budget" in response.text:
            print("Error, retrying with ТПКВКМБ...")
            self.plan_data["budget"]["breakdown"][0]["classification"] = {
                "scheme": "ТПКВКМБ",
                "id": "0100",
                "description": "Test description",
            }
            self.plan_data["budget"]["breakdown"][0]["address"] = {
                "countryName": "Україна",
                "addressDetails": [
                    {
                        "scheme": "КАТОТТГ",
                        "id": "UA32000000000030281",
                        "description": "Test address"
                    }
                ]
            }
            response = requests.post(
                f"{self.BASE_URL}/api/0/plans",
                json={"data": self.plan_data},
                headers=self.HEADERS,
            )
        elif "is required for state budget" in response.text:
            print("Error, retrying with КПК...")
            self.plan_data["budget"]["breakdown"][0]["classification"] = {
                "scheme": "КПК-2025",
                "id": "1708",
                "description": "Test description",
            }
            response = requests.post(
                f"{self.BASE_URL}/api/0/plans",
                json={"data": self.plan_data},
                headers=self.HEADERS
            )
        self.assertEqual(response.status_code, 201, response.json())
        TestAPI.plan_id = response.json()["data"]["id"]
        print("Plan created")

    def create_tender(self):        
        TestAPI.start_time = time.time()
        print("Creating tender")
        request_body = copy.deepcopy(self.tender_data)

        request_body["data"]["mode"] = "test"
        # ADD FOR TEST
        if request_body["data"]["procurementMethodType"] != "reporting" and TestAPI.minutes_to_days != 0: # True - for test
            request_body["data"]["procurementMethodDetails"] = f"quick, accelerator={86400 / (TestAPI.minutes_to_days * 60)}" # 21600
            request_body["data"]["submissionMethodDetails"] = "quick(mode:no-auction)"
        
        for key in ["awards", "noticePublicationDate", "dateModified", "tenderID", "complaintPeriod", "bids", "date", "owner", "criteria", "questions", "status", "contracts", "documents", "plans", "next_check", "complaints"]:
            request_body["data"].pop(key, None)
        
        if request_body["data"]["procurementMethodType"] != "reporting":
            for lot in request_body["data"]["lots"]: # ! Error for the procurement type (request for proposals)
                for key in ["auctionUrl", "auctionPeriod", "status"]:
                    lot.pop(key, None)

            for period in ["enquiryPeriod", "tenderPeriod", "awardPeriod"]:
                if request_body["data"].get("procurementMethodDetails"):
                    enquiry_end = (datetime.now() + timedelta(minutes=TestAPI.minutes_to_days * 8))
                    tender_end = (enquiry_end + timedelta(minutes=TestAPI.minutes_to_days * 8))
                    award_end = (tender_end + timedelta(minutes=TestAPI.minutes_to_days))
                    request_body["data"]["enquiryPeriod"] = {"endDate": enquiry_end.replace(microsecond=0).isoformat() + "+03:00"}
                    request_body["data"]["tenderPeriod"] = {"endDate": tender_end.replace(microsecond=0).isoformat() + "+03:00"}
                    request_body["data"]["awardPeriod"] = {"endDate": award_end.replace(microsecond=0).isoformat() + "+03:00"}
                else:
                    if request_body["data"].get(period):
                        date_created = datetime.fromisoformat(request_body["data"]["dateCreated"]).date()
                        if request_body["data"][period].get("endDate") and request_body["data"][period].get("startDate"):
                            end = datetime.fromisoformat(request_body["data"][period]["endDate"]).date()
                            duration = end - date_created
                            request_body["data"][period] = {
                                "endDate": (datetime.now() + timedelta(days=duration.days)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "+03:00"
                            }
                            
            request_body["data"].pop("awardPeriod", None)
            
        request_body["data"].pop("dateCreated", None)
        
        print("The clarification period ends on", request_body["data"].get("enquiryPeriod", {}).get("endDate"))
        print("The bid submission period ends on", request_body["data"].get("tenderPeriod", {}).get("endDate"))
        
        endpoint = f"{self.BASE_URL}/api/0/plans/{TestAPI.plan_id}/tenders" if hasattr(TestAPI, 'plan_id') else f"{self.BASE_URL}/api/0/tenders"
        
        response = requests.post(
            endpoint,
            json=request_body,
            headers=self.HEADERS
        )
        if "\"signerInfo\": \"This field is required" in response.text:
            print("Error, retrying with signerInfo...")
            request_body["data"]["procuringEntity"]["signerInfo"] = {
                "name": "Test Testovich",
                "telephone": "+380950000000",
                "email": "example@email.com",
                "iban": "111111111111111",
                "authorizedBy": "Статут компанії",
                "position": "Генеральний директор"
            }
            response = requests.post(
                endpoint,
                json=request_body,
                headers=self.HEADERS
            )
        self.assertEqual(response.ok, True, response.text)
        response_json = response.json()
        TestAPI.tender_id = response_json["data"]["id"]
        TestAPI.tender_token = response_json["access"]["token"]
        print("Tender created")
        print(
            f"URL: staging.prozorro.gov.ua/uk/tender/{response_json['data']['tenderID']}"
        )
        print(f"Tender ID: {TestAPI.tender_id}")
        print(f"Tender token: {TestAPI.tender_token}")

    def add_documents(self):
        print("Adding documents")
        request_body = []
        for doc in self.tender_data["data"]["documents"]:
            if TestAPI.ignore_documents:
                if doc.get('documentType', '') in ['contractTemplateName', 'contractProforma', 'notice']:
                    new_doc = {key: value for key, value in doc.items() if key != "author"}
                    request_body.append(new_doc)
            else:
                if doc.get("author") == "tender_owner" and datetime.fromisoformat(doc["datePublished"]) < datetime.fromisoformat(self.tender_data["data"]["dateCreated"]) + timedelta(hours=12):
                    new_doc = {key: value for key, value in doc.items() if key != "author"}
                    request_body.append(new_doc)
        if request_body:
            response = requests.post(
                f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/documents?acc_token={self.tender_token}",
                json={"data": request_body},
                headers=self.HEADERS,
            )
            self.assertEqual(response.status_code, 201, response.text)
            print("Documents added")
        
    def add_criteria(self):
        if not self.tender_data["data"].get("criteria"):
            print("No criteria found, skipping")
            return
        print("Adding criteria")
        response = requests.post(
            f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/criteria?acc_token={self.tender_token}",
            json={"data": self.tender_data["data"]["criteria"]},
            headers=self.HEADERS,
        )
        self.assertEqual(response.status_code, 201, response.text)
        print("Criteria added")

    def activate_tender(self):
        print("Activating tender")
        if self.tender_data["data"]["procurementMethodType"] == "reporting":
            status = "active"
        elif self.tender_data["data"]["procurementMethodType"] == "belowThreshold":
            status = "active.enquiries"
        else:
            status = "active.tendering"
        response = requests.patch(
            f"{self.BASE_URL}/api/0/tenders/{self.tender_id}?acc_token={self.tender_token}",
            json={"data": {"status": status}},
            headers=self.HEADERS,
        )
        self.assertEqual(response.status_code, 200, response.text)
        print("Tender activated")
        # Save tender_id and tender_token to a file
        tender_details = {
            "prod_tender_id": TestAPI.prod_tender_id,
            "tender_id": TestAPI.tender_id,
            "tender_token": TestAPI.tender_token
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(tender_details, f, indent=4, ensure_ascii=False)
        print("Saved tender details to config file")
        with open(LAST_TENDER_FILE, "w", encoding="utf-8") as f:
            json.dump(response.json(), f, indent=4, ensure_ascii=False)
        print("Saved last tender details to last_tender.json")

    def add_bids(self):
        # Wait for the correct status
        while True:
            response = requests.get(f"{self.BASE_URL}/api/0/tenders/{self.tender_id}")
            if not response.ok:
                print(f"Error retrieving tender status: {response.text}")
                time.sleep(5)
                continue
            tender_status = response.json()["data"]["status"]
            if tender_status not in ["active.tendering"]:
                print(f"Cannot add bids while the tender is in status '{tender_status}'")
                if self.minutes_to_days != 0 and self.minutes_to_days < 1:
                    print("Waiting...", end="\r")
                    time.sleep(60 * self.minutes_to_days)
                else:
                    return
            else:
                print(f"\nTender status is '{tender_status}', adding bids.")
                break
        
        if not self.tender_data["data"].get("bids"):
            print("No bids found in the source data, skipping.")
            return

        bids_data = self.tender_data["data"]["bids"]
        for i, bid in enumerate(bids_data):
            print(f"Adding bid {i+1}")
            bid["status"] = "pending"
            bid.pop("date", None)
            bid.pop("submissionDate", None)
    
            if bid.get("requirementResponses"):
                for rr in bid["requirementResponses"]:
                    rr.pop("classification", None)
                    rr["requirement"].pop("title", None)
                    rr.pop("unit", None)
                    rr.pop("evidences", None)
    
            if "items" not in bid:
                bid["items"] = []
                for item in self.tender_data["data"]["items"]:
                    if item.get("relatedLot") in [lv.get("relatedLot") for lv in bid.get("lotValues", [])]:
                        item.pop("classification", None)
                        item.pop("deliveryAddress", None)
                        item.pop("deliveryDate", None)
                        bid["items"].append(item)
            
            for lv in bid.get("lotValues", []):
                lv.pop("date", None)
                lv.pop("status", None)
                lv.pop("initialValue", None)
                
            for key in ["documents", "eligibilityDocuments", "financialDocuments"]:
                if key in bid and isinstance(bid[key], list):
                    for doc in bid[key]:
                        if self.copy_documents:
                            path = f"bids/{i}"
                            new_url, new_hash = TestAPI.upload_document(doc["url"], doc["format"], path)
                            if new_url and new_hash:
                                doc["url"], doc["hash"] = new_url, new_hash
                        else:
                            if doc["format"] == "application/pkcs7-signature":
                                doc["url"] = "https://public-docs-staging.prozorro.gov.ua/get/647142191cfe428d887fb80e77186ecb?KeyID=f557937a&Signature=IMFGvThQpmUhQ%252BzdgwY6pWRS6BayPJ5rgvxIxZvQZwO4cb2enJWFWCIdlH7AUFot%2FhiC5CjEruOVwFGzP4v5Dw%253D%253D"
                                doc["hash"] = "md5:9caa9d0b766f29b7ab43403d21b93a8c"
                            else:
                                doc["url"] = "https://public-docs-staging.prozorro.gov.ua/get/49e07ef1ea2b4b31936154b7ee27e908?KeyID=f557937a&Signature=QZwC1Jp3cGZfqE%2FOSAM915vcdzAP0HNjSSukq5bemDwEiTHcISYQir97A29d2NNcU94CTKx9i0t2iijqJouyCQ%253D%253D"
                                doc["hash"] = "md5:37ba6f5ebd1ba42bcc40cb867fcc1d6d"

            response = requests.post(
                f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/bids",
                json={"data": bid},
                headers=self.HEADERS
            )
            if response.ok:
                config = json.load(open(CONFIG_FILE, "r", encoding="utf-8"))
                bid_id = response.json()["data"]["id"]
                bid_token = response.json()["access"]["token"]
                if "bids_data" not in config:
                    config["bids_data"] = []
                config["bids_data"].append({"id": bid_id, "token": bid_token})
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                print(f"Bid {i+1} added; details saved.")
            else:
                print(response.text)
            
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=str, help="Tender ID (UA-... format) or UUID")
    parser.add_argument("--minutes_to_days", type=float, default=0, help="Number of minutes representing one day")
    parser.add_argument("-ignore_documents", action="store_true", help="Create documents")
    parser.add_argument("-copy_documents", action="store_true", help="Copy documents")
    parser.add_argument("-delete_documents", action="store_true", help="Delete documents")
    parser.add_argument("-from_file", action="store_true", help="Load test data from the tender_data.json file.")
    parser.add_argument("-no_bids", action="store_true", help="Do not add bids")
    args = parser.parse_args()
    
    tender_id_input = args.id
    TestAPI.minutes_to_days = args.minutes_to_days
    TestAPI.ignore_documents = args.ignore_documents
    TestAPI.copy_documents = args.copy_documents
    TestAPI.delete_documents = args.delete_documents
    TestAPI.from_file = args.from_file
    TestAPI.no_bids = args.no_bids

    # Determine whether the input is a UUID or an ID in the UA- format
    if not TestAPI.from_file:
        if tender_id_input.startswith("UA-"):
            print(f"Retrieving UUID for tender {tender_id_input}...")
            try:
                # Use the same URL as in the class
                response = requests.get(f"https://prozorro.gov.ua/api/tenders/{tender_id_input}")
                exit(1) if response.ok is False else None
                tender_uuid = response.json().get("id")
                print(f"UUID retrieved: {tender_uuid}")
                TestAPI.prod_tender_id = tender_uuid
            except requests.exceptions.RequestException as e:
                print(f"Error while making the API request: {e}")
                exit(1)
        else:
            # Assume the input is a UUID
            TestAPI.prod_tender_id = tender_id_input
    
    suite = unittest.TestSuite()
    tests = ["create_plan", "create_tender", "add_documents", "add_criteria", "activate_tender", "add_bids"] 
    if TestAPI.no_bids:
        tests.remove("add_bids")
    for test in tests:
        suite.addTest(TestAPI(test))
    
    runner = unittest.TextTestRunner(failfast=True) # verbosity=2
    runner.run(suite)