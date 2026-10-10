### Solar

Solar quotation DocTypes, print formats, and the installation flow, moved out of Client Script and Server Script so the same app can be installed on another site.

`solar.start.project` creates the project, site warehouse, material request, sales order, and draft purchase orders. Accounts and warehouses are taken from the company, not from fixed site names.

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

mit
