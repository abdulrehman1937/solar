# Copyright (c) 2026, Xeuro Tech and contributors
# For license information, please see license.txt

"""Installation documents for one solar quotation.

Profit on the project is:

    sales invoice (quoted system)
    minus purchase invoices for services
    minus stock issued from the site warehouse

A payment does not change that profit. A transfer into the site does not either.
Meters are stock bought onto the site, so their purchase invoice must not carry
the project. The closing issue picks up their value with the other site stock.
"""

from collections import defaultdict

import frappe
from frappe.utils import add_days, flt, today

from solar.accounts import (
	METER_ITEM,
	METER_QTY,
	ensure_service_item_accounts,
	job_cost_center,
	sites_parent_warehouse,
	source_warehouse,
	stock_expense_account,
)

INSTALLATION_ITEM = "Solar Installation"
STOCK_TABLES = (
	"panels_table",
	"inverters_table",
	"dc_wires_table",
	"ac_wires_table",
	"earthing_wires_table",
	"dbs_table",
	"earthing_items_table",
	"miscs_table",
)


def start_installation(name: str, company: str | None = None) -> dict:
	quotation = _quotation(name)
	if quotation.project and frappe.db.exists("Project", quotation.project):
		frappe.throw(f"Project {quotation.project} is already started")

	company = _company(company)
	if not flt(quotation.total_quoted_amount):
		frappe.throw("Save the quotation so it has a total before starting the installation")
	if not quotation.client_name:
		frappe.throw("Set the client before starting the installation")
	if not frappe.db.exists("Item", INSTALLATION_ITEM):
		frappe.throw(f"Item {INSTALLATION_ITEM} does not exist")

	ensure_service_item_accounts(company)
	cost_center = job_cost_center(company)
	warnings = []

	project = frappe.get_doc(
		{
			"doctype": "Project",
			"project_name": f"{quotation.name} - Solar Installation",
			"expected_start_date": today(),
			"customer": quotation.client_name,
			"company": company,
			"cost_center": cost_center,
		}
	).insert(ignore_permissions=True)

	warehouse = _site_warehouse(quotation, company)
	material_request = _material_request(quotation, company, warehouse, project.name, warnings)
	sales_order = _sales_order(quotation, company, project.name, cost_center)
	purchase_orders = _purchase_orders(quotation, company, warehouse, project.name, cost_center, warnings)

	quotation.db_set("project", project.name)
	quotation.db_set("site_warehouse", warehouse)
	if material_request:
		quotation.db_set("material_request", material_request)
	quotation.db_set("sales_order", sales_order)

	return {
		"project": project.name,
		"site_warehouse": warehouse,
		"material_request": material_request,
		"sales_order": sales_order,
		"purchase_orders": purchase_orders,
		"warnings": warnings,
	}


def send_to_site(name: str) -> dict:
	"""Draft a transfer of whatever is still on the material request.

	The user lowers the quantities to this trip and submits. Leftover request
	qty stays for the next trip. Submitting the transfer does not book a cost.
	"""
	quotation = _quotation(name)
	if not quotation.material_request:
		frappe.throw("Start the installation before sending material")

	from erpnext.stock.doctype.material_request.material_request import make_stock_entry

	stock_entry = make_stock_entry(quotation.material_request)
	stock_entry.project = None
	kept = []
	for row in stock_entry.items:
		if flt(row.qty) <= 0:
			continue
		# Target warehouse is set, so this row is not project consumption.
		row.project = None
		kept.append(row)
	if not kept:
		frappe.throw("Nothing is left to send. Earlier transfers already cover this request.")

	stock_entry.items = kept
	stock_entry.insert(ignore_permissions=True)
	return {"stock_entry": stock_entry.name}


def make_invoice(name: str) -> dict:
	"""Draft invoice for the quoted system only. Submit it to recognise income."""
	quotation = _quotation(name)
	if quotation.sales_invoice:
		return {"sales_invoice": quotation.sales_invoice, "existing": True}
	if not quotation.sales_order:
		frappe.throw("Start the installation before creating the invoice")

	from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

	invoice = make_sales_invoice(quotation.sales_order)
	invoice.project = quotation.project
	cost_center = job_cost_center(invoice.company)
	for row in invoice.items:
		if row.item_code != INSTALLATION_ITEM:
			frappe.throw("The sales order has items other than the quoted system. Refusing to invoice them.")
		row.project = quotation.project
		row.cost_center = cost_center
	if quotation.project:
		invoice.set_advances()
	invoice.insert(ignore_permissions=True)
	quotation.db_set("sales_invoice", invoice.name)
	return {"sales_invoice": invoice.name, "existing": False}


