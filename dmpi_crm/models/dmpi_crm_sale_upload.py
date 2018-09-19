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
import pprint
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


    upload_file = fields.Binary("Invoice Attachment")
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

            head_fmt = ['NO','SHIP TO','NOTIFY PARTY','DESTINATION','SHIPPING LINE','SHELL COLOR','DELIVERY DATE']
            tmp = self.pack_code_tmp.split(',')
            for p in tmp:
                head_fmt.append(p)
            head_fmt.append('TOTAL')

            for r in rows:
                errors = []
                error_count = 0

                if row_count == 0:

                    if len(head_fmt) != len(r):
                        raise UserError(_('Bad Header Formatting! Please use below format.\n %s' % head_fmt))

                    for h1,h2 in zip(head_fmt, r):
                        if h1 != h2:
                            raise UserError(_('Bad Header Formatting! Please use below format.\n %s' % head_fmt))

                    row_count += 1



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
                    sold_to_id = contract.partner_id.id

                    # CHECK SHIP TO EXISTS
                    shp = data['SHIP TO']
                    ship_to = self.env['dmpi.crm.ship.to'].search(['&','|',('name','=',shp),('ship_to_code','=',shp),('partner_id.id','=',sold_to_id)],limit=1)
                    if ship_to:
                        ship_to_id = ship_to.id
                    else:
                        ship_to_id = False
                        errors.append("Ship to does not exist")
                        error_count += 1

                    # CHECK NOTIFY ID EXISTS
                    notif = data['NOTIFY PARTY']
                    notify_to = self.env['dmpi.crm.ship.to'].search(['&','|',('name','=',notif),('ship_to_code','=',notif),('partner_id.id','=',sold_to_id)],limit=1)
                    if notify_to:
                        notify_to_id = notify_to.id
                    else:
                        notify_to_id = False
                        errors.append("Notify Party does not exist")
                        error_count += 1

                    # CHECK FCL AND PALLETIZATION
                    total_qty = 0
                    total_p100 = 0
                    total_p200 = 0
                    found_p60 = False

                    for pcode in tmp:

                        q = data[pcode]
                        try:
                            qty = int(q)
                            total_qty += qty

                            if 'C' not in pcode:
                                total_p100 += qty
                            else:
                                total_p200 += qty

                        except:
                            qty = 0

                        order_lines[pcode] = qty

                        if qty != 0:
                            mod_75 = qty % 75
                            mod_75_less = (qty-60) % 75

                            if not (mod_75 == 0 or mod_75_less ==0):
                                errors.append("Invalid qty %s for %s" % (qty, pcode))
                                error_count += 1

                            elif mod_75_less == 0 and not found_p60:
                                found_p60 = True

                            elif mod_75_less == 0 and found_p60:
                                errors.append("Invalid qty %s for %s" % (qty, pcode))
                                error_count += 1


                    if not (total_qty == 1500 or total_qty == 1560):
                        errors.append("Total not FCL")
                        error_count += 1

                    # CHECK DELIVERY DATE
                    # upload format mm/dd/yyyy
                    deliver_date = False
                    try:
                        deliver_date = datetime.strptime(data['DELIVERY DATE'], '%m/%d/%Y')
                    except:
                        errors.append("Invalid Delivery Date.")
                        error_count += 1

                    # CONSOLIDATE ERRORS
                    errors = '\n\n'.join(errors)

                    item = {
                        'line_no': line_no,
                        # 'ship_to': r[1],
                        'ship_to_id': ship_to_id,
                        'notify_id': notify_to_id,
                        'ship_line': data['SHIPPING LINE'],
                        'destination': data['DESTINATION'],
                        'shell_color': data['SHELL COLOR'],
                        'requested_delivery_date': deliver_date,
                        'order_lines': '%s' % order_lines,
                        'total_qty': total_qty,
                        'total_p100': total_p100,
                        'total_p200': total_p200,
                        'errors': errors,
                        'error_count': error_count,
                    }
                    line_items.append((0,0,item))
                    # pprint.pprint(item)

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

            # contract_id = self.env.context.get('default_contract_id',False)
            # contract = self.env['dmpi.crm.sale.contract'].browse(contract_id)
            # sap_doc_type = contract.contract_type.name
            sap_doc_type = self.env['dmpi.crm.sap.doc.type'].search([('default','=',True)],limit=1)[0].name
            tmp = rec.pack_code_tmp.split(',')

            print (sap_doc_type)
            for l in rec.upload_line_ids:
                so_lines = []
                so_line_no = 0


                def compute_price(date,customer_code,material,tag_ids=[]):

                    where_clause = ""
                    query = ""
                    if len(tag_ids) > 0:
                        
                        query = """SELECT * FROM (
                        SELECT i.id,i.material, amount,currency,uom, i.valid_from,i.valid_to,array_agg(tr.tag_id) as tags
                            from dmpi_crm_product_price_list_item  i
                            left join price_item_tag_rel tr on tr.item_id = i.id
                            group by i.id,i.material,i.valid_from,i.valid_to,amount,currency,uom
                        ) AS Q1
                        where material = '%s' and  ARRAY%s <@ tags
                        limit 1 """ % (material, tag_ids)

                    else:

                        query = """SELECT * FROM (
                        SELECT i.id,i.material, amount,currency,uom, i.valid_from,i.valid_to,array_agg(tr.tag_id) as tags
                            from dmpi_crm_product_price_list_item  i
                            left join price_item_tag_rel tr on tr.item_id = i.id
                            where material = '%s' and ('%s'::DATE between i.valid_from and i.valid_to)
                            group by i.id,i.material,i.valid_from,i.valid_to,amount,currency,uom
                        ) AS Q1

                        limit 1 """ % (material, date)


                    print (query)
                    # print("--------PRICE-------\n%s" % query)
                    self.env.cr.execute(query)
                    result = self.env.cr.dictfetchall()
                    # if result:
                    #     self.price = float(result[0]['amount'])
                    # else:
                    #     self.price = 0
                    # if result:
                    #     self.uom = result[0]['uom']
                    # else:
                    #     self.uom = 'CAS'

                    if result:
                        return result[0]['amount']
                    else:
                        return 0

                def format_so(rec,so_line_no,partner_id=0,qty=0,product_code=''):
                    name = "Product not Maintained"
                    product_id = False
                    query = """SELECT cp.id as product_id, cp.sku, cp.code, cp.partner_id, spu.condition_rate,spu.condition_currency, spu.uom from dmpi_crm_product cp
                            left join dmpi_sap_price_upload spu on spu.material = cp.sku
                            where cp.code = '%s' and partner_id = %s and cp.active is true""" % (product_code,partner_id)
                    # print (query)
                    self.env.cr.execute(query)
                    result = self.env.cr.dictfetchall()
                    if result:
                        name = result[0]['sku']
                        product_id = result[0]['product_id']


                    # get price
                    price = compute_price(rec.contract_id.po_date,rec.partner_id.customer_code,name, rec.contract_id.tag_ids.ids)
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

                for pcode in tmp:
                    qty = order_lines[pcode]
                    if qty != 0:
                        so_line_no += 10
                        line = format_so(rec,so_line_no,partner_id,qty,pcode)
                        so_lines.append((0,0,line))

                order = {
                        'contract_line_no': l.line_no,
                        'ship_to_id': l.ship_to_id.id,
                        'notify_id': l.notify_id.id,
                        'sap_doc_type': sap_doc_type,
                        'sales_org': l.ship_to_id.partner_id.sales_org or "",
                        'shell_color': l.shell_color,
                        'destination': l.destination,
                        'ship_line': l.ship_line,
                        'requested_delivery_date': l.requested_delivery_date,
                        'estimated_date': l.requested_delivery_date,
                        'plant_id': rec.contract_id.partner_id.default_plant.id,
                        'plant': rec.contract_id.partner_id.default_plant.name,
                        # 'p5': l.p5,
                        # 'p6': l.p6,
                        # 'p7': l.p7,
                        # 'p8': l.p8,
                        # 'p9': l.p9,
                        # 'p10': l.p10,
                        # 'p12': l.p12,
                        # 'p5c7': l.p5c7,
                        # 'p6c8': l.p6c8,
                        # 'p7c9': l.p7c9,
                        # 'p8c10': l.p8c10,
                        # 'p9c11': l.p9c11,
                        # 'p10c12': l.p10c12,
                        # 'p12c20': l.p12c20,
                        'order_ids': so_lines,
                    }

                # print(order)
                sale_orders.append((0,0,order))

            if rec.upload_type == 'customer':
                rec.contract_id.customer_order_ids.unlink()
                rec.contract_id.customer_order_ids = sale_orders
            if rec.upload_type == 'commercial':
                rec.contract_id.sale_order_ids.unlink()
                rec.contract_id.sale_order_ids = sale_orders



