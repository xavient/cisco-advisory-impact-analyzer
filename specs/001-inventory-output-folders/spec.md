# Feature Specification: Inventory & Output Folders

**Feature Branch**: `001-inventory-output-folders`

**Created**: 2026-07-14

**Status**: Draft

**Input**: User description: "we want to change the inventory and outputs folders. The inventory file is expected to exist in `inventory` folder, and the output excel files are to be saved in `output` folder. so when we're running the script, it should check that those two folders exist and go from there. Add a check, there must be only 1 inventory file to avoid collision, so in the `inventory` folder, if the script finds more than 1 file, it should throw an error and ask the user to clean it up. the output folder can have many because each file will have a unique timestamp"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dedicated inventory folder with a single source file (Priority: P1)

An operator keeps their firewall inventory spreadsheet inside a dedicated `inventory`
folder. When they run the analyzer, the tool locates the one inventory file in that
folder and uses it as the source of truth for the analysis — no guessing about which
file is the inventory and no accidental use of an unrelated file that happens to sit
next to the script.

**Why this priority**: This is the core value of the change — a predictable, dedicated
location for the single inventory input. Without it, none of the other behavior matters.

**Independent Test**: Place exactly one inventory spreadsheet in the `inventory` folder,
run the analyzer, and confirm the analysis runs against that file and produces a report.

**Acceptance Scenarios**:

1. **Given** an `inventory` folder containing exactly one inventory file, **When** the
   operator runs the analyzer, **Then** the tool uses that file as the inventory and
   proceeds with the analysis.
2. **Given** an `inventory` folder, **When** the operator runs the analyzer, **Then** the
   tool does not look for the inventory anywhere other than that folder.

---

### User Story 2 - Reject multiple inventory files to avoid collisions (Priority: P1)

An operator accidentally leaves two inventory spreadsheets in the `inventory` folder
(for example, an old copy and an updated one). When they run the analyzer, the tool
stops immediately with a clear error explaining that only one inventory file is allowed
and asking them to clean up the folder, so the tool never silently analyzes the wrong
file.

**Why this priority**: Guarding against ambiguous input is explicitly requested and is a
correctness/safety concern — analyzing the wrong inventory would produce misleading
impact results.

**Independent Test**: Place two or more files in the `inventory` folder, run the
analyzer, and confirm it exits with an error naming the problem and instructing the
operator to leave only one file.

**Acceptance Scenarios**:

1. **Given** an `inventory` folder containing two or more inventory files, **When** the
   operator runs the analyzer, **Then** the tool refuses to run, reports that more than
   one inventory file was found, and asks the operator to remove the extras so only one
   remains.
2. **Given** an `inventory` folder containing no inventory file, **When** the operator
   runs the analyzer, **Then** the tool refuses to run and reports that no inventory file
   was found in the folder.

---

### User Story 3 - Output files collected in a dedicated folder (Priority: P2)

Every time the operator runs an analysis, the resulting timestamped Excel report is
written into a dedicated `output` folder. Reports accumulate there over time, each with
a unique timestamped name, so the operator has a single place to find current and past
results without cluttering the tool's working directory.

**Why this priority**: Directing outputs to a dedicated folder is part of the requested
change and improves organization, but the analysis itself can function once inputs are
correct; hence it is slightly lower priority than the inventory-source behavior.

**Independent Test**: Run the analyzer twice and confirm that two distinct timestamped
report files appear in the `output` folder and that neither overwrites the other.

**Acceptance Scenarios**:

1. **Given** a valid inventory and a run that completes, **When** the report is produced,
   **Then** it is saved into the `output` folder with a unique timestamped name.
2. **Given** the `output` folder already contains earlier reports, **When** a new run
   completes, **Then** the new report is added alongside the existing ones without
   removing or overwriting them.

---

### Edge Cases

- **Missing folders**: If the `inventory` folder and/or the `output` folder does not
  exist when the analyzer runs, the tool stops with a clear message naming the missing
  folder and telling the operator what is expected there, rather than proceeding.
