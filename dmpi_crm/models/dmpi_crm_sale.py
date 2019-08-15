# -*- coding: utf-8 -*-

from odoo import _
from odoo.osv import expression
from odoo import models, api, fields
from odoo.exceptions import  Warning, RedirectWarning, ValidationError, AccessError, UserError
from datetime import datetime, timedelta
from dateutil.parser import parse
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from textwrap import TextWrapper

from fabric.api import *
import csv
import sys
import math
import io

import base64
from tempfile import TemporaryFile
import tempfile
import re
import json


#@parallel
def file_send(localpath,remotepath):
    with settings(warn_only=True):
        put(localpath,remotepath,use_sudo=True)

#@parallel
def file_get(remotepath, localpath):
    get(remotepath,localpath)

#@parallel
def transfer_files(remotepath, localpath):
    remote = "%s/outbound" % remotepath
    get(remote,localpath)
    mv = "mv %s/outbound/* %s/transferred" % (remotepath,remotepath)
    sudo(mv)

def round_qty(cases_pa,qty):
    if cases_pa < 1:
        cases_pa = 1

    q = math.floor(qty/cases_pa)
    if q < 1:
        q = 1
    rounded_qty = cases_pa * q
    return rounded_qty


def colnum_string(n):
    div=n
    string=""
    temp=0
    while div>0:
        module=(div-1)%26
        string=chr(65+module)+string
        div=int((div-module)/26)
    return string

def read_data(data):
    if data:
        fileobj = TemporaryFile('w+b')
        fileobj.write(base64.b64decode(data)) 
        fileobj.seek(0)

        rows = csv.reader(fileobj, quotechar='"', delimiter='\t')
        return rows


CONTRACT_STATE = [
        ('draft','Draft'),
        ('submitted','Submitted'),
        ('confirm','For Confirmation'),
        ('confirmed','Confirmed'),
        ('soa','Statement of Account'),
        ('approved','Approved'),
        ('processing','Processing'),
        ('processed','Processed'),
        ('enroute','Enroute'),
        ('received','Received'),
        ('cancel','Cancelled')]

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

