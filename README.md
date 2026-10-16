# E-Procurement Lifecycle Automation & Testing

A Python toolkit for reproducing procurement workflows, monitoring changes, and simulating procurement lifecycle events through the Prozorro REST API.

The project supports controlled testing of procurement scenarios by reproducing existing tenders in a staging environment and applying subsequent changes step by step.

## Features

- **Quick tender reproduction** — recreate a procurement workflow from the production environment in staging, using accelerated lifecycle transitions.
- **Full lifecycle reproduction** — reproduce a tender to a selected stage and continue testing through subsequent workflow operations.
- **Change monitoring** — compare the current tender state with previously saved data and identify changes.
- **Tender patching** — apply changes to documents, questions, answers, bids, awards, complaints, and contracts.
- **Document transfer** — download and upload documents between API environments when supported by the workflow.
- **JSON processing** — work with nested procurement data and local JSON files.
- **Monitoring workflow simulation** — support testing related to procurement monitoring, including simulated actions by the contracting authority and monitoring owner.

## Project Structure

```text
procurements/
├── scripts/
│   ├── event_monitor.py
│   ├── patch_tender.py
│   └── run_tender.py
├── run_tender_quick.py
├── requirements.txt
├── .gitignore
└── README.md
```

The scripts operate on procurement-specific data files. Depending on the selected workflow, these files may be created or updated automatically.

| File | Purpose |
|---|---|
| `run_tender_quick.py` | Quickly reproduces a tender without the subsequent manual patching workflow |
| `scripts/run_tender.py` | Reproduces a tender to a stage suitable for further testing |
| `scripts/event_monitor.py` | Monitors changes and compares tender states |
| `scripts/patch_tender.py` | Applies individual procurement lifecycle operations |
| `requirements.txt` | Lists Python dependencies |
| `.gitignore` | Excludes selected local configuration and data files |

## Requirements

- Python 3
- `pip`
- Network access to the relevant Prozorro API environments
- Authorized API access and any required configuration for the selected workflow

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd procurements
```

Create and activate a virtual environment.

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
py -m pip install -r requirements.txt
```

The project currently declares `requests` as its external Python dependency.

## Configuration and Working Directory

For the full reproduction workflow, create a separate working directory for each procurement. The scripts can be kept in the repository while the procurement-specific files remain in the working directory.

The main files are:

| File or directory | Purpose |
|---|---|
| `tender_config.json` | Procurement-specific configuration, including required identifiers and authorization data |
| `last_tender.json` | The last saved tender state used for subsequent comparisons |
| `tender_data.json` | Optional local JSON input for reproducing a tender from modified data |
| `documents/` | Temporary storage for documents downloaded during document-transfer operations |

Some of these files are generated or updated by the scripts. Their exact behavior depends on the selected workflow.

**Security requirements**

- Never commit tokens, passwords, or other authorization secrets.
- Do not publish signed document URLs or private configuration files.
- Review procurement JSON files and downloaded documents before sharing them.
- Use only data that you are authorized to access and reproduce.
- Verify the target environment before executing operations that create or modify resources.

The following local files are excluded by the current `.gitignore`:

```text
tender_config.json
last_tender.json
tender_data.json
```

These exclusions should be preserved and reviewed before publication.

## Workflows

### 1. Quick Tender Reproduction

The quick workflow recreates a procurement using its identifier from the production environment and reproduces it in staging.

Run the script from PowerShell:

```powershell
py <path-to-repository>\run_tender_quick.py --id YOUR_TENDER_ID
```

Replace `YOUR_TENDER_ID` with the procurement's actual identifier.

To request document copying, use the supported `-copy_documents` flag:

```powershell
py <path-to-repository>\run_tender_quick.py --id YOUR_TENDER_ID -copy_documents
```

The workflow accelerates procurement lifecycle transitions and typically takes around five minutes, depending on the procurement type and required state transitions.

This method is intended for quick reproduction rather than subsequent step-by-step patching. The operational workflow described in the project documentation does not automatically save the resulting tender ID and authorization token for later monitoring-related tasks.

The guide recommends this method for procurement procedures that do not use the electronic procurement system.

### 2. Full Tender Reproduction

