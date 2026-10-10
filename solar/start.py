# Copyright (c) 2026, Xeuro Tech and contributors
# For license information, please see license.txt

import json

import frappe

from solar.installation import consume_site_stock, make_invoice, make_payment, send_to_site, start_installation


def _name_and_company(name: str | None, company: str | None, solar_quotation: str | dict | None) -> tuple[str, str | None]:
	if solar_quotation:
		if isinstance(solar_quotation, str):
			solar_quotation = json.loads(solar_quotation)
		name = name or solar_quotation.get("name")
		company = company or solar_quotation.get("company")
	if not name:
		frappe.throw("Solar Quotation is required")
	return name, company


@frappe.whitelist()
def project(
	name: str | None = None,
	company: str | None = None,
	solar_quotation: str | dict | None = None,
) -> dict:
	"""Open the job: project, site, material request, sales order, and draft purchases."""
	name, company = _name_and_company(name, company, solar_quotation)
	return start_installation(name, company)


@frappe.whitelist()
def send_material(name: str) -> dict:
	return send_to_site(name)


@frappe.whitelist()
def invoice(name: str) -> dict:
	return make_invoice(name)


@frappe.whitelist()
def payment(name: str) -> dict:
	return make_payment(name)


@frappe.whitelist()
def use_site_stock(name: str) -> dict:
	return consume_site_stock(name)
