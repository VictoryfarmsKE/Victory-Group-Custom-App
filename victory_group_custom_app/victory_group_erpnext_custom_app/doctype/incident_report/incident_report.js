// Copyright (c) 2025, Christine Kanga and contributors
// For license information, please see license.txt

frappe.ui.form.on("Incident Report", {
	fetch_geolocation: (frm) => {
		hrms.fetch_geolocation(frm);
	},
});
