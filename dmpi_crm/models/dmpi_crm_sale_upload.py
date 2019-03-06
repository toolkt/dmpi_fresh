# -*- coding: utf-8 -*-

from odoo import _
from odoo.osv import expression
from odoo import models, api, fields
from odoo.exceptions import ValidationError, AccessError, UserError
from datetime import datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

from fabric.api import *
import csv
import sys
import math
import xlsxwriter, base64
from xlsxwriter.utility import xl_rowcol_to_cell
import io

import base64
from tempfile import TemporaryFile
import pprint
import tempfile
import re


CSV_UPLOAD_HEADERS = [
	'NO',
	'SHIP TO',
	'NOTIFY PARTY',
	'DESTINATION',
	'SHIPPING LINE',
	'SHELL COLOR',
	'DELIVERY DATE',
	'ESTIMATED DATE',
	'TOTAL'
]

def read_data(data):
	if data:
		fileobj = TemporaryFile("w+")
		fileobj.write(base64.b64decode(data).decode('utf-8'))
		fileobj.seek(0)
		line = csv.reader(fileobj, quotechar='"', delimiter=',', quoting=csv.QUOTE_ALL, skipinitialspace=True)
		return line

class DmpiCrmSaleContractUpload(models.TransientModel):
	_name = 'dmpi.crm.sale.contract.upload'
	_description = 'CRM Sale Contract Upload'

	def _get_default_pack_codes(self):
		pack_codes = self.env['dmpi.crm.product.code'].sudo().search([('active','=',True)])
		tmp = []
		for pc in pack_codes:
			tmp.append(pc.name)

		pack_code_tmp = ','.join(tmp)
		return pack_code_tmp

	def _get_customer(self):
		contract_id = self.env.context.get('active_id')
		contract = self.env['dmpi.crm.sale.contract'].browse(contract_id)
		return contract.partner_id.id

	template_file = fields.Binary("Template File")
	upload_file = fields.Binary("Upload File")
	contract_id = fields.Many2one("dmpi.crm.sale.contract","Contract")
	upload_line_ids = fields.One2many('dmpi.crm.sale.contract.upload.line','upload_id',"Upload Lines")
	error_count = fields.Integer("error_count")
	upload_type = fields.Selection([('customer','Customer Orders'),('commercial','Order Confirmation')], "Upload Type", default='customer')
	pack_code_tmp = fields.Text(string='Pack Code Tmp', help='Active Pack Codes Upon Create', default=_get_default_pack_codes)
	partner_id = fields.Many2one('dmpi.crm.partner', string='Customer', default=_get_customer)


	@api.onchange('upload_file')
	def onchange_upload_file(self):

		# if upload file exists
		if self.upload_file:
			rows = read_data(self.upload_file)

			row_count = 0
			line_items = []
			order_lines = {}
			total_errors = 0

			hdr = CSV_UPLOAD_HEADERS
			pack_codes = self.env['dmpi.crm.product.code'].get_product_codes()
			end_hdr = hdr.pop()
			hdr.extend(pack_codes)
			hdr.append(end_hdr)

			for r in rows:
				errors = []
				error_count = 0

				if row_count == 0:
					if not all([r[i] in hdr for i in range(len(r))]):
						raise UserError(_('Bad Header Formatting! Please use the CSV format.\n'))
					head_fmt = r

				elif r[0] != '':
					data = dict(zip(head_fmt, r))

					# CHECK LINE NO
					line_no = 0
					try:
						line_no = int(data['NO'])
					except:
						errors.append("No Line Number")
						error_count += 1

					# GET CONTRACT NUMBER
					contract_id = self.env.context.get('default_contract_id',False)
					contract = self.env['dmpi.crm.sale.contract'].browse(contract_id)
					sold_to = contract.partner_id

					# CHECK SHIP TO EXISTS
					shp = data['SHIP TO']
					ship_to = self.env['dmpi.crm.partner'].search(['&','|',('name','=',shp),('customer_code','=',shp),('id','in',sold_to.ship_to_ids.ids)],limit=1)
					if ship_to:
						ship_to_id = ship_to.id
					else:
						ship_to_id = False
						errors.append("Ship to does not exist")
						error_count += 1

					# CHECK NOTIFY ID EXISTS
					notif = data['NOTIFY PARTY']
					notify_to = self.env['dmpi.crm.partner'].search(['&','|',('name','=',notif),('customer_code','=',notif),('id','in',sold_to.ship_to_ids.ids)],limit=1)
					if notify_to:
						notify_to_id = notify_to.id
					else:
						notify_to_id = False
						errors.append("Notify Party does not exist")
						error_count += 1

					total_qty = 0
					total_p100 = 0
					total_p200 = 0
					qty_list = []

					for pcode in pack_codes:

						q = data.get(pcode,0)
						try:
							qty = int(q)
							print 
							total_qty += qty

							if 'C' not in pcode:
								total_p100 += qty
							else:
								total_p200 += qty

						except:
							qty = 0

						order_lines[pcode] = qty
						qty_list.append(qty)

					# upload format mm/dd/yyyy
					# CHECK DELIVERY DATE
					deliver_date = False
					try:
						deliver_date = datetime.strptime(data['DELIVERY DATE'], '%m/%d/%Y')
					except:
						errors.append("Invalid Delivery Date.")
						error_count += 1

					# CHECK ESTIMATED DATE
					estimated_date = False
					try:
						estimated_date = datetime.strptime(data['ESTIMATED DATE'], '%m/%d/%Y')
					except:
						errors.append("Invalid Estimated Date.")
						error_count += 1

					# CONSOLIDATE ERRORS
					errors = '\n\n'.join(errors)

					item = {
						'line_no': line_no,
						'ship_to_id': ship_to_id,
						'notify_id': notify_to_id,
						'ship_line': data['SHIPPING LINE'],
						'destination': data['DESTINATION'],
						'shell_color': data['SHELL COLOR'],
						'requested_delivery_date': deliver_date,
						'estimated_date': estimated_date,
						'order_lines': '%s' % order_lines,
						'total_qty': total_qty,
						'total_p100': total_p100,
						'total_p200': total_p200,
						'errors': errors,
						'error_count': error_count,
					}
					line_items.append((0,0,item))

				row_count += 1
				total_errors += error_count

			self.upload_line_ids = line_items
			if total_errors > 0:
				self.error_count = total_errors

		# no file found, remove lines
		else:
			self.upload_line_ids.unlink()


	@api.multi
	def process_upload(self):
		for rec in self:

			if rec.upload_type not in ['customer','commercial']:
				raise UserError('No Upload Type Selected.')
			sale_orders = []

			sap_doc_type = self.env['dmpi.crm.sap.doc.type'].search([('default','=',True)],limit=1)[0].name
			pack_codes = self.env['dmpi.crm.product.code'].get_product_codes()

			for l in rec.upload_line_ids:
				so_lines = []
				so_line_no = 0

				def format_so(rec,so_line_no,partner_id=0,qty=0,product_code=''):
					name = "Product not Maintained"
					product_id = False

					query = """ SELECT cp.id as product_id, cp.sku, cp.code, cp.product_class, spu.condition_rate, spu.condition_currency, spu.uom
								from dmpi_crm_product cp left join dmpi_sap_price_upload spu on spu.material = cp.sku
								where cp.code = '%s' and cp.active is true and cp.id in
								(select ppr.product_id from dmpi_partner_product_rel ppr where ppr.partner_id = %s) order by product_class """ % (product_code,partner_id)

					print ('query1',query)
					self.env.cr.execute(query)
					result = self.env.cr.dictfetchall()
					if result:
						name = result[0]['sku']
						product_id = result[0]['product_id']

					# get price
					pricelist_obj = self.env['dmpi.crm.product.price.list']
					rule_id, price, uom = pricelist_obj.get_product_price(product_id, partner_id, rec.contract_id.po_date, rec.contract_id.tag_ids.ids)

					return { 
								'name':name,
								'so_line_no':so_line_no, 
								'product_code': product_code, 
								'product_id': product_id,
								'uom': 'CAS',
								'qty': qty,
								'price': price,
							}

				partner_id = rec.contract_id.partner_id.id
				order_lines = eval(l.order_lines)

				for pcode in pack_codes:
					qty = order_lines.get(pcode,0)
					if qty != 0:
						so_line_no += 10
						line = format_so(rec,so_line_no,partner_id,qty,pcode)
						so_lines.append((0,0,line))

				order = {
						'contract_line_no': l.line_no,
						'ship_to_id': l.ship_to_id.id,
						'notify_id': l.notify_id.id,
						'sap_doc_type': sap_doc_type,
						'sales_org': rec.partner_id.sales_org or "",
						'shell_color': l.shell_color,
						'destination': l.destination,
						'ship_line': l.ship_line,
						'requested_delivery_date': l.requested_delivery_date,
						'estimated_date': l.estimated_date,
						'plant_id': rec.contract_id.partner_id.default_plant.id,
						'plant': rec.contract_id.partner_id.default_plant.name,
						'week_no': rec.contract_id.week_no,
						'order_ids': so_lines,
					}

				sale_orders.append((0,0,order))

			if rec.upload_type == 'customer' and rec.contract_id.state == 'draft':
				rec.contract_id.customer_order_ids.unlink()
				rec.contract_id.customer_order_ids = sale_orders

			if rec.upload_type == 'commercial':
				rec.contract_id.sale_order_ids.unlink()
				rec.contract_id.sale_order_ids = sale_orders


	@api.multi
	def donwload_template(self):
		output = io.StringIO()

		writer = csv.writer(output, delimiter=',', quoting=csv.QUOTE_ALL)
		pack_codes = self.env['dmpi.crm.product.code'].get_product_codes()

		hdr = CSV_UPLOAD_HEADERS
		end_hdr = hdr.pop()
		hdr.extend(pack_codes)
		hdr.append(end_hdr)
		writer.writerow(hdr)

		xy = output.getvalue().encode('utf-8')
		file = base64.encodestring(xy)
		self.write({'template_file':file})

		button = {
			'type' : 'ir.actions.act_url',
			'url': '/web/content/dmpi.crm.sale.contract.upload/%s/template_file/ff_crm_upload_template.csv?download=true'%(self.id),
			'target': 'new'
			}
		return button

class DmpiCrmSaleContractUploadLine(models.TransientModel):
	_name = 'dmpi.crm.sale.contract.upload.line'

	upload_id       = fields.Many2one("dmpi.crm.sale.contract.upload","Upload Template")
	line_no         = fields.Integer("Line No.")
	ship_to         = fields.Char(string="Ship to")
	ship_to_id      = fields.Many2one("dmpi.crm.partner","Ship to Party")
	notify_id       = fields.Many2one("dmpi.crm.partner","Notify Party")
	order_lines      = fields.Text(string='Order Lines')
	total_p100      = fields.Integer(string="With Crown", sum="TOTAL")
	total_p200      = fields.Integer(string="Crownless", sum="TOTAL")
	total_qty       = fields.Integer(string="Total", sum="TOTAL")
	ship_line       = fields.Char("Ship Line")
	destination     = fields.Char("Destination")
	shell_color     = fields.Char("Shell Color")
	requested_delivery_date = fields.Date('Req. Date')
	estimated_date = fields.Date('Estimated Date')
	errors          = fields.Text("Errors")
	error_count     = fields.Integer("Error Count")



