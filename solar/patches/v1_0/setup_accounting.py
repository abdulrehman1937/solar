import frappe

from solar.accounts import ensure_service_item_accounts


def execute():
	"""Retire the desk scripts and give service items an expense account."""
	for doctype, name in (
		("Client Script", "Solar Quotation"),
		("Server Script", "Solar Project Automation"),
	):
		if frappe.db.exists(doctype, name):
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)

	module = "Solar Quotation"
	if frappe.db.exists("Module Def", module) and frappe.db.get_value("Module Def", module, "custom"):
		if not frappe.db.exists("DocType", {"module": module}):
			frappe.delete_doc("Module Def", module, force=True, ignore_permissions=True)

	for company in frappe.get_all("Company", pluck="name"):
		ensure_service_item_accounts(company)

	# Older quotations stored project ids that are no longer in the system.
	# A Link field cannot be saved while it points at a missing project.
	for row in frappe.get_all("Solar Quotation", filters={"project": ["is", "set"]}, fields=["name", "project"]):
		if row.project and not frappe.db.exists("Project", row.project):
			frappe.db.set_value("Solar Quotation", row.name, "project", None, update_modified=False)