class DmpiCrmSaleContract(models.Model):
    _name = 'dmpi.crm.sale.contract'
    _description = "Sale Contract"
    _inherit = ['mail.thread']
    _order = 'po_date desc, name desc'


    def _get_contract_type(self):
        result = self.env['dmpi.crm.contract.type'].search([])
        res = [(r.name,r.description) for r in result]
        return res

    def _get_contract_type_default(self):
        result = self.env['dmpi.crm.contract.type'].search([('default','=',True)], limit=1)[0]
        return result.name


    @api.depends('name','sap_cn_no')
    def _get_po_display_number(self):
        if self.name:
            sap_cn_no = ""
            if self.sap_cn_no:
                sap_cn_no = "/%s" % self.sap_cn_no
            self.po_display_number = "%s%s" % (self.name, sap_cn_no)

    ## to deprecate (move to submit PO)
    @api.one
    @api.depends('customer_ref','week_no')
    def _get_customer_ref_to_sap(self):
        ref = []
        if self.week_no:
            ref.append("W%s" % self.week_no)
        if self.customer_ref:
            ref.append(self.customer_ref)
        else:
            ref.append(self.name)
        self.customer_ref_to_sap = '-'.join(ref)

    @api.one
    @api.depends('sale_order_ids.order_ids')
    def _compute_totals(self):
        self.total_sales = sum ( self.sale_order_ids.mapped('order_ids').mapped('total') )


    @api.depends('credit_limit','credit_exposure','total_sales', 'open_so')
    def _compute_credit(self):
        for rec in self:
            rec.remaining_credit = rec.credit_limit - rec.credit_exposure
            rec.credit_after_sale = rec.credit_limit - rec.credit_exposure - rec.total_sales - rec.open_so


    name = fields.Char("Contract Number", default="Draft", copy=False)
    sap_cn_no = fields.Char("SAP Contract Number", copy=False)
    po_display_number = fields.Char("Display Name", compute="_get_po_display_number")
    customer_ref = fields.Char("Customer Reference", copy=False)
    customer_ref_to_sap = fields.Char("Customer Reference to SAP", compute="_get_customer_ref_to_sap") ## to deprecate
    partner_id = fields.Many2one('dmpi.crm.partner',"Customer", domain=[('function_ids.code','=','SLD')])
    sold_via_id = fields.Many2one('dmpi.crm.partner',"Sold Via")
    contract_type = fields.Selection(_get_contract_type,"Contract Type", default=_get_contract_type_default)
    po_date = fields.Date("PO Date", default=fields.Date.context_today)
    valid_from = fields.Date("Valid From", default=fields.Date.context_today)
    valid_to = fields.Date("Valid To")
    week_no = fields.Integer("Week No")
    tag_ids = fields.Many2many('dmpi.crm.product.price.tag', 'sale_contract_tag_rel', 'contract_id', 'tag_id', string='Price Tags', copy=True)

    credit_limit = fields.Float("Credit Limit")
    credit_exposure = fields.Float("Credit Exposure")
    remaining_credit = fields.Float("Remaining Credit", compute='_compute_credit', store=True)
    open_so = fields.Float("Open SO")
    total_sales = fields.Float("Total Sales", compute='_compute_totals', store=True)
    credit_after_sale = fields.Float("Credit After Sale", compute='_compute_credit', store=True)
    ar_status = fields.Float("AR Status")

    state = fields.Selection(CONTRACT_STATE, string="Status", default='draft', track_visibility='onchange')
    state_disp = fields.Selection(CONTRACT_STATE, related='state', string="Status Display", default='draft')

    #ONE2MANY RELATIONSHIPTS
    sale_order_ids = fields.One2many('dmpi.crm.sale.order','contract_id','Sale Orders', copy=True)
    customer_order_ids = fields.One2many('customer.crm.sale.order','contract_id','Customer Orders', copy=True)
    dr_ids = fields.One2many('dmpi.crm.dr','contract_id','Delivery')
    shp_ids = fields.One2many('dmpi.crm.shp','contract_id','Shipments')
    invoice_ids = fields.One2many('dmpi.crm.invoice','contract_id','Invoices')

    #LOGS
    sent_to_sap = fields.Boolean("Sent to SAP")
    sent_to_sap_time = fields.Datetime("Sent to SAP Time")
    route_to_finance = fields.Boolean("Route to Finance")

    # ERRORS
    error_count = fields.Integer("Error Count")
    errors = fields.Text("Errors")
    errors_disp = fields.Text("Errors Display", related='errors')

    # BINARY FILES
    customer_orders_csv = fields.Binary('Customer Orders CSV')
    sale_orders_csv = fields.Binary('Sale Orders CSV')


    @api.multi
    def upload_wizard(self):
        self.ensure_one()
        res = self.env['ir.actions.act_window'].for_xml_id('dmpi_crm', 'action_dmpi_crm_sale_contract_upload')
        res['context'] = {'default_contract_id':self.id,}
        return res


    @api.multi
    def recompute_order_lines(self):
        for rec in self:
            for c in rec.customer_order_ids:
                for l in c.order_ids:
                    l.recompute_price()
            for s in rec.sale_order_ids:
                for l in s.order_ids:
                    l.recompute_price()


    @api.multi
    def action_cancel_po(self):
        for rec in self:
            for so in rec.sale_order_ids:
                so.state = 'cancelled'



    @api.onchange('partner_id')
    def on_change_partner_id(self):

        # if len(self.customer_order_ids) or len(self.sale_order_ids):
        #     raise UserError(_('Cannot change Customer if you have existing Orders. Remove first or try creating new contract.'))

        if self.partner_id:
            # COMPUTE CREDIT
            credit = self.env['dmpi.crm.partner.credit.limit'].search([('customer_code','=',self.partner_id.customer_code)], order="write_date desc, id desc", limit=1)
            self.credit_limit = credit.credit_limit
            self.credit_exposure = credit.credit_exposure


            # COMPUTE AR
            query = """SELECT sum(ar.amt_in_loc_cur *
                       case
                           when (ar.base_line_date::date + ar.cash_disc_days::INT + 14) <= NOW()::date then 1
                           else 0 end) as ar 
                       from dmpi_crm_partner_ar ar
                       where ar.acct_type = 'D' and ltrim(ar.customer_no,'0') = '%s' """ % self.partner_id.customer_code

            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()
            if result:
                self.ar_status = result[0]['ar']
            else:
                self.ar_status = 0


            # COMPUTE OPEN SO (SO WITHOUT INVOICES)
            query = """SELECT sum(sol.price * sol.qty) as openso
                        FROM dmpi_crm_sale_order_line sol
                        left join dmpi_crm_sale_order so on so.id = sol.order_id
                        left join dmpi_crm_invoice inv on inv.sap_so_no = so.sap_so_no
                        left join dmpi_crm_sale_contract sc on sc.id = so.contract_id
                        where sc.partner_id = %s and so.state in ('confirmed','process','processed','done') and inv.id is null
            """ % self.partner_id.id

            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()
            if result:
                self.open_so = result[0]['openso'] 



    @api.onchange('ar_status','credit_after_sale')
    def on_change_ar_status(self):
        error_count = 0
        errors = []
        if self.ar_status  > 0:
            error_count += 1
            errors.append("CUSTOMER HAS EXISTING AR: Will be routed to Finance for Approval")
            self.route_to_finance = True

        if self.credit_after_sale  < 0:
            error_count += 1
            errors.append("CREDIT LIMIT EXCEEDED: Please reduce purchases accordingly")

        if error_count > 0:
            self.error_count = error_count
            self.errors = '\n'.join(x for x in errors)

        else:
            self.error_count = 0
            self.errors = ""
            self.route_to_finance = False



    @api.onchange('po_date','partner_id')
    def on_change_po_date(self):
        if self.po_date and self.partner_id:
            self.valid_from = self.po_date
            validity = self.partner_id.default_validity

            if validity < 1:
                validity = 7

            self.valid_to =  datetime.strptime(self.po_date, DEFAULT_SERVER_DATE_FORMAT) + timedelta(days=validity)


    @api.multi
    def action_submit_contract(self):
        for rec in self:
            #Finalize Contract Line Numbers
            contract_line_no = 0
            sale_orders = []
            week_no = rec.week_no
            for l in rec.customer_order_ids:
                contract_line_no += 10
                l.contract_line_no = contract_line_no

                so_lines = []
                for sl in l.order_ids:

                    vals = { 
                                'name':sl.name, 
                                'so_line_no':sl.so_line_no, 
                                'product_code': sl.product_code, 
                                'product_id': sl.product_id.id,
                                'pricing_date': sl.pricing_date,
                                'price': sl.price, 
                                'uom': 'CAS', 
                                'qty': sl.qty
                            }

                    so_lines.append((0,0,vals))

                order = {
                        'contract_line_no':l.contract_line_no,
                        'ship_to_id': l.ship_to_id.id,
                        'notify_id': l.notify_id.id,
                        'sap_doc_type': l.sap_doc_type,
                        'sales_org': l.sales_org,
                        'shell_color': l.shell_color,
                        'ship_line': l.ship_line,
                        'destination': l.destination,
                        'requested_delivery_date': l.requested_delivery_date,
                        'estimated_date': l.estimated_date,
                        'plant_id': l.plant_id.id,
                        'plant': l.plant,
                        'week_no': week_no,
                        'order_ids': so_lines,
                    }

                if l.tag_ids:
                    tags = [(4,t.id,) for t in l.tag_ids]
                    order['tag_ids'] = tags

                sale_orders.append((0,0,order))

            print (sale_orders)
            rec.sale_order_ids.unlink()
            rec.sale_order_ids = sale_orders

            
            if rec.name == 'Draft' or rec.name == '':
                contract_seq  = self.env['ir.sequence'].next_by_code('dmpi.crm.sale.contract')
                rec.write({'name':contract_seq})

            rec.write({'state':'submitted'})

    @api.multi
    def action_request_confirmation(self):
        for rec in self:

            # send mail
            email_to = "<%s>" % rec.partner_id.email
            
            template = self.env.ref('dmpi_crm.commercial_send_for_confirmation')
            template['email_to'] = email_to
            template.send_mail(rec.id)

            rec.write({'state':'confirm'})


    @api.multi
    def action_confirm_contract(self):
        for rec in self:
            if not rec.week_no or not rec.customer_ref:
                raise UserError(_("No Customer Ref or Week Number!"))

            for so in rec.sale_order_ids:
                if so.error > 0:
                    raise UserError(_("Some items in sale orders have no price computation!"))


            for so in rec.sale_order_ids:
                so.write({'state':'confirmed', 'week_no': rec.week_no})
            rec.write({'state':'confirmed'})


    def get_base_url(self):
    	action = self.env.ref('dmpi_crm.action_dmpi_crm_sale_contract_finance')
    	url = "%s/web#model=dmpi.crm.sale.contract&action=%s" % (self.env['ir.config_parameter'].sudo().get_param('web.base.url'),action.id)
    	return url

    @api.multi
    def action_approve_contract(self):
        for rec in self:
            rec.on_change_partner_id()
            if rec.ar_status > 0:
                contract_line_no = 0
                for so in rec.sale_order_ids:

                    if rec.week_no:
                        so.week_no = rec.week_no
                    for sol in so.order_ids:
                        contract_line_no += 10
                        sol.write({'contract_line_no':contract_line_no})

                    if so.name == 'Draft' or '':
                        seq  = self.env['ir.sequence'].next_by_code('dmpi.crm.sale.order')
                        so.write({'name': seq})

                    sol_line_no = 0
                    for sol in so.order_ids:
                        sol_line_no += 10
                        sol.write({'so_line_no':sol_line_no})

                rec.write({'state':'soa'})
                #TODO Trigger Auto Email to Finance Users

                template = self.env.ref('dmpi_crm.notify_finance_release_contract_with_ar')
                user_ids = self.env['dmpi.crm.email.notification.subscriber'].search([('name','=',template.id)])
                email_to = ','.join(["<%s>" % x.user_id.login for x in user_ids])
                template['email_to'] = email_to

                print (email_to,self.get_base_url)
                template.send_mail(rec.id)



            else:
                contract_line_no = 0
                for so in rec.sale_order_ids:

                    if rec.week_no:
                        so.week_no = rec.week_no
                    for sol in so.order_ids:
                        contract_line_no += 10
                        sol.write({'contract_line_no':contract_line_no})

                    if so.name == 'Draft' or '':
                        seq  = self.env['ir.sequence'].next_by_code('dmpi.crm.sale.order')
                        so.write({'name': seq})

                    sol_line_no = 0
                    for sol in so.order_ids:
                        sol_line_no += 10
                        sol.write({'so_line_no':sol_line_no})

                rec.write({'state':'approved'})


    @api.multi
    def action_release_contract(self):
        for rec in self:
            rec.write({'state':'approved'})


    @api.multi
    def action_send_contract_to_sap(self):
        for rec in self:

            filename = 'ODOO_PO_%s_%s.csv' % (rec.name,datetime.now().strftime("%Y%m%d_%H%M%S"))
            path = '/tmp/%s' % filename

            lines = []
            for so in rec.sale_order_ids:
                for sol in so.order_ids:

                    ref_po_no = rec.customer_ref_to_sap

                    po_date = datetime.strptime(rec.po_date, '%Y-%m-%d')
                    po_date = po_date.strftime('%Y%m%d')

                    if not sol.pricing_date:
                        raise UserError(_("Some sales orders have no configured PRICING DATE, please see SO and Pricelist and ensure that the all data are in place"))
                    
                    pricing_date = datetime.strptime(sol.pricing_date, '%Y-%m-%d')
                    pricing_date = pricing_date.strftime('%Y%m%d')

                    valid_from = datetime.strptime(rec.valid_from, '%Y-%m-%d')
                    valid_from = valid_from.strftime('%Y%m%d')

                    valid_to = datetime.strptime(rec.valid_to, '%Y-%m-%d')
                    valid_to =   valid_to.strftime('%Y%m%d')

                    tags = rec.tag_ids



                    line = {
                        'odoo_po_no' : rec.name,
                        'sap_doc_type' : rec.contract_type,
                        'sales_org' : rec.partner_id.sales_org,
                        'dist_channel' : rec.partner_id.dist_channel,
                        'division' : rec.partner_id.division,
                        'sold_to' : rec.partner_id.customer_code,
                        'ship_to' : so.ship_to_id.customer_code,
                        'ref_po_no' : ref_po_no,
                        'po_date' : po_date,
                        'pricing_date' : pricing_date,
                        'valid_from' : valid_from,
                        'valid_to' : valid_to,
                        'ship_to_dest' : so.ship_to_id.customer_code,
                        'po_line_no' : sol.contract_line_no,
                        'material' : sol.product_id.sku,
                        'qty' : int(sol.qty),
                        'uom' : 'CAS',
                    }

                    #SBFTI SCENARIO
                    # 1.       If key-user uses the customer sold-to as 13046 and any related ship-to, kindly send in the csv file the sold to and ship-to as 14067.
                    # 2.       In this scenario sale organization is 1050 distribution channel is 35 and division is 01.
                    # 3.       The value of the “Final Ship-to” column which is “Your Reference” field i.e. VBKD-IHREZ in SAP should be the related ship-to chosen by the key-user from point 1 above.
                    # 4.       The sales order document type sent in the csv file should be ZKM3 instead of ZXSO when this is the scenario (i.e. sold-to customer is 13046).  

                    if rec.sold_via_id:
                        line['sold_to'] = rec.sold_via_id.customer_code
                        line['ship_to'] = rec.sold_via_id.customer_code
                        line['sales_org'] = rec.sold_via_id.sales_org
                        line['ship_to_dest'] = rec.sold_via_id.customer_code
                        line['dist_channel'] = rec.sold_via_id.dist_channel 
                        line['division'] = rec.sold_via_id.division
                        line['sold_to'] = rec.sold_via_id.customer_code
                    

                    lines.append(line)


            with open(path, 'w') as f:
                writer = csv.writer(f, delimiter='\t')
                for l in lines:
                    writer.writerow([
                            l['odoo_po_no'],
                            l['sap_doc_type'],
                            l['sales_org'],
                            l['dist_channel'],
                            l['division'],
                            l['sold_to'],
                            l['ship_to'],
                            l['ref_po_no'],
                            l['po_date'],
                            l['pricing_date'],
                            l['valid_from'],
                            l['valid_to'],
                            l['ship_to_dest'],
                            l['po_line_no'],
                            l['material'],
                            l['qty'],
                            l['uom']
                        ])


            #TRANSFER TO REMOTE SERVER
            h = self.env['dmpi.crm.config'].search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass

            localpath = path
            path = '%s/%s' % (h.inbound_k,filename)
            remotepath = path

            execute(file_send,localpath,remotepath)
            rec.sent_to_sap = True

            # if rec.ar_status > 0 or rec.credit_after_sale < 0:
            #     rec.state = 'soa'
            # else:
            #     rec.state = 'submitted'            

            rec.write({'state':'processing'})



    # def modify_order_lines(self, context, order_lines=False):
    #     '''
    #     This function modify the order lines of an SO. EDIT if line is existing, CREATE if line 
    #     is not exiting, and DELETE if lines is not found.

    #     :param order_lines: array of dict values for each order_line
    #         {
    #             'name':name,
    #             'so_line_no':so_line_no,
    #             'product_code': product_code, 
    #             'product_id': product_id,
    #             'uom': 'CAS',
    #             'qty': qty,
    #             'price': price,
    #         }
    #     :return: boolean
    #     '''
        
    @api.multi
    def download_order_wizard(self):
        self.ensure_one()
        res = self.env['ir.actions.act_window'].for_xml_id('dmpi_crm', 'action_dmpi_crm_download_order_wizard')
        res['context'] = {'default_contract_id':self.id,}
        return res

    @api.multi
    def action_multi_order_tag(self):
        self.ensure_one()
        res = self.env['ir.actions.act_window'].for_xml_id('dmpi_crm', 'action_dmpi_crm_multi_tag')
        res['context'] = {'default_contract_id':self.id,}
        return res


