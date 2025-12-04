# Copyright (c) 2025, Christine Kanga and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today
from frappe.model.document import Document
from hrms.hr.utils import set_geolocation_from_coordinates
from frappe import _

class IncidentReport(Document):
	def validate(self):
		self.set_geolocation()
		
		if self.date_and_time and self.date_and_time > today():
				frappe.throw("Date cannot be in the future.")
		
	@frappe.whitelist()
	def set_geolocation(self):
		set_geolocation_from_coordinates(self)
	 
	# before save ensure attachments are added to the document
	def on_submit(doc):
		# Check if there are any attachments linked to the document
		attachments = frappe.get_all('File', filters={'attached_to_doctype': doc.doctype, 'attached_to_name': doc.name})
		
		if not attachments:
			frappe.throw(_("Please Attach Reference Document(s)."))

