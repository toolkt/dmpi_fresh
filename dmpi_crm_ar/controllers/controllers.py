# -*- coding: utf-8 -*-
from odoo import http

# class DmpiCrmAr(http.Controller):
#     @http.route('/dmpi_crm_ar/dmpi_crm_ar/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/dmpi_crm_ar/dmpi_crm_ar/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('dmpi_crm_ar.listing', {
#             'root': '/dmpi_crm_ar/dmpi_crm_ar',
#             'objects': http.request.env['dmpi_crm_ar.dmpi_crm_ar'].search([]),
#         })

#     @http.route('/dmpi_crm_ar/dmpi_crm_ar/objects/<model("dmpi_crm_ar.dmpi_crm_ar"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('dmpi_crm_ar.object', {
#             'object': obj
#         })