class DmpiCrmSaleOrder(models.Model):
    _name = 'dmpi.crm.sale.order'
    _inherit = ['mail.thread']


    def submit_so_file(self,rec):
        if rec.contract_id.sap_cn_no != '' and rec.name != 'Draft' and rec.state != 'hold':
            print ("Contract Not Draft")
            lines = []
            cid = rec.contract_id
            line_no = 0
            for sol in rec.order_ids:
                line_no += 10
                sol.so_line_no = line_no
                ref_po_no = rec.destination+'-'+cid.customer_ref_to_sap if rec.destination else cid.customer_ref_to_sap

                po_date = datetime.strptime(cid.po_date, '%Y-%m-%d')
                po_date = po_date.strftime('%Y%m%d')

                pricing_date = datetime.strptime(sol.pricing_date, '%Y-%m-%d')
                pricing_date = pricing_date.strftime('%Y%m%d')

                valid_from = datetime.strptime(cid.valid_from, '%Y-%m-%d')
                valid_from = valid_from.strftime('%Y%m%d')

                valid_to = datetime.strptime(cid.valid_to, '%Y-%m-%d')
                valid_to =   valid_to.strftime('%Y%m%d')


                line = {
                    'odoo_po_no' : cid.name,
                    'sap_cn_no' : cid.sap_cn_no,
                    'odoo_so_no' : rec.name,
                    'sap_doc_type' : rec.sap_doc_type,  
                    'sales_org' : rec.sales_org,
                    'dist_channel' : cid.partner_id.dist_channel,
                    'division' : cid.partner_id.division,  
                    'sold_to' : cid.partner_id.customer_code,
                    'ship_to' : rec.ship_to_id.customer_code,
                    'ref_po_no' : ref_po_no,  
                    'po_date' : po_date,
                    # 'rdd' : valid_to, #TODO: CHANGE TO CORRECT SO RDD
                    'rdd' : rec.create_date,
                    'po_line_no' : sol.contract_line_no,
                    'so_line_no' : sol.so_line_no,  
                    'material' : sol.product_id.sku,    
                    'qty' : int(sol.qty),
                    'uom' : 'CAS', 
                    'plant' : rec.plant,
                    'reject_reason' : '',
                    'so_alt_item' : '',
                    'usage' : '',
                    'original_ship_to' : '',
                    'pricing_date' : pricing_date,
                }

                if cid.sold_via_id:
                    line['sold_to'] = cid.sold_via_id.customer_code
                    line['ship_to'] = cid.sold_via_id.customer_code
                    line['sap_doc_type'] = 'ZKM3'
                    line['original_ship_to'] = rec.ship_to_id.customer_code
                    line['dist_channel'] = cid.sold_via_id.dist_channel
                    line['division'] = cid.sold_via_id.division
                    line['sales_org'] = cid.sold_via_id.sales_org
                
                lines.append(line)
            # print (lines)

            filename = 'ODOO_SO_%s_%s.csv' % (rec.name,datetime.now().strftime("%Y%m%d_%H%M%S"))
            path = '/tmp/%s' % filename

            with open(path, 'w') as f:
                writer = csv.writer(f, delimiter='\t')
                for l in lines:
                    if 'original_ship_to' in l: 
                        writer.writerow([ l['odoo_po_no'],l['sap_cn_no'],
                                    l['odoo_so_no'],l['sap_doc_type'],
                                    l['sales_org'],l['dist_channel'],
                                    l['division'],l['sold_to'],
                                    l['ship_to'],l['ref_po_no'],
                                    l['po_date'],l['rdd'],
                                    l['po_line_no'],l['so_line_no'],
                                    l['material'],l['qty'],
                                    l['uom'],l['plant'],
                                    l['original_ship_to'],l['pricing_date']
                                ])
                    else:
                        writer.writerow([ l['odoo_po_no'],l['sap_cn_no'],
                                    l['odoo_so_no'],l['sap_doc_type'],
                                    l['sales_org'],l['dist_channel'],
                                    l['division'],l['sold_to'],
                                    l['ship_to'],l['ref_po_no'],
                                    l['po_date'],l['rdd'],
                                    l['po_line_no'],l['so_line_no'],
                                    l['material'],l['qty'],
                                    l['uom'],l['plant'],
                                    '',l['pricing_date']
                                ])

                if rec.instructions:
                    writer.writerow(['INSTRUCTIONS'])
                    tw = TextWrapper()
                    tw.width = 30
                    for i in tw.wrap(rec.instructions):
                        writer.writerow(['%s' % i])

            #TRANSFER TO REMOTE SERVER
            h = self.env['dmpi.crm.config'].search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass

            localpath = path

            path = '%s/%s' % (h.inbound_so,filename)
            remotepath = path

            execute(file_send,localpath,remotepath)
            rec.write({'state':'process'})
            return True
        else:
            #TODO Create real Warning
            return False


    @api.multi
    def action_submit_so(self):
        for rec in self:
            submitted = rec.submit_so_file(rec)
            if submitted:
                msg = "SUCCESS: <br/>%s Retriggered the creation of SO: %s" % (self.env.user.partner_id.name,rec.name)
                rec.message_post(msg)
                raise Warning("SO was Successfully Created")
            else:
                msg = "FAIL: <br/>USER %s Retriggered the creation of SO but the SO was NOT Created since state is in Draft or on Hold." % self.env.user.partner_id.name
                rec.message_post(msg)
                raise Warning("State is in Draft or on Hold. The SO was NOT Created")


    @api.onchange('ship_to_id')
    def on_change_ship_to(self):
        self.sales_org = self.contract_id.partner_id.sales_org
        self.plant_id = self.contract_id.partner_id.default_plant

        tag_ids = self.contract_id.tag_ids.ids
        self.tag_ids = [[6,0,tag_ids]]



    @api.multi
    def action_hold_so(self):
        for rec in self:
            rec.state = 'hold'
            rec.write({'state':'hold'})
            
        
    @api.multi
    def action_release_so(self):
        for rec in self:
            rec.state = 'confirmed'
            rec.write({'state':'confirmed'})
        
    def _get_doc_types(self):
        res = [(r.name,r.description) for r in self.env['dmpi.crm.sap.doc.type'].search([])]
        return res

    def _get_default_doc_types(self):
        res = self.env['dmpi.crm.sap.doc.type'].search([('default','=',True)])[0].name
        return res

    @api.one
    @api.depends('name','sap_so_no')
    def _get_name_disp(self):
        name = []
        if self.name:
            name.append(self.name)
        if self.sap_so_no:
            name.append(self.sap_so_no)

        self.name_disp = '/'.join(name)


    @api.multi
    def toggle_valid(self):
        for rec in self:
            rec.write({'valid': not rec.valid})
            return True

    def _check_if_fcl(self, qty_list, total_qty):
        # get FCL configs
        query = """SELECT distinct fc.cases, fc.pallet
                    from dmpi_crm_fcl_config fc
                    order by fc.cases desc """
        self.env.cr.execute(query)
        res = self.env.cr.dictfetchall()
        fcl_config = {}

        for r in res:
            fcl_config[r['cases']] = eval(r['pallet'])

        if total_qty not in fcl_config.keys():
            s = 'Total orders is not Full Container Load'
            return s
        else:

            # check each order lines
            pallet_conf = []
            cases_conf = []
            for p in fcl_config[total_qty]:
                pallet_conf.append({
                        'max_pallets': p[0],
                        'cases': p[1],
                        'count': 0,
                })

                cases_conf.append(p[1])

            for p in pallet_conf:
                cases = p['cases']

                # loop over qtys
                for i in range(len(qty_list)):
                    qty = qty_list[i]
                    m = qty / cases
                    r = qty % cases

                    if (m).is_integer():
                        p['count'] += m
                    else:
                        p['count'] += math.floor(qty / cases)

                    qty_list[i] = r

                    # check if beyond max pallets
                    if p['count'] > p['max_pallets']:
                        s = 'Invalid quantity combinations'
                        return s
                    # print (qty, cases, m, p['count'], qty_list,)

            if any(qty_list):
                s = 'Invalid quantity combinations'
                return s

            return False

    @api.multi
    @api.depends('order_ids')
    def _get_error_msg(self):
        for so in self:
            # error for no price
            error = 0
            error_msg = []
            msg = ''
            total_qty = 0


            for l in so.order_ids:
                # no price error
                if l.price == 0 and l.product_id:
                    error += 1
                    s = 'No Price set for %s (%s)' % (l.product_id.code, l.product_id.sku)
                    error_msg.append(s)

                if not l.pricing_date:
                    error += 1
                    s = 'No Pricing Date set for %s %s (%s)' % (so.partner_id.name,l.product_id.code, l.product_id.sku)
                    error_msg.append(s)


                # lcl total qty
                total_qty += l.qty

            # CHECK IF FCL
            # qty_list = [l.qty for l in so.order_ids]
            # s = self._check_if_fcl(qty_list, total_qty)
            # if s:
            #     error_msg.append(s)



            msg = '\n'.join(error_msg)
            so.error = error
            so.error_msg = msg


    def _price_list_remarks(self):
        res = [(r.name,r.description) for r in self.env['dmpi.crm.sap.doc.type'].search([])]
        return res

    @api.one
    @api.depends('plant_id')
    def _get_plant_name(self):
        self.plant = self.plant_id.name



    name_disp = fields.Char("Display No.", compute='_get_name_disp')
    name = fields.Char("CRM SO No.", default="Draft", copy=False)
    plant = fields.Char("Plant", compute='_get_plant_name')
    plant_id = fields.Many2one('dmpi.crm.plant')
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Contract ID", ondelete="cascade")
    customer_ref = fields.Char('Customer Reerence', related='contract_id.customer_ref', store=True)
    contract_line_no = fields.Integer("Contract Line No.")
    so_no = fields.Integer("SO Num")
    sap_so_no = fields.Char("SAP SO no.")
    sap_so_date = fields.Date("SAP SO Date")
    sap_doc_type = fields.Selection(_get_doc_types,"Doc Type",default=_get_default_doc_types)
    order_ids = fields.One2many('dmpi.crm.sale.order.line','order_id','Order IDs', copy=True)
    valid = fields.Boolean("Valid Order", default=True)
    valid_disp = fields.Boolean("Valid Order", related='valid')
    error = fields.Integer('Error Count', compute="_get_error_msg")
    error_msg = fields.Text('Error Message', compute="_get_error_msg")
    price_list = fields.Selection(_price_list_remarks)
    destination = fields.Char('Destination')
    instructions = fields.Text('Instructions')

    @api.multi
    @api.depends('partner_id')
    def _get_allowed_ids(self):
        for rec in self:
            rec.allowed_ship_to = rec.partner_id.ship_to_ids
            rec.allowed_products = rec.partner_id.product_ids


    allowed_ship_to = fields.One2many('dmpi.crm.partner', compute="_get_allowed_ids")
    allowed_products = fields.One2many('dmpi.crm.product', compute="_get_allowed_ids")

    contract_tag_ids = fields.Many2many('dmpi.crm.product.price.tag',"Contract Price Tags", related='contract_id.tag_ids')
    tag_ids = fields.Many2many('dmpi.crm.product.price.tag', 'sale_order_tag_rel', 'order_id', 'tag_id', string='Sale Price Tags', copy=True)


    @api.multi
    @api.onchange('tag_ids')
    def onchange_tag_ids(self):
        for rec in self:
            for l in rec.order_ids:
                l.onchange_product_id()


    def _get_default_pack_codes(self):
        pack_codes = self.env['dmpi.crm.product.code'].sudo().search([('active','=',True)])
        tmp = []
        for pc in pack_codes:
            tmp.append(pc.name)

        pack_code_tmp = ','.join(tmp)
        return pack_code_tmp

    pack_code_tmp = fields.Text(string='Pack Code Tmp', help='Active Pack Codes Upon Create', default=_get_default_pack_codes)
    total_p100 = fields.Integer(string="With Crown", compute='get_product_qty')
    total_p200 = fields.Integer(string="Crownless", compute='get_product_qty')

    @api.multi
    @api.depends('order_ids','pack_code_tmp')
    def get_product_qty(self):
        for rec in self:

            data = {}
            total_amount = 0
            total_qty = 0
            total_p100 = 0
            total_p200 = 0

            # get totals per pack code
            for l in rec.order_ids:

                product = l.product_id
                pcode = product and product.code_id.name
                if pcode:
                    if pcode not in data:
                        data[pcode] = 0

                    data[pcode] += l.qty
                    total_p100 += l.qty if 'C' not in pcode else 0
                    total_p200 += l.qty if 'C' in pcode else 0
                    total_amount += l.total
                    total_qty += l.qty

            # change to summary formatting view
            headers = []
            rows = []
            tmp = rec.pack_code_tmp
            tmp = tmp.split(',')
            
            for t in tmp:
                qty = data[t] if t in data else 0
                headers.append("""<th data-original-title="" title="" style="text-align: center; color:#FFF; background-color: #78717e;" >%s</th>""" % t)
                rows.append("""<td class="o_data_cell o_list_number">%s</td>""" % qty)

            rec.notes = """
                <h3>SUMMARY</h3>
                <table class="o_list_view table table-condensed table-striped o_list_view_ungrouped">
                    <thead><tr> %s </tr></thead>
                    <tbody> <tr class="o_data_row"> %s </tr> </tbody>
                </table>
            """ %(''.join(headers),''.join(rows))

            # compute totals
            rec.total_p100 = total_p100
            rec.total_p200 = total_p200
            rec.total_amount = total_amount
            rec.total_qty = total_qty

    partner_id = fields.Many2one('dmpi.crm.partner',"Customer", related='contract_id.partner_id', store=True)
    ship_to_id = fields.Many2one('dmpi.crm.partner', 'Ship To')
    notify_id = fields.Many2one("dmpi.crm.partner","Notify Party")
    mailing_id = fields.Many2one("dmpi.crm.partner","Mailing Address")
    sales_org = fields.Char("Sales Org")
    dest_country_id = fields.Many2one('dmpi.crm.country', 'Destination')
    order_date = fields.Date("Order Date")
    estimated_date = fields.Date("Estimated Date")
    shell_color = fields.Char("Shell Color")
    ship_line = fields.Char("Ship Line")
    requested_delivery_date = fields.Date("Req. Date")
    notes = fields.Text("Notes/Remarks", compute='get_product_qty')

    total_qty = fields.Float('Qty Total', compute='get_product_qty', store=True)
    total_amount = fields.Float('Amount Total', compute='get_product_qty', store=True)

    week_no = fields.Integer("Week No", related='contract_id.week_no', store=True, group_operator="avg")
    state = fields.Selection([('draft','Draft'),('confirmed','Confirmed'),('hold','Hold'),('process','For Processing'),('processed','Processed'),('cancelled','Cancelled')], default="draft", string="Status")
    po_state = fields.Selection(CONTRACT_STATE,string="Status", related='contract_id.state', store=True)
    found_p60 = fields.Integer('Found Pallet 60 order', compute="_compute_found_p60")


    @api.multi
    def action_go_record(self):
        for rec in self:
            return {
                'name': 'Record',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'dmpi.crm.sale.order',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': rec.id,
            }

    @api.multi
    def action_set_confirm(self):
        for rec in self:
            rec.state = 'confirmed'

    @api.multi
    def action_set_hold(self):
        for rec in self:
            rec.state = 'hold'

    @api.multi
    def action_set_cancel(self):
        for rec in self:
            rec.state = 'cancelled'    

    @api.multi
    @api.depends('order_ids')
    def _compute_found_p60(self):
        for so in self:
            count = 0
            for l in so.order_ids:
                if l.found_p60:
                    count += 1
            so.found_p60 = count

    @api.multi
    def convert_to_dict(self):
        self.ensure_one()
        vals = {
            'NO': self.contract_line_no or '',
            'SHIP TO': self.ship_to_id.customer_code or '',
            'NOTIFY PARTY': self.notify_id.customer_code or '',
            'DESTINATION': self.destination or '',
            'SHIPPING LINE': self.ship_line or '',
            'SHELL COLOR': self.shell_color or '',
            'DELIVERY DATE': datetime.strftime(parse(self.requested_delivery_date),'%m/%d/%Y') if self.requested_delivery_date else '',
            'ESTIMATED DATE': datetime.strftime(parse(self.estimated_date),'%m/%d/%Y') if self.estimated_date else '',
            'TOTAL': int(self.total_qty),
        }
        for l in self.order_ids:
            vals[l.product_code] = int(l.qty)
        return vals



