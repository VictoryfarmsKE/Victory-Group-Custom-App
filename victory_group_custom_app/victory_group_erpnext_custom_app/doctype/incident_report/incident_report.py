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
        if desc_words < 50:
            frappe.throw(
                _(f"Description must be at least 50 words (current: {desc_words}).")
            )

    @frappe.whitelist()
    def set_geolocation(self):
        set_geolocation_from_coordinates(self)

    # before submit ensure attachments are added to the document
    def on_submit(self):
        # Check if there are any attachments linked to the document
        attachments = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": self.doctype,
                "attached_to_name": self.name,
            },
        )

        if not attachments:
            frappe.throw(_("Please Attach Reference Document(s)."))


def _user_emails_from_role(role):
    users = frappe.get_all("Has Role", filters={"role": role}, fields=["parent"])
    emails = set()
    for u in users:
        user = u.get("parent")
        if user:
            email = frappe.get_value("User", user, "email")
            if email:
                emails.add(email)
    return list(emails)


def _employee_user_email(employee_name):
    if not employee_name:
        return None
    user = frappe.get_value("Employee", employee_name, "user_id")
    if user:
        return frappe.get_value("User", user, "email")
    return None


def _hod_user_email(department_name):
    if not department_name:
        return None
    hod_employee = frappe.get_value("Department", department_name, "custom_hod")
    if hod_employee:
        return _employee_user_email(hod_employee)
    return None


def build_recipient_list(doc):
    """Return ordered unique emails for the document."""
    recipients = []

    # Line Manager
    if doc.get("role_type") == "Employee (FTE)" and doc.get("victim_employee"):
        lm_email = _employee_user_email(doc.victim_employee)
        if lm_email:
            recipients.append(lm_email)

    # HOD
    if doc.get("victim_employee_department"):
        hod_email = _hod_user_email(doc.victim_employee_department)
        if hod_email:
            recipients.append(hod_email)

    recipients += _user_emails_from_role("HSE User - VF")
    recipients += _user_emails_from_role("Farm Ops Executive")
    recipients += _user_emails_from_role("HR Manager")
    recipients += _user_emails_from_role("CEO - VF")
    recipients += _user_emails_from_role("Chief")

    # Deduplicate preserving order
    seen = set()
    ordered = []
    for email in recipients:
        if email and email not in seen:
            ordered.append(email)
            seen.add(email)
    return ordered


def recipients_for_incident(doc):
    """Select recipient group based on incident type and severity."""
    t = doc.get("incident_type")
    s = doc.get("severity")

    # Build groups
    low_group = []
    if doc.get("role_type") == "Employee (FTE)" and doc.get("victim_employee"):
        lm_email = _employee_user_email(doc.victim_employee)
        if lm_email:
            low_group.append(lm_email)
    if doc.get("victim_employee_department"):
        hod_email = _hod_user_email(doc.victim_employee_department)
        if hod_email:
            low_group.append(hod_email)
    low_group += _user_emails_from_role("HSE User - VF")

    moderate_group = (
        low_group
        + _user_emails_from_role("HR Manager")
        + _user_emails_from_role("Farm Ops Executive")
    )
    high_group = moderate_group + _user_emails_from_role("CEO - VF")
    catastrophic_group = high_group + _user_emails_from_role("Chief")

    if t == "Near Miss (NM)":
        return low_group + _user_emails_from_role("Farm Ops Executive")
    if t == "First Aid Case (FAC)":
        return moderate_group + _user_emails_from_role("CEO - VF")
    if t in ("Lost Time Injury (LTI)", "Fatality"):
        return catastrophic_group
    if t == "Others":
        if s == "Low":
            return low_group
        if s == "Moderate":
            return moderate_group
        if s in ("High", "Catastrophic"):
            return catastrophic_group
    return low_group


def notify_on_submit(doc, method=None):
    try:
        recipients = recipients_for_incident(doc)
        if not recipients:
            frappe.log_error(
                message=f"No recipients resolved for Incident Report {doc.name}",
                title="Incident Notification: No recipients",
            )
            return

        subject = f"Incident Notification — {doc.incident_type}"
        message = frappe.render_template(
            "<p>Hello,</p>"
            "<p>An incident has been recorded in the ERP system:</p>"
            "<p>&nbsp;</p>"
            "<ul>"
            "<li><strong>Person involved:</strong> {{ doc.reported_by }}</li>"
            "<li><strong>Date:</strong> {{ doc.date_and_time }}</li>"
            "<li><strong>Incident Type:</strong> {{ doc.incident_type }}</li>"
            "<li><strong>Short Description:</strong> {{ doc.incident_title }}</li>"
            "<li><strong>Location:</strong> {{ doc.get('location') or 'Not specified' }}</li>"
            "</ul>"
            "<p>&nbsp;</p>"
            "<p>You can view the full incident details and updates in the ERP system here: <a href='{{ url }}'>{{ url }}</a></p>"
            "<p>&nbsp;</p>"
            "<p>Please stay informed and take note of this incident.</p>"
            "<p>&nbsp;</p>"
            "<p>Best regards,</p>"
            "<p><strong>Health & Safety Department</strong></p>",
            {"doc": doc, "url": frappe.utils.get_url_to_form(doc.doctype, doc.name)},
        )
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=message,
            reference_doctype=doc.doctype,
            reference_name=doc.name,
        )
        frappe.get_doc(
            {
                "doctype": "Communication",
                "communication_type": "Communication",
                "subject": subject,
                "content": sanitize_html(message),
                "sender": frappe.session.user,
                "recipients": ", ".join(recipients),
                "reference_doctype": doc.doctype,
                "reference_name": doc.name,
            }
        ).insert(ignore_permissions=True)
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
            if root_words < 100:
                frappe.throw(
                    _(
                        f"Root Cause must be at least 100 words before moving to Pending sign off (current: {root_words})."
                    )
                )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(), "Error enforcing Pending sign off requirements"
        )
        raise