def make_payment(name: str) -> dict:
	"""Draft receipt for the open balance. Change the amount before submitting.

	The project is stored on the payment so the money can be traced. It does
	not increase project income. Income is the submitted sales invoice.
	"""
	quotation = _quotation(name)
	if quotation.sales_invoice and frappe.db.get_value("Sales Invoice", quotation.sales_invoice, "docstatus") == 1:
		reference_doctype, reference_name = "Sales Invoice", quotation.sales_invoice
	elif quotation.sales_order:
		reference_doctype, reference_name = "Sales Order", quotation.sales_order
	else:
		frappe.throw("Start the installation before recording a payment")

	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	payment = get_payment_entry(reference_doctype, reference_name)
	if not payment.reference_no:
		payment.reference_no = quotation.name
	if not payment.reference_date:
		payment.reference_date = today()
	payment.project = quotation.project
	if quotation.project:
		payment.cost_center = job_cost_center(payment.company)
	payment.insert(ignore_permissions=True)
	return {"payment_entry": payment.name, "paid_amount": payment.paid_amount}


def consume_site_stock(name: str) -> dict:
	"""Issue the whole balance of the site warehouse to the project.

	This is the material cost. Run it when the job is finished, after any
	unused material has been transferred back to the store.
	"""
	quotation = _quotation(name)
	if not quotation.site_warehouse:
		frappe.throw("This quotation has no site warehouse")
	if not quotation.project or not frappe.db.exists("Project", quotation.project):
		frappe.throw("This quotation has no project")

	company = frappe.db.get_value("Warehouse", quotation.site_warehouse, "company")
	cost_center = job_cost_center(company)
	expense_account = stock_expense_account(company)
	rows = []
	needs_serial = False
	for bin_row in frappe.get_all(
		"Bin",
		filters={"warehouse": quotation.site_warehouse, "actual_qty": [">", 0]},
		fields=["item_code", "actual_qty"],
	):
		item = frappe.get_cached_value(
			"Item", bin_row.item_code, ["stock_uom", "has_serial_no", "has_batch_no"], as_dict=True
		)
		if item.has_serial_no or item.has_batch_no:
			needs_serial = True
		rows.append(
			{
				"item_code": bin_row.item_code,
				"qty": bin_row.actual_qty,
				"uom": item.stock_uom,
				"stock_uom": item.stock_uom,
				"conversion_factor": 1,
				"s_warehouse": quotation.site_warehouse,
				"project": quotation.project,
				"cost_center": cost_center,
				"expense_account": expense_account,
			}
		)
	if not rows:
		frappe.throw(f"Site warehouse {quotation.site_warehouse} has no stock to issue")

	stock_entry = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"purpose": "Material Issue",
			"company": company,
			"project": quotation.project,
			"items": rows,
		}
	)
	stock_entry.insert(ignore_permissions=True)
	for row in stock_entry.items:
		row.project = quotation.project
		row.t_warehouse = None
		row.expense_account = expense_account
		row.cost_center = cost_center
	stock_entry.save(ignore_permissions=True)
	if needs_serial:
		return {"stock_entry": stock_entry.name, "draft": True}
	stock_entry.submit()
	return {"stock_entry": stock_entry.name, "draft": False}


def _quotation(name: str):
	quotation = frappe.get_doc("Solar Quotation", name)
	quotation.check_permission("write")
	return quotation


def _company(company: str | None) -> str:
	company = company or frappe.defaults.get_user_default("Company")
	company = company or frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		frappe.throw("Select a company")
	return company


def _site_warehouse(quotation, company: str) -> str:
	abbr = frappe.get_cached_value("Company", company, "abbr")
	warehouse_name = f"Site for {quotation.name}"
	existing = f"{warehouse_name} - {abbr}"
	if frappe.db.exists("Warehouse", existing):
		return existing
	warehouse = frappe.get_doc(
		{
			"doctype": "Warehouse",
			"warehouse_name": warehouse_name,
			"company": company,
			"parent_warehouse": sites_parent_warehouse(company),
		}
	).insert(ignore_permissions=True)
	return warehouse.name


def _stock_lines(quotation) -> dict[str, float]:
	quantities = defaultdict(float)
	for table in STOCK_TABLES:
		for row in quotation.get(table) or []:
			if row.item_code and flt(row.quantity) > 0:
				quantities[row.item_code] += flt(row.quantity)
	if quotation.battery == "Yes" and quotation.battery_item_code and flt(quotation.battery_quantity) > 0:
		quantities[quotation.battery_item_code] += flt(quotation.battery_quantity)
	# Meters are purchased, not picked from the store.
	quantities.pop(METER_ITEM, None)
	missing = [item_code for item_code in quantities if not frappe.db.exists("Item", item_code)]
	if missing:
		frappe.throw("These quotation items do not exist: " + ", ".join(missing))
	return quantities


def _material_request(quotation, company, warehouse, project, warnings) -> str | None:
	lines = _stock_lines(quotation)
	if not lines:
		warnings.append("No store items were found, so no material request was created.")
		return None

	source = source_warehouse(company)
	items = []
	for item_code, qty in lines.items():
		if not frappe.get_cached_value("Item", item_code, "is_stock_item"):
			warnings.append(f"{item_code} is not stock, so it was left off the material request.")
			continue
		items.append(
			{
				"item_code": item_code,
				"qty": qty,
				"schedule_date": today(),
				"warehouse": warehouse,
				"from_warehouse": source,
			}
		)
	if not items:
		warnings.append("No stock items were left to request from the store.")
		return None

	payload = {
		"doctype": "Material Request",
		"title": f"{quotation.name} - Material Request",
		"material_request_type": "Material Transfer",
		"company": company,
		"schedule_date": today(),
		"set_from_warehouse": source,
		"set_warehouse": warehouse,
		"items": items,
	}
	if frappe.get_meta("Material Request").has_field("project"):
		payload["project"] = project
	material_request = frappe.get_doc(payload)
	material_request.insert(ignore_permissions=True)
	# Submitting the request does not move stock. Transfers are created per trip.
	material_request.submit()
	return material_request.name


