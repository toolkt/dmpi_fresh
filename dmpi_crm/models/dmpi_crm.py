# -*- coding: utf-8 -*-

from odoo import _
from odoo import models, api, fields
from odoo.modules.module import get_module_resource
from odoo.osv import expression
from odoo.exceptions import ValidationError, AccessError, UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import string

import csv
import sys
import math

import base64
from tempfile import TemporaryFile
import tempfile
import re
from dateutil.parser import parse
from io import BytesIO

# pip3 install Fabric3
import logging
from fabric.api import *
import paramiko
import socket
import os
import glob


_logger = logging.getLogger(__name__)
removeWhiteSpace = {ord(c): None for c in string.whitespace}


#@parallel
def file_send(localpath,remotepath):
    with settings(warn_only=True):
        put(localpath,remotepath,use_sudo=True)


#@parallel
def change_permission(path):
    with cd(path):
        cmd = 'chmod 777 -R *'
        sudo(cmd)

#@parallel
def file_get(remotepath, localpath):
    with settings(warn_only=True):
        get(remotepath,localpath)

#@parallel
def transfer_files(from_path, to_path):
    with settings(warn_only=True):
        mv = "mv %s %s" % (from_path,to_path)
        sudo(mv)

CROWN = [('C','w/Crown'),('CL','Crownless')]


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
    short_name      = fields.Char('Short Name')
    email           = fields.Char("Email")
    active          = fields.Boolean("Active", default=True)
    default_plant   = fields.Many2one('dmpi.crm.plant',"Default Plant")
    customer_code   = fields.Char("Code")
    account_group   = fields.Char("Account Group")
    default_validity = fields.Integer("Default Validity", default=30)
    city            = fields.Char("City")
    city_code       = fields.Char("City Code")
    street          = fields.Char("Street")
    postal_code     = fields.Char("Postal Code")
    phone           = fields.Char("Telephone")
    fax             = fields.Char("Fax")
    country         = fields.Many2one('dmpi.crm.country',string='Country')
    country_code    = fields.Char('Country Code', related="country.code", store=True)
    sales_org       = fields.Char("Sales Org")
    dist_channel    = fields.Char("Distribution Channel")
    division        = fields.Char("Division")

    # ship_to_ids = fields.Many2many('dmpi.crm.partner','dmpi_partner_shp_rel','partner_id','ship_to_id',string='Partner Functions',domain=[('function_ids.code','=','SHP')])
    ship_to_ids = fields.Many2many('dmpi.crm.partner','dmpi_partner_shp_rel','partner_id','ship_to_id',string='Partner Functions')
    tag_ids = fields.Many2many('dmpi.crm.product.price.tag', 'partner_tag_rel', 'partner_id', 'tag_id', string='Default Price Tags', copy=True)
    product_ids = fields.Many2many('dmpi.crm.product','dmpi_partner_product_rel','partner_id','product_id',string='Assigned Products')

    ar_records = fields.One2many('dmpi.crm.partner.ar','partner_id','AR Records')
    
    # additional
    address = fields.Text('Address')
    contact = fields.Text('Contact Info')
    function_ids = fields.Many2many('dmpi.crm.partner.function','dmpi_partner_function_rel','ship_to_id','function_id', string='Function Type')
    instructions = fields.Text('Default Insructions')



