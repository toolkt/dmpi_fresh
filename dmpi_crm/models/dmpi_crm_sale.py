# -*- coding: utf-8 -*-

from odoo import _
from odoo.osv import expression
from odoo import models, api, fields
from odoo.exceptions import  Warning, RedirectWarning, ValidationError, AccessError, UserError
from datetime import datetime, timedelta
from dateutil.parser import parse
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

from fabric.api import *
import csv
import sys
import math

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
        ('hold','Hold'),
        ('processing','Processing'),
        ('processed','Processed'),
        ('enroute','Enroute'),
        ('received','Received'),
        ('cancel','Cancelled')]

PRODUCT_CODES = [
        ('P5','P5'),
        ('P6','P6'),
        ('P7','P7'),
        ('P8','P8'),
        ('P9','P9'),
        ('P10','P10'),
        ('P12','P12'),
        ('P5C7','P5C7'),
        ('P6C8','P6C8'),
        ('P7C9','P7C9'),
        ('P8C10','P8C10'),
        ('P9C11','P9C11'),
        ('P10C12','P10C12'),
        ('P12C20','P12C20')]


class DmpiCrmSaleContract(models.Model):
    _name = 'dmpi.crm.sale.contract'
    _description = "Sale Contract"
    _inherit = ['mail.thread']


    # @api.model
    # def create(self, vals):
    #     contract_seq  = self.env['ir.sequence'].next_by_code('dmpi.crm.sale.contract')
    #     vals['name'] = contract_seq
    #     print(contract_seq)
    #     res = super(DmpiCrmSaleContract, self).create(vals)
    #     return res

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

    @api.one
    @api.depends('customer_ref','week_no')
    def _get_customer_ref_to_sap(self):
        ref = []
        if self.customer_ref:
            ref.append(self.customer_ref)
        else:
            ref.append(self.name)
        if self.week_no:
            ref.append("-W%s" % self.week_no)

        self.customer_ref_to_sap = ''.join(ref)



    po_display_number = fields.Char("PO Numbers", compute="_get_po_display_number")
    name = fields.Char("ContractNo", default="Draft", copy=False)
    active = fields.Boolean("Active", default=True)
    cn_no = fields.Integer("CRM Contract no.", copy=False)
    sap_cn_no = fields.Char("SAP Contract no.", copy=False)
    customer_ref = fields.Char("Customer Reference", copy=False)
    customer_ref_to_sap = fields.Char("Customer Reference", compute="_get_customer_ref_to_sap")

    sheet_settings = fields.Text("Settings")
    sheet_data = fields.Text("Data")

    partner_id = fields.Many2one('dmpi.crm.partner',"Customer")
    sold_via_id = fields.Many2one('dmpi.crm.partner',"Sold Via")

    contract_type = fields.Selection(_get_contract_type,"Contract Type", default=_get_contract_type_default)
    po_date = fields.Date("PO Date", default=fields.Date.context_today)
    valid_from = fields.Date("Valid From", default=fields.Date.context_today)
    valid_to = fields.Date("Valid To")

    credit_limit = fields.Float("Credit Limit")
    credit_exposure = fields.Float("Credit Exposure")
    remaining_credit = fields.Float("Remaining Credit", compute='_compute_credit')
    ar_status = fields.Float("AR Status")
    state = fields.Selection(CONTRACT_STATE,string="Status", default='draft', track_visibility='onchange')
    state_disp = fields.Selection(CONTRACT_STATE,related='state',string="Status Display", default='draft')

    contract_total = fields.Float("Contract Total")

    open_so = fields.Float("Open SO")
    total_sales = fields.Float("Total Sales",compute='_compute_totals')
    credit_after_sale = fields.Float("Credit After Sale", compute='_compute_credit')


    worksheet_item_text = fields.Text("Worksheet Items")

    #ONE2MANY RELATIONSHIPTS
    # contract_line_ids = fields.One2many('dmpi.crm.sale.contract.line','contract_id','Contract Lines', track_visibility=True)
    sale_order_ids = fields.One2many('dmpi.crm.sale.order','contract_id','Sale Orders', copy=True)
    customer_order_ids = fields.One2many('customer.crm.sale.order','contract_id','Customer Orders', copy=True)
    invoice_ids = fields.One2many('dmpi.crm.invoice','contract_id','Invoice (DMPI)')
    # dmpi_invoice_ids = fields.One2many('dmpi.crm.invoice.dmpi','contract_id','Invoice (DMPI)')
    # dms_invoice_ids = fields.One2many('dmpi.crm.invoice.dms','contract_id','Invoice (DMS)')
    dr_ids = fields.One2many('dmpi.crm.dr','contract_id','DR')
    shp_ids = fields.One2many('dmpi.crm.shp','contract_id','SHP')

    #LOGS
    sent_to_sap = fields.Boolean("Sent to SAP")
    sent_to_sap_time = fields.Datetime("Sent to SAP Time")

    # upload_file = fields.Binary("Upload")
    # upload_file_name = fields.Char("Upload Filename")
    # upload_file_template = fields.Binary("Upload Template")

    # upload_file_so = fields.Binary("Upload")

    error_count = fields.Integer("Error Count")
    errors = fields.Text("Errors")
    errors_disp = fields.Text("Errors", related='errors')

    # import_errors = fields.Text("Import Errors")
    # import_errors_disp = fields.Text("Import Errors", related='import_errors')

    sap_errors = fields.Text("SAP Errors")
    week_no = fields.Char("Week No")
    #week_id = fields.Many2one('dmpi.crm.week',"Week No")

    

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
    def re_map_products(self):
        for rec in self:
            print(rec)


    @api.multi
    def action_cancel_po(self):
        for rec in self:
            rec.state = 'cancel'

    @api.multi
    def send_email(self):

        action = self.env.ref('mail.action_view_mail_mail').read()[0]
        action.update({
            'views': [(self.env.ref('mail.view_mail_form').id, 'form')],
            # 'res_id' : self.id,
            'target': 'new',
            'context': {
                'default_body_html': "KIT"
            }
        })

        return action
        

    # def check_row_error(self,data):
    #     errors = []
    #     error_count = 0
        
        
    #     #print "-----CHECK ROW ERROR------"

    #     row_count = 0
    #     for row in data:
    #         row_error = []
    #         if row_count > 0:
    #             print(row)
    #         row_count += 1
    #         print (row[0])

    #     return errors,error_count



    @api.depends('sale_order_ids')
    def _compute_totals(self):
        total_sales = 0.0
        for s in self.sale_order_ids:
            if s.state not in ['draft','hold']:
                for l in s.order_ids:
                    total_sales += l.total

        self.total_sales = total_sales



    @api.depends('credit_limit','credit_exposure','total_sales', 'open_so')
    def _compute_credit(self):
        for rec in self:
            rec.remaining_credit = rec.credit_limit - rec.credit_exposure
            rec.credit_after_sale = rec.credit_limit - rec.credit_exposure - rec.total_sales - rec.open_so


    @api.onchange('partner_id')
    def on_change_partner_id(self):

        if self.partner_id:
            credit = self.env['dmpi.crm.partner.credit.limit'].search([('customer_code','=',self.partner_id.customer_code)], order="write_date desc, id desc", limit=1)

            # query = """SELECT sum(replace(ar.amt_in_loc_cur,',','')::float) as ar from dmpi_crm_partner_ar ar
            #             where ar.active is True and ltrim(ar.customer_no,'0') = '%s'
            #         """ % self.partner_id.customer_code


            query = """SELECT sum(ar.amt_in_loc_cur *
                       case
                           when (ar.base_line_date::date + ar.cash_disc_days::INT + 14) <= NOW()::date then 1
                           else 0 end) as ar 
                       from dmpi_crm_partner_ar ar
                       where ar.active is True and ar.acct_type = 'D' and ltrim(ar.customer_no,'0') = '%s' """ % self.partner_id.customer_code


            print(query)        
            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()
            if result:
                self.ar_status = result[0]['ar'] 
            else:
                self.ar_status = 0



            query = """SELECT sum(sol.price * sol.qty) as openso
                from dmpi_crm_sale_order_line sol
                left join dmpi_crm_sale_order so on so.id = sol.order_id
                left join (select odoo_so_no from dmpi_crm_invoice 
                                        where odoo_so_no is not null
                                        group by odoo_so_no) inv_so on inv_so.odoo_so_no = so.name
                left join dmpi_crm_sale_contract sc on sc.id = so.contract_id
                where sc.partner_id = %s and so.state in ('confirmed','process','processed')
            """ % self.partner_id.id

            print ("-----------OpenSO--------------")
            print (query)

            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()
            if result:
                self.open_so = result[0]['openso'] 


            self.credit_limit = credit.credit_limit
            self.credit_exposure = credit.credit_exposure
            self.on_change_po_date()


    @api.onchange('ar_status','credit_after_sale')
    def on_change_ar_status(self):
        print('AR STATUS CHANGED')
        error_count = 0
        errors = []
        if self.ar_status  > 0:
            error_count += 1
            errors.append("CUSTOMER HAS EXISTING AR: Will be routed to Finance for Approval")

        if self.credit_after_sale  < 0:
            error_count += 1
            errors.append("CREDIT LIMIT EXCEEDED: Please reduce purhcases accordingly")

        if error_count > 0:
            self.error_count = error_count
            self.errors = '\n'.join(x for x in errors)

        else:
            self.error_count = 0
            self.errors = ""




    @api.onchange('po_date')
    def on_change_po_date(self):
        if self.po_date and self.partner_id:
            self.valid_from = self.po_date
            validity = self.partner_id.default_validity 
            if validity < 1:
                validity = 7


            self.valid_to =  datetime.strptime(self.po_date, DEFAULT_SERVER_DATE_FORMAT) + timedelta(days=validity)




    @api.multi
    def action_release(self):
        for rec in self:
            rec.state = 'submitted'


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
                        'requested_delivery_date': l.requested_delivery_date,
                        'plant': l.plant,
                        'week_no': week_no,
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


    @api.multi
    def action_approve_contract(self):
        for rec in self:
            rec.on_change_partner_id()
            if rec.ar_status > 0:
                contract_line_no = 0
                for so in rec.sale_order_ids:
                    # so.write({'contract_line_no':contract_line_no})
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

            else:
                contract_line_no = 0
                for so in rec.sale_order_ids:
                    # so.write({'contract_line_no':contract_line_no})
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

                    valid_from = datetime.strptime(rec.valid_from, '%Y-%m-%d')
                    valid_from = valid_from.strftime('%Y%m%d')

                    valid_to = datetime.strptime(rec.valid_to, '%Y-%m-%d')
                    valid_to =   valid_to.strftime('%Y%m%d')


                    line = {
                        'odoo_po_no' : rec.name,
                        'sap_doc_type' : rec.contract_type,
                        'sales_org' : rec.partner_id.sales_org,
                        'dist_channel' : rec.partner_id.dist_channel,
                        'division' : rec.partner_id.division,
                        'sold_to' : rec.partner_id.customer_code,
                        'ship_to' : so.ship_to_id.ship_to_code,
                        'ref_po_no' : ref_po_no,
                        'po_date' : po_date,
                        'valid_from' : valid_from,
                        'valid_to' : valid_to,
                        'ship_to_dest' : so.ship_to_id.ship_to_code,
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




class DmpiCrmSaleOrder(models.Model):
    _name = 'dmpi.crm.sale.order'
    _inherit = ['mail.thread']


    def _get_doc_type(self):
        group = 'doc_type'
        query = """SELECT cs.select_name,cs.select_value
                from dmpi_crm_config_selection cs
                left join dmpi_crm_config cc on cc.id = cs.config_id
                where select_group = '%s'  and cc.active is True and cc.default is True
                order by sequence 
                """ % group
        self.env.cr.execute(query)
        result = self.env.cr.dictfetchall()
        res = [(r['select_value'],r['select_name']) for r in result]
        return res

    def _get_doc_type_default(self):
        group = 'doc_type'
        query = """SELECT cs.select_name,cs.select_value
                from dmpi_crm_config_selection cs
                left join dmpi_crm_config cc on cc.id = cs.config_id
                where cs.select_group = '%s'  and cc.active is True and cc.default is True and cs.default is True
                order by sequence 
                limit 1 
                """ % group
        self.env.cr.execute(query)
        result = self.env.cr.dictfetchone()
        # print (result)
        if result:
            return result['select_name']

    @api.model
    def _sale_order_demand_create_csv(self, so_ids):
        csv = ''
        headers = ['ODOO PO','ODOO SO','SOLD TO','SHIP TO','DESTINATION','WEEK','P5','P6','P7','P8','P9','P10','P12','P5C7',
                'P6C8','P7C9','P8C10','P9C11','P10C12','P12C20','Total','Shipp Line','Shell Color','Delivery Date','STATUS']

        csv = u','.join(headers) + '\n'

        # add row data
        for sid in so_ids:
            row = []
            so = self.browse(sid)

            odoo_po_no = so.contract_id.name or ''
            odoo_so_no = so.name or ''
            sold_to = so.contract_id.partner_id.name or ''
            ship_to = so.ship_to_id.name or ''
            destination = ''
            week_no = '%s' % (so.week_no or '')
            total = 0
            ship_line = so.ship_line or ''
            shell_color = so.shell_color or ''
            delivery_date = so.requested_delivery_date or ''
            status = so.state.upper()

            if delivery_date:
                delivery_date = datetime.strftime(parse(delivery_date), '%M/%d/%Y')

            for l in so.order_ids:
                p5  = l.qty if l.product_code == 'P5' else ''
                p6  = l.qty if l.product_code == 'P6' else ''
                p7  = l.qty if l.product_code == 'P7' else ''
                p8  = l.qty if l.product_code == 'P8' else ''
                p9  = l.qty if l.product_code == 'P9' else ''
                p10 = l.qty if l.product_code == 'P10' else ''
                p12 = l.qty if l.product_code == 'P12' else ''
                p5c7    = l.qty if l.product_code == 'P5C7' else ''
                p6c8    = l.qty if l.product_code == 'P6C8' else ''
                p7c9    = l.qty if l.product_code == 'P7C9' else ''
                p8c10   = l.qty if l.product_code == 'P8C10' else ''
                p9c11   = l.qty if l.product_code == 'P9C11' else ''
                p10c12  = l.qty if l.product_code == 'P10C12' else ''
                p12c20  = l.qty if l.product_code == 'P12C20' else ''

                total += l.qty

            row = [odoo_po_no, odoo_so_no, sold_to, ship_to, destination, week_no, 
                p5, p6, p7, p8, p9, p10, p12, p5c7, p6c8, p7c9, p8c10, p9c11, p10c12, p12c20,
                total, ship_line, shell_color, delivery_date, status]

            csv += ','.join(str(d) for d in row) + '\n'

        return csv

    @api.multi
    def download_demand_sale_order(self):
        print('EXPORT SALE ORDERS DEMAND')
        active_ids = self.browse(self.env.context.get('active_ids'))

        docids = []
        for rec in active_ids:
            docids.append(rec.id)

        if docids:
            values = {
                'type': 'ir.actions.act_url',
                'url': '/csv/download/dmpi_crm_sale_order/?docids=%s' % (json.dumps(docids)),
                'target': 'current',
            }

            return values
        
        else:
            raise UserError(_("Nothing to Download."))



    def submit_so_file(self,rec):
        if rec.contract_id.sap_cn_no != '' and rec.name != 'Draft' and rec.state != 'hold':
            print ("Contract Not Draft")
            lines = []
            cid = rec.contract_id
            line_no = 0
            for sol in rec.order_ids:
                line_no += 10
                sol.so_line_no = line_no
                ref_po_no = cid.customer_ref_to_sap

                po_date = datetime.strptime(cid.po_date, '%Y-%m-%d')
                po_date = po_date.strftime('%Y%m%d')

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
                    'ship_to' : rec.ship_to_id.ship_to_code, 
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
                    'original_ship_to' : ''
                }

                if cid.sold_via_id:
                    line['sold_to'] = cid.sold_via_id.customer_code
                    line['ship_to'] = cid.sold_via_id.customer_code
                    line['sap_doc_type'] = 'ZKM3'
                    line['original_ship_to'] = rec.ship_to_id.ship_to_code
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
                                    l['uom'],l['plant'],l['original_ship_to']
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
                                    l['uom'],l['plant']
                                ])



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
                raise Warning("SO was Successfully Created")
            else:
                raise Warning("State is in Draft or on Hold. The SO was NOT Created")


    @api.onchange('ship_to_id')
    def on_change_ship_to(self):
        self.notify_id = self.ship_to_id.id
        self.sales_org = self.contract_id.partner_id.sales_org
        self.plant = self.contract_id.partner_id.plant
        # sales_org = self.env['dmpi.crm.partner'].search([('customer_code','=',self.ship_to.customer_code)], limit=1)[0].sales_org
        # if sales_org:
        #     self.sales_org = sales_org
        # print("Onchange Partner")


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



    # @api.depends('p5','p6','p7','p8','p9','p10','p12','p5c7','p6c8','p7c9','p8c10','p9c11','p10c12','p12c20','order_ids')
    # def get_totals(self):
        
    #     for rec in self:
    #         total_amount = 0.0
    #         for l in rec.order_ids:
    #             total_amount += l.total
    #             if l.product_code == 'P5': rec.p5 += l.qty
    #             if l.product_code == 'P6': rec.p6 += l.qty
    #             if l.product_code == 'P7': rec.p7 += l.qty
    #             if l.product_code == 'P8': rec.p8 += l.qty
    #             if l.product_code == 'P9': rec.p9 += l.qty
    #             if l.product_code == 'P10': rec.p10 += l.qty
    #             if l.product_code == 'P12': rec.p12 += l.qty
    #             if l.product_code == 'P5C7': rec.p5c7 += l.qty
    #             if l.product_code == 'P6C8': rec.p6c8 += l.qty
    #             if l.product_code == 'P7C9': rec.p7c9 += l.qty
    #             if l.product_code == 'P8C10': rec.p8c10 += l.qty
    #             if l.product_code == 'P9C11': rec.p9c11 += l.qty
    #             if l.product_code == 'P10C12': rec.p10c12 += l.qty
    #             if l.product_code == 'P12C20': rec.p12c20 += l.qty

    #         rec.total_amount = total_amount
    #         rec.total_crown = rec.p5+rec.p6+rec.p7+rec.p8+rec.p9+rec.p10+rec.p12
    #         rec.total_crownless = rec.p5c7+rec.p6c8+rec.p7c9+rec.p8c10+rec.p9c11+rec.p10c12+rec.p12c20
    #         rec.total_qty = rec.total_crown + rec.total_crownless

        
    def _get_doc_types(self):
        res = [(r.name,r.description) for r in self.env['dmpi.crm.sap.doc.type'].search([])]
        return res

    def _get_default_doc_types(self):
        res = self.env['dmpi.crm.sap.doc.type'].search([('default','=',True)])[0].name
        return res

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


    @api.multi
    @api.depends('order_ids')
    def _get_no_price_error(self):
        for so in self:
            error = 0
            error_msg = []
            msg = ''

            for l in so.order_ids:
                if l.price == 0:
                    error += 1
                    s = 'No Price set for %s (%s)' % (l.product_id.code, l.product_id.sku)
                    error_msg.append(s)

            msg = '\n'.join(error_msg)
            so.error = error
            so.error_msg = msg


    name_disp = fields.Char("Display No.", compute='_get_name_disp')
    name = fields.Char("CRM SO No.", default="Draft", copy=False)
    plant = fields.Char("Plant")
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Contract ID")
    contract_line_no = fields.Integer("Contract Line No.")
    so_no = fields.Integer("SO Num")
    sap_so_no = fields.Char("SAP SO no.")
    sap_so_date = fields.Date("SAP SO Date")
    sap_doc_type = fields.Selection(_get_doc_types,"Doc Type",default=_get_default_doc_types)
    order_ids = fields.One2many('dmpi.crm.sale.order.line','order_id','Order IDs', copy=True)
    valid = fields.Boolean("Valid Order", default=True)
    valid_disp = fields.Boolean("Valid Order", related='valid')
    error = fields.Integer('Error Count', compute="_get_no_price_error")
    error_msg = fields.Text('Error Message', compute="_get_no_price_error")


    #Crown
    p101 = fields.Integer(string="P5", compute='_get_product_qty')
    p102 = fields.Integer(string="P6", compute='_get_product_qty')
    p103 = fields.Integer(string="P7", compute='_get_product_qty')
    p104 = fields.Integer(string="P8", compute='_get_product_qty')
    p105 = fields.Integer(string="P9", compute='_get_product_qty')
    p106 = fields.Integer(string="P10", compute='_get_product_qty')
    p107 = fields.Integer(string="P12", compute='_get_product_qty')
    p108 = fields.Integer(string="UA", compute='_get_product_qty')
    p109 = fields.Integer(string="UA", compute='_get_product_qty')
    p110 = fields.Integer(string="UA", compute='_get_product_qty')
    total_p100 = fields.Integer(string="Total", compute='_get_product_qty')

    #Crownless
    p201 = fields.Integer(string="P5C7", compute='_get_product_qty')
    p202 = fields.Integer(string="P6C8", compute='_get_product_qty')
    p203 = fields.Integer(string="P7C9", compute='_get_product_qty')
    p204 = fields.Integer(string="P8C10", compute='_get_product_qty')
    p205 = fields.Integer(string="P9C11", compute='_get_product_qty')
    p206 = fields.Integer(string="P10C12", compute='_get_product_qty')
    p207 = fields.Integer(string="P12C20", compute='_get_product_qty')
    p208 = fields.Integer(string="UA", compute='_get_product_qty')
    p209 = fields.Integer(string="UA", compute='_get_product_qty')
    p210 = fields.Integer(string="UA", compute='_get_product_qty')
    total_p200 = fields.Integer(string="Total", compute='_get_product_qty')

    @api.multi
    def _get_product_qty(self):
        for rec in self:
            if rec[0].id:
                query = """ SELECT SUM (seq) AS seq,code,array_to_string(ARRAY_AGG (sku),'') AS sku,SUM (qty) AS qty,SUM (amount) AS amount FROM (
                    SELECT SEQUENCE AS seq,NAME AS code,'' AS sku,0 AS qty,0 AS amount FROM dmpi_crm_product_code pc WHERE active=TRUE UNION ALL 
                    SELECT 0 AS seq,P.code,P.sku,sol.qty,sol.price*sol.qty AS amount FROM dmpi_crm_sale_order_line sol LEFT JOIN dmpi_crm_product P ON P.ID=sol.product_id WHERE sol.order_id=%s) AS Q1 GROUP BY code ORDER BY seq
                """ % rec[0].id
                # print (query)
                self.env.cr.execute(query)
                result = self.env.cr.dictfetchall()

                headers = []
                skus = []
                rows = []
                total_amount = 0
                total_qty = 0
                for l in result:
                    total_amount += l['amount'] or 0
                    total_qty += l['qty'] or 0

                    if l['code'] == 'P5': rec.p101 = l['qty'] 
                    if l['code'] == 'P6': rec.p102 = l['qty']
                    if l['code'] == 'P7': rec.p103 = l['qty']
                    if l['code'] == 'P8': rec.p104 = l['qty']
                    if l['code'] == 'P9': rec.p105 = l['qty']
                    if l['code'] == 'P10': rec.p106 = l['qty']
                    if l['code'] == 'P12': rec.p107 = l['qty']
                    if l['code'] == 'P': rec.p108 = l['qty']
                    if l['code'] == 'P': rec.p109 = l['qty']
                    if l['code'] == 'P': rec.p110 = l['qty']

                    if l['code'] == 'P5C7': rec.p201 = l['qty']
                    if l['code'] == 'P6C8': rec.p202 = l['qty']
                    if l['code'] == 'P7C9': rec.p203 = l['qty']
                    if l['code'] == 'P8C10': rec.p204 = l['qty']
                    if l['code'] == 'P9C11': rec.p205 = l['qty']
                    if l['code'] == 'P10C12': rec.p206 = l['qty']
                    if l['code'] == 'P12C20': rec.p207 = l['qty']
                    if l['code'] == 'P': rec.p208 = l['qty']
                    if l['code'] == 'P': rec.p209 = l['qty']
                    if l['code'] == 'P': rec.p210 = l['qty']

                    headers.append("""<th data-original-title="" title="" style="text-align: center; color:#FFF; background-color: #78717e;" >%s</th>""" % l['code'])
                    # skus.append("""<th data-original-title="" title="" style="text-align: center; color:#FFF; background-color: #999999;" >%s</th>""" % '7AOB19912')# l['sku'])
                    rows.append("""<td class="o_data_cell o_list_number">%s</td>""" % l['qty'])

                rec.notes = """
                    <h3>SUMMARY</h3>
                    <table class="o_list_view table table-condensed table-striped o_list_view_ungrouped">
                        <thead><tr> %s </tr></thead>
                        <tbody> <tr class="o_data_row"> %s </tr> </tbody>
                    </table>
                """ %(''.join(headers),''.join(rows))

                rec.total_p100 = 1#self.p101,self.p102,self.p103,self.p104,self.p105,self.p106,self.p107,self.p108,self.p109,self.p110
                rec.total_p200 = 1#self.p201,self.p202,self.p203,self.p204,self.p205,self.p206,self.p207,self.p208,self.p209,self.p210
                rec.total_amount = total_amount
                rec.total_qty = total_qty

    partner_id = fields.Many2one('dmpi.crm.partner',"Customer", related='contract_id.partner_id')
    ship_to_id = fields.Many2one("dmpi.crm.ship.to","Ship to Party")
    notify_id = fields.Many2one("dmpi.crm.ship.to","Notify Party")
    # notify_partner_id = fields.Many2one('dmpi.crm.partner',"Notify Party")
    sales_org = fields.Char("Sales Org")
    dest_country_id = fields.Many2one('dmpi.crm.country', 'Destination')
    order_date = fields.Date("Order Date")
    estimated_date = fields.Date("Estimated Date")
    shell_color = fields.Char("Shell Color")
    ship_line = fields.Char("Ship Line")
    requested_delivery_date = fields.Date("Req. Date")
    notes = fields.Text("Notes/Remarks", compute='_get_product_qty')

    total_qty = fields.Float('Total', compute='_get_product_qty')
    total_amount = fields.Float('Total', compute='_get_product_qty')

    week_no = fields.Char("Week No")
    state = fields.Selection([('draft','Draft'),('confirmed','Confirmed'),('hold','Hold'),('process','For Processing'),('processed','Processed'),('cancelled','Cancelled')], default="draft", string="Status")
    po_state = fields.Selection(CONTRACT_STATE,string="Status", related='contract_id.state')
    

    # @api.model
    # def create(self, vals):
    #     seq  = self.env['ir.sequence'].next_by_code('dmpi.crm.sale.order')
    #     vals['name'] = seq
    #     res = super(DmpiCrmSaleOrder, self).create(vals)
    #     return res


