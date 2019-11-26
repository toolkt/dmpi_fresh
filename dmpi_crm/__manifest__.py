# -*- coding: utf-8 -*-
{
    "name": "Dmpi CRM",
    "summary": """DMPI Customer Resource Management""",
    "description": """ 
        DMPI CRM
    """,
    "version": '1.0',   
    "category": 'Application',   
    "license": "AGPL-3",
    "website": "http://www.toolkt.com",
    "author": "Toolkit",
    "contributors": [
        "Armand Pontejos <agpontejos@gmail.com>",
    ],
    "depends": [
        'base',
        'web',
        'mail',
        'report_xlsx',
        'tk_pentaho_reports_odoo_v11',
        # 'bus',
    ],
    "data": [

        "security/ir.model.access.csv",
        "security/security.xml",

        "views/dmpi_crm_menu.xml",
        "views/dmpi_crm_config.xml",
        "views/dmpi_crm.xml",
        "views/res_users.xml",
        "views/dmpi_crm_sale_contract.xml",
        "views/dmpi_crm_sale_customer.xml",

        "views/dmpi_crm_report.xml",
        "views/dmpi_crm_sale_upload.xml",
        "views/dmpi_crm_dialogue.xml",

        "views/dmpi_crm_commercial.xml",
        "views/dmpi_crm_finance.xml",
        "views/dmpi_crm_logistics.xml",
        "views/dmpi_crm_production.xml",
        "views/dmpi_crm_complaints.xml",

        "data/schedule.xml",
        "data/sequence.xml",
        "data/crm_data.xml",
        "data/report_config.xml",
        "data/report_attachment.xml",

        "reports/report.xml",
    ],
    "demo": [

    ],
    "qweb": [
        "static/src/xml/*.xml",
    ],
    "images": [
        'static/description/banner.png'
    ],
    "external_dependencies": {
        "python": [],
        "bin": [],
    },
    "application": True,
    "installable": True,
}