class DmpiCrmPartnerCreditLimit(models.Model):
    _name = 'dmpi.crm.partner.credit.limit'

    partner_id          = fields.Many2one('dmpi.crm.partner',"Partner")
    customer_code       = fields.Char("Customer Code")
    credit_control_no   = fields.Char("Credit Control No")
    credit_limit        = fields.Float("Credit Limit")
    credit_exposure     = fields.Float("Credit Exposure")
    currency            = fields.Char("Currency")


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
    _order = 'name'


    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            # domain = ['|', ('destination', '=ilike', name + '%'), ('name', operator, name)]
            domain = [('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        accounts = self.search(domain + args, limit=limit)
        return accounts.name_get()


    @api.multi
    @api.depends('name', 'ship_to_code')
    def name_get(self):
        result = []
        for rec in self:
            if rec.ship_to_code:
                name = rec.name + ' [' + rec.ship_to_code + ']'
            else:
                name = rec.name + ' [ ]'
            result.append((rec.id, name))
        return result

    name = fields.Char("Partner Name", required=True)
    destination = fields.Char("Destination")
    country_id = fields.Many2one('dmpi.crm.country', 'Country')
    ship_to_code = fields.Char('Ship to Code')
    address = fields.Text('Address')
    contact = fields.Text('Contact Info')
    function_ids = fields.Many2many('dmpi.crm.partner.function','dmpi_ship_to_function_rel','ship_to_id','function_id', string='Function Type')

class DmpiCrmPartnerFunction(models.Model):
    _name = 'dmpi.crm.partner.function'

    name = fields.Char('Type')
    code = fields.Char('Code')

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

class DmpiCrmPlant(models.Model):
    _name = 'dmpi.crm.plant'

    name            = fields.Char("Plant")
    description     = fields.Char("Description")
    active          = fields.Boolean("Active", default=True)


class DmpiCrmProduct(models.Model):
    _name = 'dmpi.crm.product'
    _sql_constraints = [
        ('unique_sku', 'UNIQUE (sku)', _('Similar Material Already Exist!'))
    ]

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


    @api.one
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault('sku', _("%s (copy)") % (self.sku or ''))
        return super(DmpiCrmProduct, self).copy(default)


    partner_id      = fields.Many2one('dmpi.crm.partner','Customer')
    fruit_size      = fields.Char("Fruit Size")
    fruit_count     = fields.Char("Fruit Count")
    weight          = fields.Float("Gross Weight")
    net_weight      = fields.Float("Net Weight")
    psd             = fields.Integer("Pack Size")
    uom             = fields.Char("UOM")
    case_factor     = fields.Float("Case Factor")
    code_id         = fields.Many2one('dmpi.crm.product.code','Pack Code')
    code            = fields.Char("Pack Code Name", related='code_id.name', store=True)
    product_crown   = fields.Selection(CROWN, string='Crown', related='code_id.product_crown', store=True)
    product_class   = fields.Char('Fruit Class')
    sku             = fields.Char("SKU") # sku
    name            = fields.Char("Name") # description
    packaging       = fields.Char("Packaging")
    category        = fields.Char('Category')
    sub_category    = fields.Char('Sub-Category')
    brand           = fields.Char('Brand')
    sub_brand       = fields.Char('Sub-Brand')
    variant         = fields.Many2one('dmpi.crm.variety','Variant')
    active          = fields.Boolean("Active", default=True)


class DmpiCrmProductPriceList(models.Model):
    _name = 'dmpi.crm.product.price.list'
    _description = "Price List"
    _inherit = ['mail.thread']

    name = fields.Char("Name", required=True, track_visibility='onchange')
    description = fields.Char("Description", track_visibility='onchange')
    date = fields.Datetime("Date",track_visibility='onchange', default=fields.Datetime.now())
    week_no = fields.Integer("Week No")
    upload_filename = fields.Char("Filename")
    upload_file = fields.Binary("Upload File", track_visibility='onchange')
    item_ids = fields.One2many('dmpi.crm.product.price.list.item','version_id','Items', ondelete='cascade')
    state = fields.Selection([('draft','Draft'),('submitted','Submitted'),('approved','Approved'),('cancelled','Cancelled')], "State", default='draft', track_visibility='onchange')
    active = fields.Boolean('Active', default=False, track_visibility='onchange')
    template = fields.Binary('Upload Template')
    sent_to_sap_date = fields.Datetime('Sent to SAP Date', track_visibility='onchange')
    sent_to_sap = fields.Boolean('Sent to SAP', track_visibility='onchange')

    @api.onchange('upload_file')
    def onchange_upload_file(self):
        if self.upload_file:
            rows = read_data(self.upload_file)

            row_count = 1
            error_count = 0
            line_items = []
            errors = []

            for r in rows:
                if r[0] != '':
                    if row_count == 1:
                        print ('headers \n %s' % r)
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
                            'sap_from': parse_date(r[9]),
                            'sap_to': parse_date(r[10]),
                            'remarks': r[11],
                        }

                        if r[1]:
                            partner = self.env['dmpi.crm.partner'].search([('customer_code','=',r[1]),('active','=',True)], limit=1)
                            if partner:
                                item['partner_id'] = partner[0].id
                            else:
                                errors.append('Partner %s does not exist on row %s.' % (r[1],row_count) )

                        if r[2]:
                            product = self.env['dmpi.crm.product'].search([('sku','=',r[2]),('active','=',True)], limit=1)
                            if product:
                                item['product_id'] = product[0].id
                            else:
                                errors.append('Product %s does not exist on row %s. \n' % (r[2],row_count) )

                        if r[11]:
                            tags = r[11].split(',')
                            tag_ids = []
                            for t in tags:
                                tag = self.env['dmpi.crm.product.price.tag'].search([('name','=',t)], limit=1)
                                if tag:
                                    tag_ids.append((4,tag.id,))
                                else:
                                    errors.append('Price Tag %s does not exist on row %s. \n' % (t,row_count) )
                            item['tag_ids'] = tag_ids

                        line_items.append((0,0,item))

                row_count+=1

            if errors:
                raise UserError( _('\n'.join(errors)) )
            else:
                self.item_ids.unlink()
                self.item_ids = line_items


    def download_pricelist_template(self):
        file_path = get_module_resource('dmpi_crm','data','fresh_pricelist_upload_template.csv')
        file_content = open(file_path, 'rb').read()
        self.template = base64.encodestring(file_content)

        action = {
            'type' : 'ir.actions.act_url',
            'url': '/web/content/dmpi.crm.product.price.list/%s/template/fresh_pricelist_upload_template.csv?download=true'%(self.id),
            'target': 'current'
        }

        return action

    @api.multi
    def get_product_price(self, product_id, partner_id, date, price, tag_ids=[]):
        """
            use date by default to find price.
            if tag_ids exist and has a result use that pirce
            if no result, back to default
        """
        print ('get product price Product:%s Partner:%s Date:%s Tags:%s Price:%s' % (product_id, partner_id, date, tag_ids, price))
        query = ""
        query_tmp = """
            SELECT * FROM (
                SELECT
                    i.id,i.product_id,i.partner_id,i.material,i.amount,i.currency,i.uom,i.valid_from,i.valid_to
                    ,array_agg(tr.tag_id) as tags, p.active
                    ,i.sap_from as pricing_date ,p.name as pricelist_name
                FROM dmpi_crm_product_price_list_item i
                LEFT JOIN dmpi_crm_product_price_list p on p.id = i.version_id
                LEFT JOIN price_item_tag_rel tr on tr.item_id = i.id
                WHERE i.product_id = %s and i.partner_id = %s
                GROUP BY i.id,i.product_id,i.partner_id,i.material,i.valid_from,i.valid_to,i.amount,i.currency,i.uom,p.active,i.sap_from,p.name
            ) A
            WHERE A.active is true
                and ('%s'::DATE between A.valid_from and A.valid_to)
                %s
                ORDER by tags desc
            LIMIT 1
        """

        mode = ''
        rule_id = False
        pricing_date = ''
        uom = 'CAS'
        valid = False
        where_clause = ""

        if not all([product_id, partner_id, date]):
            return rule_id, price, uom

        if tag_ids:
            mode = 'has tag ids'
            where_clause = """%sand ARRAY%s && tags""" % (where_clause,tag_ids)
            
        if price:
            where_clause = """and amount = %s""" % price
        else:
            price = 0.0

        query = query_tmp % (product_id, partner_id, date, where_clause)
        self._cr.execute(query)
        res = self._cr.dictfetchall()

        if res:
            rule_id = res[0]['id']
            price = res[0]['amount']
            uom = res[0]['uom']
            pricing_date = res[0]['pricing_date']
        else:
            pricing_date = False

        # print (mode)
        print (query)
        return rule_id, price, uom, pricing_date


    def action_send_pricelist_to_sap(self):
        print('send to sap pricelist')
        for rec in self:
            try:
                # filename = 'ODOOPriceUploadZPR8_%s_%s.csv' % (rec.name.translate(removeWhiteSpace),datetime.now().strftime("%Y%m%d_%H%M%S"))
                filename = 'ODOOPRICE_%s_%s.csv' % (rec.id, datetime.now().strftime("%Y%m%d"))
                path = '/tmp/%s' % filename

                query = """
                    SELECT *
                    from (
                            select rp.dist_channel, ppi.customer_code, ppi.material, ppi.amount, ppi.currency, ppi.uom,
                                CASE 
                                    WHEN ppi.sap_from IS NOT NULL THEN to_char(ppi.sap_from,'MMDDYYYY')
                                    ELSE to_char(ppi.valid_from,'MMDDYYYY')
                                END AS valid_from,
                                CASE 
                                    WHEN ppi.sap_to IS NOT NULL THEN to_char(ppi.sap_to,'MMDDYYYY')
                                    ELSE to_char(ppi.valid_to,'MMDDYYYY')
                                END AS valid_to,                                        
                                ppi.remarks,
                                row_number() over (partition by ppi.customer_code, ppi.material, ppi.sap_from, ppi.sap_to order by ppi.remarks desc) occurrence
                            from dmpi_crm_product_price_list_item ppi
                            left join dmpi_crm_product_price_list pp on pp.id = ppi.version_id
                            left join dmpi_crm_partner rp on rp.id = ppi.partner_id
                            where pp.id in (%s)
                            order by ppi.customer_code, ppi.material, ppi.remarks desc
                    ) A
                    where A.occurrence = 1
                """ % rec.id

                self._cr.execute(query)
                res = self._cr.fetchall()

                lines = []
                for ppi in res:
                    line = {
                        'pricelist' : 'ZPR8',
                        'dist_channel' : ppi[0],
                        'sold_to' : ppi[1],
                        'material' : ppi[2],
                        'amount' : float(ppi[3]),
                        'currency' : ppi[4],
                        'uom' : ppi[5],
                        'valid_from' : ppi[6],
                        'valid_to' : ppi[7],
                    }

                    lines.append(line)

                headers = ['KSCHL','VTWEG','KUNNR','MATNR','KBETR','Currency','Quantity','UoM','DATAB','DATBI']

                with open(path, 'w') as f:
                    writer = csv.writer(f, delimiter='\t')
                    writer.writerow(headers)
                    for l in lines:
                        writer.writerow([l['pricelist'],l['dist_channel'],l['sold_to'],l['material'],l['amount'],l['currency'],1,l['uom'],l['valid_from'],l['valid_to']])


                # #TRANSFER TO REMOTE SERVER
                h = self.env['dmpi.crm.config'].search([('default','=',True)],limit=1)
                host_string = h.ssh_user + '@' + h.ssh_host + ':22'
                env.hosts.append(host_string)
                env.passwords[host_string] = h.ssh_pass

                localpath = path
                path = '%s/%s' % (h.outbound_prc_success,filename)
                remotepath = path

                execute(file_send,localpath,remotepath)
                rec.sent_to_sap = True
                rec.sent_to_sap_date = datetime.now()

            except Exception as e:
                raise UserError( "Error: %s" % e )



class DmpiCrmProductPriceListItem(models.Model):
    _name = 'dmpi.crm.product.price.list.item'
    _rec_name = 'product_id'


    @api.multi
    @api.depends('partner_id')
    def get_allowed_products(self):
        for rec in self:
            rec.allowed_products = rec.partner_id.product_ids

    version_id = fields.Many2one('dmpi.crm.product.price.list','Pricelist', ondelete="cascade")
    product_id = fields.Many2one('dmpi.crm.product',"Product")
    sales_org = fields.Char("Sales Org")
    customer_code = fields.Char("Customer Code")
    partner_id = fields.Many2one("dmpi.crm.partner","Customer")
    material = fields.Char("Material")
    freight_term = fields.Char("Freight")
    amount = fields.Float("Amount")
    currency = fields.Char("Currency", default="USD")
    uom = fields.Char("Unit of Measure", default="CAS")
    valid_from = fields.Date("Valid From")
    valid_to = fields.Date("Valid To")
    sap_from = fields.Date("SAP From")
    sap_to = fields.Date("SAP To")    
    remarks = fields.Char("Remarks")
    tag_ids = fields.Many2many('dmpi.crm.product.price.tag', 'price_item_tag_rel', 'item_id', 'tag_id', string='Tags', copy=True)
    allowed_products = fields.One2many('dmpi.crm.product', compute="get_allowed_products")

    @api.onchange('product_id','partner_id','tag_ids')
    def onchange_item(self):
        for rec in self:
            if self.product_id:
                self.material = self.product_id.sku

            if self.partner_id:
                self.customer_code = self.partner_id.customer_code
                self.sales_org = self.partner_id.sales_org

            if self.tag_ids:
                self.remarks = ','.join([t.name for t in self.tag_ids])

class DmpiCrmProductPriceTag(models.Model):
    _name = 'dmpi.crm.product.price.tag'
    _sql_constraints = [
        ('unique_name', 'UNIQUE (name)', _('Similar TAG Already Exist!'))
    ]

    name = fields.Char("Tag")
    description = fields.Char("Description")
    date_from = fields.Date("Date From")
    date_to = fields.Date("Date To")
    active = fields.Boolean("Active", default=True)


class DmpiCRMProductCode(models.Model):
    _name = 'dmpi.crm.product.code'
    _description = 'Product Code'
    _order = 'sequence'

    name = fields.Char("Name")
    description = fields.Char("Description")
    psd = fields.Integer("PSD")
    product_crown   = fields.Selection(CROWN,'Crown')
    sequence = fields.Integer("Sequence")
    field_name = fields.Char("Field Name")
    factor = fields.Float("Factor")
    active = fields.Boolean("Active", default=True)


    def get_product_codes(self):
        product_codes = self.env['dmpi.crm.product.code'].sudo().search([], order='sequence')
        return product_codes.mapped('name')

class DmpiCRMPaymentTerms(models.Model):
    _name = 'dmpi.crm.payment.terms'
    _description = 'Payment Terms'

    name = fields.Char("Code")
    days = fields.Integer("Days Due")


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

    name = fields.Char("Activity")
    description = fields.Text("Log")
    log_type = fields.Selection([('success','Success'),('fail','Fail'),('warning','Warning'),('note','Note')],"Type")
    model_id = fields.Many2one('ir.model',"Model")
    record_id = fields.Integer("Record ID")


class DmpiCrmEmailNotificationSubscriber(models.Model):
    _name = 'dmpi.crm.email.notification.subscriber'

    name = fields.Many2one('mail.template',"Mail Template")
    user_id = fields.Many2one('res.users',"User")



class DmpiCrmDialogWizard(models.TransientModel):
    _name = 'dmpi.crm.dialog.wizard'

    name = fields.Char('Name')
    description = fields.Char('Description')



class DmpiCRMResPartner(models.Model):
    _name = 'dmpi.crm.res.partner'

    name = fields.Char('Name')
    function = fields.Char('Function')