class DmpiCrmSaleOrderLine(models.Model):
    _name = 'dmpi.crm.sale.order.line'


    @api.depends('price','qty')
    def _get_total(self):
        for rec in self:
            rec.total = rec.price*rec.qty


    def _get_product_codes(self):
        res = [(r.name,r.description) for r in self.env['dmpi.crm.product.code'].search([])]
        return res



    def compute_price(self,date,customer_code,material,tag_ids=[]):

        product_id = self.env['dmpi.crm.product'].search([('sku','=',material)], limit=1)
        partner_id = self.env['dmpi.crm.partner'].search([('customer_code','=',customer_code)], limit=1)
        pricelist_obj = self.env['dmpi.crm.product.price.list']

        print (product_id.id, partner_id.id, date, tag_ids)
        rule_id, price, uom, pricing_date = pricelist_obj.get_product_price(product_id.id, partner_id.id, date, False, tag_ids)
        self.price = price
        if not pricing_date:
            pricing_date = date
        self.pricing_date = pricing_date
        self.uom = uom
        self.order_id.get_product_qty()
        self.order_id.contract_id.on_change_partner_id()
        self.order_id.contract_id.on_change_ar_status()
        return rule_id

    # @api.onchange('product_id','qty')
    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            result = self.compute_price(self.order_id.contract_id.po_date,self.order_id.partner_id.customer_code,self.product_id.sku, self.order_id.tag_ids.ids)

            # self.price = result
            self.product_code = self.product_id.code
            self.total = self.qty * self.price
            self.name = self.product_id.name
            print (self.order_id.destination,self.order_id.tag_ids.ids)

    @api.onchange('price')
    def onchange_price(self):
        if self.price:
            print ("THE PRICE HAS CHANGED",self.price)
            pricelist_obj = self.env['dmpi.crm.product.price.list']
            rule_id, price, uom, pricing_date = pricelist_obj.get_product_price(self.product_id.id, self.order_id.partner_id.id, self.order_id.contract_id.po_date, self.price, self.order_id.tag_ids.ids)
            
            self.pricing_date = pricing_date


    @api.multi
    def recompute_price(self):
        if self.product_id:
            print (self.order_id.tag_ids.ids)
            result = self.compute_price(self.order_id.contract_id.po_date,self.order_id.partner_id.customer_code,self.product_id.sku,self.order_id.tag_ids.ids)




    name = fields.Char("Description", related="product_id.name", store=True)
    contract_line_no = fields.Integer('Contract Line No')
    so_line_no = fields.Integer("Line No")
    sequence = fields.Integer('Sequence')
    pricing_date = fields.Date('Pricing Date')

    order_id = fields.Many2one('dmpi.crm.sale.order','Sale Order ID', ondelete='cascade')
    product_code = fields.Selection(_get_product_codes,"Code")
    product_id = fields.Many2one('dmpi.crm.product','SKU')
    price = fields.Float("Price")
    uom = fields.Char("Uom")
    qty = fields.Float("Qty")
    total = fields.Float("Total", compute='_get_total')
    found_p60 = fields.Boolean('Found Pallet 60', default=False)

