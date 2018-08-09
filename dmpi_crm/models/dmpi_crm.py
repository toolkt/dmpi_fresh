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
from odoo import models, api, fields
from odoo.osv import expression
from odoo.exceptions import ValidationError, AccessError, UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


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


    #DEFAULTS
    default_validity = fields.Integer("Default Validity")

    #SBFTI          
    alt_customer_code = fields.Char("ALT Code")
    alt_sales_org       = fields.Char("ALT Sales Org")
    alt_dist_channel    = fields.Char("ALT Distribution Channel")
    alt_division        = fields.Char("ALT Division")
    final_ship_to       = fields.Char("Final Ship to")


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
            date1 = datetime.strptime(rec.base_line_date, DEFAULT_SERVER_DATE_FORMAT) + timedelta(days=+7)
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
                    rec.partner_id = partner.id


    name                = fields.Char("AR ID")
    customer_code       = fields.Char("Customer Code")
    amount              = fields.Float("Amount")
    currency            = fields.Char("Currency")
    partner_id          = fields.Many2one('dmpi.crm.partner',"Partner")
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
    amt_in_loc_cur= fields.Char("Amount in Local Currency")
    base_line_date= fields.Char("Baseline Date for Due Date Calculation")
    terms= fields.Char("Terms of Payment Key")
    cash_disc_days= fields.Char("Cash Discount Days 1")
    acct_doc_no2= fields.Char("Accounting Document Number")
    acct_doc_num_line= fields.Char("Number of Line Item Within Accounting Document")
    acct_type= fields.Char("Account Type")
    debit_credit= fields.Char("Debit/Credit Indicator")
    amt_in_loc_cur2= fields.Char("Amount in Local Currency")
    assign_no= fields.Char("Assignment Number")
    gl_acct_no= fields.Char("G/L Account Number")
    gl_acct_no2= fields.Char("G/L Account Number")
    customer_no2= fields.Char("Customer Number")

    active=fields.Boolean("Active", default=True)



class DmpiCrmCountry(models.Model):
    _name = 'dmpi.crm.country'

    name        = fields.Char("Name")
    code        = fields.Char("Country Code")
    active      = fields.Boolean("Active", default=True)


class DmpiCrmDestination(models.Model):
    _name = 'dmpi.crm.destination'

    name            = fields.Char("Name")
    ship_to_code    = fields.Char("Ship to code")
    dest_country_id = fields.Many2one('dmpi.crm.country', 'Destination')
    active          = fields.Boolean("Active", default=True)



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



# class DmpiCrmProductPriceList(models.Model):
#     _name = 'dmpi.crm.product.price.list'
#     _inherit = ['mail.thread']

#     name            = fields.Char("Description")
#     partner_id      = fields.Many2one('dmpi.crm.partner','Customer ID')
#     valid_from      = fields.Date("Valid From")
#     valid_to        = fields.Date("Valid To")
#     date_sync       = fields.Datetime("Last Sync")
#     price_upload    = fields.Binary("Upload File")
#     item_ids        = fields.One2many('dmpi.crm.product.price.list.item','version_id','Items')
#     upload_ids      = fields.One2many('dmpi.crm.product.price.list.upload','version_id','Uploads')

# class DmpiCrmProductPriceListItem(models.Model):
#     _name = 'dmpi.crm.product.price.list.item'

#     version_id      = fields.Many2one('dmpi.crm.product.price.list.version','Versin ID')
#     product_id      = fields.Many2one('dmpi.crm.product',"Product ID")
#     price           = fields.Float("Price")


# class DmpiCrmProductPriceListItem(models.Model):
#     _name = 'dmpi.crm.product.price.list.upload'

#     version_id      = fields.Many2one('dmpi.crm.product.price.list.version','Versin ID')
#     valid_from      = fields.Date("Valid From")
#     valid_to        = fields.Date("Valid To")
#     sku             = fields.Char('SKU')
#     customer        = fields.Char('Customer')
#     price           = fields.Float("Price")



class DmpiCRMPaymentTerms(models.Model):
    _name = 'dmpi.crm.payment.terms'
    #_description = 'DMS_A910_PRICEDOWNLOAD'

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




class DmpiCrmClp(models.Model):
    _name = 'dmpi.crm.clp'
    _rec_name = 'control_no'

    @api.model
    def create(self, vals):
        vals['control_no'] = self.env['ir.sequence'].next_by_code('dmpi.crm.clp')
        res = super(DmpiCrmClp, self).create(vals)
        return res

    def print_clp(self):
        user = self.env.user

        values = {
            'type': 'ir.actions.report',
            'report_name': 'dmpi_crm.clp_report',
            'report_type': 'pentaho',
            'name': 'Container Load Plan',
            'datas': {
                'output_type': 'pdf',
                'variables': {
                    'user': user.name,
                    'ids': self.ids,
                },
            },
        }

        return values

    control_no = fields.Char('Control No', default="/")
    logo = fields.Binary('Logo')
    layout_name = fields.Char('Layout Name')

    container_no = fields.Char('Container No') # Van No
    seal_no = fields.Char('Seal No')
    vessel_name = fields.Char('Vessel Name')
    plant = fields.Char('Plant') # Packing House
    port_origin = fields.Char('Port of Origin')
    port_destination = fields.Char('Port of Destination')
    customer = fields.Char('Customer')

    week = fields.Integer('Week')
    brand = fields.Char('Brand')
    description = fields.Char('Description')
    boxes = fields.Integer('Boxes')
    installed = fields.Boolean('Is Installed?')

    encoder = fields.Char('Encoder')
    outbound_checker = fields.Char('Outbound Checker')
    supervisor = fields.Char('Supervisor')
    prod_load_counter = fields.Char('Production Loading Counter')
    inspector = fields.Char('QA Inspector')

    date_start = fields.Char('Start')
    date_end = fields.Char('Finish')
    date_depart = fields.Char('ETD')
    date_arrive = fields.Char('ETA')

    summary_case_a = fields.Char('Summary of Cases A')
    summary_case_b = fields.Char('Summary of Cases B')
    summary_case_c = fields.Char('Summary of Cases C')

    container_temp = fields.Text('Container Temp Details')
    pulp_room_temp = fields.Text('Pulp Room Temp Details')
    remarks = fields.Text('Remarks')

    dr_id = fields.Many2one('dmpi.crm.dr', 'DR ID', ondelete='cascade')
    clp_line_ids = fields.One2many('dmpi.crm.clp.line', 'clp_id', "CLP Line Ids")

class DmpiCrmClpLine(models.Model):
    _name = 'dmpi.crm.clp.line'
    _rec_name = 'tag_no'

    @api.onchange('position')
    def check_position(self):
        if self.position<=0 or self.position not in range(1,25):
            raise UserError('Position number must be in the range 1 to 24!')
        else:
            pass

    position = fields.Integer('Sequence', default=1, help="Order placing of packages on the form: from left to right, top to bottom (head to door). \
                                                Numbered 1 - 24.")
    tag_no = fields.Char('Tag No')
    pack_code = fields.Char('Pack Code')
    pack_size = fields.Char('Pack Size')

    clp_id = fields.Many2one('dmpi.crm.clp', 'CLP ID', ondelete='cascade')




