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

import base64
from tempfile import TemporaryFile
import tempfile
import re

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

    upload_file = fields.Binary("Invoice Attachment")
    contract_id = fields.Many2one("dmpi.crm.sale.contract","Contract")
    upload_line_ids = fields.One2many('dmpi.crm.sale.contract.upload.line','upload_id',"Upload Lines")
    error_count = fields.Integer("error_count")
    upload_type = fields.Selection([('customer','Customer'),('commercial','Commercial')])

    @api.onchange('upload_file')
    def onchange_upload_file(self):
        if self.upload_file:
            rows = read_data(self.upload_file)

            row_count = 0
            error_count = 0
            line_items = []
            for r in rows:
                errors = []
                if r[0] != '':
                    if row_count == 0: 
                        print (r)
                    else:
                        ship_to_id = 0
                        print (r[0])
                        ship_to = self.env['dmpi.crm.ship.to'].search([('name','=',r[0])],limit=1)[0]
                        if ship_to:
                            ship_to_id = ship_to.id
                        else:
                            errors.append("Ship to does not exist")
                            error_count += 1
                        item = {
                            'ship_to': r[0],
                            'ship_to_id': ship_to_id,
                            'notify_id': ship_to_id,
                            'p5': r[2],
                            'p6': r[3],
                            'p7': r[4],
                            'p8': r[5],
                            'p9': r[6],
                            'p10': r[7],
                            'p12': r[8],
                            'p5c7': r[9],
                            'p6c8': r[10],
                            'p7c9': r[11],
                            'p8c10': r[12],
                            'p9c11': r[13],
                            'p10c12': r[14],
                            'p12c20': r[15],
                            'ship_line': r[17],
                            'shell_color': r[18],
                            'errors': errors,
                        }
                        line_items.append((0,0,item))
                row_count+=1
            self.upload_line_ids = line_items
            if error_count > 0:
                self.error_count = error_count


    @api.multi
    def process_upload(self):
        for rec in self:
            sale_orders = []
            sap_doc_type = self.env['dmpi.crm.sap.doc.type'].search([('default','=',True)],limit=1)[0].name
            print (sap_doc_type)
            for l in rec.upload_line_ids:
                so_lines = []
                so_line_no = 0

                

                def format_so(rec,so_line_no,partner_id=0,qty=0,product_code=''):
                    name = "Product not Maintained"
                    product_id = False
                    query = """SELECT cp.id as product_id, cp.sku, cp.code, cp.partner_id, spu.condition_rate,spu.condition_currency, spu.uom from dmpi_crm_product cp
                            left join dmpi_sap_price_upload spu on spu.material = cp.sku
                            where cp.code = '%s' and partner_id = %s""" % (product_code,partner_id)
                    self.env.cr.execute(query)
                    result = self.env.cr.dictfetchall()
                    if result:
                        name = result[0]['sku']
                        product_id = result[0]['product_id']
                    return { 
                                'name':name, 
                                'so_line_no':so_line_no, 
                                'product_code': product_code, 
                                'product_id': product_id,
                                'uom': 'CAS', 
                                'qty': qty
                            }

                partner_id = rec.contract_id.partner_id.id

                if l.p5 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p5,'P5')
                    so_lines.append((0,0,line))

                if l.p6 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p6,'P6')
                    so_lines.append((0,0,line))

                if l.p7 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p7,'P7')
                    so_lines.append((0,0,line))

                if l.p8 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p8,'P8')
                    so_lines.append((0,0,line))

                if l.p9 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p9,'P9')
                    so_lines.append((0,0,line))

                if l.p10 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p10,'P10')
                    so_lines.append((0,0,line))

                if l.p12 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p12,'P12')
                    so_lines.append((0,0,line))

                if l.p5c7 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p5c7,'P5C7')
                    so_lines.append((0,0,line))

                if l.p6c8 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p6c8,'P6C8')
                    so_lines.append((0,0,line))

                if l.p7c9 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p7c9,'P7C9')
                    so_lines.append((0,0,line))

                if l.p8c10 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p8c10,'P8C10')
                    so_lines.append((0,0,line))

                if l.p9c11 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p9c11,'P9C11')
                    so_lines.append((0,0,line))

                if l.p10c12 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p10c12,'P10C12')
                    so_lines.append((0,0,line))

                if l.p12c20 > 0:
                    so_line_no += 10
                    line = format_so(rec,so_line_no,partner_id,l.p12c20,'P12C20')
                    so_lines.append((0,0,line))



                order = {
                        'ship_to_id': l.ship_to_id.id,
                        'notify_id': l.notify_id.id,
                        'sap_doc_type': sap_doc_type,
                        'sales_org': l.ship_to_id.partner_id.sales_org or "",
                        'shell_color': l.shell_color,
                        'ship_line': l.ship_line,
                        'plant': rec.contract_id.partner_id.plant,
                        'p5': l.p5,
                        'p6': l.p6,
                        'p7': l.p7,
                        'p8': l.p8,
                        'p9': l.p9,
                        'p10': l.p10,
                        'p12': l.p12,
                        'p5c7': l.p5c7,
                        'p6c8': l.p6c8,
                        'p7c9': l.p7c9,
                        'p8c10': l.p8c10,
                        'p9c11': l.p9c11,
                        'p10c12': l.p10c12,
                        'p12c20': l.p12c20,
                        'order_ids': so_lines,
                    }

                print(order)
                sale_orders.append((0,0,order))
            if rec.upload_type == 'customer':
                rec.contract_id.customer_order_ids.unlink()
                rec.contract_id.customer_order_ids = sale_orders
            if rec.upload_type == 'commercial':
                rec.contract_id.sale_order_ids.unlink()
                rec.contract_id.sale_order_ids = sale_orders



