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
        group = 'contract_type'
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

    def _get_contract_type_default(self):
        group = 'contract_type'
        query = """SELECT cs.select_name,cs.select_value
                from dmpi_crm_config_selection cs
                left join dmpi_crm_config cc on cc.id = cs.config_id
                where cs.select_group = '%s'  and cc.active is True and cc.default is True and cs.default is True
                order by sequence 
                limit 1 
                """ % group
        self.env.cr.execute(query)
        result = self.env.cr.dictfetchone()
        print (result)
        return result['select_name']


    @api.depends('name','sap_cn_no')
    def _get_po_display_number(self):
        if self.name:
            sap_cn_no = ""
            if self.sap_cn_no:
                sap_cn_no = "/%s" % self.sap_cn_no
            self.po_display_number = "%s%s" % (self.name, sap_cn_no)

    po_display_number = fields.Char("PO Numbers", compute="_get_po_display_number")
    name = fields.Char("ContractNo", default="Draft")
    active = fields.Boolean("Active", default=True)
    cn_no = fields.Integer("CRM Contract no.")
    sap_cn_no = fields.Char("SAP Contract no.")
    customer_ref = fields.Char("Customer Reference")

    sheet_settings = fields.Text("Settings")
    sheet_data = fields.Text("Data")

    partner_id = fields.Many2one('dmpi.crm.partner',"Customer")

    contract_type = fields.Many2one("dmpi.crm.contract.type","Contract Type")
    po_date = fields.Date("PO Date", default=fields.Date.context_today)
    valid_from = fields.Date("Valid From", default=fields.Date.context_today)
    valid_to = fields.Date("Valid To")

    credit_limit = fields.Float("Credit Limit")
    credit_exposure = fields.Float("Credit Exposure")
    remaining_credit = fields.Float("Remaining Credit", compute='_compute_credit')
    ar_status = fields.Float("AR Status")
    state = fields.Selection(CONTRACT_STATE,string="State", default='draft')
    state_disp = fields.Selection(CONTRACT_STATE,related='state',string="State", default='draft')

    contract_total = fields.Float("Contract Total")

    open_so = fields.Float("Open SO")
    total_sales = fields.Float("Total Sales",compute='_compute_totals')
    credit_after_sale = fields.Float("Credit After Sale", compute='_compute_credit')


    worksheet_item_text = fields.Text("Worksheet Items")

    #ONE2MANY RELATIONSHIPTS
    contract_line_ids = fields.One2many('dmpi.crm.sale.contract.line','contract_id','Contract Lines', track_visibility=True)
    sale_order_ids = fields.One2many('dmpi.crm.sale.order','contract_id','Sale Orders')
    customer_order_ids = fields.One2many('customer.crm.sale.order','contract_id','Customer Orders')
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


    @api.onchange('upload_file')
    def onchange_data(self):
        if self.upload_file:
            # file = base64.decodestring(self.upload_file)
            file = base64.b64decode(self.upload_file).decode('utf-8')
            file.split('\n')

            print(file)
            # for row in line:
            #     print (row)



    @api.multi
    def import_po(self):
        for rec in self:
            if rec.upload_file:
                fileobj = TemporaryFile("w+")
                fileobj.write(base64.b64decode(rec.upload_file).decode('utf-8'))
                fileobj.seek(0)
                
                line = csv.reader(fileobj, quotechar='"', delimiter=',', quoting=csv.QUOTE_ALL, skipinitialspace=True)
                # for l in line:
                #     print (l)

                
                new_credit_list = []
                contract_lines = []
                import_errors = []
                line_counter = 0
                for row in line:
                    line_counter += 1
                    # row = l.split(',')
                    if row[0] != '' and line_counter > 1:
                        print (row)
                        partner = self.env['dmpi.crm.partner'].search([('name','like',row[0]),('active','=',True)], limit=1)[0]
                        #destination = self.env['dmpi.crm.partner'].search([('name','like',row[1]),('active','=',True)], limit=1)[0]
                        #ship_to = self.env['dmpi.crm.partner'].search([('name','like',row[2]),('active','=',True)], limit=1)[0]
                        #notify_party = self.env['dmpi.crm.partner'].search([('name','like',row[3]),('active','=',True)], limit=1)[0]


                        #TEMPORARY: Populate contract
                        if partner:
                            rec.partner_id = partner.id
                            rec.contract_type = self.env['dmpi.crm.config.selection'].search([('select_group','=','contract_type'),('default','=',True)], limit=1)[0].select_value
                            rec.on_change_partner_id()

                        if row[5] == '':
                            rec.po_date = fields.date.today()
                            rec.valid_from = fields.date.today()
                            rec.valid_to =  fields.date.today() + timedelta(days=7)


                        
                        contract_line = {}

                        # P5  P6  P7  P8  P9  P10 P12
                        if row[0]:
                            contract_line['partner_id'] = self.env['dmpi.crm.partner'].search([('name','like',row[0]),('active','=',True)], limit=1)[0].id

                        if row[7]:
                            contract_line['p5'] = re.sub('[^0-9]','', row[7])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P5'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P5")
                        if row[8]:
                            contract_line['p6'] = re.sub('[^0-9]','', row[8])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P6'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P6")
                        if row[9]:
                            contract_line['p7'] = re.sub('[^0-9]','', row[9])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P7'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P7")
                        if row[10]:
                            contract_line['p8'] = re.sub('[^0-9]','', row[10])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P8'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P8")
                        if row[11]:
                            contract_line['p9'] = re.sub('[^0-9]','', row[11])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P9'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P9")
                        if row[12]:
                            contract_line['p10'] = re.sub('[^0-9]','', row[12])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P10'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P10")
                        if row[13]:
                            contract_line['p12'] = re.sub('[^0-9]','', row[13])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P12'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P12")


                        if row[15]:
                            contract_line['p5c7'] = re.sub('[^0-9]','', row[15])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P5C7'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P5C7")
                        if row[16]:
                            contract_line['p6c8'] = re.sub('[^0-9]','', row[16])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P6C8'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P6C8")
                        if row[17]:
                            contract_line['p7c9'] = re.sub('[^0-9]','', row[17])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P7C9'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P7C9")
                        if row[18]:
                            contract_line['p8c10'] = re.sub('[^0-9]','', row[18])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P8C10'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P8C10")
                        if row[19]:
                            contract_line['p9c11'] = re.sub('[^0-9]','', row[19])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P9C11'),('partner_id','=',partner.id)])
                            print("Product:",product_code.name)
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P9C11")
                        if row[20]:
                            contract_line['p10c12'] = re.sub('[^0-9]','', row[20])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P10C12'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P10C12")
                        if row[21]:
                            contract_line['p12c20'] = re.sub('[^0-9]','', row[21])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P12C20'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P12C20")

                        contract_lines.append((0,0,contract_line))

                        #update scripter
                        # vals = {
                        #     'partner_id' : partner.id,
                        #     'destination' : destination.id,
                        #     'ship_to' : ship_to.id,
                        #     'notify_party' : notify_party.id,


                        # }
                        print (import_errors)
                        if len(import_errors):
                            rec.write({'import_errors':'\n'.join(i for i in import_errors)})
                        else:
                            rec.write({'import_errors':''})
                        print(contract_line)

                if len(contract_lines)>0:
                    rec.contract_line_ids.unlink()

                    rec.contract_line_ids = contract_lines
                    rec.on_change_contract_line_ids()
        



    @api.multi
    def import_so(self):
        for rec in self:
            if rec.upload_file:
                file = base64.decodestring(rec.upload_file_so).decode('utf-8')
                line = file.split('\n')


                line = csv.reader(line, quotechar='"', delimiter=',',
                     quoting=csv.QUOTE_ALL, skipinitialspace=True)
                # for l in line:
                #     print (l)

                
                sale_orders = []
                import_errors = []
                line_counter = 0
                for row in line:
                    line_counter += 1
                    # row = l.split(',')
                    if row[0] != '' and line_counter > 1:
                        print (row)
                        partner = self.env['dmpi.crm.partner'].search([('name','like',row[0]),('active','=',True)], limit=1)[0]
                        destination = self.env['dmpi.crm.partner'].search([('name','like',row[1]),('active','=',True)], limit=1)[0]
                        ship_to = self.env['dmpi.crm.partner'].search([('name','like',row[2]),('active','=',True)], limit=1)[0]
                        notify_party = self.env['dmpi.crm.partner'].search([('name','like',row[3]),('active','=',True)], limit=1)[0]


                        #TEMPORARY: Populate contract
                        if partner:
                            rec.partner_id = partner.id
                            rec.contract_type = self.env['dmpi.crm.config.selection'].search([('select_group','=','contract_type'),('default','=',True)], limit=1)[0].select_value
                            rec.on_change_partner_id()

                        if row[5] == '':
                            rec.po_date = fields.date.today()
                            rec.valid_from = fields.date.today()
                            rec.valid_to =  fields.date.today() + timedelta(days=7)


                        
                        so = {
                            'partner_id': ''
                        }


                        # P5  P6  P7  P8  P9  P10 P12
                        if row[0]:
                            contract_line['partner_id'] = self.env['dmpi.crm.partner'].search([('name','like',row[0]),('active','=',True)], limit=1)[0].id

                        if row[7]:
                            contract_line['p5'] = re.sub('[^0-9]','', row[7])
                            product_code = self.env['dmpi.crm.product'].search([('code','=','P5'),('partner_id','=',partner.id)])
                            if not product_code.name:
                                import_errors.append("PRODUCT NOT DEFINED: P5")






    @api.depends('sale_order_ids')
    def _compute_totals(self):
        total_sales = 0.0
        for s in self.sale_order_ids:
            for l in s.order_ids:
                total_sales += l.total

        self.total_sales = total_sales



    @api.depends('credit_limit','credit_exposure','total_sales')
    def _compute_credit(self):
        for rec in self:
            rec.remaining_credit = rec.credit_limit - rec.credit_exposure
            rec.credit_after_sale = rec.credit_limit - rec.credit_exposure - rec.total_sales



    @api.multi
    def action_view_sheet(self):
        for rec in self:
            print (rec)

    @api.onchange('partner_id')
    def on_change_partner_id(self):

        if self.partner_id:
            credit = self.env['dmpi.crm.partner.credit.limit'].search([('customer_code','=',self.partner_id.customer_code)], order="write_date desc, id desc", limit=1)

            # query = """SELECT sum(replace(ar.amt_in_loc_cur,',','')::float) as ar from dmpi_crm_partner_ar ar
            #             where ar.active is True and ltrim(ar.customer_no,'0') = '%s'
            #         """ % self.partner_id.customer_code

            query = """SELECT sum(replace(ar.amt_in_loc_cur,',','')::float *
                                     case
                       when (NOW()::date-ar.base_line_date::date)>(pt.days+14) then 1
                       else 0
                       end) as ar
                                         from dmpi_crm_partner_ar ar
                       left join dmpi_crm_payment_terms pt on pt.name = ar.terms
                       where ar.active is True and ltrim(ar.customer_no,'0') = '%s' """ % self.partner_id.customer_code


            print(query)        
            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()
            if result:
                self.ar_status = result[0]['ar'] 
            else:
                self.ar_status = 0



            query = """SELECT so.partner_id, sum(coalesce(so.total_amount,0)) openso from dmpi_crm_sale_order so
            left join dmpi_crm_invoice inv on inv.contract_id = so.contract_id and inv.odoo_so_no = so.name  
            where so.valid = True and inv.id is NULL and so.partner_id = %s
            group by so.partner_id
            """ % self.partner_id.id

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


    @api.onchange('sale_order_ids')
    def on_change_sale_order_ids(self):
        for rec in self:
            print(rec)


    @api.onchange('contract_line_ids')
    def on_change_contract_line_ids(self):
        lines = []
        contract_lines = []
        errors = []
        error_count = 0
        po_line_no = 0

        contract_total = 0.0

        for rec in self:
            for l in rec.contract_line_ids:
                items = []

                odoo_po_no  = rec.name
                sap_doc_type  =  rec.contract_type.name
                sales_org =  rec.partner_id.sales_org
                dist_channel =   rec.partner_id.dist_channel
                division =   rec.partner_id.division

                sold_to = rec.partner_id.customer_code
                ship_to = l.partner_id.customer_code
                ship_to_dest = l.partner_id.customer_code

                plant = rec.partner_id.plant
                original_ship_to = ""

                try:
                    if rec.partner_id.alt_customer_code:
                        sold_to = rec.partner_id.alt_customer_code
                        ship_to_dest = rec.partner_id.alt_customer_code 
                        ship_to = l.partner_id.alt_customer_code
                        original_ship_to = rec.partner_id.final_ship_to 
                    if rec.partner_id.alt_dist_channel:
                        dist_channel = rec.partner_id.alt_dist_channel
                    if rec.partner_id.alt_division:
                        division = rec.partner_id.alt_division
                    if rec.partner_id.alt_customer_code:
                        sold_to = rec.partner_id.alt_customer_code

                except:
                    pass
                    # print("SBFTI PASS")
                
                ref_po_no =  rec.customer_ref

                po_date = datetime.strptime(rec.po_date, '%Y-%m-%d')
                po_date = po_date.strftime('%Y%m%d')

                valid_from = datetime.strptime(rec.valid_from, '%Y-%m-%d')
                valid_from = valid_from.strftime('%Y%m%d')

                valid_to = datetime.strptime(rec.valid_to, '%Y-%m-%d')
                valid_to =   valid_to.strftime('%Y%m%d')



                so_no = l.so_no

                rdd = datetime.strptime(l.rdd, '%Y-%m-%d')
                rdd =   rdd.strftime('%Y%m%d')


                

                material = False
                so_line_no = 0

                if l.p5 > 0:

                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P5'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                    except:
                        pass
                    qty = l.p5
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))

                if l.p6 > 0:
                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P6'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                    except:
                        pass
                    qty = l.p6
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))
                if l.p7 > 0:
                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P7'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                    except:
                        pass
                    qty = l.p7
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))
                if l.p8 > 0:
                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P8'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                    except:
                        pass
                    qty = l.p8
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))
                if l.p9 > 0:
                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P9'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                    except:
                        pass
                    qty = l.p9
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))
                if l.p10 > 0:
                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P10'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                        print(material)
                    except:
                        pass
                    qty = l.p10
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))

                if l.p12 > 0:
                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P12'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                    except:
                        pass
                    qty = l.p12
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))


                if l.p5c7 > 0:
                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P5C7'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                    except:
                        pass
                    qty = l.p5c7
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))
                if l.p6c8 > 0:
                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P6C8'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                    except:
                        pass
                    qty = l.p6c8
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))
                if l.p7c9 > 0:
                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P7C9'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                    except:
                        pass
                    qty = l.p7c9
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))
                if l.p8c10 > 0:
                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P8C10'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                    except:
                        pass
                    qty = l.p8c10
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))
                if l.p9c11 > 0:
                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P9C11'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                    except:
                        pass
                    qty = l.p9c11
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))
                if l.p10c12 > 0:
                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P10C12'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                    except:
                        pass
                    qty = l.p10c12
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))
                if l.p12c20 > 0:
                    po_line_no += 10
                    so_line_no += 10
                    try:
                        material = self.env['dmpi.crm.product'].search([('code','=','P12C20'),('partner_id','=',rec.partner_id.id)],limit=1)[0].sku or False
                    except:
                        pass
                    qty = l.p12c20
                    uom = 'CAS'
                    items.append((odoo_po_no,sap_doc_type,sales_org,dist_channel,division,sold_to,ship_to,
                        ref_po_no,po_date,valid_from,valid_to,ship_to_dest,po_line_no,material,qty,uom,
                        so_no,rdd,so_line_no,plant,original_ship_to))

                lines.append(items)

                crown_total = l.p5+l.p6+l.p7+l.p8+l.p9+l.p10+l.p12
                crownless_total = l.p5c7+l.p6c8+l.p7c9+l.p8c10+l.p9c11+l.p10c12+l.p12c20

                contract_total +=  (crown_total+crownless_total)*10

                crown_totals = crown_total+crownless_total
                if crown_totals > 1500:
                    error_count += 1
                    errors.append("%s Exceeded the 1500 limit" % crown_totals)

            rec.worksheet_item_text = lines
            rec.contract_total = contract_total
            rec.credit_after_sale = rec.credit_limit - rec.contract_total 
            if error_count > 0:
                rec.error_count = error_count
                rec.errors = errors
            else:
                rec.error_count = 0
                rec.errors = ""               



    @api.multi
    def action_release(self):
        for rec in self:
            rec.state = 'submitted'


    @api.multi
    def action_approve(self):
        for rec in self:
            sheet = eval(rec.worksheet_item_text)

            for so in sheet:
                lines = []
                so_no = ""


                #so = {}
                so_line = []
                total_amount = 0.0

                for l in so:
                    so_no = "SO00000%s" % l[16]

                    line = [l[0],rec.sap_cn_no,so_no,'ZXSO',l[2],l[3],l[4],l[5],l[6],l[7],l[8],l[17],l[12],l[18],l[13],l[14],l[15],l[19]]
                    if l[20] != '':
                        line = [l[0],rec.sap_cn_no,so_no,'ZKM3',l[2],l[3],l[4],l[5],l[6],l[7],l[8],l[17],l[12],l[18],l[13],l[14],l[15],l[19],l[20]]

                    lines.append(line)
                    
                    print (l)
                    # odoo_po_no  
                    # sap_contract_no 
                    # odoo_so_no  
                    # sap_doc_type    
                    # sales_org   
                    # dist_channel    
                    # division    
                    # sold_to 
                    # ship_to 
                    # ref_po_no   
                    # po_date 
                    # rdd 
                    # po_line_no  
                    # so_line_no  
                    # material    
                    # qty 
                    # uom 
                    # plant   
                    # reject_reason   
                    # so_alt_item 
                    # usage


                    # so = {
                    #     'name' : so_no,
                    #     'so_no' : so_no,
                    #     #'sap_so_no' :
                    #     'sap_doc_type' : 'ZXSO',
                    #     'contract_id' :
                    #     #'order_ids' :

                    #     'partner_id' :
                    #     'dest_country_id' :
                    #     'order_date' :
                    #     'estimated_date' :
                    #     'requested_deivery_date' :

                    #     'total_amount' :
                    # }



                print(lines)

            # rec.state = 'approved'


                filename = 'ODOO_SO_%s_%s.csv' % (so_no,datetime.now().strftime("%Y%m%d_%H%M%S"))
                path = '/tmp/%s' % filename

                with open(path, 'w') as f:
                    writer = csv.writer(f, delimiter='\t')
                    for l in lines:
                        writer.writerow(l)


                #TRANSFER TO REMOTE SERVER
                h = self.env['dmpi.crm.config'].search([('default','=',True)],limit=1)
                host_string = h.ssh_user + '@' + h.ssh_host + ':22'
                env.hosts.append(host_string)
                env.passwords[host_string] = h.ssh_pass

                localpath = path

                path = '%s/%s' % (h.inbound_so,filename)
                remotepath = path

                execute(file_send,localpath,remotepath)
                rec.sent_to_sap = True
                rec.state = 'approved'
                # rec.worksheet_item_text = contract




    @api.multi
    def action_submit(self):
        for rec in self:

            #Sort the sale order line ids
            for so in rec.sale_order_ids:
                line_no = 0
                for sol in so.order_ids:
                    line_no += 10
                    sol.so_line_no = line_no




            #OLD Contract style
            sheet = eval(rec.worksheet_item_text)
            lines = []

            for so in sheet:
                for l in so:
                    lines.append(l)

            print(lines)
            

            if rec.name == 'Draft':
                self._cr.execute("""SELECT string_agg (DISTINCT q1.pr,''),MAX (cn_no)+1 FROM (SELECT*FROM (
                    SELECT cn_no_prefix AS pr,0 AS cn_no FROM dmpi_crm_config WHERE "default" IS TRUE AND active IS TRUE ORDER BY create_date DESC LIMIT 1) AS pref UNION ALL 
                    SELECT '' AS pr,MAX (cn_no) cn_no FROM dmpi_crm_sale_contract) AS q1 LIMIT 1
                """)
                prefix,cn_no = self._cr.fetchone()
                name = "%s%s" % (prefix,'{0:08d}'.format(cn_no))
                rec.cn_no = cn_no
                rec.name = name


            filename = 'ODOO_PO_%s_%s.csv' % (rec.name,datetime.now().strftime("%Y%m%d_%H%M%S"))
            path = '/tmp/%s' % filename

            with open(path, 'w') as f:
                writer = csv.writer(f, delimiter='\t')
                for l in lines:
                    writer.writerow([l[0],l[1],l[2],l[3],l[4],l[5],l[6],l[7],l[8],l[9],l[10],l[11],l[12],l[13],l[14],l[15]])


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

            if rec.ar_status > 0 or rec.credit_after_sale < 0:
                rec.state = 'soa'
            else:
                rec.state = 'submitted'
            # rec.worksheet_item_text = contract





    @api.multi
    def action_submit_contract(self):
        for rec in self:
            #Finalize Contract Line Numbers
            contract_line_no = 0
            sale_orders = []
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
                        'plant': l.plant,
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
            rec.write({'state':'confirmed'})


    @api.multi
    def action_approve_contract(self):
        for rec in self:
            for so in rec.sale_order_ids:
                if so.name == 'Draft' or '':
                    seq  = self.env['ir.sequence'].next_by_code('dmpi.crm.sale.order')
                    so.write({'name': seq})
            rec.write({'state':'approved'})


    @api.multi
    def action_release_contract(self):
        for rec in self:
            rec.write({'state':'confirmed'})


    @api.multi
    def action_send_contract_to_sap(self):
        for rec in self:

            filename = 'ODOO_PO_%s_%s.csv' % (rec.name,datetime.now().strftime("%Y%m%d_%H%M%S"))
            path = '/tmp/%s' % filename

            lines = []
            for so in rec.sale_order_ids:
                for sol in so.order_ids:

                    ref_po_no = rec.name
                    if rec.customer_ref != '':
                        ref_po_no = rec.customer_ref

                    po_date = datetime.strptime(rec.po_date, '%Y-%m-%d')
                    po_date = po_date.strftime('%Y%m%d')

                    valid_from = datetime.strptime(rec.valid_from, '%Y-%m-%d')
                    valid_from = valid_from.strftime('%Y%m%d')

                    valid_to = datetime.strptime(rec.valid_to, '%Y-%m-%d')
                    valid_to =   valid_to.strftime('%Y%m%d')


                    line = {
                        'odoo_po_no' : rec.name,
                        'sap_doc_type' : rec.contract_type.name,
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
                        'po_line_no' : so.contract_line_no,
                        'material' : sol.product_id.sku,
                        'qty' : sol.qty,
                        'uom' : 'CAS',
                    }

                    #SBFTI SCENARIO
                    # 1.       If key-user uses the customer sold-to as 13046 and any related ship-to, kindly send in the csv file the sold to and ship-to as 14067.
                    # 2.       In this scenario sale organization is 1050 distribution channel is 35 and division is 01.
                    # 3.       The value of the “Final Ship-to” column which is “Your Reference” field i.e. VBKD-IHREZ in SAP should be the related ship-to chosen by the key-user from point 1 above.
                    # 4.       The sales order document type sent in the csv file should be ZKM3 instead of ZXSO when this is the scenario (i.e. sold-to customer is 13046).  

                    if rec.partner_id.alt_customer_code:
                        line['sold_to'] = rec.partner_id.alt_customer_code
                        line['ship_to'] = rec.partner_id.alt_customer_code
                        line['ship_to_dest'] = rec.partner_id.alt_customer_code 
                    if rec.partner_id.alt_dist_channel:
                        line['dist_channel'] = rec.partner_id.alt_dist_channel
                    if rec.partner_id.alt_division:
                        line['division'] = rec.partner_id.alt_division
                    if rec.partner_id.alt_customer_code:
                        line['sold_to'] = rec.partner_id.alt_customer_code


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

            # rec.write({'state':'processing'})



