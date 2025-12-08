// Copyright (c) 2025, Christine Kanga and contributors
// For license information, please see license.txt

frappe.ui.form.on("Incident Report", {
	fetch_geolocation: (frm) => {
		hrms.fetch_geolocation(frm);
	},
});

function update_severity_options(frm) {
	const restricted_types = ["Near Miss (NM)", "Others"];
	const restricted_options = "\nModerate\nHigh\nCatastrophic";
	const default_options = "\nLow\nModerate\nHigh\nCatastrophic\nLow Catastrophic";

	if (restricted_types.includes(frm.doc.incident_type)) {
		frm.set_df_property('severity', 'options', restricted_options);
		// If current value is not allowed, clear it so user picks a valid one
		const allowed = ['Moderate', 'High', 'Catastrophic'];
		if (frm.doc.severity && !allowed.includes(frm.doc.severity)) {
			frm.set_value('severity', null);
		}
	} else {
		frm.set_df_property('severity', 'options', default_options);
	}
}

frappe.ui.form.on("Incident Report", {
	refresh: function(frm) {
		update_severity_options(frm);
	},
	incident_type: function(frm) {
		update_severity_options(frm);
	}
});
