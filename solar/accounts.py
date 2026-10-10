# Copyright (c) 2026, Xeuro Tech and contributors
# For license information, please see license.txt

import frappe

# Bought as services. Their purchase invoices are project cost.
# They must not be stock items, or the closing stock issue would count them again.
SERVICE_ITEMS = (
	"Solar Installation",
	"Solar Customized Structure",
	"Earthing Bor",
	"Net Metering Processing Charges",
)

# WAPDA: two meters, bought onto the site. Stock, so the cost waits until the closing issue.
METER_ITEM = "Green Meter"
METER_QTY = 2


def job_cost_account(company: str) -> str:
	"""Expense account for installer, structure, boring, and net-metering bills."""
	abbr = frappe.get_cached_value("Company", company, "abbr")
	account = f"Solar Job Cost - {abbr}"
	if frappe.db.exists("Account", account):
		return account

	parent = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": "Direct Expenses", "is_group": 1},
		"name",
	)
	if not parent:
		frappe.throw(f"Company {company} has no Direct Expenses group to hold Solar Job Cost")

	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": "Solar Job Cost",
			"parent_account": parent,
			"company": company,
			"root_type": "Expense",
			"is_group": 0,
			"report_type": "Profit and Loss",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def stock_expense_account(company: str) -> str:
	"""COGS for material issued from the client site. Not used on the meter purchase."""
	account = frappe.get_cached_value("Company", company, "default_expense_account")
	if account:
		return account
	abbr = frappe.get_cached_value("Company", company, "abbr")
	return f"Cost of Goods Sold - {abbr}"


def job_cost_center(company: str) -> str:
	abbr = frappe.get_cached_value("Company", company, "abbr")
	name = f"Solar Business - {abbr}"
	if frappe.db.exists("Cost Center", name):
		return name
	return frappe.get_cached_value("Company", company, "cost_center")


def sites_parent_warehouse(company: str) -> str:
	abbr = frappe.get_cached_value("Company", company, "abbr")
	name = f"Sites - {abbr}"
	if not frappe.db.exists("Warehouse", name):
		frappe.throw(f"Create a group warehouse {name} before starting an installation")
	return name


def source_warehouse(company: str) -> str:
	warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")
	if warehouse and frappe.db.exists("Warehouse", warehouse):
		return warehouse
	frappe.throw(f"Set the default warehouse in Stock Settings for {company}")


def ensure_service_item_accounts(company: str) -> str:
	"""Point service items at Solar Job Cost so a purchase invoice expenses them once."""
	account = job_cost_account(company)
	for item_code in SERVICE_ITEMS:
		if not frappe.db.exists("Item", item_code):
			continue
		_set_expense_account(item_code, company, account)
	return account


def _set_expense_account(item_code: str, company: str, account: str) -> None:
	item = frappe.get_doc("Item", item_code)
	if item.is_stock_item:
		frappe.throw(f"{item_code} is a stock item. Service cost would be counted twice if it is purchased onto a project.")

	row = next((d for d in item.item_defaults if d.company == company), None)
	if row and row.expense_account == account:
		return
	if row:
		row.expense_account = account
	else:
		item.append("item_defaults", {"company": company, "expense_account": account})
	item.flags.ignore_mandatory = True
	item.save(ignore_permissions=True)