class DmpiCrmSaleContractUploadLine(models.TransientModel):
    _name = 'dmpi.crm.sale.contract.upload.line'


    # @api.depends('p5','p6','p7','p8','p9','p10','p12','p5c7','p6c8','p7c9','p8c10','p9c11','p10c12','p12c20')
    # def _get_totals(self):
    #     for rec in self:
    #         rec.total_crown = rec.p5+rec.p6+rec.p7+rec.p8+rec.p9+rec.p10+rec.p12
    #         rec.total_crownless = rec.p5c7+rec.p6c8+rec.p7c9+rec.p8c10+rec.p9c11+rec.p10c12+rec.p12c20
    #         rec.total_qty = rec.total_crown + rec.total_crownless

    upload_id       = fields.Many2one("dmpi.crm.sale.contract.upload","Upload Template")
    line_no         = fields.Integer("Line No.")
    ship_to         = fields.Char(string="Ship to")
    ship_to_id      = fields.Many2one("dmpi.crm.ship.to","Ship to Party")
    notify_id       = fields.Many2one("dmpi.crm.ship.to","Notify Party")
    # p5              = fields.Integer(string="P5", sum="TOTAL")
    # p6              = fields.Integer(string="P6", sum="TOTAL")
    # p7              = fields.Integer(string="P7", sum="TOTAL")
    # p8              = fields.Integer(string="P8", sum="TOTAL")
    # p9              = fields.Integer(string="P9", sum="TOTAL")
    # p10             = fields.Integer(string="P10", sum="TOTAL")
    # p12             = fields.Integer(string="P12", sum="TOTAL")
    # p5c7            = fields.Integer(string="P5C7", sum="TOTAL")
    # p6c8            = fields.Integer(string="P6C8", sum="TOTAL")
    # p7c9            = fields.Integer(string="P7C9", sum="TOTAL")
    # p8c10           = fields.Integer(string="P8C10", sum="TOTAL")
    # p9c11           = fields.Integer(string="P9C11", sum="TOTAL")
    # p10c12          = fields.Integer(string="P10C12", sum="TOTAL")
    # p12c20          = fields.Integer(string="P12C20", sum="TOTAL")
    order_lines      = fields.Text(string='Order Lines')
    total_p100      = fields.Integer(string="With Crown", sum="TOTAL")
    total_p200      = fields.Integer(string="Crownless", sum="TOTAL")
    total_qty       = fields.Integer(string="Total", sum="TOTAL")
    ship_line       = fields.Char("Ship Line")
    destination     = fields.Char("Destination")
    shell_color     = fields.Char("Shell Color")
    errors          = fields.Text("Errors")
    error_count     = fields.Integer("Error Count")
    requested_delivery_date = fields.Date('Req. Date')


