// Copyright (c) 2025, Christine Kanga and contributors
// For license information, please see license.txt

const VICTIM_FIELDS = ['role_type', 'victim', 'victim_employee', 'victim_employee_department', 
	'victim_presence_status', 'ppe_status', 'department'];
const SEVERITY_MAP = { "First Aid Case (FAC)": "Moderate", "Lost Time Injury (LTI)": "High", "Fatality": "Catastrophic" };

function set_field_props(frm, fields, hidden, reqd) {
	fields.forEach(f => {
		frm.set_df_property(f, 'hidden', hidden);
		frm.set_df_property(f, 'reqd', reqd);
	});
	fields.forEach(f => frm.refresh_field(f));
}

function toggle_victim_fields(frm) {
	const is_others = frm.doc.incident_type === 'Others';
	const subcategory = frm.doc.incident_type_subcategory;
	
	if (is_others && (subcategory === 'Asset damage' || subcategory === 'Environmental damage')) {
		set_field_props(frm, VICTIM_FIELDS, 1, 0);
	} else if (is_others && subcategory === 'Third-party individual') {
		set_field_props(frm, ['role_type', 'victim_employee', 'victim_employee_department', 'victim_presence_status', 'ppe_status', 'department'], 1, 0);
		frm.set_df_property('victim', 'hidden', 0);
		frm.set_df_property('victim', 'reqd', 1);
		frm.refresh_field('victim');
	} else if (is_others) {
		set_field_props(frm, VICTIM_FIELDS, 1, 0);
	} else {
		set_field_props(frm, VICTIM_FIELDS, 0, 0);
		frm.set_df_property('role_type', 'reqd', 1);
		
		const role = frm.doc.role_type;
		const configs = {
			'Employee (FTE)': { show: ['victim_employee', 'victim_employee_department'], hide: ['victim', 'department'] },
			'Casual': { show: ['victim', 'department'], hide: ['victim_employee', 'victim_employee_department'] },
			_default: { show: ['victim'], hide: ['victim_employee', 'victim_employee_department', 'department'] }
		};
		const config = configs[role] || configs._default;
		
		config.show.forEach(f => {
			frm.set_df_property(f, 'hidden', 0);
			frm.set_df_property(f, 'reqd', 1);
		});
		config.hide.forEach(f => {
			frm.set_df_property(f, 'hidden', 1);
			frm.set_df_property(f, 'reqd', 0);
		});
		['victim', 'victim_employee', 'victim_employee_department', 'department'].forEach(f => frm.refresh_field(f));
		
		frm.set_df_property('victim_presence_status', 'reqd', 1);
		frm.set_df_property('ppe_status', 'reqd', 1);
	}
}

frappe.ui.form.on("Incident Report", {
	fetch_geolocation: (frm) => {
		hrms.fetch_geolocation(frm);
	},
	onload: function(frm) {
		toggle_victim_fields(frm);
		const sev = SEVERITY_MAP[frm.doc.incident_type];
		if (sev && !frm.doc.severity) {
			frm.set_value('severity', sev);
		}
	},
	incident_type: function(frm) {
		toggle_victim_fields(frm);
		const sev = SEVERITY_MAP[frm.doc.incident_type];
		if (sev) {
			frm.set_value('severity', sev);
		}
	},
	incident_type_subcategory: toggle_victim_fields,
	role_type: toggle_victim_fields
});