class CustomerCrmSaleOrder(models.Model):
    _name = 'customer.crm.sale.order'
    _display_summary = 'Customer Sale Contract'
    _inherit = ['dmpi.crm.sale.order']

    order_ids = fields.One2many('customer.crm.sale.order.line','order_id','Order IDs', copy=True, ondelete='cascade')
    tag_ids = fields.Many2many('dmpi.crm.product.price.tag', 'customer_order_tag_rel', 'order_id', 'tag_id', string='Price Tags', copy=True)

    @api.multi
    @api.onchange('tag_ids')
    def onchange_tag_ids(self):
        for rec in self:
            for l in rec.order_ids:
                l.onchange_product_id()


    @api.multi
    @api.depends('order_ids','pack_code_tmp')
    def get_product_qty(self):
        for rec in self:

            data = {}
            total_amount = 0
            total_qty = 0
            total_p100 = 0
            total_p200 = 0

            # get totals per pack code
            for l in rec.order_ids:

                product = l.product_id
                pcode = product and product.code_id.name
                if pcode:
                    if pcode not in data:
                        data[pcode] = 0

                    data[pcode] += l.qty
                    total_p100 += l.qty if 'C' not in pcode else 0
                    total_p200 += l.qty if 'C' in pcode else 0
                    total_amount += l.total
                    total_qty += l.qty

            # change to summary formatting view
            headers = []
            rows = []
            tmp = rec.pack_code_tmp
            tmp = tmp.split(',')
            
            for t in tmp:
                qty = data[t] if t in data else 0
                headers.append("""<th data-original-title="" title="" style="text-align: center; color:#FFF; background-color: #78717e;" >%s</th>""" % t)
                rows.append("""<td class="o_data_cell o_list_number">%s</td>""" % qty)

            rec.notes = """
                <h3>SUMMARY</h3>
                <table class="o_list_view table table-condensed table-striped o_list_view_ungrouped">
                    <thead><tr> %s </tr></thead>
                    <tbody> <tr class="o_data_row"> %s </tr> </tbody>
                </table>
            """ %(''.join(headers),''.join(rows))

            # compute totals
            # print ('compute totals',total_amount,total_qty)
            rec.total_p100 = total_p100
            rec.total_p200 = total_p200
            rec.total_amount = total_amount
            rec.total_qty = total_qty

            # print (rec.total_amount,'total amount')