- **Empty inventory folder**: Treated as "no inventory file found" (see User Story 2).
- **Incidental non-inventory files**: Operating-system metadata files (e.g. `.DS_Store`)
  and spreadsheet lock/temp files (e.g. `~$...`) that may appear in the `inventory`
  folder should not be counted as inventory files for the "exactly one" check.
- **Unreadable inventory file**: If the single inventory file exists but cannot be
  opened or is not a valid inventory spreadsheet, the tool reports the problem clearly
  instead of failing obscurely.
- **Report name collision within the same second**: Two runs completing within the same
  timestamp granularity must still both be preserved rather than one overwriting the
  other.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST read the firewall inventory from a dedicated `inventory`
  folder rather than from a fixed file beside the program.
- **FR-002**: The tool MUST require exactly one inventory file in the `inventory` folder.
- **FR-003**: When the `inventory` folder contains more than one inventory file, the tool
  MUST refuse to run and present an error that (a) states more than one inventory file
  was found and (b) instructs the operator to remove the extras so only one remains.
- **FR-004**: When the `inventory` folder contains no inventory file, the tool MUST refuse
  to run and report that no inventory file was found in the folder.
- **FR-005**: The tool MUST write every generated report into a dedicated `output`
  folder.
- **FR-006**: The tool MUST allow the `output` folder to contain many reports, giving each
  report a unique timestamped name so that new reports never overwrite existing ones.
- **FR-007**: On startup, before performing analysis, the tool MUST verify that both the
  `inventory` and `output` folders exist and MUST stop with a clear, actionable message
  identifying any missing folder.
- **FR-008**: Error messages for missing folders, missing inventory, and multiple
  inventory files MUST be understandable by a non-developer operator and tell them what
  to do next.
- **FR-009**: When counting inventory files for the "exactly one" rule, the tool MUST
  ignore incidental non-inventory files such as hidden OS metadata files and spreadsheet
  lock/temporary files.

### Key Entities *(include if feature involves data)*

- **Inventory folder**: The single, dedicated location that holds the one firewall
  inventory spreadsheet the tool will analyze.
- **Inventory file**: The single spreadsheet describing the operator's firewalls; it is
  the sole analysis input and must be unambiguous (exactly one present).
- **Output folder**: The dedicated location where all generated reports are collected.
- **Report file**: A timestamped Excel result produced by a run; many may coexist in the
  output folder, each uniquely named.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With exactly one inventory file present in the `inventory` folder, an
  operator can run an analysis to completion without specifying the inventory's location.
- **SC-002**: In 100% of runs where the `inventory` folder contains more than one file,
  the tool stops before analysis and shows a message telling the operator to leave only
  one file.
- **SC-003**: In 100% of runs where a required folder is missing, the tool stops before
  analysis and names the missing folder.
- **SC-004**: After N successful runs, the `output` folder contains N distinct report
  files, with zero reports overwritten.
- **SC-005**: A non-developer operator can resolve a "multiple inventory files" or
  "missing folder" error using only the on-screen message, without consulting external
  documentation.

## Assumptions

- Missing required folders are treated as an error with guidance (consistent with the
  tool's existing "refuse to run when prerequisites are missing" behavior), rather than
  being silently created by the tool.
- "Only 1 inventory file" is measured against real inventory spreadsheets; incidental
  files created by the operating system or by a spreadsheet application (hidden metadata,
  temporary lock files) are not counted.
- The `inventory` and `output` folders are located relative to the tool's working
  directory (the folder the operator runs the tool from / where the tool lives), matching
  how the inventory file was previously placed beside the program.
- Report files continue to use the existing timestamped naming scheme that guarantees
  uniqueness across runs.
- This change replaces the previous behavior of reading the inventory from a fixed file
  beside the program and writing reports into the working directory; the documented
  setup instructions will need to reflect the new folder layout.
