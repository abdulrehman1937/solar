async function updateDefaultRate(frm, cdt, cdn) {
  let row = frappe.get_doc(cdt, cdn);
  try {
    // Fetch item details asynchronously
    const { message: item } = await frappe.call({
      method: "frappe.client.get",
      args: {
        doctype: "Item",
        name: row.item_code,
      },
    });
    row.description = item.item_group;
    const conversionFactor = item.uoms.filter(
      ({ uom }) => uom === item.custom_default_unit_of_rate
    )[0].conversion_factor;
    if (row.rate && row.quantity) {
      row.watts = row.quantity / conversionFactor;
      row.total = (row.rate / conversionFactor) * row.quantity;
      frm.refresh_field("panels_table");
    }
    else{
        row.total=0
    }
  } catch (err) {
    console.log(err);
  }
}
async function calculateTotal(frm, cdt, cdn, field, save_description = false) {
  let row = frappe.get_doc(cdt, cdn);
  if (save_description) {
    try {
      // Fetch item details asynchronously
      const { message: item } = await frappe.call({
        method: "frappe.client.get",
        args: {
          doctype: "Item",
          name: row.item_code,
        },
      });
      row.description = `Inverter ${item.item_group}`;
    } catch (error) {
      console.log(error);
    }
  }

  if (typeof row.rate === 'number' && typeof row.quantity === 'number') {
    row.total = row.rate * row.quantity;
    frm.refresh_field(field);
  }
}
frappe.ui.form.on("Solar Quotation Panel Item", {
  rate: updateDefaultRate,
  item_code: updateDefaultRate,
  quantity: updateDefaultRate,
});
frappe.ui.form.on("Solar Quotation Inverter Item", {
  rate: (frm, cdt, cdn) =>
    calculateTotal(frm, cdt, cdn, "inverters_table", true),
  item_code: (frm, cdt, cdn) =>
    calculateTotal(frm, cdt, cdn, "inverters_table", true),
  quantity: (frm, cdt, cdn) =>
    calculateTotal(frm, cdt, cdn, "inverters_table", true),
});
frappe.ui.form.on("Solar Quotation DC Wire Item", {
  rate: (frm, cdt, cdn) => calculateTotal(frm, cdt, cdn, "dc_wires_table"),
  item_code: (frm, cdt, cdn) => calculateTotal(frm, cdt, cdn, "dc_wires_table"),
  quantity: (frm, cdt, cdn) => calculateTotal(frm, cdt, cdn, "dc_wires_table"),
});
frappe.ui.form.on("Solar Quotation AC Wire Item", {
  rate: (frm, cdt, cdn) => calculateTotal(frm, cdt, cdn, "ac_wires_table"),
  item_code: (frm, cdt, cdn) => calculateTotal(frm, cdt, cdn, "ac_wires_table"),
  quantity: (frm, cdt, cdn) => calculateTotal(frm, cdt, cdn, "ac_wires_table"),
});
frappe.ui.form.on("Solar Quotation DB Item", {
  rate: (frm, cdt, cdn) => calculateTotal(frm, cdt, cdn, "dbs_table"),
  item_code: (frm, cdt, cdn) => calculateTotal(frm, cdt, cdn, "dbs_table"),
  quantity: (frm, cdt, cdn) => calculateTotal(frm, cdt, cdn, "dbs_table"),
});
frappe.ui.form.on("Solar Quotation Earthing Wire", {
  rate: (frm, cdt, cdn) =>
    calculateTotal(frm, cdt, cdn, "earthing_wires_table"),
  item_code: (frm, cdt, cdn) =>
    calculateTotal(frm, cdt, cdn, "earthing_wires_table"),
  quantity: (frm, cdt, cdn) =>
    calculateTotal(frm, cdt, cdn, "earthing_wires_table"),
});
frappe.ui.form.on("Solar Quotation Earthing Item", {
  rate: (frm, cdt, cdn) =>
    calculateTotal(frm, cdt, cdn, "earthing_items_table"),
  item_code: (frm, cdt, cdn) =>
    calculateTotal(frm, cdt, cdn, "earthing_items_table"),
  quantity: (frm, cdt, cdn) =>
    calculateTotal(frm, cdt, cdn, "earthing_items_table"),
});
frappe.ui.form.on("Solar Quotation Misc Item", {
  rate: (frm, cdt, cdn) => calculateTotal(frm, cdt, cdn, "miscs_table"),
  item_code: (frm, cdt, cdn) => calculateTotal(frm, cdt, cdn, "miscs_table"),
  quantity: (frm, cdt, cdn) => calculateTotal(frm, cdt, cdn, "miscs_table"),
});