class DmpiCrmSaleOrderLine(models.Model):
    _name = 'dmpi.crm.sale.order.line'


    @api.depends('price','qty')
    def _get_total(self):
        for rec in self:
            rec.total = rec.price*rec.qty


    def _get_product_codes(self):
        res = [(r.name,r.description) for r in self.env['dmpi.crm.product.code'].search([])]
        return res



    def compute_price(self,date,customer_code,material):
        query = """SELECT amount,currency,uom from dmpi_crm_product_price_list_item  
                where material = '%s'
                and '%s'::DATE between valid_from and valid_to
                limit 1 """ % (material,date)

        print("--------PRICE-------\n%s" % query)
        self.env.cr.execute(query)
        result = self.env.cr.dictfetchall()
        if result:
            self.price = float(result[0]['amount'])
        else:
            self.price = 0
        if result:
            self.uom = result[0]['uom']
        else:
            self.uom = 'CAS'

        if result:
            return result[0]
        else:
            return False


    @api.onchange('product_id','qty')
    def onchange_product_id(self):
        if self.product_id:
            result = self.compute_price(datetime.today(),self.order_id.partner_id.customer_code,self.product_id.sku)

            self.product_code = self.product_id.code
            self.total = self.qty * self.price
            self.name = self.product_id.name
            qty = round_qty(75,self.qty)
            self.qty = qty  
        


    def recompute_price(self):
        if self.product_id:
            result = self.compute_price(datetime.today(),self.order_id.partner_id.customer_code,self.product_id.sku)




    name = fields.Char("Description")
    contract_line_no = fields.Integer('Contract Line No')
    so_line_no = fields.Integer("Line No")
    sequence = fields.Integer('Sequence')

    order_id = fields.Many2one('dmpi.crm.sale.order','Sale Order ID', ondelete='cascade')
    product_code = fields.Selection(_get_product_codes,"Code")
    product_id = fields.Many2one('dmpi.crm.product','SKU')
    price = fields.Float("Price")
    uom = fields.Char("Uom")
    qty = fields.Float("Qty")
    total = fields.Float("Total", compute='_get_total')