class DmpiCrmSaleContractLine(models.Model):
    _name = 'dmpi.crm.sale.contract.line'
    _order = 'sequence'


    def _get_totals(self):
        for rec in self:
            rec.total_crown = rec.p5+rec.p6+rec.p7+rec.p8+rec.p9+rec.p10+rec.p12
            rec.total_crownless = rec.p5c7+rec.p6c8+rec.p7c9+rec.p8c10+rec.p9c11+rec.p10c12+rec.p12c20
            rec.total = rec.total_crown + rec.total_crownless

    @api.onchange('destination_id','p5','p6','p7','p8','p9','p10','p12','p5c7','p6c8','p7c9','p8c10','p9c11','p10c12','p12c20')
    def _on_change_qty(self):
        for rec in self:

            if rec.p5 != 0:
                rec.p5 = round_qty(75,rec.p5)
            if rec.p6 != 0:
                rec.p6 = round_qty(75,rec.p6)
            if rec.p7 != 0:
                rec.p7 = round_qty(75,rec.p7)
            if rec.p8 != 0:
                rec.p8 = round_qty(75,rec.p8)
            if rec.p9 != 0:
                rec.p9 = round_qty(75,rec.p9)
            if rec.p10 != 0:
                rec.p10 = round_qty(75,rec.p10)
            if rec.p12 != 0:
                rec.p12 = round_qty(75,rec.p12)

            if rec.p5c7 != 0:
                rec.p5c7 = round_qty(75,rec.p5c7)
            if rec.p6c8 != 0:
                rec.p6c8 = round_qty(75,rec.p6c8)
            if rec.p7c9 != 0:
                rec.p7c9 = round_qty(75,rec.p7c9)
            if rec.p8c10 != 0:
                rec.p8c10 = round_qty(75,rec.p8c10)
            if rec.p9c11 != 0:
                rec.p9c11 = round_qty(75,rec.p9c11)
            if rec.p10c12 != 0:
                rec.p10c12 = round_qty(75,rec.p10c12)
            if rec.p12c20 != 0:
                rec.p12c20 = round_qty(75,rec.p12c20)

            rec.total_crown = rec.p5+rec.p6+rec.p7+rec.p8+rec.p9+rec.p10+rec.p12
            rec.total_crownless = rec.p5c7+rec.p6c8+rec.p7c9+rec.p8c10+rec.p9c11+rec.p10c12+rec.p12c20
            rec.total = rec.total_crown + rec.total_crownless



            

    contract_id     = fields.Many2one('dmpi.crm.sale.contract', "Contract ID")
    sequence        = fields.Integer('Sequence')
    partner_id      = fields.Many2one('dmpi.crm.partner', "Destination")
    p5              = fields.Integer(string="P5")
    p6              = fields.Integer(string="P6")
    p7              = fields.Integer(string="P7")
    p8              = fields.Integer(string="P8")
    p9              = fields.Integer(string="P9")
    p10             = fields.Integer(string="P10")
    p12             = fields.Integer(string="P12")
    p5c7            = fields.Integer(string="P5C7")
    p6c8            = fields.Integer(string="P6C8")
    p7c9            = fields.Integer(string="P7C9")
    p8c10           = fields.Integer(string="P8C10")
    p9c11           = fields.Integer(string="P9C11")
    p10c12          = fields.Integer(string="P10C12")
    p12c20          = fields.Integer(string="P12C20")
    total_crown     = fields.Integer(string="Total", compute='_get_totals')
    total_crownless = fields.Integer(string="Total", compute='_get_totals')
    total           = fields.Integer(string="Total", compute='_get_totals')
    rdd             = fields.Date(string="RDD", default=lambda *a:datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    so              = fields.Boolean(string="SO", default=True)
    so_no           = fields.Integer(string="SO No")

    p5_visible              = fields.Boolean(string="P5",compute='_compute_visible')
    p6_visible              = fields.Boolean(string="P6",compute='_compute_visible')
    p7_visible              = fields.Boolean(string="P7",compute='_compute_visible')
    p8_visible              = fields.Boolean(string="P8",compute='_compute_visible')
    p9_visible              = fields.Boolean(string="P9",compute='_compute_visible')
    p10_visible             = fields.Boolean(string="P10",compute='_compute_visible')
    p12_visible             = fields.Boolean(string="P12",compute='_compute_visible')
    p5c7_visible            = fields.Boolean(string="P5C7",compute='_compute_visible')
    p6c8_visible            = fields.Boolean(string="P6C8",compute='_compute_visible')
    p7c9_visible            = fields.Boolean(string="P7C9",compute='_compute_visible')
    p8c10_visible           = fields.Boolean(string="P8C10",compute='_compute_visible')
    p9c11_visible           = fields.Boolean(string="P9C11",compute='_compute_visible')
    p10c12_visible          = fields.Boolean(string="P10C12",compute='_compute_visible')
    p12c20_visible          = fields.Boolean(string="P12C20",compute='_compute_visible')


    @api.one
    @api.depends(
        'contract_id.partner_id',
    )
    def _compute_visible(self):
        active_products = [x.code for x in self.env['dmpi.crm.product'].search([('partner_id','=',self.contract_id.partner_id.id)])]
        print(active_products)
        if 'P5' in active_products:
            self.p5_visible = True
        else:
            self.p5_visible = False

        if 'P6' in active_products:
            self.p6_visible = True
        else:
            self.p6_visible = False

        if 'P7' in active_products:
            self.p7_visible = True
        else:
            self.p7_visible = False

        if 'P8' in active_products:
            self.p8_visible = True
        else:
            self.p8_visible = False

        if 'P9' in active_products:
            self.p9_visible = True
        else:
            self.p9_visible = False

        if 'P10' in active_products:
            self.p10_visible = True
        else:
            self.p10_visible = False

        if 'P12' in active_products:
            self.p12_visible = True
        else:
            self.p12_visible = False

        if 'P5C7' in active_products:
            self.p5c7_visible = True
        else:
            self.p5c7_visible = False

        if 'P6C8' in active_products:
            self.p6c8_visible = True
        else:
            self.p6c8_visible = False

        if 'P7C9' in active_products:
            self.p7c9_visible = True
        else:
            self.p7c9_visible = False

        if 'P8C10' in active_products:
            self.p8c10_visible = True
        else:
            self.p8c10_visible = False

        if 'P9C11' in active_products:
            self.p9c11_visible = True
        else:
            self.p9c11_visible = False

        if 'P10C12' in active_products:
            self.p10c12_visible = True
        else:
            self.p10c12_visible = False

        if 'P12C20' in active_products:
            self.p12c20_visible = True
        else:
            self.p12c20_visible = False


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


    @api.multi
    def action_submit_so(self):
        for rec in self:
            print("SUBMIT SO to SAP")


    @api.onchange('ship_to_id')
    def on_change_ship_to(self):
        self.notify_id = self.ship_to_id.id
        self.sales_org = self.contract_id.partner_id.sales_org
        self.plant = self.contract_id.partner_id.plant
        # sales_org = self.env['dmpi.crm.partner'].search([('customer_code','=',self.ship_to.customer_code)], limit=1)[0].sales_org
        # if sales_org:
        #     self.sales_org = sales_org
        # print("Onchange Partner")


    @api.depends('p5','p6','p7','p8','p9','p10','p12','p5c7','p6c8','p7c9','p8c10','p9c11','p10c12','p12c20','order_ids')
    def get_totals(self):
        
        for rec in self:
            total_amount = 0.0
            for l in rec.order_ids:
                total_amount += l.total
                if l.product_code == 'P5': rec.p5 += l.qty
                if l.product_code == 'P6': rec.p6 += l.qty
                if l.product_code == 'P7': rec.p7 += l.qty
                if l.product_code == 'P8': rec.p8 += l.qty
                if l.product_code == 'P9': rec.p9 += l.qty
                if l.product_code == 'P10': rec.p10 += l.qty
                if l.product_code == 'P12': rec.p12 += l.qty
                if l.product_code == 'P5C7': rec.p5c7 += l.qty
                if l.product_code == 'P6C8': rec.p6c8 += l.qty
                if l.product_code == 'P7C9': rec.p7c9 += l.qty
                if l.product_code == 'P8C10': rec.p8c10 += l.qty
                if l.product_code == 'P9C11': rec.p9c11 += l.qty
                if l.product_code == 'P10C12': rec.p10c12 += l.qty
                if l.product_code == 'P12C20': rec.p12c20 += l.qty

            rec.total_amount = total_amount
            rec.total_crown = rec.p5+rec.p6+rec.p7+rec.p8+rec.p9+rec.p10+rec.p12
            rec.total_crownless = rec.p5c7+rec.p6c8+rec.p7c9+rec.p8c10+rec.p9c11+rec.p10c12+rec.p12c20
            rec.total_qty = rec.total_crown + rec.total_crownless

        
    def _get_doc_types(self):
        res = [(r.name,r.description) for r in self.env['dmpi.crm.sap.doc.type'].search([])]
        return res

    def _get_default_doc_types(self):
        res = self.env['dmpi.crm.sap.doc.type'].search([('default','=',True)])[0].name
        return res

    @api.depends('name','sap_so_no')
    def _get_name_disp(self):
        self.name_disp = "%s/%s" % (self.name, self.sap_so_no)


    @api.multi
    def toggle_valid(self):
        self.write({'valid': not self.valid})
        return True

        
    name_disp = fields.Char("Display No.", compute='_get_name_disp')
    name = fields.Char("CRM SO No.", default="Draft")
    plant = fields.Char("Plant")
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Contract ID")
    contract_line_no = fields.Integer("Contract Line No.")
    so_no = fields.Integer("SO Num")
    sap_so_no = fields.Char("SAP SO no.")
    sap_so_date = fields.Date("SAP SO Date")
    sap_doc_type = fields.Selection(_get_doc_types,"Doc Type",default=_get_default_doc_types)
    order_ids = fields.One2many('dmpi.crm.sale.order.line','order_id','Order IDs')
    valid = fields.Boolean("Valid Order", default=True)


    p5              = fields.Integer(string="P5", compute='get_totals')
    p6              = fields.Integer(string="P6", compute='get_totals')
    p7              = fields.Integer(string="P7", compute='get_totals')
    p8              = fields.Integer(string="P8", compute='get_totals')
    p9              = fields.Integer(string="P9", compute='get_totals')
    p10             = fields.Integer(string="P10", compute='get_totals')
    p12             = fields.Integer(string="P12", compute='get_totals')
    p5c7            = fields.Integer(string="P5C7", compute='get_totals')
    p6c8            = fields.Integer(string="P6C8", compute='get_totals')
    p7c9            = fields.Integer(string="P7C9", compute='get_totals')
    p8c10           = fields.Integer(string="P8C10", compute='get_totals')
    p9c11           = fields.Integer(string="P9C11", compute='get_totals')
    p10c12          = fields.Integer(string="P10C12", compute='get_totals')
    p12c20          = fields.Integer(string="P12C20", compute='get_totals')
    total_crown     = fields.Integer(string="w/Crown", compute='get_totals')
    total_crownless = fields.Integer(string="Crownlesss", compute='get_totals')
    total_qty       = fields.Integer(string="Total", compute='get_totals')



    p5_id              = fields.Many2one("dmpi.crm.product", string="P5", compute='_get_product_codes')
    p6_id              = fields.Many2one("dmpi.crm.product", string="P6", compute='_get_product_codes')
    p7_id              = fields.Many2one("dmpi.crm.product", string="P7", compute='_get_product_codes')
    p8_id              = fields.Many2one("dmpi.crm.product", string="P8", compute='_get_product_codes')
    p9_id              = fields.Many2one("dmpi.crm.product", string="P9", compute='_get_product_codes')
    p10_id             = fields.Many2one("dmpi.crm.product", string="P10", compute='_get_product_codes')
    p12_id             = fields.Many2one("dmpi.crm.product", string="P12", compute='_get_product_codes')
    p5c7_id            = fields.Many2one("dmpi.crm.product", string="P5C7", compute='_get_product_codes')
    p6c8_id            = fields.Many2one("dmpi.crm.product", string="P6C8", compute='_get_product_codes')
    p7c9_id            = fields.Many2one("dmpi.crm.product", string="P7C9", compute='_get_product_codes')
    p8c10_id           = fields.Many2one("dmpi.crm.product", string="P8C10", compute='_get_product_codes')
    p9c11_id           = fields.Many2one("dmpi.crm.product", string="P9C11", compute='_get_product_codes')
    p10c12_id          = fields.Many2one("dmpi.crm.product", string="P10C12", compute='_get_product_codes')
    p12c20_id          = fields.Many2one("dmpi.crm.product", string="P12C20", compute='_get_product_codes')



    partner_id = fields.Many2one('dmpi.crm.partner',"Customer", related='contract_id.partner_id')
    ship_to_id = fields.Many2one("dmpi.crm.ship.to","Ship to Party")
    notify_id = fields.Many2one("dmpi.crm.ship.to","Notify Party")
    sold_via_id = fields.Many2one('dmpi.crm.partner',"Sold Via")
    # notify_partner_id = fields.Many2one('dmpi.crm.partner',"Notify Party")
    sales_org = fields.Char("Sales Org")
    dest_country_id = fields.Many2one('dmpi.crm.country', 'Destination')
    order_date = fields.Date("Order Date")
    estimated_date = fields.Date("Estimated Date")
    shell_color = fields.Char("Shell Color")
    ship_line = fields.Char("Ship Line")
    requested_deivery_date = fields.Date("Req. Date")
    notes = fields.Text("Notes/Remarks", compute='display_summary')

    total_amount = fields.Float('Total', compute='get_totals')

    @api.depends('p5','p6','p7','p8','p9','p10','p12','p5c7','p6c8','p7c9','p8c10','p9c11','p10c12','p12c20',
        'p5_id','p6_id','p7_id','p8_id','p9_id','p10_id','p12_id','p5c7_id','p6c8_id','p7c9_id','p8c10_id','p9c11_id','p10c12_id','p12c20_id')
    def display_summary(self):

        headers = """ 
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P5</th>
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P6</th>
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P7</th>
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P8</th>
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P9</th>
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P10</th>
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P12</th>
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P5C7</th>
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P6C8</th>
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P7C9</th>
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P8C10</th>
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P9C11</th>
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P10C12</th>
            <th data-original-title="" title="" style="text-align: right; color:#FFF; background-color: #78717e;" >P12C20</th>
        """ 

        rows = """
            <td class="o_data_cell o_list_number">%s</td>
            <td class="o_data_cell o_list_number">%s</td>
            <td class="o_data_cell o_list_number">%s</td>
            <td class="o_data_cell o_list_number">%s</td>
            <td class="o_data_cell o_list_number">%s</td>
            <td class="o_data_cell o_list_number">%s</td>
            <td class="o_data_cell o_list_number">%s</td>
            <td class="o_data_cell o_list_number">%s</td>
            <td class="o_data_cell o_list_number">%s</td>
            <td class="o_data_cell o_list_number">%s</td>
            <td class="o_data_cell o_list_number">%s</td>
            <td class="o_data_cell o_list_number">%s</td>
            <td class="o_data_cell o_list_number">%s</td>
            <td class="o_data_cell o_list_number">%s</td>
        """ % (self.p5, self.p6, self.p7, self.p8, self.p9, self.p10, self.p12, 
            self.p5c7, self.p6c8, self.p7c9, self.p8c10, self.p9c11, self.p10c12, self.p12c20)


        self.notes = """
            <h3>SUMMARY</h3>
            <table class="o_list_view table table-condensed table-striped o_list_view_ungrouped">
                <thead>
                    <tr>
                        %s
                    </tr>
                </thead>
                <tbody>
                    <tr class="o_data_row">
                        %s
                    </tr>
                </tbody>
            </table>
        """ %(headers,rows)



    @api.depends('contract_id')
    def _get_product_codes(self):
        if self.contract_id.partner_id.id:
            query = """SELECT p.id, p.code, p.sku from dmpi_crm_product p
                        where p.code != '' and p.partner_id = %s""" % self.contract_id.partner_id.id

            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()

            for r in result:
                if r['code'].upper() == 'P5': self.p5_id = r['id']
                if r['code'].upper() == 'P6': self.p6_id = r['id']
                if r['code'].upper() == 'P7': self.p7_id = r['id']
                if r['code'].upper() == 'P8': self.p8_id = r['id']
                if r['code'].upper() == 'P9': self.p9_id = r['id']
                if r['code'].upper() == 'P10': self.p10_id = r['id']
                if r['code'].upper() == 'P12': self.p12_id = r['id']
                if r['code'].upper() == 'P5C7': self.p5c7_id = r['id']
                if r['code'].upper() == 'P6C8': self.p6c8_id = r['id']
                if r['code'].upper() == 'P7C9': self.p7c9_id = r['id']
                if r['code'].upper() == 'P8C10': self.p8c10_id = r['id']
                if r['code'].upper() == 'P9C11': self.p9c11_id = r['id']
                if r['code'].upper() == 'P10C12': self.p10c12_id = r['id']
                if r['code'].upper() == 'P12C20': self.p12c20_id = r['id']


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
        query = """SELECT sales_org, customer_code, material,freight_term,amount,currency,uom 
                from dmpi_crm_product_price_list_item i
                where '%s'::DATE between valid_from and valid_to
                and customer_code = '%s' and material = '%s'
                limit 1 """ % (date,customer_code,material)
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

    order_ids = fields.One2many('customer.crm.sale.order.line','order_id','Order IDs')



class CustomerCrmSaleOrderLine(models.Model):
    _name = 'customer.crm.sale.order.line'
    _inherit = ['dmpi.crm.sale.order.line']

    order_id = fields.Many2one('customer.crm.sale.order','Sale Order ID', ondelete='cascade')


class DmpiCrmDr(models.Model):
    _name = 'dmpi.crm.dr'

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








