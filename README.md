# Victory Group ERPNext Custom App

## 1. Overview

This app adds two business capabilities on top of ERPNext for Victory Group:

- HSE incident reporting with staged completion, email escalation, printable investigation output, and management reporting.
- Lease contract master-data capture for rented branches / locations, including rent escalation history and payment/accounting metadata.

Key problems it solves:

- Standardizes incident capture within the first 12 hours and later investigation details within the full report workflow.
- Forces minimum narrative quality for incident descriptions, interventions, and root-cause analysis.
- Routes incident notifications to line managers, HODs, and mailing-list groups based on incident type and severity.
- Provides a custom script report to summarize incident status by type and severity.
- Stores lease details in ERPNext instead of scattered spreadsheets or offline files.

Where it fits in the broader system:

- ERPNext HR / HSE-adjacent processes: `Incident Report` relies on `Employee`, `Department`, `User`, `Mailing List`, and `File`.
- ERPNext buying / finance master data: `Lease Contract` links to `Supplier`, `Company`, `Warehouse`, `Department`, `Cost Center`, `Account`, `Currency`, and `Bank Account`.
- HRMS: incident geolocation uses `hrms.hr.utils.set_geolocation_from_coordinates`.

## 2. Architecture & Design

High-level architecture:

- `hooks.py` wires the app through `doc_events` on `Incident Report` and fixture import definitions.
- `victory_group_erpnext_custom_app/doctype/incident_report/` contains the Python business logic.
- `victory_group_erpnext_custom_app/doctype/lease_contract/` and child table DocTypes define lease schema but currently have no server-side automation.
- `victory_group_erpnext_custom_app/report/incident_summary_report/` implements a script report plus printable HTML report output.
- `victory_group_erpnext_custom_app/print_format/incident_report_print/` provides a custom Jinja print format for submitted incident reports.

Key DocTypes and relationships:

- `Incident Report`
	- Main HSE document.
	- Child table: `Incident Corrective Actions`.
	- Links to `Employee`, `Department`, `File`, and indirectly `User` and `Mailing List` for notifications.
	- Submittable DocType with workflow-state-dependent fields.
- `Incident Corrective Actions`
	- Child table for CAPA rows with `user_responsible`, `date`, and `corrective_action`.
- `Lease Contract`
	- Main leasing master record.
	- Child table: `Lease Rent Escalation`.
	- Links to organization structure, lessor (`Supplier`), banking, and accounting masters.
- `Lease Rent Escalation`
	- Child table for effective-date rent changes.

Custom scripts, hooks, and report components:

- `doc_events` in `hooks.py`
	- `on_submit` calls `notify_on_submit` for `Incident Report`.
	- `before_save` calls `enforce_pending_signoff` for `Incident Report`.
- `incident_report.js`
	- Dynamically hides or requires victim-related fields based on incident type, subcategory, and role type.
	- Auto-populates severity for some incident types.
	- Triggers geolocation fetch through HRMS.
- `incident_summary_report.py`
	- Aggregates incidents into `open`, `pending`, and `closed` buckets based on workflow state.
- `incident_summary_report.js`
	- Adds a second severity chart after the report datatable renders.
- `incident_report_print.html`
	- Renders a structured printable investigation form with CAPA rows and signature blocks.

Design decisions and patterns used:

- Workflow-state-driven behavior
- Business rules are set in DocType controller hooks 
- Recipient selection is inferred from organization structure and named mailing lists rather than hardcoded email addresses.
- Lease management is modeled as master data first; automation for renewals, PO generation, or escalations is not implemented yet.

## 3. Installation & Setup
Installation steps:

```bash
cd /path/to/frappe-bench
bench get-app /path/to/apps/victory_group_custom_app
bench --site <site-name> install-app victory_group_custom_app
bench build
bench --site <site-name> migrate
```

## 4. Configuration

Key settings and master-data dependencies:

- `Mailing List`
	- Incident notification logic expects mailing lists named exactly `Tier 1` and `Tier 2`.
- `Department`
	- Incident recipient resolution expects a custom field `custom_hod` on `Department`.