class CustomerCrmSaleOrderLine(models.Model):
    _name = 'customer.crm.sale.order.line'
    _inherit = ['dmpi.crm.sale.order.line']

    order_id = fields.Many2one('customer.crm.sale.order','Sale Order ID', ondelete='cascade')


class DmpiCrmDr(models.Model):
    _name = 'dmpi.crm.dr'
    _inherit = ['mail.thread']
    _order = 'id desc'

    @api.model
    def create(self, vals):

        # check duplicates
        sap_dr_no = vals.get('sap_dr_no',False)
        if sap_dr_no:
            is_duplicate, dr_count = self.check_duplicates(sap_dr_no, 'create')
            vals['is_duplicate'] = is_duplicate

        return super(DmpiCrmDr, self).create(vals)

    @api.multi
    def unlink(self):

        # check duplicates
        sap_drs = list(set( self.mapped('sap_dr_no') ))
        res = super(DmpiCrmDr, self).unlink()
        for sap_dr_no in sap_drs:
            is_duplicate, dr_count = self.check_duplicates(sap_dr_no, 'unlink')

        return res


    @api.multi
    def check_duplicates(self, sap_dr_no, typ):
        # type = 'create' or 'unlink'
        similar_dr = self.env['dmpi.crm.dr'].search([('sap_dr_no','=',sap_dr_no)])
        dr_count = len(similar_dr)

        if dr_count > 0 and typ == 'create':
            for rec in similar_dr:
                rec.is_duplicate = True
            return True, dr_count

        if dr_count == 1 and typ == 'unlink':
            similar_dr.is_duplicate = False
            return True, dr_count

        return False, dr_count


    @api.multi
    @api.depends('sap_so_no')
    def _get_odoo_doc(self):
        for rec in self:
            
            so_id = False
            contract_id = False
            sap_so_no = rec.sap_so_no

            if sap_so_no:
                so = self.env['dmpi.crm.sale.order'].search([('sap_so_no','=',rec.sap_so_no)], limit=1)

                if so:
                    so_id = so
                    contract_id = so.contract_id

            rec.so_id = so_id
            rec.contract_id = contract_id



    # odoo docs
    name = fields.Char("DR No.", related='sap_dr_no', store=True)
    odoo_po_no = fields.Char("Odoo PO No.")
    odoo_so_no  = fields.Char("Odoo SO No.")
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Oodoo PO", compute='_get_odoo_doc', store=True)
    so_id = fields.Many2one('dmpi.crm.sale.order', 'Odoo SO', compute='_get_odoo_doc', store=True)

    # sap docs
    sap_so_no = fields.Char("SAP SO No.")
    sap_dr_no = fields.Char("SAP DR No.")
    sap_delivery_no  = fields.Char("SAP Delivery No.")
    sto_no = fields.Char("STO No.")

    # headers
    ship_to  = fields.Char("Ship To")
    shipment_no  = fields.Char("Shipment No.")
    fwd_agent  = fields.Char("Forward Agent")
    van_no  = fields.Char("Container No.")
    vessel_name  = fields.Char("Vessel Name / Voyage")
    truck_no  = fields.Char("Truck No.")
    load_no  = fields.Char("Load no.")
    booking_no  = fields.Char("Booking No.")
    seal_no  = fields.Char("Seal No.")
    delivery_creation_date  = fields.Char("Delivery Create Date")
    gi_date  = fields.Char("GI Date")
    port_origin  = fields.Char("Port of Origin")
    port_destination  = fields.Char("Port of Destination")
    port_discharge = fields.Char("Port of Discharge")

    # others
    raw = fields.Text("Raw")
    state = fields.Selection([('generated','SAP Generated'),('cancelled','Cancelled')], default="generated", string="Status", track_visibility='onchange')
    is_duplicate = fields.Boolean('Duplicate', default=False)

    dr_lines = fields.One2many('dmpi.crm.dr.line', 'dr_id', 'DR Lines')
    alt_items = fields.One2many('dmpi.crm.alt.item', 'dr_id', 'Alt Items')
    insp_lots = fields.One2many('dmpi.crm.inspection.lot', 'dr_id', 'Insp Lots')
    clp_ids = fields.One2many('dmpi.crm.clp', 'dr_id', 'CLP')
    preship_ids = fields.One2many('dmpi.crm.preship.report', 'dr_id', 'Preship Report')

    @api.multi
    def action_cancel(self):
        for rec in self:
            rec.write({'state':'cancelled'})


    @api.multi
    def action_generated(self):
        for rec in self:
            rec.write({'state':'generated'})

