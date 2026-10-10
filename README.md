### Solar

Solar quotation DocTypes, print formats, and the installation flow, moved out of Client Script and Server Script so the same app can be installed on another site.

`solar.start.project` creates the project, site warehouse, material request, sales order, and draft purchase orders. Accounts and warehouses are taken from the company, not from fixed site names.

The profit formula, the expense accounts, and every decision behind them are in [docs/accounting.md](docs/accounting.md).

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app solar
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/solar
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

GNU Affero General Public License v3.0. See [license.txt](license.txt).

You may use this app, change it, and pass it on. A changed version that you distribute, or run on a server for other people, stays under this same license and the source stays available.

You may charge for a copy, for installation, or for support. You may not take a changed version private.

Copyright is held by Xeuro Tech. That copyright is what allows paid installation, support, and a separate commercial license for a company that will not publish its own changes.