function populatePdf(frm, cdt, cdn) {
  let doc = frappe.get_doc(cdt, cdn);
  const {
    panels_table,
    inverters_table,
    battery,
    dc_wires_table,
    battery_item_code,
    battery_quantity,
    battery_rate,
    db_box_rate,
    db_box_quantity,
    miscs_charges,
    structure,
    net_metering,
    net_metering_charges,
    light_arrester,
    light_arrester_charges,
    earthing_quantity,
    earthing_rate,
    structure_rate,
    structure_panels,
    earthing_wires_table,
    ac_wires_table,
    labour_per_watt,
    labour_watts,
    transport,
    additionals_table
  } = doc;
  const watts = parseFloat(
    panels_table.reduce((sum, panel) => sum + (panel.watts || 0), 0)
  ).toFixed(0);
  if(!labour_watts){
      frm.set_value("labour_watts",watts)
  }
  frm.set_value("capacity", `${(watts / 1000).toFixed(2)} KW`);
  const quotation = [];
  let panels = 0;
  panels_table.forEach((panel) => {
    panels += panel.quantity;
    quotation.push({
      description: `${panel.description} (A – Grade Panels – Tier-01)`,
      item_code: panel.item_code,
      rate: panel.rate,
      total: panel.total,
      quantity: panel.quantity,
    });
  });
  frm.set_value("total_panels", panels);
  frm.set_value("panel_name", panels_table[0].item_code);
  inverters_table.forEach((inverter) =>
    quotation.push({
      description: inverter.description,
      item_code: inverter.item_code,
      rate: inverter.rate,
      total: inverter.total,
      quantity: inverter.quantity,
    })
  );
  if (battery === "Yes") {
    quotation.push({
      description: "Battery",
      item_code: battery_item_code,
      rate: battery_rate,
      total: battery_quantity * battery_rate,
      quantity: battery_quantity,
    });
  }
  quotation.push({
    description:
      "Customized Structure or L2 / L3 Stands i/c Rawal Bolts & Nuts / Solar Clips",
    item_code: structure === "L2/L3" ? "L2/L3" : "Customized Structure (14 Gauge)",
    rate: structure_rate,
    total: structure_panels * structure_rate,
    quantity: structure_panels,
  });

  dc_wires_table.forEach((wire) =>
    quotation.push({
      description: wire.description,
      item_code: wire.item_code,
      rate: wire.rate,
      total: wire.total,
      quantity: wire.quantity,
    })
  );
  quotation.push({
    description:
      "Distribution Box, DC Breakers, AC Breakers, DC & AC SPDs, (if required)",
    item_code: "Whole DB Box",
    rate: db_box_rate,
    total: db_box_quantity * db_box_rate,
    quantity: db_box_quantity,
  });
  quotation.push(...additionals_table)
  quotation.push({
    description:
      "Miscellaneous Expenses including MC-4 Panel Connectors IP 65, pipes, etc",
    item_code: "China / GM / Adam Jee",
    rate: miscs_charges,
    total: panels * miscs_charges,
    quantity: panels,
  });
  quotation.push({
    description: "Net-Metering including Bidirectional Green Meters",
    item_code: "Job",
    rate: net_metering_charges,
    total: net_metering === "Yes" ? net_metering_charges : 0,
    quantity: 1,
  });
  quotation.push({
    description: "Demand Notice (Load Sanction / Change of Name) ",
    item_code: "Job",
    rate: "Client End",
    total: 0,
    quantity: 0,
  });
  quotation.push({
    description:
      "Earthing i/c boring labour, Copper Wire, Copper Patti, Earthing powder",
    item_code: "80 ft deep",
    rate: earthing_rate,
    total: earthing_rate * earthing_quantity,
    quantity: earthing_quantity,
  });
  if(light_arrester==="Yes"){
      quotation.push({
    description:"Light Arrester with Pipe",
    item_code: "N/A",
    rate: light_arrester_charges,
    total: light_arrester_charges * 1,
    quantity: 1,
  });
  }
  quotation.push({
    description: "Earthing Cable Flexible",
    item_code: earthing_wires_table[0].item_code,
    rate: earthing_wires_table[0].rate,
    total: earthing_wires_table[0].total,
    quantity: earthing_wires_table[0].quantity,
  });

  ac_wires_table.forEach(({ description, item_code, rate, total, quantity }) =>
    quotation.push({
      description,
      item_code,
      rate,
      total,
      quantity,
    })
  );
  quotation.push({
    description: "Labour & Installation Charges ",
    item_code: "Solar Installation",
    rate: labour_per_watt,
    total: (labour_watts || watts) * (labour_per_watt || 0),
    quantity: labour_watts || watts,
  });
  quotation.push({
    description: "Transportation of Staff & Material (within Multan)",
    item_code: "Transport",
    rate: transport,
    total: transport,
    quantity: 1,
  });
  const total_amount = quotation.reduce(
    (sum, quote) => sum + (quote.total || 0),
    0
  );
  frm.set_value("total_quoted_amount", total_amount.toFixed(0));
  frm.set_value("watts", watts);
  frm.set_value("quotation_table", quotation);
}
async function call_installation(frm, method, freeze_message) {
  const args = { name: frm.doc.name };
  if (method === "solar.start.project") {
    args.company = frappe.defaults.get_user_default("Company");
  }
  const { message } = await frappe.call({
    method,
    args,
    freeze: true,
    freeze_message,
  });
  return message;
}

