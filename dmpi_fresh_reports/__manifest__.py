{
    'name': 'DMPI FRESH Reports',
    'category': 'Specific Industry Applications',
    'summary': 'DMPI FRESH Reports V11',
    'version': '0.1',
    'description': """
 
 
DMPI FRESH Reports Module 2018
====================================
For Version 11
  
        """,
    'author': 'Toolkit',
    'depends': [
        'base',
        'report_xlsx',
        'tk_pentaho_reports_odoo_v11',
    ],
    'demo': [
    ],
    'data': [
        # data
        'data/report_config.xml',
        'data/report_attachment.xml',
        'data/dr_data.xml',

        # reports
        'reports/report.xml',

        # views
        'views/views.xml',
    ],
    "js": [
    ],
    'qweb': [
    ],
    'installable': True,
}