class DmpiCrmDrLine(models.Model):
    _name = 'dmpi.crm.dr.line'
    _rec_name = 'sku'

    container = fields.Char('Container')
    partner = fields.Char('Partner')
    
    lot = fields.Char('Inspection Lot')
    type = fields.Char('Operation Type')
    factor = fields.Char('Factor')
    no_sample = fields.Integer('No of Samples')
    no_defect = fields.Integer('No of Defects')
    dr_id = fields.Many2one('dmpi.crm.dr', 'DR ID', ondelete='cascade')


    dr_line_item_no = fields.Integer("Line No")
    sku = fields.Char('SKU')
    qty = fields.Float('Qty')
    uom = fields.Char('UOM')
    plant = fields.Char('Plant')
    wh_no = fields.Char('Warehouse No.')
    storage_loc = fields.Char('Storage Location')
    to_num = fields.Char('TO No.')
    tr_order_item = fields.Char('TR No.')
    material = fields.Char('Material')
    plant2 = fields.Char('Plant2')
    batch = fields.Char('Batch')
    stock_category = fields.Char('Tr Order item')
    source_su = fields.Char('Tr Order item')
    sap_delivery_no  = fields.Char("SAP Delivery No.")


class DmpiCrmAltItem(models.Model):
    _name = 'dmpi.crm.alt.item'

    sap_so_no = fields.Char('SAP SO No.')
    sap_so_line_no = fields.Char('So Line No.')
    material = fields.Char('Material')
    qty = fields.Float('Qty')
    uom = fields.Char('UOM')
    plant = fields.Char('Plant')
    rejection_reason = fields.Char('Rejection Reason')
    alt_item = fields.Char('SO Alternative item')
    usage = fields.Char('Usage')

    dr_id = fields.Many2one('dmpi.crm.dr', 'DR ID', ondelete='cascade')


class DmpiCrmInspectionLot(models.Model):
    _name = 'dmpi.crm.inspection.lot'

    dr_line_item_no = fields.Char('Del Line item No.')  
    sap_so_no = fields.Char('SU Material')
    stock_unit = fields.Char('Stock Unit')
    lot = fields.Char('Inspection Lot')  
    node_num = fields.Char('Node (Operation) Number') 
    type = fields.Char('Node (Operation) Description')    
    factor_num = fields.Char('Characteristic Number')  
    factor = fields.Char('Characteristic Short Text')  
    no_sample = fields.Integer('No of Samples')
    no_defect = fields.Integer('No of Defects') 
    value = fields.Float('Mean Value')

    dr_id = fields.Many2one('dmpi.crm.dr', 'DR ID', ondelete='cascade')


class DmpiCrmPreshipInspectionLot(models.Model):
    _name = 'dmpi.crm.preship.inspection.lot'

    dr_line_item_no = fields.Char('Del Line item No.')
    sap_so_no = fields.Char('SU  Material')
    lot = fields.Char('Inspection Lot')
    node_num = fields.Char('Node (Operation) Number')
    type = fields.Char('Node (Operation) Description')
    factor_num = fields.Char('Characteristic Number')
    factor = fields.Char('Characteristic Short Text')  
    no_sample = fields.Integer('No of Samples')
    no_defect = fields.Integer('No of Defects') 
    value = fields.Float('Mean Value')

    # dr_id = fields.Many2one('dmpi.crm.dr', 'DR ID', ondelete='cascade')
    preship_id = fields.Many2one('dmpi.crm.preship.report', 'Preshipment Report', ondelete='cascade')

