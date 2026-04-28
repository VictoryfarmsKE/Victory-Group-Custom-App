// Copyright (c) 2026, Christine Kanga and contributors
// For license information, please see license.txt

frappe.query_reports["Incident Summary Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.now_date(),
		},
		{
			fieldname: "location",
			label: __("Location"),
			fieldtype: "Select",
			options: "\nFishQ\nRoo Farm\nBranch\nMLC\nKLC\nFLC\nVLC\n106\nOther",
		},
	],

	after_datatable_render: function () {
		const severities = ["Low", "Moderate", "High", "Catastrophic"];
		const buckets = {
			Low: { Open: 0, Pending: 0, Closed: 0 },
			Moderate: { Open: 0, Pending: 0, Closed: 0 },
			High: { Open: 0, Pending: 0, Closed: 0 },
			Catastrophic: { Open: 0, Pending: 0, Closed: 0 },
		};

		const data = frappe.query_report.data || [];
		for (const row of data) {
			if (severities.includes(row.severity) && buckets[row.severity][row.report_status] !== undefined) {
				buckets[row.severity][row.report_status] += 1;
			}
		}

		const open_vals = severities.map((severity) => buckets[severity].Open);
		const pending_vals = severities.map((severity) => buckets[severity].Pending);
		const closed_vals = severities.map((severity) => buckets[severity].Closed);

		const $main = frappe.query_report.page.main;
		const $chart_wrapper = $main.find(".chart-wrapper");
		if (!$chart_wrapper.length) return;

		$main.find("#incident-severity-chart").remove();

		const $container = $(
			'<div id="incident-severity-chart" style="padding: 1rem 1.5rem 0.5rem;">' +
				'<h6 style="margin-bottom: 0.25rem; font-weight: 600;">' +
				__("Incidents by Severity") +
				"</h6>" +
				'<div class="severity-chart-target"></div>' +
				"</div>"
		);
		$chart_wrapper.after($container);

		new frappe.Chart($container.find(".severity-chart-target")[0], {
			data: {
				labels: severities,
				datasets: [
					{ name: __("Open"), values: open_vals },
					{ name: __("Pending"), values: pending_vals },
					{ name: __("Closed"), values: closed_vals },
				],
			},
			type: "bar",
			height: 300,
			colors: ["#e74c3c", "#00BDF0", "#10812E"],
			valuesOverPoints: 1,
			barOptions: { stacked: 0 },
			axisOptions: { shortenYAxisNumbers: 1 },
		});
	},
};