function show_warnings(message) {
  if (message && message.warnings && message.warnings.length) {
    frappe.msgprint({
      title: __("Check these"),
      indicator: "orange",
      message: message.warnings.join("<br>"),
    });
  }
}

function installation_buttons(frm) {
  if (!frm.doc.project) {
    frm.add_custom_button(__("Start Installation"), async () => {
      try {
        const message = await call_installation(
          frm,
          "solar.start.project",
          __("Opening the project, site, and material request...")
        );
        show_warnings(message);
        const orders = (message.purchase_orders || []).join(", ");
        let text = __("Project {0} started. Send store material in trips with Send to Site. Submit the draft purchase orders and make their invoices to book service cost. The meter purchase, if any, must not have this project on it.", [message.project]);
        if (orders) {
          text += "\n" + orders;
        }
        frappe.msgprint(text);
        frm.reload_doc();
      } catch (error) {
        frappe.msgprint({
          title: __("Error"),
          indicator: "red",
          message: error.message,
        });
      }
    }).addClass("btn-primary");
    return;
  }

  const group = __("Installation");
  if (frm.doc.material_request) {
    frm.add_custom_button(__("Send to Site"), async () => {
      try {
        const message = await call_installation(
          frm,
          "solar.start.send_material",
          __("Preparing this trip...")
        );
        frappe.msgprint(__("Draft transfer {0}. Lower the quantities to this trip, then submit. What you remove stays for the next trip.", [message.stock_entry]));
        frappe.set_route("Form", "Stock Entry", message.stock_entry);
      } catch (error) {
        frappe.msgprint({ title: __("Error"), indicator: "red", message: error.message });
      }
    }, group);
  }
  if (frm.doc.sales_order && !frm.doc.sales_invoice) {
    frm.add_custom_button(__("Sales Invoice"), async () => {
      try {
        const message = await call_installation(frm, "solar.start.invoice", __("Creating the invoice..."));
        frappe.msgprint(__("Draft invoice {0}. It is only the quoted system. Submit it to book the income.", [message.sales_invoice]));
        frm.reload_doc();
        frappe.set_route("Form", "Sales Invoice", message.sales_invoice);
      } catch (error) {
        frappe.msgprint({ title: __("Error"), indicator: "red", message: error.message });
      }
    }, group);
  }
  if (frm.doc.sales_order || frm.doc.sales_invoice) {
    frm.add_custom_button(__("Payment"), async () => {
      try {
        const message = await call_installation(frm, "solar.start.payment", __("Preparing the receipt..."));
        frappe.msgprint(__("Draft receipt {0} for the open balance. Change the amount if the client is paying less, then submit. This does not change project profit.", [message.payment_entry]));
        frappe.set_route("Form", "Payment Entry", message.payment_entry);
      } catch (error) {
        frappe.msgprint({ title: __("Error"), indicator: "red", message: error.message });
      }
    }, group);
  }
  if (frm.doc.site_warehouse) {
    frm.add_custom_button(__("Use Stock at Site"), () => {
      frappe.confirm(
        __("Issue every item still in {0} to this project? Transfer leftovers back to the store first. This books the material cost.", [frm.doc.site_warehouse]),
        async () => {
          try {
            const message = await call_installation(frm, "solar.start.use_site_stock", __("Issuing site stock..."));
            if (message.draft) {
              frappe.msgprint(__("Draft issue {0}. Enter serial or batch numbers, then submit.", [message.stock_entry]));
            } else {
              frappe.msgprint(__("Site stock was issued on {0}. Project material cost is updated.", [message.stock_entry]));
            }
            frappe.set_route("Form", "Stock Entry", message.stock_entry);
          } catch (error) {
            frappe.msgprint({ title: __("Error"), indicator: "red", message: error.message });
          }
        }
      );
    }, group);
  }
}

frappe.ui.form.on("Solar Quotation", {
  before_save: populatePdf,
  refresh: (frm) => installation_buttons(frm),
});
