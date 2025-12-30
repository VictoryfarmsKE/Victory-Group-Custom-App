// Copyright (c) 2025, Christine Kanga and contributors
// For license information, please see license.txt

frappe.ui.form.on("Incident Report", {
	fetch_geolocation: (frm) => {
		hrms.fetch_geolocation(frm);
	},
});

function update_severity_options(frm) {
	const restricted_types = ["Near Miss (NM)", "Others"];
	const restricted_options = "\nLow\nModerate\nHigh\nCatastrophic";
	const default_options = "\nLow\nModerate\nHigh\nCatastrophic";

	if (restricted_types.includes(frm.doc.incident_type)) {
		frm.set_df_property('severity', 'options', restricted_options);
		const allowed = ['Moderate', 'High', 'Catastrophic'];
		if (frm.doc.severity && !allowed.includes(frm.doc.severity)) {
			frm.set_value('severity', null);
		}
	} else {
		frm.set_df_property('severity', 'options', default_options);
	}
}

frappe.ui.form.on("Incident Report", {
	onload: function(frm) {
		update_severity_options(frm);
		// On load, if incident_type exists and severity is blank, set default
		const mapping = {
			"First Aid Case (FAC)": "Moderate",
			"Lost Time Injury (LTI)": "High",
			"Fatality": "Catastrophic",
		};
		const sev = mapping[frm.doc.incident_type];
		if (sev && !frm.doc.severity) {
			frm.set_value('severity', sev);
		}
	},
	incident_type: function(frm) {
		update_severity_options(frm);
		// Always set mapped severity on type change (overwrite existing)
		const mapping = {
			"First Aid Case (FAC)": "Moderate",
			"Lost Time Injury (LTI)": "High",
			"Fatality": "Catastrophic",
		};
		const sev = mapping[frm.doc.incident_type];
		if (sev) {
			frm.set_value('severity', sev);
		}
	}
});