The full workflow creates a tender that can be extended through individual operations.

Run the script with a procurement identifier:

```powershell
py <path-to-repository>\scripts\run_tender.py --id YOUR_TENDER_ID
```

The tender is reproduced to a stage suitable for further testing. Depending on the procedure, this may be the clarification period or the proposal-submission period.

#### Accelerating the lifecycle

The `--minutes_to_days` argument allows the original duration, expressed in days, to be mapped to a shorter duration in minutes.

For example:

```powershell
py <path-to-repository>\scripts\run_tender.py --id YOUR_TENDER_ID --minutes_to_days 1
```

With this configuration, an eight-day period in the source procurement is represented as approximately eight minutes in the reproduced workflow, where the relevant API transitions support this behavior.

Acceleration is configured during tender creation.

#### Available options

| Option | Description |
|---|---|
| `--id` | Identifies the source procurement |
| `--minutes_to_days` | Sets the number of minutes corresponding to one day in the accelerated workflow |
| `-no_bids` | Skips immediate proposal submission where supported; documented primarily for simplified procurements |
| `-copy_documents` | Enables document copying from the source procurement |
| `-delete_documents` | Removes the local `documents/` directory and its contents after reproduction |
| `-ignore_documents` | Skips document uploads except for required contract templates |
| `-from_file` | Reproduces the procurement using local `tender_data.json` instead of retrieving the source data through the normal workflow |

When using `-from_file`, place `tender_data.json` in the working directory and omit `--id`:

```powershell
py <path-to-repository>\scripts\run_tender.py -from_file
```

Review the script's argument parser if an option is rejected. Some options in the existing workflow use a single leading hyphen, including multi-character flags.

#### Important considerations

- Follow the source procurement's event chronology when planning subsequent actions.
- Submit bids separately when required by the workflow.
- The source procurement must have reached the appropriate disclosure stage before its proposals can be reproduced. Attempting to proceed without available proposals can cause the reproduced procurement to become unsuccessful.
- Some document operations require documents to be transferred through the document service. If the API reports that a document URL is not accepted, review the document-copying settings.

### 3. Monitoring Tender Changes

Use `event_monitor.py` to inspect changes in the reproduced procurement and the relative timing of those changes.

Run:

```powershell
py <path-to-repository>\scripts\event_monitor.py
```

Available options:

| Option | Description |
|---|---|
| `-save` | Saves the latest tender state from the test environment to `last_tender.json` |
| `-from_file` | Compares the tender with data from a saved local file |
| `--contract_index` | Specifies the index of the contract to compare |

For example:

```powershell
py <path-to-repository>\scripts\event_monitor.py -save
```

To compare against a saved file:

```powershell
py <path-to-repository>\scripts\event_monitor.py -from_file
```

For a specific contract:

```powershell
py <path-to-repository>\scripts\event_monitor.py --contract_index 0
```

The documented workflow recommends running the monitor regularly while the procurement is still progressing. Monitoring may be unnecessary once the procurement has reached the contract or another final stage, depending on the testing scenario.

### 4. Applying Tender Changes

The `patch_tender.py` script applies individual operations to a reproduced procurement.

The general command pattern is:

```powershell
py <path-to-repository>\scripts\patch_tender.py OPERATION [OPTIONS]
```

Replace `OPERATION` with the requested operation and supply its required arguments.

#### Supported operations

| Operation | Purpose | Main arguments |
|---|---|---|
| `add_document` | Adds a document to a supported procurement object | `--doc_index`, `--doc_title`, `--index`, `--object`, `--subobject`, `--subindex` |
| `post_question` | Submits a question to the contracting authority | `--index` |
| `post_answer` | Submits an answer to a question | `--index` |
| `post_complaint` | Submits a complaint | `--index`, optional `--award_index` |
| `add_bids` | Adds proposals when they become available in the workflow | No additional argument is shown in the documented example |
| `prolong_award` | Extends the consideration of a proposal | `--index`, optional `--subindex` |
| `sign_award` | Signs a proposal before the corresponding decision | `--index` |
| `decide_award` | Records a decision on a proposal | `--index` |
| `activate_contract` | Activates a contract | `--index` |
| `add_contract_change` | Adds a contract change | `--index`, optional `--subindex` |

