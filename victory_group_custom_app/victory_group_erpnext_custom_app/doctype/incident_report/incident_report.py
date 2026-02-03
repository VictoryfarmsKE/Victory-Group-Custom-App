# Copyright (c) 2025, Christine Kanga and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today
from frappe.model.document import Document
from hrms.hr.utils import set_geolocation_from_coordinates
from frappe import _
from frappe.email.doctype.notification.notification import get_context
from frappe.utils import now_datetime, sanitize_html
from frappe.utils.data import get_datetime


class IncidentReport(Document):
    def validate(self):
        self.set_geolocation()

        # ensure date_and_time (string or datetime) is not in the future
        if self.date_and_time:
            dt = get_datetime(self.date_and_time)
            if dt and dt > now_datetime():
                frappe.throw(_("Date cannot be in the future."))

        # enforce minimum word counts
        def _count_words(text):
            if not text:
                return 0
            return len(text.strip().split())

        desc_words = _count_words(self.description)
        if desc_words < 25:
            frappe.throw(
                _(f"Description must be at least 25 words (current: {desc_words}).")
            )
        #enforce minimum of 25 words for description_of_intervention
        intervention_words = _count_words(self.description_of_intervention)
        if intervention_words < 25:
            frappe.throw(
                _(f"Description of Intervention must be at least 25 words (current: {intervention_words}).")
            )

    @frappe.whitelist()
    def set_geolocation(self):
        set_geolocation_from_coordinates(self)
        
def _user_emails_from_mailing_list(role):
    mailing_list = frappe.get_doc("Mailing List", role)
    emails = []
    for user in mailing_list.users:
        emails.append(user.user)
    return emails

def _linemanager_user_email(employee_name):
    if not employee_name:
        return None

    reports_to = frappe.get_value("Employee", employee_name, "reports_to")
    if not reports_to:
        return None

    manager_user = frappe.get_value("Employee", reports_to, "user_id")
    if not manager_user:
        return None

    enabled = frappe.get_value("User", manager_user, "enabled")
    if int(enabled or 0) == 1:
        return manager_user

    return None

def _hod_user_email(department_name):
    if not department_name:
        return None
    hod_employee = frappe.get_value("Department", department_name, "custom_hod")
    if hod_employee:
            hod = frappe.get_value("Employee", hod_employee, "user_id")
            if hod:
                status = frappe.get_value("User", hod_employee, "enabled")
                if status == "1":
                    return frappe.get_value("User", hod_employee, "email")
    return hod

def recipients_for_incident(doc):
    """Select recipient group based on incident type and severity."""
    t = doc.get("incident_type")
    s = doc.get("severity")

    # Build groups and Deduplicate them to preserve order
    low_moderate_group = []
    
    #get line manager email if role_type is Employee (FTE) and victim_employee is set
    if doc.get("role_type") == "Employee (FTE)" and doc.get("victim_employee"):
        lm_email = _linemanager_user_email(doc.victim_employee)
        if lm_email:
            low_moderate_group.append(lm_email)
            
    # get HOD email if victim_employee_department OR department is set
    dept = doc.get("victim_employee_department") or doc.get("department")
    if dept:
        try:
            hod_email = _hod_user_email(dept)
            if hod_email:
                low_moderate_group.append(hod_email)
        except Exception:
            # don't block Tier 1 emails if HOD lookup fails
            pass
            
    low_moderate_group += _user_emails_from_mailing_list("Tier 1")
    # low_moderate_group 
    high_catastrophic_group = (
        low_moderate_group + _user_emails_from_mailing_list("Tier 2")
    )

    if t == "Near Miss (NM)":
        return low_moderate_group
    if t == "First Aid Case (FAC)":
        return low_moderate_group
    if t in ("Lost Time Injury (LTI)", "Fatality"):
        return high_catastrophic_group
    if t == "Others":
        if s == "Low":
            return low_moderate_group
        if s == "Moderate":
            return low_moderate_group
        if s in ("High", "Catastrophic"):
            return high_catastrophic_group
    return low_moderate_group

