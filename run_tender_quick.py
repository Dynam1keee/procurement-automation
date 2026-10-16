import unittest
import requests
import time
import copy
from datetime import datetime, timedelta
import argparse
import urllib.parse
import os
import shutil


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
    contracts_data = []
    bids_data = []
    copy_documents = False
    delete_documents = False

    # TODO: Implement contract modifications

    # DOCUMENT PROCESSING
    @staticmethod
    def upload_document(url, format):
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

                documents_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents")
                filename = temp_filename

                # Create the directory if it does not exist
                os.makedirs(documents_dir, exist_ok=True)
                with open(os.path.join(documents_dir, filename), 'wb') as f:
                    f.write(download_response.content)

                # print(f"\nDocument successfully downloaded and saved as '{filename}'")
            else:
                print(f"\nFailed to download the document. Server returned status code: {download_response.status_code}")
                print("Response text:", download_response.text)

        except requests.exceptions.RequestException as e:
            print(f"\nAn error occurred while making the request: {e}")

        if filename and download_response and download_response.ok:
            doc_server_url = "https://upload-docs-staging.prozorro.gov.ua/upload"

            files_to_upload = [('file', (filename, open(os.path.join(documents_dir, temp_filename), 'rb'), download_response.headers.get('Content-Type')))]
            # print("Preparing for upload:", files_to_upload)
            headers = {
                'Authorization': "YOUR_TOKEN",
            }

            upload_api_response = requests.post(doc_server_url, headers=headers, files=files_to_upload)

            print(f"Uploaded: 'documents/{filename}'")
            # print("\nServer response to the upload:")
            return upload_api_response.json()["data"]["url"], upload_api_response.json()["data"]["hash"]

    @staticmethod
    def replace_documents(data):
        def _replace(d):
            if isinstance(d, dict):
                for key, value in d.items():
                    if "documents" in key.lower() and isinstance(value, list):
                        for doc in value:
                            if TestAPI.copy_documents:
                                doc["url"], doc["hash"] = TestAPI.upload_document(doc["url"], doc["format"])
                            else:
                                if doc["format"] == "application/pkcs7-signature":
                                    doc["url"] = "https://public-docs-staging.prozorro.gov.ua/get/647142191cfe428d887fb80e77186ecb?KeyID=f557937a&Signature=IMFGvThQpmUhQ%252BzdgwY6pWRS6BayPJ5rgvxIxZvQZwO4cb2enJWFWCIdlH7AUFot%2FhiC5CjEruOVwFGzP4v5Dw%253D%253D"
                                    doc["hash"] = "md5:9caa9d0b766f29b7ab43403d21b93a8c"
                                else:
                                    doc["url"] = "https://public-docs-staging.prozorro.gov.ua/get/49e07ef1ea2b4b31936154b7ee27e908?KeyID=f557937a&Signature=QZwC1Jp3cGZfqE%2FOSAM915vcdzAP0HNjSSukq5bemDwEiTHcISYQir97A29d2NNcU94CTKx9i0t2iijqJouyCQ%253D%253D"
                                    doc["hash"] = "md5:37ba6f5ebd1ba42bcc40cb867fcc1d6d"
                    else:
                        _replace(value)
            elif isinstance(d, list):
                for item in d:
                    _replace(item)

        _replace(data)

    @classmethod
    def setUpClass(cls):
        if not cls.prod_tender_id:
            raise unittest.SkipTest("prod_tender_id is not set. Skipping tests that depend on this data.")
        if cls.delete_documents:
            print("Cleaning up the documents directory...")
            documents_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents")
            if os.path.exists(documents_dir):
                try:
                    shutil.rmtree(documents_dir)
                    print(f"Directory '{documents_dir}' and its contents have been successfully deleted for a fresh download.")
                except Exception as e:
                    print(f"Error while cleaning up directory '{documents_dir}': {e}")
        print("Processing documents")
        cls.tender_data = requests.get(f"{cls.BASE_URL_PROD}/api/2.5/tenders/{cls.prod_tender_id}").json()
        if cls.tender_data.get("data", {}).get("plans"):
            cls.plan_data = requests.get(f"{cls.BASE_URL_PROD}/api/2.5/plans/{cls.tender_data['data']['plans'][0]['id']}").json()["data"]
            cls.replace_documents(cls.plan_data)
        if cls.tender_data.get("data", {}).get("contracts"):
            cls.contracts_data = [
                requests.get(f"{cls.BASE_URL_PROD}/api/0/contracts/{c['id']}").json()['data']
                for c in cls.tender_data["data"]["contracts"]
            ]
            cls.replace_documents(cls.contracts_data)

        cls.replace_documents(cls.tender_data)

    @classmethod
    def tearDownClass(cls):
        if cls.delete_documents:
            print('=' * 70)
            print("Deleting documents")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            documents_dir = os.path.join(script_dir, "documents")
            if os.path.exists(documents_dir):
                try:
                    shutil.rmtree(documents_dir)
                    print(f"Directory '{documents_dir}' and its contents have been successfully deleted.")
                except Exception as e:
                    print(f"Error while deleting directory '{documents_dir}': {e}")

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
                "id": "0110000",
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
        print("Creating tender")
        request_body = copy.deepcopy(self.tender_data)

        MINUTES_TO_DAYS = 0.2

        request_body["data"]["mode"] = "test"
        # ADD FOR TEST
        if request_body["data"]["procurementMethodType"] != "reporting" and True: # True - for testing
            request_body["data"]["procurementMethodDetails"] = f"quick, accelerator={86400 / (MINUTES_TO_DAYS * 60)}" # 21600
            request_body["data"]["submissionMethodDetails"] = "quick(mode:no-auction)"

        for key in ["awards", "noticePublicationDate", "dateCreated", "dateModified", "tenderID", "complaintPeriod", "bids", "date", "owner", "criteria", "questions", "status", "contracts", "documents", "plans", "next_check", "complaints"]:
            request_body["data"].pop(key, None)

        if request_body["data"]["procurementMethodType"] != "reporting":
            for lot in request_body["data"]["lots"]:
                for key in ["auctionUrl", "auctionPeriod", "status"]:
                    lot.pop(key, None)

            enquiry_end = (datetime.now() + timedelta(minutes=(MINUTES_TO_DAYS * 3) + 0.5)) # 3
            tender_end = (enquiry_end + timedelta(minutes=MINUTES_TO_DAYS * 8))
            award_end = (tender_end + timedelta(minutes=MINUTES_TO_DAYS))
            request_body["data"]["enquiryPeriod"] = {"endDate": enquiry_end.replace(microsecond=0).isoformat() + "+03:00"}
            request_body["data"]["tenderPeriod"] = {"endDate": tender_end.replace(microsecond=0).isoformat() + "+03:00"}
            request_body["data"]["awardPeriod"] = {"endDate": award_end.replace(microsecond=0).isoformat() + "+03:00"}

        endpoint = f"{self.BASE_URL}/api/0/plans/{TestAPI.plan_id}/tenders" if TestAPI.plan_data else f"{self.BASE_URL}/api/0/tenders"
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
        request_body = [
            {key: value for key, value in doc.items() if key != "author"}
            for doc in self.tender_data["data"]["documents"]
            if doc.get("author") == "tender_owner"
        ]
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

    def post_questions_and_answers(self):
        if not self.tender_data["data"].get("questions"):
            print("No questions or answers found, skipping")
            return
        print("Publishing questions and answers")
        for i, q in enumerate(copy.deepcopy(self.tender_data['data']['questions'])):
            # Post question
            q.pop('dateAnswered', None)
            q.pop('answer', None)

            q['author'] = {
                "address": {
                    "countryName": "Україна",
                    "locality": "м. Львів",
                    "postalCode": "79013",
                    "region": "Львівська область",
                    "streetAddress": "вул. Островського, 34"
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
                f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/questions",
                json={"data": q},
                headers=self.HEADERS
            )
            if response.status_code != 201:
                print(response.text)
            else:
                response_json = response.json()
                question_id = response_json['data']['id']
                print("Done")

            # Post answer
            response = requests.patch(
                f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/questions/{question_id}?acc_token={self.tender_token}",
                json={
                    "data": {"answer": self.tender_data['data']['questions'][i]['answer']}},
                headers=self.HEADERS
            )
            print("Done") if response.ok else print(response.text)

    def post_complaint(self, award_index=None):
        if award_index is None:
            if not self.tender_data["data"].get("complaints"):
                print("No complaints found, skipping")
                return
        elif not self.tender_data["data"]["awards"][award_index].get("complaints"):
            print("No complaints found, skipping")
            return

        if award_index is not None:
            response = requests.get(
                f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/awards",
            )
            award_data = response.json()["data"][award_index]
            award_id = award_data["id"] if award_index is not None else None

        if award_id:
            endpoint_url = f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/awards/{award_id}/complaints"
            complaint_data = self.tender_data["data"]["awards"][award_index]["complaints"][0]
        else:
            endpoint_url = f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/complaints"
            complaint_data = self.tender_data["data"]["complaints"][0]

        print("Creating complaint")
        complaint_data_copy = copy.deepcopy(complaint_data)
        complaint_data_copy.pop("reviewPlace", None)
        complaint_data_copy.pop("reviewDate", None)
        complaint_data_copy.pop("tendererActionDate", None)
        complaint_data_copy.pop("complaintID", None)
        complaint_data_copy.pop("tendererAction", None)
        complaint_data_copy.pop("value", None)
        complaint_data_copy.pop("acceptance", None)
        complaint_data_copy.pop("dateSubmitted", None)
        complaint_data_copy.pop("dateAccepted", None)
        complaint_data_copy.pop("dateDecision", None)

        complaint_data_copy["status"] = "draft"

        bid_token = None
        if award_id:
            bid_id = award_data["bid_id"]
            for bid in self.bids_data:
                if bid["id"] == bid_id:
                    complaint_data_copy["bid_id"] = bid["id"]
                    bid_token = bid["token"]
                    break

        for obj in complaint_data_copy["objections"]:
            if award_id:
                obj["relatedItem"] = award_id
            else:
                obj["relatedItem"] = self.tender_id

        complaint_data_copy["documents"] = [
            {k: v for k, v in doc.items() if k != "author"}
            for doc in complaint_data["documents"]
            if doc["author"] == "complaint_owner"
        ]

        while True:
            response = requests.post(
                f"{endpoint_url}?acc_token={bid_token if award_id else self.tender_token}",
                json={"data": complaint_data_copy},
                headers=self.HEADERS,
            )
            if response.status_code != 201:
                print(response.text)
                time.sleep(5)
            else:
                break

        print(response.json()['data']['status'])
        complaint_id = response.json()["data"]["id"]
        complaint_token = response.json()["access"]["token"]

        if complaint_data["status"] == "mistaken":
            print("Complaint marked as mistaken")
            response = requests.patch(
                f"{endpoint_url}/{complaint_id}?acc_token={complaint_token}",
                json={"data": {"status": "mistaken"}},
                headers=self.HEADERS,
            )
            self.assertEqual(response.ok, True, response.text)
            print("Done")
        else:
            print("Submitting complaint")
            response = requests.patch(
                f"{endpoint_url}/{complaint_id}?acc_token={complaint_token}",
                json={"data": {"status": "pending"}},
                headers={
                    "Authorization": "YOUR_TOKEN",
                    "Content-Type": "application/json",
                },
            )
            self.assertEqual(response.ok, True, response.text)
            print("Done")
            if complaint_data["status"] == "pending": return

        # Accept complaint
        print("Accepting complaint...")
        response = requests.patch(
            f"{endpoint_url}/{complaint_id}?acc_token={complaint_token}",
            json={
                "data": {
                    "status": "accepted",
                    "reviewDate": complaint_data['reviewDate'],
                    "reviewPlace": complaint_data['reviewPlace']
                }
            },
            headers={
                "Authorization": "YOUR_TOKEN",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        print("Done")
        if complaint_data["status"] == "accepted": return

        # Process complaint decision
        # Add documents
        print("Adding documents to the complaint decision")
        response = requests.post(
            f"{endpoint_url}/{complaint_id}/documents?acc_token={complaint_token}",
            json={"data": [
                {k: v for k, v in doc.items() if k != "author"}
                for doc in complaint_data["documents"]
                if doc["author"] == "aboveThresholdReviewers"
            ]},
            headers={
                "Authorization": "YOUR_TOKEN",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        print("Done")

        # Confirm resolution
        if complaint_data["status"] == "resolved" or not award_id:
            # Satisfy complaint
            print("Satisfying complaint")
            response = requests.patch(
                f"{endpoint_url}/{complaint_id}?acc_token={complaint_token}",
                json={"data": {"status": "satisfied"}},
                headers={
                    "Authorization": "YOUR_TOKEN",
                    "Content-Type": "application/json",
                }
            )
            self.assertEqual(response.status_code, 200, response.text)

            if award_id:
                # Cancel award
                print("Cancelling award")
                while True:
                    response = requests.patch(
                        f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/awards/{award_id}?acc_token={self.tender_token}",
                        json={"data": {"status": "cancelled"}},
                        headers=self.HEADERS
                    )
                    if response.status_code != 200:
                        print(response.text)
                        time.sleep(10)
                    else:
                        print("Decision accepted")
                        break

            # Confirm resolution
            # Add documents
            print("Adding documents to confirm the resolution")
            response = requests.post(
                f"{endpoint_url}/{complaint_id}/documents?acc_token={self.tender_token}",
                json={
                    "data": [
                        {k: v for k, v in doc.items() if k != "author"}
                        for doc in complaint_data["documents"]
                        if doc["author"] == "tender_owner"
                    ]
                },
                headers=self.HEADERS
            )
            self.assertEqual(response.status_code, 201, response.text)

            print("Confirming resolution")
            response = requests.patch(
            f"{endpoint_url}/{complaint_id}?acc_token={self.tender_token}",
            json={"data": {
                "tendererAction": complaint_data["tendererAction"],
                "status": "resolved"
            }},
            headers=self.HEADERS)
            self.assertEqual(response.status_code, 200, response.text)
            print("Done")
        else:
            print("Declining complaint")
            response = requests.patch(
            f"{endpoint_url}/{complaint_id}?acc_token={complaint_token}",
            json={"data": {
                "status": "declined"
            }},
            headers={
                "Authorization": "YOUR_TOKEN",
                "Content-Type": "application/json",
            })
            self.assertEqual(response.status_code, 200, response.text)
            print("Done")

    def add_bids(self):
        if not self.tender_data["data"].get("bids"):
            print("No bids found, skipping")
            return
        while True:
            new_tender_data = requests.get(f"{self.BASE_URL}/api/0/tenders/{self.tender_id}").json()["data"]
            if new_tender_data["status"] not in ["active.tendering"]:
                print(f"Cannot add bids while tender status is '{new_tender_data['status']}'", end="\r")
                time.sleep(5)
            else:
                break
        print("Adding bids")
        TestAPI.bids_data = []
        for i, bid in enumerate(self.tender_data["data"]["bids"]):
            bid["status"] = "pending"
            bid.pop("date", None)
            bid.pop("submissionDate", None)

            if "requirementResponses" in bid:
                for rr in bid["requirementResponses"]:
                    rr.pop("classification", None)
                    rr["requirement"].pop("title", None)
                    rr.pop("unit", None)

                    rr.pop("evidences", None)

            if "items" not in bid:
                bid["items"] = []
                for item in self.tender_data["data"]["items"]:
                    if item["relatedLot"] in [lv["relatedLot"] for lv in bid["lotValues"]]:
                        item.pop("classification", None)
                        item.pop("deliveryAddress", None)
                        item.pop("deliveryDate", None)
                        bid["items"].append(item)

            # for rr in bid["requirementResponses"]:
                # rr.pop("classification", None)
                # rr["requirement"].pop("title", None)

            # Special handling for procurement UA-2025-06-10-012672-a
            if self.prod_tender_id == "3db217b6a38a441081637b31deead063":
                bid["items"][3]["quantity"] = 70000 # TODO: test

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

            response = requests.post(
                f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/bids",
                json={"data": bid},
                headers=self.HEADERS
            )
            if "\"signerInfo\": \"This field is required" in response.text:
                print("Error, retrying with signerInfo...")
                bid["tenderers"][0]["signerInfo"] = {
                    "name": "Test Testovich",
                    "telephone": "+380950000000",
                    "email": "example@email.com",
                    "iban": "111111111111111",
                    "authorizedBy": "Статут компанії",
                    "position": "Генеральний директор"
                }
                response = requests.post(
                    f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/bids",
                    json={"data": bid},
                    headers=self.HEADERS
                )
            if response.ok:
                print(f"Bid {i+1} added")
                response_json = response.json()
                TestAPI.bids_data.append({"id": response_json["data"]["id"], "token": response_json["access"]["token"]})
            else:
                print(response.text)

    def add_awards(self):
        if self.tender_data["data"]["procurementMethodType"] == "reporting":
            # Add award
            award_data = self.tender_data['data']['awards'][0]
            award_data.pop('status', None)
            response = requests.post(
                f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/awards?acc_token={self.tender_token}", json={'data': award_data}, headers=self.HEADERS
            )
            response_json = response.json()
            if response.status_code != 201:
                print(response.text)
            else:
                award_id = response_json["data"]["id"]

            # Confirm winner
            response = requests.patch(
                f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/awards/{award_id}?acc_token={self.tender_token}",
                json={"data": {"status": "active", "qualified": True}},
                headers=self.HEADERS
            )
            print("Done") if response.ok else print(response.text)
        else:
            for i, a in enumerate(self.tender_data["data"]["awards"]):
                print(f"=== Award {i+1} ===")
                if self.tender_data["data"]["awards"][i]["status"] == "pending": self.fail("The decision on the bid has not been made")
                # Get award ID
                seconds = 0
                while True:
                    response = requests.get(
                        f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/awards", headers=self.HEADERS
                    )
                    if response.json()["data"] == []:
                        seconds += 5
                        print(f"Waiting {seconds} seconds", end="\r")
                        time.sleep(5)
                    else:
                        break

                award_id = response.json()["data"][i]["id"]

                # Extend award period
                print("Extending award period")
                if "milestones" in a:
                    for milestone in a["milestones"]:
                        if milestone["code"] != "alp":
                            response = requests.post(
                                f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/awards/{award_id}/milestones?acc_token={self.tender_token}",
                                json={"data": milestone},
                                headers=self.HEADERS,
                            )
                            self.assertEqual(response.status_code, 201, response.text)
                            print("Review period extended")

                # Sign award
                print("Signing award")
                response = requests.post(
                    f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/awards/{award_id}/documents?acc_token={self.tender_token}",
                    json={"data": [
                            {key: value for key, value in doc.items() if key != "author"}
                            for doc in a["documents"]
                            if doc.get("documentType") == "notice"
                        ]
                    },
                    headers=self.HEADERS)
                print("Done") if response.ok else print(response.text)

                # Add documents
                for doc in self.tender_data["data"]["awards"][i]["documents"]:
                    if doc["format"] != "application/pkcs7-signature":
                        doc.pop("author", None)

                        response = requests.post(
                            f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/awards/{award_id}/documents?acc_token={self.tender_token}",
                            json={"data": doc},
                            headers=self.HEADERS,
                        )
                        self.assertEqual(response.status_code, 201, response.text)
                        print("Document added")

                # Decide award
                print("Making award decision")
                print(a.get("qualified"), a.get("eligible"))
                request_body = {
                    "data": {
                        "status": "active" if (a.get("qualified") == True or a.get("eligible") == True) else "unsuccessful",
                        "title": a.get("title"),
                        "description": a.get("description")
                    }
                }
                if a.get("qualified") is not None:
                    request_body["data"]["qualified"] = a.get("qualified")
                if a.get("eligible") is not None:
                    request_body["data"]["eligible"] = a.get("eligible")

                while True:
                    response = requests.patch(
                        f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/awards/{award_id}?acc_token={self.tender_token}",
                        json=request_body,
                        headers=self.HEADERS,
                    )
                    if response.status_code != 200:
                        print(response.text)
                        time.sleep(10)
                    else:
                        print("Decision accepted")
                        break

                if self.tender_data["data"]["awards"][i]["status"] == "cancelled":
                    # Cancel award
                    print("Cancelling award")
                    request_body = {
                        "data": {
                            "status": "cancelled"
                        }
                    }
                    response = requests.patch(
                        f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/awards/{award_id}?acc_token={self.tender_token}",
                        json=request_body,
                        headers=self.HEADERS,
                    )
                    print("Award cancelled") if response.ok else print(response.text)

                if a.get("complaints"):
                    self.post_complaint(i)

    def activate_contracts(self):
        print("Activating contracts")
        new_contracts = [
            requests.get(f"{self.BASE_URL}/api/0/contracts/{c['id']}").json()['data']
            for c in requests.get(f"{self.BASE_URL}/api/0/tenders/{self.tender_id}/contracts").json()["data"]
        ]
        # print(new_contracts)
        if new_contracts == []:
            print("No contract found, skipping")
            return
        for oc in self.contracts_data:
            if oc["status"] not in ["active", "terminated"]:
                continue
            for nc in new_contracts:
                buyer_info_new = nc.get("buyer", None)
                buyer_info_old = oc.get("buyer", None)
                if buyer_info_new and buyer_info_old:
                    if buyer_info_new["identifier"]["id"] != buyer_info_old["identifier"]["id"]:
                        continue
                if oc['suppliers'][0]['identifier']['id'] == nc['suppliers'][0]['identifier']['id']:
                    c = copy.deepcopy(oc)

                    c.pop('id', None)
                    c.pop('amountPaid', None)
                    c.pop('changes', None)
                    c.pop('contractID', None)
                    c.pop('buyerID', None)
                    # c.pop('contractNumber', None) # Uncomment if an error occurs
                    c.pop('contractTemplateName', None)
                    c.pop('tender_id', None)
                    c.pop('awardID', None)
                    c.pop('buyer', None)
                    c.pop('documents', None)
                    c.pop('date', None)
                    c.pop('suppliers', None)
                    c.pop('owner', None)
                    c.pop('dateModified', None)
                    c.pop('dateCreated', None)
                    c.pop('dateSigned', None)

                    c['status'] = 'active'

                    # for item in c['items']:
                    #     item['deliveryAddress'] = {"countryName": "Україна"}

                    # for item in c["items"]:
                    #     item.pop('id', None)
                    #     item.pop('classification', None)

                    while True:
                        # Activate contract
                        response = requests.patch(
                            f"{self.BASE_URL}/api/0/contracts/{nc['id']}?acc_token={self.tender_token}",
                            json={"data": c},
                            headers=self.HEADERS,
                        )
                        if response.status_code != 200:
                            print(response.text)
                            time.sleep(10)
                        else:
                            # Upload contract documents
                            if "documents" in oc: # If the original contract has documents
                                response = requests.post(
                                    f"{self.BASE_URL}/api/0/contracts/{nc['id']}/documents?acc_token={self.tender_token}",
                                    json={'data': [
                                        doc for doc in oc['documents'] if doc['documentOf'] == 'contract'
                                    ]},
                                    headers=self.HEADERS
                                )
                                print("Done") if response.ok else print(response.text)
                                break
            # TODO: Add contract changes


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=str, required=True, help="Tender ID (UA-... format) or UUID")
    parser.add_argument("-copy_documents", action="store_true", help="Copy documents")
    parser.add_argument("-delete_documents", action="store_true", help="Delete documents")
    args = parser.parse_args()

    tender_id_input = args.id
    TestAPI.copy_documents = args.copy_documents
    TestAPI.delete_documents = args.delete_documents

    # Determine whether a UUID or a UA-... tender ID was provided
    if tender_id_input.startswith("UA-"):
        print(f"Retrieving UUID for tender {tender_id_input}...")
        try:
            # Use the same URL as the class
            response = requests.get(f"https://prozorro.gov.ua/api/tenders/{tender_id_input}")
            exit(1) if response.ok is False else None
            tender_uuid = response.json().get("id")
            print(f"UUID retrieved: {tender_uuid}")
            TestAPI.prod_tender_id = tender_uuid
        except requests.exceptions.RequestException as e:
            print(f"Error while requesting the API: {e}")
            exit(1)
    else:
        # Assume the provided value is a UUID
        TestAPI.prod_tender_id = tender_id_input

    suite = unittest.TestSuite()
    tests = ["create_plan", "create_tender", "add_documents", "add_criteria", "activate_tender", "post_complaint", "post_questions_and_answers", "add_bids", "add_awards", "activate_contracts"]
    for test in tests: # Use [:5] to run only the first five tests
        suite.addTest(TestAPI(test))

    runner = unittest.TextTestRunner(failfast=True)  # verbosity=2
    runner.run(suite)