#### Examples

Submit a question:

```powershell
py <path-to-repository>\scripts\patch_tender.py post_question --index 0
```

Submit an answer to the first question:

```powershell
py <path-to-repository>\scripts\patch_tender.py post_answer --index 0
```

Add a tender document by its index:

```powershell
py <path-to-repository>\scripts\patch_tender.py add_document --doc_index 0
```

Add a document to a contract:

```powershell
py <path-to-repository>\scripts\patch_tender.py add_document --index 0 --object "contracts" --doc_index 0
```

A document can also be selected by title with `--doc_title`. For multiple documents, the documented interface provides `--doc_index_from` and `--doc_index_to`.

Submit a complaint:

```powershell
py <path-to-repository>\scripts\patch_tender.py post_complaint --index 0
```

Submit a complaint related to a specific award:

```powershell
py <path-to-repository>\scripts\patch_tender.py post_complaint --index 0 --award_index 0
```

Add bids:

```powershell
py <path-to-repository>\scripts\patch_tender.py add_bids
```

Extend consideration of an award:

```powershell
py <path-to-repository>\scripts\patch_tender.py prolong_award --index 0 --subindex 0
```

Sign an award and then record the decision:

```powershell
py <path-to-repository>\scripts\patch_tender.py sign_award --index 0
py <path-to-repository>\scripts\patch_tender.py decide_award --index 0
```

Activate a contract:

```powershell
py <path-to-repository>\scripts\patch_tender.py activate_contract --index 0
```

Add a change to a contract:

```powershell
py <path-to-repository>\scripts\patch_tender.py add_contract_change --index 0 --subindex 0
```

**Indexing:** indices used by the documented workflow are zero-based. The first item in a list has index `0`.

For nested objects, select the parent object and its index before specifying nested collections such as complaints or contract changes. Exact argument requirements depend on the operation and the current script implementation.

### 5. Planning the Procurement Timeline

Before applying changes, determine the chronology of events in the source procurement. The timeline should identify when each event occurred and which corresponding operation should be performed in the reproduced procurement.

The source procurement's JSON representation can be saved as `tender_data.json` for analysis or, where appropriate, for reproduction from edited data.

The JSON object contains nested structures, including:

- `questions` — questions and their answers;
- `documents` — documents attached to tenders and other objects;
- `bids` — submitted proposals;
- `complaints` — complaints and their associated data;
- `awards` — qualification and award information;
- `lots` — procurement lots;
- `contracts` — contracts and their changes.

Use the official Prozorro API documentation when determining valid field values and operation sequences:

- [Prozorro API documentation — Ukrainian](https://prozorro-api-docs.readthedocs.io/uk/master/index.html)
- [Prozorro API documentation — latest version](https://prozorro-api-docs.readthedocs.io/uk/latest/)

An example of a timeline is:

| Relative event | Operation | Purpose |
|---|---|---|
| Tender creation | `run_tender.py` | Reproduce the initial procurement state |
| Clarification period | `post_question`, `post_answer` | Reproduce questions and answers |
| Document publication | `add_document` | Add the relevant document |
| Proposal stage | `add_bids` | Add proposals when available |
| Award consideration | `prolong_award` | Reproduce an extension of consideration |
| Award decision | `sign_award`, `decide_award` | Reproduce signing and the decision |
| Contract stage | `activate_contract` | Activate the corresponding contract |

The actual sequence and indices must be determined from the source procurement data.

## Safety and Limitations

This toolkit interacts with external APIs and is not an isolated offline test suite. Some operations create or modify remote procurement resources.

Before execution:

- Confirm that the API endpoint is the intended environment.
- Use staging for reproduction and controlled testing.
- Verify the source identifier and the expected effects of each operation.
- Protect credentials, signed URLs, and procurement-specific local files.
- Use only authorized source data and document content.
- Validate the command-line arguments against the current script before running an unfamiliar operation.

The documented workflow focuses on reproducing procurement lifecycles and applying changes through individual operations. The available operations and their behavior depend on the API environment and the current implementation.

## License

No license has been specified. Add an appropriate license before permitting reuse or redistribution.