def notify_on_submit(doc, method=None):

    try:
        recipients = recipients_for_incident(doc)
        if not recipients:
            frappe.log_error(
                message=f"No recipients resolved for Incident Report {doc.name}",
                title="Incident Notification: No recipients",
            )
            return

        # Log resolved recipients
        # frappe.log_error(
        #     message=f"Recipients resolved for Incident Report {doc.name}: {recipients}",
        #     title="Incident Notification: Recipients Fetched",
        # )

        subject = f"Incident Notification — {doc.incident_type} - {doc.severity} severity - Full Report"

        # Determine person involved and formatted date once
        person_involved = doc.victim if doc.get("victim") else doc.get("victim_employee")
        #Resolve victim_empployee name from Employee doctype
        if doc.get("victim_employee"):
            emp_name = frappe.get_value("Employee", doc.victim_employee, "employee_name")
            if emp_name:
                person_involved = emp_name

        for recipient in recipients:
            try:
                # Resolve recipient display name
                try:
                    user = frappe.get_doc("User", recipient)
                    recipient_name = user.first_name if user.first_name else (user.email or recipient)
                except Exception:
                    recipient_name = recipient

                message = frappe.render_template(
                    "<p>Dear {{ recipient_name }},</p>"
                    "<p>Earlier you were notified about an incident that had taken place. The ERP report of this incident is now <strong>complete</strong>.</p>"
                    "<p>&nbsp;</p>"
                    "<ul>"
                    "<li><strong>Person involved:</strong> {{ person_involved }}</li>"
                    "<li><strong>Location:</strong> {{ doc.location or 'Not specified' }}</li>"
                    "<li><strong>Date:</strong> {{frappe.format_date(doc.posting_date, format='dd MMMM YYYY')}}</li>"
                    "<li><strong>Incident Type:</strong> {{ doc.incident_type }}</li>"
                    "<li><strong>Incident Severity:</strong> {{ doc.severity }}</li>"
                    "<li><strong>Short Description:</strong> {{ doc.incident_title }}</li>"
                    "</ul>"
                    "<p>&nbsp;</p>"
                    "<p>You can view the incident details and updates in the ERP system here: <a href='{{ url }}'>{{ url }}</a></p>"
                    "<p>&nbsp;</p>"
                    "<p>Please stay informed and take note of this incident.</p>"
                    "<p>&nbsp;</p>"
                    "<p>Best regards,</p>"
                    "<p><strong>Health & Safety Department</strong></p>",
                    {
                        "doc": doc,
                        "url": frappe.utils.get_url_to_form(doc.doctype, doc.name),
                        "recipient_name": recipient_name,
                        "person_involved": person_involved
                    },
                )

                frappe.sendmail(
                    recipients=[recipient],
                    subject=subject,
                    message=message,
                    reference_doctype=doc.doctype,
                    reference_name=doc.name,
                )
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Error sending incident notification to {recipient} for {doc.name}",
                )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Error sending incident notifications for {doc.name}",
        )

def notify_on_create(doc, method=None):

    try:
            recipients = recipients_for_incident(doc)
            if not recipients:
                frappe.log_error(
                    message=f"No recipients resolved for Incident Report {doc.name}",
                    title="Incident Notification: No recipients",
                )
                return

            # Log resolved recipients
            frappe.log_error(
                message=f"Recipients resolved for Incident Report {doc.name}: {recipients}",
                title="Incident Notification: Recipients Fetched",
            )

            subject = f"Incident Notification — {doc.incident_type} - {doc.severity} severity - Preliminary Report"

            # Determine person involved
            person_involved = doc.victim if doc.get("victim") else doc.get("victim_employee")
            #Resolve victim_empployee name from Employee doctype
            if doc.get("victim_employee"):
                emp_name = frappe.get_value("Employee", doc.victim_employee, "employee_name")
                if emp_name:
                    person_involved = emp_name
            

            for recipient in recipients:
                try:
                    # Resolve recipient display name
                    try:
                        user = frappe.get_doc("User", recipient)
                        recipient_name = user.first_name if user.first_name else (user.email or recipient)
                    except Exception:
                        recipient_name = recipient

                    message = frappe.render_template(
                        "<p>Dear {{ recipient_name }},</p>"
                        "<p>An incident has taken place in the last 12 hours which has been recorded in ERP. "
                        "The status of this report is <strong>preliminary</strong>.</p>"
                        "<p>&nbsp;</p>"
                        "<ul>"
                        "<li><strong>Person involved:</strong> {{ person_involved }}</li>"
                        "<li><strong>Location:</strong> {{ doc.location or 'Not specified' }}</li>"
                        "<li><strong>Date:</strong> {{ frappe.format_date(doc.posting_date, 'dd MMMM yyyy') }}</li>"
                        "<li><strong>Incident Type:</strong> {{ doc.incident_type }}</li>"
                        "<li><strong>Incident Severity:</strong> {{ doc.severity }}</li>"
                        "<li><strong>Short Description:</strong> {{ doc.incident_title }}</li>"
                        "</ul>"
                        "<p>&nbsp;</p>"
                        "<p>You can view the incident details and updates in the ERP system here: <a href='{{ url }}'>{{ url }}</a></p>"
                        "<p>&nbsp;</p>"
                        "<p>Please stay informed and take note of this incident.</p>"
                        "<p>&nbsp;</p>"
                        "<p>Best regards,</p>"
                        "<p><strong>Health & Safety Department</strong></p>",
                        {
                            "doc": doc,
                            "url": frappe.utils.get_url_to_form(doc.doctype, doc.name),
                            "recipient_name": recipient_name,
                            "person_involved": person_involved,
                        },
                    )

                    frappe.sendmail(
                        recipients=[recipient],
                        subject=subject,
                        message=message,
                        reference_doctype=doc.doctype,
                        reference_name=doc.name,
                    )
                except Exception:
                    frappe.log_error(
                        frappe.get_traceback(),
                        f"Error sending incident notification to {recipient} for {doc.name}",
                    )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Error sending incident notifications for {doc.name}",
        )

