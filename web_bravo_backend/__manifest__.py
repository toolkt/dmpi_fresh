# -*- coding: utf-8 -*-
# OPL-1 Licensing. See LICENSE file for full copyright and licensing details.
# Copyright 2017 UNIBRAVO. @author UNIBRAVO <info@unibravo.com>  License OPL-1 (http://www.odoo.com)
{
    'name': 'Bravo Backend Theme v11',
    'category': 'Themes/Backend',
    'version': '11.0.2.0',
	'author': 'UNIBRAVO',
	"website": "https://www.unibravo.com",
    'description':
        """
Good-looking Backend User Interface for Odoo v11.0
==================================================

This well-favored backend theme module modifies the Odoo Backend User Interface to provide Professional design and responsiveness. Developed on based OCA's web_responsive theme.
        """,
    'depends': ['web'],
	'images':['images/theme_page.png', 'images/tablet_screenshot.png'],
	'application': False,
    'auto_install': False,
	'installable': True,
    "data": [
        'views/assets.xml',
        'views/web.xml',
    ],
    'qweb': [
        'static/src/xml/form_view.xml',
        'static/src/xml/navbar.xml',
    ],
    'license': 'LGPL-3',
	'price': 89,
	'currency': 'EUR',
}
