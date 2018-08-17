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

import base64
from tempfile import TemporaryFile
import tempfile
import re


PRODUCT_CODES = ['p5','p6','p7','p8','p9','p10','p12','p5c7','p6c8','p7c9','p8c10','p9c11','p10c12','p12c20']

def read_data(data):
    if data:
        fileobj = TemporaryFile("w+")
        fileobj.write(base64.b64decode(data).decode('utf-8'))
        fileobj.seek(0)
        line = csv.reader(fileobj, quotechar='"', delimiter=',', quoting=csv.QUOTE_ALL, skipinitialspace=True)
        return line


def check_pallet(qty, round_1, round_2):
    rem_qty = qty

    while (rem_qty % round_2) != 0:

        rem_qty -= round_1
        if rem_qty < 0:
            return False

        elif rem_qty == 0:
            return True

    return True



class DmpiCrmSaleContractUpload(models.TransientModel):
    _name = 'dmpi.crm.sale.contract.upload'
    _description = 'CRM Sale Contract Upload'

    upload_file = fields.Binary("Invoice Attachment")
    contract_id = fields.Many2one("dmpi.crm.sale.contract","Contract")
    upload_line_ids = fields.One2many('dmpi.crm.sale.contract.upload.line','upload_id',"Upload Lines")
    error_count = fields.Integer("error_count")
    upload_type = fields.Selection([('customer','Customer'),('commercial','Commercial')], "Upload Type", default='customer')

    @api.onchange('upload_file')
    def onchange_upload_file(self):
        if self.upload_file:
            rows = read_data(self.upload_file)

            row_count = 0
            pcode_start = 3
            pcode_end = 16
            line_items = []
            total_errors = 0

            for r in rows:
                errors = []
                error_count = 0

                if r[0] != '':
                    if row_count == 0:
                        print (r)
                    else:
                        # CHECK LINE NO
                        line_no = 0
                        try:
                            line_no = int(r[0])
                        except:
                            errors.append("No Line Number")
                            error_count += 1

                        # GET CONTRACT NUMBER
                        contract_id = self.env.context.get('default_contract_id',False)
                        contract = self.env['dmpi.crm.sale.contract'].browse(contract_id)
                        sold_to_id = contract.partner_id.id



                        # CHECK SHIP TO EXISTS
                        ship_to = self.env['dmpi.crm.ship.to'].search([('name','=',r[1]),('partner_id.id','=',sold_to_id)],limit=1)
                        if ship_to:
                            ship_to_id = ship_to.id
                        else:
                            ship_to_id = False
                            errors.append("Ship to does not exist")
                            error_count += 1



                        # CHECK NOTIFY ID EXISTS
                        notify_to = self.env['dmpi.crm.ship.to'].search([('name','=',r[1]),('partner_id.id','=',sold_to_id)],limit=1)
                        if notify_to:
                            notify_to_id = notify_to.id
                        else:
                            notify_to_id = False
                            errors.append("Notify to does not exist")
                            error_count += 1



                        # CHECK TOTAL QUANTITY
                        fcl_config = self.env['dmpi.crm.fcl.config'].search([('config_id.active','=',True),('active','=',True)], limit=2)
                        fcl_config_cases_van = fcl_config.mapped('cases_van')
                        fcl_config_pallet = fcl_config.mapped('pallet')

                        total = 0
                        for i in range(pcode_start, pcode_end+1):
                            try:
                                qty = int(r[i])
                                total += qty
                            except:
                                continue


                            # CHECK PALLET ROUNDING
                            round_1 = fcl_config_pallet[0]
                            round_2 = fcl_config_pallet[1]
                            is_pallet = check_pallet(qty, round_1, round_2)

                            if not is_pallet:
                                errors.append("Wrong Pallet Combination %s" % qty)
                                error_count += 1

                        if total not in fcl_config_cases_van:
                            errors.append("Invalid Total %s" % total)
                            error_count += 1




                        # CHECK DELIVERY DATE
                        # upload format dd/mm/yyyy
                        deliver_date = False
                        try:
                            deliver_date = datetime.strptime(r[20], '%d/%m/%Y')
                        except:
                            errors.append("Invalid Deliver Date")
                            error_count += 1



                        # CONSOLIDATE ERRORS
                        errors = '\n\n'.join(errors)

                        item = {
                            'line_no': line_no,
                            'ship_to': r[1],
                            'ship_to_id': ship_to_id,
                            'notify_id': notify_to_id,
                            'p5': r[3],
                            'p6': r[4],
                            'p7': r[5],
                            'p8': r[6],
                            'p9': r[7],
                            'p10': r[8],
                            'p12': r[9],
                            'p5c7': r[10],
                            'p6c8': r[11],
                            'p7c9': r[12],
                            'p8c10': r[13],
                            'p9c11': r[14],
                            'p10c12': r[15],
                            'p12c20': r[16],
                            'ship_line': r[18],
                            'shell_color': r[19],
                            'requested_delivery_date': deliver_date,
                            'errors': errors,
                            'error_count': error_count,

                        }
                        line_items.append((0,0,item))
                row_count+=1
                total_errors += error_count

            self.upload_line_ids = line_items
            if total_errors > 0:
                self.error_count = total_errors

        else:
            self.upload_line_ids.unlink()


    @api.multi
    def process_upload(self):
        for rec in self:

            if rec.upload_type not in ['customer','commercial']:
                raise UserError('No Upload Type Selected.')
            sale_orders = []

            # contract_id = self.env.context.get('default_contract_id',False)
            # contract = self.env['dmpi.crm.sale.contract'].browse(contract_id)
            # sap_doc_type = contract.contract_type.name
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
                        'contract_line_no': l.line_no,
                        'ship_to_id': l.ship_to_id.id,
                        'notify_id': l.notify_id.id,
                        'sap_doc_type': sap_doc_type,
                        'sales_org': l.ship_to_id.partner_id.sales_org or "",
                        'shell_color': l.shell_color,
                        'ship_line': l.ship_line,
                        'requested_delivery_date': l.requested_delivery_date,
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
    line_no         = fields.Integer("Line No.")
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
    errors          = fields.Text("Errors")
    error_count     = fields.Integer("Error Count")
    requested_delivery_date = fields.Date('Req. Date')