class CustomerCrmSaleOrder(models.Model):
    _name = 'customer.crm.sale.order'
    _display_summary = 'Customer Sale Contract'
    _inherit = ['dmpi.crm.sale.order']

    order_ids = fields.One2many('customer.crm.sale.order.line','order_id','Order IDs', copy=True)

    @api.multi
    def _get_product_qty(self):
        for rec in self:
            query = """ SELECT SUM (seq) AS seq,code,array_to_string(ARRAY_AGG (sku),'') AS sku,SUM (qty) AS qty,SUM (amount) AS amount FROM (
                SELECT SEQUENCE AS seq,NAME AS code,'' AS sku,0 AS qty,0 AS amount FROM dmpi_crm_product_code pc WHERE active=TRUE UNION ALL 
                SELECT 0 AS seq,P.code,P.sku,sol.qty,sol.price*sol.qty AS amount FROM customer_crm_sale_order_line sol LEFT JOIN dmpi_crm_product P ON P.ID=sol.product_id WHERE sol.order_id=%s) AS Q1 GROUP BY code ORDER BY seq
            """ % rec[0].id
            # print (query)
            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()

            headers = []
            skus = []
            rows = []
            total_amount = 0
            total_qty = 0
            for l in result:
                total_amount += l['amount'] or 0
                total_qty += l['qty'] or 0

                if l['code'] == 'P5': rec.p101 = l['qty'] 
                if l['code'] == 'P6': rec.p102 = l['qty']
                if l['code'] == 'P7': rec.p103 = l['qty']
                if l['code'] == 'P8': rec.p104 = l['qty']
                if l['code'] == 'P9': rec.p105 = l['qty']
                if l['code'] == 'P10': rec.p106 = l['qty']
                if l['code'] == 'P12': rec.p107 = l['qty']
                if l['code'] == 'P': rec.p108 = l['qty']
                if l['code'] == 'P': rec.p109 = l['qty']
                if l['code'] == 'P': rec.p110 = l['qty']

                if l['code'] == 'P5C7': rec.p201 = l['qty']
                if l['code'] == 'P6C8': rec.p202 = l['qty']
                if l['code'] == 'P7C9': rec.p203 = l['qty']
                if l['code'] == 'P8C10': rec.p204 = l['qty']
                if l['code'] == 'P9C11': rec.p205 = l['qty']
                if l['code'] == 'P10C12': rec.p206 = l['qty']
                if l['code'] == 'P12C20': rec.p207 = l['qty']
                if l['code'] == 'P': rec.p208 = l['qty']
                if l['code'] == 'P': rec.p209 = l['qty']
                if l['code'] == 'P': rec.p210 = l['qty']

                headers.append("""<th data-original-title="" title="" style="text-align: center; color:#FFF; background-color: #78717e;" >%s</th>""" % l['code'])
                # skus.append("""<th data-original-title="" title="" style="text-align: center; color:#FFF; background-color: #999999;" >%s</th>""" % '7AOB19912')# l['sku'])
                rows.append("""<td class="o_data_cell o_list_number">%s</td>""" % l['qty'])

            rec.notes = """
                <h3>SUMMARY</h3>
                <table class="o_list_view table table-condensed table-striped o_list_view_ungrouped">
                    <thead><tr> %s </tr></thead>
                    <tbody> <tr class="o_data_row"> %s </tr> </tbody>
                </table>
            """ %(''.join(headers),''.join(rows))

            rec.total_p100 = 1#self.p101,self.p102,self.p103,self.p104,self.p105,self.p106,self.p107,self.p108,self.p109,self.p110
            rec.total_p200 = 1#self.p201,self.p202,self.p203,self.p204,self.p205,self.p206,self.p207,self.p208,self.p209,self.p210
            rec.total_amount = total_amount
            rec.total_qty = total_qty


