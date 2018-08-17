# -*- coding: utf-8 -*-

###################################################################################
# 
#    Copyright (C) 2017 MuK IT GmbH
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###################################################################################

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
        # 'web_widget_sheet',
    ],
    "data": [
        "views/dmpi_crm_menu.xml",
        "views/dmpi_crm_config.xml",
        "views/dmpi_crm.xml",
        "views/dmpi_crm_sale.xml",
        "views/dmpi_crm_sale_order.xml",
        # "views/customer_crm_sale_order.xml",
        "views/dmpi_crm_sale_contract.xml",
        "views/dmpi_crm_report.xml",
        "views/dmpi_crm_sale_upload.xml",
        "views/dmpi_crm_dialogue.xml",

        #"views/dmpi_crm_contract.xml",
        #"views/dmpi_crm_web.xml",
        "security/ir.model.access.csv",
        "security/security.xml",

        "data/schedule.xml",
        "data/sequence.xml",
        "data/crm_data.xml",
        "data/report_config.xml",
        "data/report_attachment.xml",

        "reports/report.xml"
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