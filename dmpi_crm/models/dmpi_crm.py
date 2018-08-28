# -*- coding: utf-8 -*-

from odoo import _
from odoo import models, api, fields
from odoo.osv import expression
from odoo.exceptions import ValidationError, AccessError, UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

import csv
import sys
import math

import base64
from tempfile import TemporaryFile
import tempfile
import re
from dateutil.parser import parse



def read_data(data):
    if data:
        fileobj = TemporaryFile("w+")
        fileobj.write(base64.b64decode(data).decode('utf-8'))
        fileobj.seek(0)
        line = csv.reader(fileobj, quotechar='"', delimiter=',', quoting=csv.QUOTE_ALL, skipinitialspace=True)
        return line


def parse_date(date):
    try:
        return parse(date)
    except:
        return False


class DmpiCrmPartner(models.Model):
    _name = 'dmpi.crm.partner'
    _inherit = ['mail.thread']



    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('customer_code', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        accounts = self.search(domain + args, limit=limit)
        return accounts.name_get()


    @api.multi
    @api.depends('name', 'customer_code')
    def name_get(self):
        result = []
        for rec in self:
            customer_code = ''
            if rec.customer_code:
                customer_code = rec.customer_code
            name = rec.name+' [' + customer_code+ ']'
            result.append((rec.id, name))
        return result



    name            = fields.Char("Name")
    email           = fields.Char("Email")
    active          = fields.Boolean("Active", default=True)
    default_plant   = fields.Many2one('dmpi.crm.plant',"Default Plant")
    customer_code   = fields.Char("Code")
    function        = fields.Selection([('bp','Billto and Payer'),('so','Shipto'),('sosh','Soldto or Shipto')],"Partner Function")
    account_group   = fields.Char("Account Group")
    city            = fields.Char("City")
    city_code       = fields.Char("City Code")
    street          = fields.Char("Street")
    postal_code     = fields.Char("Postal Code")
    phone           = fields.Char("Telephone")
    fax             = fields.Char("Fax")
    sales_org       = fields.Char("Sales Org")
    dist_channel    = fields.Char("Distribution Channel")
    division        = fields.Char("Division")
    plant           = fields.Char("Plant")
    ship_to_ids = fields.One2many('dmpi.crm.ship.to','partner_id','Ship to Codes')


    #DEFAULTS
    default_validity = fields.Integer("Default Validity", default=30)

    # #SBFTI          
    # alt_customer_code = fields.Char("ALT Code")
    # alt_sales_org       = fields.Char("ALT Sales Org")
    # alt_dist_channel    = fields.Char("ALT Distribution Channel")
    # alt_division        = fields.Char("ALT Division")
    # final_ship_to       = fields.Char("Final Ship to")


    ar_records = fields.One2many('dmpi.crm.partner.ar','partner_id','AR Records')




class DmpiCrmPartnerCreditLimit(models.Model):
    _name = 'dmpi.crm.partner.credit.limit'

    customer_code       = fields.Char("Customer Code")
    credit_control_no   = fields.Char("Credit Control No")
    credit_limit        = fields.Float("Credit Limit")
    credit_exposure     = fields.Float("Credit Exposure")
    currency            = fields.Char("Currency")
    partner_id          = fields.Many2one('dmpi.crm.partner',"Partner")


class DmpiCrmPartnerAR(models.Model):
    _name = 'dmpi.crm.partner.ar'


    @api.depends('base_line_date','payment_term_days')
    def _get_date_overdue(self):
        for rec in self:
            print(rec.payment_term_days)
            date1 = datetime.strptime(rec.base_line_date, "%m/%d/%Y") + timedelta(days=+7)
            date2 = datetime.now()
            # print ((date2-date1).days)
            rec.days_overdue = (date2-date1).days
            
    @api.depends('customer_code')
    def _get_partner(self):
        for rec in self:
            if rec.customer_no:
                customer = rec.customer_no.lstrip("0")
                partner = self.env['dmpi.crm.partner'].search([('customer_code','=',customer)],limit=1)
                if partner:
                    rec.partner_id_get = partner.id


    name                = fields.Char("AR ID")
    customer_code       = fields.Char("Customer Code")
    amount              = fields.Float("Amount")
    currency            = fields.Char("Currency")
    partner_id          = fields.Many2one('dmpi.crm.partner',"Customer")
    partner_id_get      = fields.Many2one('dmpi.crm.partner',"CustGet",compute='_get_partner')
    payment_term_days   = fields.Integer("Payment Term (Days)")
    days_overdue        = fields.Integer("Days Overdue", compute='_get_date_overdue')
    


    company_code= fields.Char("Company Code")
    customer_no= fields.Char("Customer Number")
    assignment_no= fields.Char("Assignment Number")
    fiscal_year= fields.Char("Fiscal Year")
    acct_doc_no= fields.Char("Accounting Document Number")
    psting_date= fields.Char("Posting Date in the Document")
    doc_date= fields.Char("Document Date in Document")
    local_curr= fields.Char("Local Currency")
    ref_doc= fields.Char("Reference Document Number")
    doc_type= fields.Char("Document Type")
    fiscal_period= fields.Char("Fiscal Period")
    amt_in_loc_cur= fields.Float("Amount in Local Currency")
    base_line_date= fields.Char("Baseline Date for Due Date Calculation")
    terms= fields.Char("Terms of Payment Key")
    cash_disc_days= fields.Char("Cash Discount Days 1")
    acct_doc_no2= fields.Char("Accounting Document Number")
    acct_doc_num_line= fields.Char("Number of Line Item Within Accounting Document")
    acct_type= fields.Char("Account Type")
    debit_credit= fields.Char("Debit/Credit Indicator")
    amt_in_loc_cur2= fields.Float("Amount in Local Currency")
    assign_no= fields.Char("Assignment Number")
    gl_acct_no= fields.Char("G/L Account Number")
    gl_acct_no2= fields.Char("G/L Account Number")
    customer_no2= fields.Char("Customer Number")

    # active=fields.Boolean("Active", default=True)
    line_ids = fields.One2many('dmpi.crm.partner.ar.line','ar_id', "AR Line Items", compute="_line_ids")



    @api.depends('acct_doc_no')
    def _line_ids(self):
        for rec in self:
            rec.line_ids = self.env['dmpi.crm.partner.ar.line'].search([('acct_doc_no', '=', rec.acct_doc_no)])


class DmpiCrmPartnerARLine(models.Model):
    _name = 'dmpi.crm.partner.ar.line'
    _inherit = 'dmpi.crm.partner.ar'

    @api.depends('acct_doc_no')
    def _get_ar_id(self):
        self.ar_id = self.env['dmpi.crm.partner.ar'].search([('acct_doc_no','=',self.acct_doc_no)], limit=1)[0].id


    ar_id = fields.Many2one('dmpi.crm.partner.ar', "AR Header")
    line_ids = fields.Boolean("Null Line IDs", default=False)


    # name                = fields.Char("AR ID")
    # customer_code       = fields.Char("Customer Code")
    # amount              = fields.Float("Amount")
    # currency            = fields.Char("Currency")
    # partner_id          = fields.Many2one('dmpi.crm.partner',"Customer")
    # partner_id_get      = fields.Many2one('dmpi.crm.partner',"CustGet",compute='_get_partner')
    # payment_term_days   = fields.Integer("Payment Term (Days)")
    # days_overdue        = fields.Integer("Days Overdue", compute='_get_date_overdue')
    


    # company_code= fields.Char("Company Code")
    # customer_no= fields.Char("Customer Number")
    # assignment_no= fields.Char("Assignment Number")
    # fiscal_year= fields.Char("Fiscal Year")
    # acct_doc_no= fields.Char("Accounting Document Number")
    # psting_date= fields.Char("Posting Date in the Document")
    # doc_date= fields.Char("Document Date in Document")
    # local_curr= fields.Char("Local Currency")
    # ref_doc= fields.Char("Reference Document Number")
    # doc_type= fields.Char("Document Type")
    # fiscal_period= fields.Char("Fiscal Period")
    # amt_in_loc_cur= fields.Char("Amount in Local Currency")
    # base_line_date= fields.Char("Baseline Date for Due Date Calculation")
    # terms= fields.Char("Terms of Payment Key")
    # cash_disc_days= fields.Char("Cash Discount Days 1")
    # acct_doc_no2= fields.Char("Accounting Document Number")
    # acct_doc_num_line= fields.Char("Number of Line Item Within Accounting Document")
    # acct_type= fields.Char("Account Type")
    # debit_credit= fields.Char("Debit/Credit Indicator")
    # amt_in_loc_cur2= fields.Char("Amount in Local Currency")
    # assign_no= fields.Char("Assignment Number")
    # gl_acct_no= fields.Char("G/L Account Number")
    # gl_acct_no2= fields.Char("G/L Account Number")
    # customer_no2= fields.Char("Customer Number")
    # active=fields.Boolean("Active", default=True)

class DmpiCrmShipTo(models.Model):
    _name = 'dmpi.crm.ship.to'


    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('destination', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        accounts = self.search(domain + args, limit=limit)
        return accounts.name_get()


    @api.multi
    @api.depends('name', 'destination')
    def name_get(self):
        result = []
        for rec in self:
            destination = ''
            if rec.destination:
                destination = rec.destination
            name = destination+' [' + rec.name+ ']'
            result.append((rec.id, name))
        return result

    @api.depends('customer_code')
    def _get_partner_id(self):
        for rec in self:
            if rec.customer_code:
                partner = self.env['dmpi.crm.partner'].search([('customer_code','=',rec.customer_code)],limit=1)
                if partner:
                    rec.partner_id = partner[0].id

    name = fields.Char("Commercial Code", required=True)
    name_disp = fields.Char("Ship to Code", placeholder="Shipto Code", related='name')
    customer_name = fields.Char("Corporate Name")
    customer_code = fields.Char("Customer Code")
    partner_id = fields.Many2one('dmpi.crm.partner',"Partner", compute='_get_partner_id', store=True)
    registered_address = fields.Text("Registered Address")
    contact_no = fields.Char("Contact No")
    contact_person = fields.Char("Contact Person")
    contact_person_email = fields.Char("Contact Email")
    destination = fields.Char("Destination")
    notify_party = fields.Char("Notify Party")
    notify_party_detail = fields.Text("Notify Party Details")
    ship_to_code = fields.Char("Ship to Code")
    ship_to = fields.Char("Consignee / Ship to")
    ship_to_detail = fields.Text("Consignee / Ship to Details")
    incoterm = fields.Char("Incoterm")
    mailing_address = fields.Text("Mailing Address")


class DmpiCrmContractType(models.Model):
    _name = 'dmpi.crm.contract.type'

    name = fields.Char("Code")
    description = fields.Char("Description")
    default = fields.Boolean("Default")


class DmpiCrmSapDocType(models.Model):
    _name = 'dmpi.crm.sap.doc.type'

    name = fields.Char("Code")
    description = fields.Char("Description")
    default = fields.Boolean("Default")


class DmpiCrmCountry(models.Model):
    _name = 'dmpi.crm.country'

    name        = fields.Char("Name")
    code        = fields.Char("Country Code")
    active      = fields.Boolean("Active", default=True)


# class DmpiCrmDestination(models.Model):
#     _name = 'dmpi.crm.destination'

#     name            = fields.Char("Name")
#     ship_to_code    = fields.Char("Ship to code")
#     dest_country_id = fields.Many2one('dmpi.crm.country', 'Destination')
#     active          = fields.Boolean("Active", default=True)



class DmpiCrmPlant(models.Model):
    _name = 'dmpi.crm.plant'

    name            = fields.Char("Plant")
    sorg            = fields.Char("SOrg")
    dist_channel    = fields.Char("Dist Channel")
    client          = fields.Char("Client")
    description     = fields.Char("Description")
    active          = fields.Boolean("Active", default=True)


class DmpiCrmSalesOrg(models.Model):
    _name = 'dmpi.crm.sales.org'

    name        = fields.Char("Name")
    client      = fields.Char("Client")
    sorg        = fields.Char("SOrg")
    client_desc = fields.Char("Client Description")
    ccode       = fields.Char("CCode")
    ccode_desc  = fields.Char("Description")


class DmpiCrmProduct(models.Model):
    _name = 'dmpi.crm.product'
    _sql_constraints = [
        ('unique_sku_customer', 'UNIQUE (sku,partner_id)', _('Similar Product Customer Combination Already Exist!'))
    ]



    def _get_product_class(self):
        group = 'product_class'
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

    def _get_product_crown(self):
        group = 'product_crown'
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


    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        accounts = self.search(domain + args, limit=limit)
        return accounts.name_get()


    @api.multi
    @api.depends('sku', 'code')
    def name_get(self):
        result = []
        for rec in self:
            code = ''
            if rec.code:
                code = rec.code
            sku = code+' (' + rec.sku+ ')'
            result.append((rec.id, sku))
        return result

    def _get_code(self):
        print("TODO: SET THE CODE BASED ON CROWN AND PSD")


    name            = fields.Char("Name")
    code            = fields.Char("Code")
    sku             = fields.Char("SKU")
    partner_id      = fields.Many2one('dmpi.crm.partner','Customer')
    product_class   = fields.Selection(_get_product_class,'Class')
    product_crown   = fields.Selection(_get_product_crown,'Crown')
    psd             = fields.Integer("PSD")
    weight          = fields.Float("Weight")
    box             = fields.Float("Box")
    volume          = fields.Float("Volume")
    crate_box       = fields.Float("Crate/Box")
    dest_country_id = fields.Many2one('dmpi.crm.country', 'Destination')
    active          = fields.Boolean("Active", default=True)



class DmpiCrmProductPriceList(models.Model):
    _name = 'dmpi.crm.product.price.list'
    _description = "Price List"
    _inherit = ['mail.thread']

    name = fields.Char("Name", required=True, track_visibility='onchange')
    description = fields.Char("Description", track_visibility='onchange')
    date = fields.Datetime("Date",track_visibility='onchange', default=fields.Datetime.now())
    week_no = fields.Integer("Week No")

    upload_filename  = fields.Char("Filename")
    upload_file    = fields.Binary("Upload File")
    item_ids        = fields.One2many('dmpi.crm.product.price.list.item','version_id','Items', track_visibility='onchange')
    state = fields.Selection([('draft','Draft'),('approved','Approved'),('cancelled','Cancelled')], "State", default='draft', track_visibility='onchange')



    @api.multi
    def action_approve(self):
        for rec in self:
            rec.write({'state':'approved'})

    @api.multi
    def action_cancel(self):
        for rec in self:
            rec.write({'state':'cancelled'})

    @api.multi
    def action_draft(self):
        for rec in self:
            rec.write({'state':'draft'})


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
                        item = {
                            'sales_org': r[0],
                            'customer_code': r[1],
                            'material': r[2],
                            'freight_term': r[3],
                            'amount': r[4],
                            'currency': r[5],
                            'uom': r[6],
                            'valid_from': parse_date(r[7]),
                            'valid_to': parse_date(r[8]),
                            'remarks': r[9],

                        }

                        if r[1]:
                            partner = self.env['dmpi.crm.partner'].search([('customer_code','=',r[1])])
                            if partner:
                                item['partner_id'] = partner[0].id
                        if r[2]:
                            product = self.env['dmpi.crm.product'].search([('sku','=',r[2])])
                            if product:
                                item['product_id'] = product[0].id


                        line_items.append((0,0,item))
                row_count+=1
            self.item_ids.unlink()
            self.item_ids = line_items



class DmpiCrmProductPriceListItem(models.Model):
    _name = 'dmpi.crm.product.price.list.item'

    
    version_id = fields.Many2one('dmpi.crm.product.price.list','Versin ID', ondelete="cascade")
    product_id = fields.Many2one('dmpi.crm.product',"Product ID")
    sales_org = fields.Char("Sales Org")
    customer_code = fields.Char("Customer Code")
    partner_id = fields.Many2one("dmpi.crm.partner","Customer")
    material = fields.Char("Material")
    freight_term = fields.Char("Freight")
    amount = fields.Float("Amount")
    currency = fields.Char("Currency")
    uom = fields.Char("Unit of Measure")
    valid_from = fields.Date("Valid From")
    valid_to = fields.Date("Valid To")
    remarks = fields.Char("Remarks")


class DmpiCRMSaleContractGroup(models.Model):
    _name = 'dmpi.crm.sale.contract.group'
    _description = 'Contract Group'

    name = fields.Char("Name")
    description = fields.Char("Description")


class DmpiCRMProductCode(models.Model):
    _name = 'dmpi.crm.product.code'
    _description = 'Product Code'
    _order = 'sequence'

    name = fields.Char("Name")
    description = fields.Char("Description")
    sequence = fields.Integer("Sequence")
    field_name = fields.Char("Field Name")
    active = fields.Boolean("Active")


class DmpiCRMPaymentTerms(models.Model):
    _name = 'dmpi.crm.payment.terms'
    _description = 'Payment Terms'

    name = fields.Char("Code")
    days = fields.Integer("Days Due")


class DmpiSAPPriceUpload(models.Model):
    _name = 'dmpi.sap.price.upload'
    #_description = 'DMS_A910_PRICEDOWNLOAD'

    name = fields.Char("Code")
    application = fields.Char("Application")
    condition_type = fields.Char("Condition Type")
    sales_org = fields.Char("Sales Org")
    customer = fields.Char("Customer")
    material = fields.Char("Material")
    valid_to_sap = fields.Char("Valid To (SAP)")
    valid_to = fields.Date("Valid To (Date)")
    condition_record = fields.Char("Application")
    condition_rate = fields.Float("Application")
    condition_currency = fields.Char("Currency")
    uom = fields.Char("Unit of Measure")



class DmpiCRMChannelGroup(models.Model):
    _name = 'dmpi.crm.channel.group'
    _description = 'DMPI CRM Channel Groups'

    name = fields.Char('Channel')
    code = fields.Char('Channel Code', help="unique identifier of channel")
    partner_ids = fields.Many2many('res.partner','dmpi_crm_channel_res_partner_rel','channel_id','partner_id', string='Subscribers',
        help="Email to partners for email notifications.")
    active = fields.Boolean('Active', default=True)



class MailMail(models.Model):
    _inherit = 'mail.mail'

    channel_group_id = fields.Many2one('dmpi.crm.channel.group', string='Channel Group')
    email_temp_id = fields.Many2one('mail.template', string='Template')


    @api.onchange('channel_group_id')
    def onchange_channel_group_id(self):
        if self.channel_group_id:
            email_string = []
            for p in self.channel_group_id.partner_ids:
                s = '%s <%s>' % (p.name, p.email)
                email_string.append(s)

            email_to = ' , '.join(email_string)
            self.email_to = email_to

        else:
            self.email_to = ''

    @api.onchange('email_temp_id')
    def onchange_email_temp_id(self):
        self.body_html = self.email_temp_id.body_html


class DmpiCRMFiscalYear(models.Model):
    _name = 'dmpi.crm.fiscal.year'

    name = fields.Char('Description')
    code = fields.Char('Code')
    date_from = fields.Date('Date From')
    date_to = fields.Date('Date To')
    status = fields.Selection([('open','Open'),('close','Close')], default='open', string="State")
    week_ids = fields.One2many('dmpi.crm.week','fiscal_year_id', string="Week Ids")


class DmpiCRMWeek(models.Model):
    _name = 'dmpi.crm.week'

    name = fields.Char('Description')
    week_no = fields.Integer('Week No.')
    date_from = fields.Date('Date From')
    date_to = fields.Date('Date To')
    fiscal_year_id = fields.Many2one('dmpi.crm.fiscal.year', string="Fiscal Year ID")


class DmpiCRMVariety(models.Model):
    _name = 'dmpi.crm.variety'

    name = fields.Char('Name')
    description = fields.Char('Description')
    active = fields.Boolean('Active', default=True)



class DmpiCrmActivityLog(models.Model):
    _name = 'dmpi.crm.activity.log'

    # @api.model
    # def create(self, vals):
    #     self.env['ir.model'].search([('')])
    #     vals['name'] = vals['model_id'],vals['record_id']
    #     res = super(DmpiCrmActivityLog, self).create(vals)
    #     return res

    name = fields.Char("Activity")
    description = fields.Text("Log")
    log_type = fields.Selection([('success','Success'),('fail','Fail'),('warning','Warning'),('note','Note')],"Type")
    model_id = fields.Many2one('ir.model',"Model")
    record_id = fields.Integer("Record ID")



class DmpiCrmDialogWizard(models.TransientModel):
    _name = 'dmpi.crm.dialog.wizard'

    name = fields.Char('Name')
    description = fields.Char('Description')