def _sales_order(quotation, company, project, cost_center) -> str:
	sales_order = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"customer": quotation.client_name,
			"company": company,
			"project": project,
			"cost_center": cost_center,
			"delivery_date": add_days(today(), 7),
			"items": [
				{
					"item_code": INSTALLATION_ITEM,
					"qty": 1,
					"rate": flt(quotation.total_quoted_amount),
					"project": project,
					"cost_center": cost_center,
					"delivery_date": add_days(today(), 7),
				}
			],
		}
	)
	sales_order.insert(ignore_permissions=True)
	sales_order.submit()
	return sales_order.name


def _purchase_orders(quotation, company, warehouse, project, cost_center, warnings) -> list[str]:
	created = []
	created.extend(_service_orders(quotation, company, project, cost_center, warnings))
	meter_order = _meter_order(quotation, company, warehouse, cost_center, warnings)
	if meter_order:
		created.append(meter_order)
	return created


def _service_orders(quotation, company, project, cost_center, warnings) -> list[str]:
	by_supplier = defaultdict(list)
	for item_code, qty, rate, supplier in _services(quotation):
		if not frappe.db.exists("Item", item_code):
			warnings.append(f"Service item {item_code} does not exist, so it was not ordered.")
			continue
		if not supplier:
			warnings.append(f"No supplier for {item_code}, so that purchase was left out.")
			continue
		if not frappe.db.exists("Supplier", supplier):
			warnings.append(f"Supplier {supplier} does not exist, so {item_code} was left out.")
			continue
		by_supplier[supplier].append(
			{
				"item_code": item_code,
				"qty": qty,
				"rate": rate,
				"schedule_date": today(),
				"project": project,
				"cost_center": cost_center,
			}
		)

	names = []
	for supplier, items in by_supplier.items():
		order = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"supplier": supplier,
				"company": company,
				"project": project,
				"cost_center": cost_center,
				"schedule_date": today(),
				"items": items,
			}
		)
		order.insert(ignore_permissions=True)
		names.append(order.name)
	return names


def _services(quotation) -> list[tuple]:
	rows = []
	if flt(quotation.solar_installer_charge) and flt(quotation.watts):
		rows.append(
			(INSTALLATION_ITEM, flt(quotation.watts), flt(quotation.solar_installer_charge), quotation.solar_installer)
		)
	if flt(quotation.solar_structure_charges) and flt(quotation.total_panels):
		rows.append(
			(
				"Solar Customized Structure",
				flt(quotation.total_panels),
				flt(quotation.solar_structure_charges),
				quotation.solar_structure_installer,
			)
		)
	if flt(quotation.earthing_bor) and flt(quotation.earthing_quantity):
		rows.append(
			("Earthing Bor", flt(quotation.earthing_quantity), flt(quotation.earthing_bor), quotation.earthing_bore_supplier)
		)
	if flt(quotation.net_meter_charges):
		rows.append(
			("Net Metering Processing Charges", 1, flt(quotation.net_meter_charges), quotation.net_meter_supplier)
		)
	return rows


def _meter_order(quotation, company, warehouse, cost_center, warnings) -> str | None:
	if quotation.net_metering != "Yes":
		return None
	if not frappe.db.exists("Item", METER_ITEM):
		warnings.append(f"Item {METER_ITEM} does not exist, so the two meters were not ordered.")
		return None
	supplier = quotation.green_meter_supplier
	if not supplier or not frappe.db.exists("Supplier", supplier):
		warnings.append("Set the green meter supplier and make a purchase order for 2 Green Meters. Do not put the project on that purchase.")
		return None

	if not flt(quotation.green_meter_charges):
		warnings.append(
			"Set the green meter charges, then purchase 2 Green Meters into the site warehouse. Leave the project off that purchase."
		)
		return None

	rate = flt(quotation.green_meter_charges) / METER_QTY
	# No project. The meters stay in stock until the site is issued to the project.
	order = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"supplier": supplier,
			"company": company,
			"cost_center": cost_center,
			"schedule_date": today(),
			"items": [
				{
					"item_code": METER_ITEM,
					"qty": METER_QTY,
					"rate": rate,
					"schedule_date": today(),
					"warehouse": warehouse,
					"cost_center": cost_center,
				}
			],
		}
	)
	order.insert(ignore_permissions=True)
	order.add_comment(
		"Comment",
		"Do not put the project on this order or its invoice. Receive the meters into the site warehouse. Their cost is booked when the site stock is issued to the project.",
	)
	return order.name
