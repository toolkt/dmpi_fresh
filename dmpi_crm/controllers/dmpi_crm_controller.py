# -*- coding: utf-8 -*-

from odoo import _
from odoo import models, api, fields
from odoo.exceptions import ValidationError, AccessError, UserError
from odoo import http
from odoo.http import content_disposition, dispatch_rpc, request, serialize_exception as _serialize_exception, Response

import base64
from tempfile import TemporaryFile
from datetime import datetime
import tempfile
import re
import json

class DmpiCrmSaleOrderController(http.Controller):
	@http.route('/csv/download/dmpi_crm_sale_order/', auth='user')
	def demand_sale_orders_csv_download(self, docids, **kw):
		print ('PASSED CONTROLLER SALE ORDER DEMAND')

		docids = json.loads(docids)
		csv = http.request.env['dmpi.crm.sale.order']._sale_order_demand_create_csv(docids)
		today = datetime.today()
		filename = 'sale_orders_demand_%s.csv' % today

		return request.make_response(csv,
				[('Content-Type','application/octet-stream'),
				 ('Content-Disposition','attachment; filename=%s' % filename)])


