{
    "name": "Partner NCC / RCCM (Côte d'Ivoire)",
    "summary": "Ivorian company identifiers (NCC, RCCM) on contacts and invoices",
    "version": "17.0.1.2.0",
    "category": "Accounting/Localizations",
    "license": "LGPL-3",
    "author": "Koffi Modeste Junior",
    "website": "https://github.com/Junmodeste/odoo-partner-ncc",
    "depends": ["account"],
    "data": [
        "views/res_partner_views.xml",
        "views/res_company_views.xml",
        "report/report_invoice.xml",
    ],
    "installable": True,
}