- `Employee`
	- `reported_by`, `victim_employee`, and the employee reporting line (`reports_to`) are used to determine recipients.
- `User`
	- Notification logic checks if recipient users are enabled.
- `Supplier`
	- Lease payment metadata uses fixture custom fields `custom_till_number` and `custom_pay_bill`.

## 5. Key Workflows

### Incident reporting workflow

1. User creates an `Incident Report`.
2. Client-side form logic adjusts victim-related fields based on:
	 - `incident_type`
	 - `incident_type_subcategory`
	 - `role_type`
3. During validation, the server:
	 - populates geolocation via HRMS,
	 - rejects future `date_and_time`,
	 - requires at least 25 words in `description`,
	 - requires at least 25 words in `description_of_intervention`.
4. When the workflow moves to `Pending Acknowledgement`, `before_save` triggers `notify_on_create()` and emails preliminary incident details.
5. When the workflow moves to `Pending sign off`, `before_save` enforces:
	 - at least 25 words in `root_cause`,
	 - at least one file attachment linked to the document.
6. On submit, `notify_on_submit()` emails the completed incident report to the resolved recipient list.

### Incident recipient resolution

1. Base recipients come from `Mailing List` named `Tier 1`.
2. For high-severity / serious incidents, `Tier 2` is appended.
3. If the victim is an employee, the line manager’s email is included when available.
4. If a victim department is available, the HOD’s email is included using `Department.custom_hod`.
5. The final recipient set depends on `incident_type` and, for `Others`, on `severity`.

### Lease contract capture

1. User creates a `Lease Contract` record.
2. The document captures organizational ownership, lessor details, lease term, rent escalation details, payment details, and accounting mappings.
3. Rent escalation history is stored in the `Lease Rent Escalation` child table.
4. No server-side validation, automation, or document creation is currently triggered from this DocType.

### Incident summary reporting

1. User runs `Incident Summary Report` with `from_date`, `to_date`, and optional `location`.
2. The report queries `Incident Report` rows with `docstatus < 2`.
3. Workflow states are normalized into `Open`, `Pending`, or `Closed` buckets.
4. The report returns:
	 - detail rows,
	 - report summary cards,
	 - an incident-type bar chart,
	 - a client-side severity chart.

## 6. Code Structure

Folder breakdown:

- `victory_group_custom_app/hooks.py`
	- App metadata, fixture declarations, and `Incident Report` doc event hooks.
- `victory_group_custom_app/fixtures/`
	- Exported site fixtures.
	- In practice only `custom_field.json` contains data; `client_script.json` and `server_script.json` are empty arrays.
- `victory_group_custom_app/victory_group_erpnext_custom_app/doctype/`
	- Custom DocTypes and controllers.
- `victory_group_custom_app/victory_group_erpnext_custom_app/report/incident_summary_report/`
	- Script report Python, query report JS, and printable HTML.
- `victory_group_custom_app/victory_group_erpnext_custom_app/print_format/incident_report_print/`
	- Jinja print format for incident reports.
- `victory_group_custom_app/victory_group_erpnext_custom_app/dashboard_chart/`
	- Present but empty.
- `victory_group_custom_app/victory_group_erpnext_custom_app/number_card/`
	- Folders exist but are empty.

Important files:

- `hooks.py`: first stop for lifecycle behavior.
- `doctype/incident_report/incident_report.py`: primary business-rule implementation.
- `doctype/incident_report/incident_report.js`: form UX and field requirements.
- `report/incident_summary_report/incident_summary_report.py`: reporting logic.
- `print_format/incident_report_print/incident_report_print.html`: printable handover output for investigations.


## 7. Customizations & Overrides

Active customizations:

- Supplier custom fields:
	- `custom_till_number`
	- `custom_pay_bill`
- Incident form logic that dynamically hides and requires fields.
- Workflow-state-gated mandatory sections in `Incident Report`.
- Custom report and custom print format for incidents.

Business Assumptions:

- Email notification routing depends on exact mailing list names `Tier 1` and `Tier 2`.
- Workflow logic depends on exact state names; renaming the workflow will silently break validations and notifications.


## License

MIT