class CustomerCrmSaleOrderLine(models.Model):
    _name = 'customer.crm.sale.order.line'
    _inherit = ['dmpi.crm.sale.order.line']

    order_id = fields.Many2one('customer.crm.sale.order','Sale Order ID', ondelete='cascade')


class DmpiCrmDr(models.Model):
    _name = 'dmpi.crm.dr'
    _inherit = ['mail.thread']


    name = fields.Char("CRM DR No.", related='sap_dr_no')
    sap_so_no = fields.Char("SAP So No.")
    sap_dr_no = fields.Char("SAP DR No.")
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Contract ID")
    sale_order_id = fields.Many2one('dmpi.crm.sale.order', "Sale Order ID")
    raw = fields.Text("Raw")

    dr_lines = fields.One2many('dmpi.crm.dr.line', 'dr_id', 'DR Lines')
    alt_items = fields.One2many('dmpi.crm.alt.item', 'dr_id', 'Alt Items')
    insp_lots = fields.One2many('dmpi.crm.inspection.lot', 'dr_id', 'Insp Lots')
    clp_ids = fields.One2many('dmpi.crm.clp', 'dr_id', 'CLP')
    preship_ids = fields.One2many('dmpi.crm.preship.report', 'dr_id', 'Preship Report')
    

    odoo_po_no = fields.Char("Odoo PO No.")
    odoo_so_no  = fields.Char("Odoo SO No.")
    sap_so_no  = fields.Char("SAP SO No.")  
    sap_delivery_no  = fields.Char("SAP Delivery No.")
    ship_to  = fields.Char("Ship-to")
    delivery_creation_date  = fields.Char("Delivery Creation Date") 
    gi_date  = fields.Char("GI Date.")
    shipment_no  = fields.Char("Shipment No.")
    fwd_agent  = fields.Char("Fwd Agent")  
    van_no  = fields.Char("VAN no.") 
    vessel_name  = fields.Char("Vessel Name / Voyage")
    truck_no  = fields.Char("Truck No.")   
    load_no  = fields.Char("Load no.")
    booking_no  = fields.Char("Booking no.") 
    seal_no  = fields.Char("Seal no.")
    port_origin  = fields.Char("Port of Origin")
    port_destination  = fields.Char("Port of destination")   
    port_discharge = fields.Char("Port of discharge")
    sto_no = fields.Char("STO No")
    state = fields.Selection([('generated','SAP Generated'),('cancelled','Cancelled')], default="generated", string="Status", track_visibility='onchange')
    

    @api.multi
    def action_cancel(self):
        for rec in self:
            rec.write({'state':'cancelled'})


    @api.multi
    def action_generated(self):
        for rec in self:
            rec.write({'state':'generated'})

    # @api.multi
    # def action_view_invoice(self):
    #     action = self.env.ref('account.action_invoice_out_refund').read()[0]

    #     invoices = self.mapped('invoice_ids')
    #     if len(invoices) > 1:
    #         action['domain'] = [('id', 'in', invoices.ids)]
    #     elif invoices:
    #         action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
    #         action['res_id'] = invoices.id
    #     return action

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
    to_num = fields.Char('TO Number')
    tr_order_item = fields.Char('Tr Order item')
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
    sap_so_no = fields.Char('SU  Material')    
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
    _rec_name = 'shp_no'

    name = fields.Char("CRM DR No.")
    sap_so_no = fields.Char("SAP So No.")
    sap_dr_no = fields.Char("SAP DR No.")
    sap_shp_no = fields.Char("SAP SHP No.")
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Contract ID")
    raw = fields.Text("Raw")


    odoo_po_no = fields.Char("Odoo PO No.")  
    odoo_so_no = fields.Char("Odoo SO No.")   
    sap_so_no = fields.Char("SAP SO No.")    
    sap_dr_no = fields.Char("SAP Delivery No.")    
    ship_to = fields.Char("Ship-to (header)")  
    dr_create_date = fields.Char("Delivery creation date")   
    gi_date = fields.Char("GI date") 
    shp_no  = fields.Char("Shipment No.")  
    fwd_agent = fields.Char("Fwd Agent")    
    van_no  = fields.Char("VAN no.")  
    vessel_no = fields.Char("Vessel Name / Voyage")    
    truck_no = fields.Char("Truck No.")     
    load_no  = fields.Char("Load no.")
    booking_no  = fields.Char("Booking no.")  
    seal_no  = fields.Char("Seal no.")
    origin = fields.Char("Port of Origin")   
    destination = fields.Char("Port of destination")  
    discharge = fields.Char("Port of discharge") 

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

    name = fields.Char("Source")
    inv_no = fields.Integer("Invoice Num")
    dmpi_sap_inv_no = fields.Char("FF Contract No.")
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Contract ID")
    raw = fields.Text("Raw")

    odoo_po_no  = fields.Char("Odoo PO No.")
    odoo_so_no  = fields.Char("Odoo SO No.")
    sap_so_no = fields.Char("SAP SO No.")  
    sap_dr_no = fields.Char("SAP Delivery No.")  
    shp_no  = fields.Char("Shipment No.")
    dmpi_inv_no = fields.Char("DMPI Invoice No.")
    dms_inv_no = fields.Char("DMS Invoice No.") 
    sbfti_inv_no = fields.Char("SBFTI Invoice No.")   
    payer = fields.Char("Payer")  
    inv_create_date = fields.Char("Invoice creation date")
    header_net = fields.Char("Header net value") 
    source = fields.Selection([('500','500'),('530','530'),('570','570')], "Source")

    invoice_filename = fields.Char("Invoice Filename ")
    invoice_file = fields.Binary("Invoice Attachment")


    inv_lines = fields.One2many('dmpi.crm.invoice.line', 'inv_id', 'Invoice Lines')

class DmpiCrmInvoiceLine(models.Model):
    _name = 'dmpi.crm.invoice.line'

    so_line_no = fields.Char("SO Line item No.") 
    inv_line_no = fields.Char("Invoice Line item No.")
    material = fields.Char("Material")   
    qty = fields.Char("Invoice Qty")
    uom = fields.Char("Invoice UOM")
    line_net_value = fields.Char("Line item net value")

    inv_id = fields.Many2one('dmpi.crm.invoice', 'SHP ID', ondelete='cascade')


class DmpiCrmInvoiceDms(models.Model):
    _name = 'dmpi.crm.invoice.dms'

    name = fields.Char("DMS Invoice No.")
    inv_no = fields.Integer("Invoice Num")
    dmpi_sap_inv_no = fields.Char("FF Invoice No.")
    dms_sap_inv_no = fields.Char("DMS Invoice No.")
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Contract ID")
    raw = fields.Text("Raw")