def enforce_pending_signoff(doc, method=None):
    """Enforce root_cause word count when workflow_state transitions to 'Pending sign off'."""
    try:
        prev = doc.get_doc_before_save()
        # frappe.log_error(f"Previous workflow state: {prev.workflow_state if prev else 'N/A'}; Current: {doc.workflow_state}")
        prev_state = prev.workflow_state if prev else None
        if (
            prev_state != "Pending sign off"
            and doc.workflow_state == "Pending sign off"
        ):

            def _count_words(text):
                if not text:
                    return 0
                return len(text.strip().split())

            root_words = _count_words(doc.get("root_cause"))
            if root_words < 25:
                frappe.throw(
                    _(
                        f"Root Cause must be at least 25 words before moving to Pending sign off (current: {root_words})."
                    )
                )
            # Check if there are any attachments linked to the document
            attachments = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": doc.doctype,
                    "attached_to_name": doc.name,
                },
            )

            if not attachments:
                frappe.throw(_("Please Attach Reference Document(s)."))
    except Exception:
        # frappe.log_error(
        #     frappe.get_traceback(), "Error enforcing Pending sign off requirements"
        # )
        raise

def notify_hse_reviewer_on_transition(doc, method=None):
    """
    Sends an email to HSE Reviewers when the workflow moves into 
    'Pending Acknowledgement' or 'Pending sign off'.
    """
    try:
        # 1. Identify the states that require HSE Reviewer action
        target_states = ["Pending Acknowledgement", "Pending sign off"]
        
        # 2. Get the previous state to ensure we only send on a NEW transition
        prev_doc = doc.get_doc_before_save()
        prev_state = prev_doc.workflow_state if prev_doc else None

        # 3. Check if we just entered one of our target states
        if doc.workflow_state in target_states and prev_state != doc.workflow_state:
            
            # 4. Fetch all active users with the 'HSE Reviewer' role
            reviewers = frappe.get_all(
                "Has Role",
                filters={"role": "HSE Reviewer", "parenttype": "User"},
                fields=["parent"]
            )
            
            recipient_emails = [
                r.parent for r in reviewers 
                if frappe.db.get_value("User", r.parent, "enabled") == 1
            ]

            if not recipient_emails:
                return

            # 5. Prepare the notification
            url = frappe.utils.get_url_to_form(doc.doctype, doc.name)
            subject = f"Action Required: Incident Report {doc.name} is {doc.workflow_state}"
            
            # Context-aware message based on the state
            action_type = "acknowledge" if doc.workflow_state == "Pending Acknowledgement" else "sign off on"
            
            message = f"""
                <p>Hello,</p>
                <p>An Incident Report has reached a stage requiring your action.</p>
                <ul>
                    <li><strong>ID:</strong> {doc.name}</li>
                    <li><strong>Current Status:</strong> {doc.workflow_state}</li>
                    <li><strong>Severity:</strong> {doc.severity}</li>
                </ul>
                <p>Please click below to {action_type} this report:</p>
                <p><a href="{url}" style="background-color: #04b404; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; display: inline-block;">Open Incident Report</a></p>
                <br>
                <p>Best regards,<br>Health & Safety Department</p>
            """

            # 6. Send email (No attachment included by default)
            frappe.sendmail(
                recipients=recipient_emails,
                subject=subject,
                message=message,
                reference_doctype=doc.doctype,
                reference_name=doc.name,
                now=True # Sends immediately rather than waiting for the background queue
            )

    except Exception:
        frappe.log_error(frappe.get_traceback(), "HSE Reviewer Workflow Notification Error")
