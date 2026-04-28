# Copyright (c) 2026, Christine Kanga and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	return IncidentSummaryReport(filters).run()


class IncidentSummaryReport:
	INCIDENT_TYPES = [
		"Near Miss (NM)",
		"First Aid Case (FAC)",
		"Lost Time Injury (LTI)",
		"Fatality",
		"Others",
	]
	SEVERITIES = ["Low", "Moderate", "High", "Catastrophic"]

	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})

	def run(self):
		self.fetch_raw_data()
		self.build_aggregates()
		self.get_columns()
		self.get_rows()
		self.get_chart()
		self.get_report_summary()
		return self.columns, self.rows, None, self.chart, self.report_summary


	def fetch_raw_data(self):
		conditions, values = self._build_conditions()
		self.incidents = frappe.db.sql(
			f"""
			SELECT name, incident_type, severity, location, workflow_state, date_and_time
			FROM `tabIncident Report`
			WHERE docstatus < 2
			{conditions}
			ORDER BY date_and_time DESC, modified DESC
			""",
			values,
			as_dict=True,
		)

	def _build_conditions(self):
		conditions = []
		values = {}

		if self.filters.get("from_date"):
			conditions.append("AND date_and_time >= %(from_date)s")
			values["from_date"] = self.filters.from_date

		if self.filters.get("to_date"):
			conditions.append("AND date_and_time < DATE_ADD(%(to_date)s, INTERVAL 1 DAY)")
			values["to_date"] = self.filters.to_date

		if self.filters.get("location"):
			conditions.append("AND location = %(location)s")
			values["location"] = self.filters.location

		return " ".join(conditions), values


	def _classify(self, workflow_state):
		"""Map a workflow state to open / pending / closed."""
		if not workflow_state or workflow_state == "Draft":
			return "open"
		if "Pending" in workflow_state:
			return "pending"
		if workflow_state == "Approved":
			return "closed"
		return "open"

	def build_aggregates(self):
		self.type_data = {t: {"open": 0, "pending": 0, "closed": 0} for t in self.INCIDENT_TYPES}
		self.sev_data = {s: {"open": 0, "pending": 0, "closed": 0} for s in self.SEVERITIES}

		for row in self.incidents:
			bucket = self._classify(row.workflow_state)
			if row.incident_type in self.type_data:
				self.type_data[row.incident_type][bucket] += 1
			if row.severity in self.sev_data:
				self.sev_data[row.severity][bucket] += 1

	def get_columns(self):
		self.columns = [
			{"label": _("Incident"),"fieldname": "name","fieldtype": "Link","options": "Incident Report","width": 180},
			{"label": _("Severity"), "fieldname": "severity", "fieldtype": "Data", "width": 120},
			{"label": _("Incident Type"),"fieldname": "incident_type","fieldtype": "Data","width": 180},
            {"label": _("Date & Time"), "fieldname": "date_and_time", "fieldtype": "Datetime", "width": 180},
			{"label": _("Location"), "fieldname": "location", "fieldtype": "Data", "width": 120},
			{"label": _("Status"), "fieldname": "report_status", "fieldtype": "Data", "width": 110},
		]

	def _sum(self, bucket_map):
		totals = {"open": 0, "pending": 0, "closed": 0}
		for d in bucket_map.values():
			for k in totals:
				totals[k] += d[k]
		return totals

	def get_rows(self):
		self.type_totals = self._sum(self.type_data)
		self.sev_totals = self._sum(self.sev_data)
		self.rows = []

		for incident in self.incidents:
			self.rows.append(
				{
					"name": incident.name,
					"severity": incident.severity,
					"incident_type": incident.incident_type,
					"location": incident.location,
                    "date_and_time": incident.date_and_time,
					"report_status": self._classify(incident.workflow_state).title(),
				}
			)
  
	def get_chart(self):
		self.chart = {
			"data": {
				"labels": self.INCIDENT_TYPES,
				"datasets": [
					{"name": _("Open"), "values": [self.type_data[t]["open"] for t in self.INCIDENT_TYPES]},
					{"name": _("Pending"), "values": [self.type_data[t]["pending"] for t in self.INCIDENT_TYPES]},
					{"name": _("Closed"), "values": [self.type_data[t]["closed"] for t in self.INCIDENT_TYPES]},
				],
			},
			"type": "bar",
			"height": 300,
			"colors": ["#e74c3c", "#00BDF0", "#10812E"],
			"valuesOverPoints": 1,
			"barOptions": {"stacked": 0},
			"fieldtype": "Int",
		}


	def get_report_summary(self):
		open_count = self.type_totals["open"]
		pending_count = self.type_totals["pending"]
		closed_count = self.type_totals["closed"]
		grand_total = open_count + pending_count + closed_count

		self.report_summary = [
			{"value": open_count, "label": _("Open"), "indicator": "Red", "datatype": "Int"},
			{"value": pending_count, "label": _("Pending"), "indicator": "Orange", "datatype": "Int"},
			{"value": closed_count, "label": _("Closed"), "indicator": "Green", "datatype": "Int"},
			{"value": grand_total, "label": _("Total Incidents"), "indicator": "Blue", "datatype": "Int"},
		]