class DmpiCrmSaleContractUploadLine(models.TransientModel):
    _name = 'dmpi.crm.sale.contract.upload.line'


    @api.depends('p5','p6','p7','p8','p9','p10','p12','p5c7','p6c8','p7c9','p8c10','p9c11','p10c12','p12c20')
    def _get_totals(self):
        for rec in self:
            rec.total_crown = rec.p5+rec.p6+rec.p7+rec.p8+rec.p9+rec.p10+rec.p12
            rec.total_crownless = rec.p5c7+rec.p6c8+rec.p7c9+rec.p8c10+rec.p9c11+rec.p10c12+rec.p12c20
            rec.total_qty = rec.total_crown + rec.total_crownless

    upload_id       = fields.Many2one("dmpi.crm.sale.contract.upload","Upload Template")
    ship_to         = fields.Char(string="Ship to")
    ship_to_id      = fields.Many2one("dmpi.crm.ship.to","Ship to Party")
    notify_id       = fields.Many2one("dmpi.crm.ship.to","Notify ID")
    p5              = fields.Integer(string="P5", sum="TOTAL")
    p6              = fields.Integer(string="P6", sum="TOTAL")
    p7              = fields.Integer(string="P7", sum="TOTAL")
    p8              = fields.Integer(string="P8", sum="TOTAL")
    p9              = fields.Integer(string="P9", sum="TOTAL")
    p10             = fields.Integer(string="P10", sum="TOTAL")
    p12             = fields.Integer(string="P12", sum="TOTAL")
    p5c7            = fields.Integer(string="P5C7", sum="TOTAL")
    p6c8            = fields.Integer(string="P6C8", sum="TOTAL")
    p7c9            = fields.Integer(string="P7C9", sum="TOTAL")
    p8c10           = fields.Integer(string="P8C10", sum="TOTAL")
    p9c11           = fields.Integer(string="P9C11", sum="TOTAL")
    p10c12          = fields.Integer(string="P10C12", sum="TOTAL")
    p12c20          = fields.Integer(string="P12C20", sum="TOTAL") 
    total_qty       = fields.Integer(string="Total", compute="_get_totals", sum="TOTAL")
    ship_line       = fields.Char("Ship Line")
    shell_color     = fields.Char("Shell Color")
    errors          = fields.Char("Errors")


