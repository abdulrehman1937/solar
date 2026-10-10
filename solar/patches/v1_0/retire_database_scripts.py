import frappe


def execute():
	"""Drop the desk copies now that the app owns the form script and the API."""
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