class DmpiCrmShp(models.Model):
    _name = 'dmpi.crm.shp'
    _inherit = ['mail.thread']
    _order = 'id desc'
    # _rec_name = 'shp_no'

    @api.model
    def create(self, vals):

        # check duplicates
        shp_no = vals.get('shp_no',False)
        if shp_no:
            is_duplicate, shp_count = self.check_duplicates(shp_no, 'create')
            vals['is_duplicate'] = is_duplicate

        return super(DmpiCrmShp, self).create(vals)

    @api.multi
    def unlink(self):

        # check duplicates
        shp_nos = list(set( self.mapped('shp_no') ))
        res = super(DmpiCrmShp, self).unlink()
        for shp_no in shp_nos:
            is_duplicate, shp_count = self.check_duplicates(shp_no, 'unlink')

        return res


    @api.multi
    def check_duplicates(self, shp_no, typ):
        # type = 'create' or 'unlink'
        similar_shp = self.env['dmpi.crm.shp'].search([('shp_no','=',shp_no)])
        shp_count = len(similar_shp)

        if shp_count > 0 and typ == 'create':
            for rec in similar_shp:
                rec.is_duplicate = True
            return True, shp_count

        if shp_count == 1 and typ == 'unlink':
            similar_shp.is_duplicate = False
            return True, shp_count

        return False, shp_count


    @api.multi
    @api.depends('sap_so_no')
    def _get_odoo_doc(self):
        for rec in self:
            
            so_id = False
            contract_id = False
            sap_so_no = rec.sap_so_no

            if sap_so_no:
                so = self.env['dmpi.crm.sale.order'].search([('sap_so_no','=',rec.sap_so_no)], limit=1)

                if so:
                    so_id = so
                    contract_id = so.contract_id

            rec.so_id = so_id
            rec.contract_id = contract_id

    # odoo docs
    name = fields.Char("Shipment No.", related="shp_no", store=True)
    odoo_po_no = fields.Char("Odoo PO No.")
    odoo_so_no = fields.Char("Odoo SO No.")
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Odoo PO", compute="_get_odoo_doc", store=True)
    so_id = fields.Many2one('dmpi.crm.sale.order', 'Odoo SO', compute="_get_odoo_doc", store=True)

    # sap docs
    shp_no  = fields.Char("Shipment No.")
    sap_so_no = fields.Char("SAP SO No.")
    sap_dr_no = fields.Char("SAP DR No.")

    # headers
    ship_to = fields.Char("Ship To")
    dr_create_date = fields.Char("Delivery Create Date")
    gi_date = fields.Char("GI Date")
    fwd_agent = fields.Char("Forward Agent")
    van_no  = fields.Char("Container No.")
    vessel_no = fields.Char("Vessel Name / Voyage")
    truck_no = fields.Char("Truck No.")
    load_no  = fields.Char("Load No.")
    booking_no  = fields.Char("Boking No.")
    seal_no  = fields.Char("Seal No.")
    origin = fields.Char("Port of Origin")
    destination = fields.Char("Port of Destination")
    discharge = fields.Char("Port of Discharge")

    # others
    raw = fields.Text("Raw")
    is_duplicate = fields.Boolean('Duplicate', default=False)

    shp_lines = fields.One2many('dmpi.crm.shp.line', 'shp_id', 'SHP Lines')
    

class DmpiCrmShpLine(models.Model):
    _name = 'dmpi.crm.shp.line'

    sap_so_no  = fields.Char("SAP SO No.")   
    so_line_no  = fields.Char("SO Line item No.")
    material  = fields.Char("Material")    
    qty  = fields.Float("SO Order Qty")
    uom  = fields.Char("SO UoM")
    plant  = fields.Char("Plant")   
    reject_reason = fields.Char("Rejection Reason")    
    alt_item   = fields.Char("SO Alternative item")   
    usage = fields.Char("Usage") 

    shp_id = fields.Many2one('dmpi.crm.shp', 'SHP ID', ondelete='cascade')

class DmpiCrmInvoice(models.Model):
    _name = 'dmpi.crm.invoice'
    _inherit = ['mail.thread']
    _order = 'id desc'

    @api.multi
    @api.depends('sap_so_no')
    def _get_odoo_doc(self):
        for rec in self:
            
            so_id = False
            contract_id = False
            sap_so_no = rec.sap_so_no

            if sap_so_no:
                so = self.env['dmpi.crm.sale.order'].search([('sap_so_no','=',rec.sap_so_no)], limit=1)

                if so:
                    so_id = so
                    contract_id = so.contract_id

            rec.so_id = so_id
            rec.contract_id = contract_id

    # odoo docs
    name = fields.Char("Name")
    odoo_po_no  = fields.Char("Odoo PO No.")
    odoo_so_no  = fields.Char("Odoo SO No.")
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Odoo PO", compute="_get_odoo_doc", store=True)
    so_id = fields.Many2one('dmpi.crm.sale.order', 'Odoo SO', compute="_get_odoo_doc", store=True)

    # sap docs
    inv_no = fields.Integer("Invoice No.")
    sap_so_no = fields.Char("SAP SO No.")  
    sap_dr_no = fields.Char("SAP DR No.")
    shp_no  = fields.Char("Shipment No.")
    dmpi_inv_no = fields.Char("DMPI Invoice No.")
    dms_inv_no = fields.Char("DMS Invoice No.")
    sbfti_inv_no = fields.Char("SBFTI Invoice No.")

    # headers
    payer = fields.Char("Payer")  
    inv_create_date = fields.Char("Invoice creation date")
    header_net = fields.Char("Header net value") 
    invoice_file = fields.Binary("Invoice Attachment")
    invoice_filename = fields.Char("Invoice Filename ")
    source = fields.Selection([('500','DMPI'),('530','DMS'),('570','SBFTI')], "Source")

    # others
    raw = fields.Text("Raw")
    is_duplicate = fields.Boolean('Duplicate', default=False)

    inv_lines = fields.One2many('dmpi.crm.invoice.line', 'inv_id', 'Invoice Lines')

class DmpiCrmInvoiceLine(models.Model):
    _name = 'dmpi.crm.invoice.line'

    so_line_no = fields.Char("SO Line Item No.")
    inv_line_no = fields.Char("Invoice Line Item No.")
    material = fields.Char("Material")
    qty = fields.Float("Qty")
    uom = fields.Char("UoM")
    line_net_value = fields.Float("Net Value")

    inv_id = fields.Many2one('dmpi.crm.invoice', 'SHP ID', ondelete='cascade')




class DmpiCrmDownloadOrderWizard(models.TransientModel):
    _name = 'dmpi.crm.download.order.wizard'

    csv_file = fields.Binary('CSV File')

    @api.multi
    def download_orders(self):
        pack_codes = self.env['dmpi.crm.product.code'].get_product_codes()
        hdr = CSV_UPLOAD_HEADERS.copy()
        end_hdr = hdr.pop()
        hdr.extend(pack_codes)
        hdr.append(end_hdr)

        output = io.StringIO()
        writer = csv.DictWriter(output, hdr, delimiter=',')
        writer.writeheader()

        contract_id = self.env.context.get('default_contract_id',False)
        contract = self.env['dmpi.crm.sale.contract'].browse(contract_id)
        order_typ = self.env.context.get('type',False)
        fname = '%s %s' % (contract.partner_id.customer_code, contract.name)

        
        if order_typ == 'customer':
            orders = contract.customer_order_ids
            fname += ' PO'
        elif order_typ == 'commercial':
            orders = contract.sale_order_ids
            fname += ' SO'

        data = []
        for o in orders:
            vals = o.convert_to_dict()
            writer.writerow(vals)

        xy = output.getvalue().encode('utf-8')
        file = base64.encodestring(xy)
        self.write({'csv_file':file})

        button = {
            'type' : 'ir.actions.act_url',
            'url': '/web/content/dmpi.crm.download.order.wizard/%s/csv_file/%s.csv?download=true'%(self.id,fname),
            'target': 'new'
            }
        return button


class DmpiCrmMultiTag(models.TransientModel):
    _name = 'dmpi.crm.multi.tag'

    tag_ids = fields.Many2many('dmpi.crm.product.price.tag', 'wizard_tag_rel', 'wizard_id', 'tag_id', string='Price Tags')

    def domain_on_orders(self):
        contract_id = self.env.context.get('default_contract_id',False)
        domain = [('contract_id','in',[contract_id])]
        return domain

    customer_order_ids = fields.Many2many('customer.crm.sale.order', 'wizard_customer_order_rel', 'wizard_id', 'customer_order_id', string='Customer Orders', domain=domain_on_orders)
    sale_order_ids = fields.Many2many('dmpi.crm.sale.order', 'wizard_sale_order_rel', 'wizard_id', 'sale_order_id', string='Sale Orders', domain=domain_on_orders)

    @api.multi
    def apply_settings(self):
        for co in self.customer_order_ids:
            co.tag_ids = self.tag_ids
        for so in self.sale_order_ids:
            so.tag_ids = self.tag_ids

