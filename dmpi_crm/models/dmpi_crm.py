# -*- coding: utf-8 -*-

from odoo import _
from odoo import models, api, fields
from odoo.modules.module import get_module_resource
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

	ship_to_ids = fields.Many2many('dmpi.crm.partner','dmpi_partner_shp_rel','partner_id','ship_to_id',string='Partner Functions',domain=[('function_ids.code','=','SHP')])
	notify_ids = fields.Many2many('dmpi.crm.partner','dmpi_partner_nfy_rel','partner_id','nofity_id',string='Partner Functions',domain=[('function_ids.code','=','NFY')])
	mailing_ids = fields.Many2many('dmpi.crm.partner','dmpi_partner_mal_rel','partner_id','mailing_id',string='Partner Functions',domain=[('function_ids.code','=','MAL')])
	tag_ids = fields.Many2many('dmpi.crm.product.price.tag', 'partner_tag_rel', 'partner_id', 'tag_id', string='Default Price Tags', copy=True)
	product_ids = fields.Many2many('dmpi.crm.product','dmpi_partner_product_rel','partner_id','product_id',string='Assigned Products')

	ar_records = fields.One2many('dmpi.crm.partner.ar','partner_id','AR Records')
	
	# additional
	address = fields.Text('Address')
	contact = fields.Text('Contact Info')
	function_ids = fields.Many2many('dmpi.crm.partner.function','dmpi_partner_function_rel','ship_to_id','function_id', string='Function Type')



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
							'remarks': r[9],
						}

						if r[1]:
							partner = self.env['dmpi.crm.partner'].search([('customer_code','=',r[1])], limit=1)
							if partner:
								item['partner_id'] = partner[0].id
							else:
								errors.append('Partner %s does not exist on row %s.' % (r[1],row_count) )

						if r[2]:
							product = self.env['dmpi.crm.product'].search([('sku','=',r[2])], limit=1)
							if product:
								item['product_id'] = product[0].id
							else:
								errors.append('Product %s does not exist on row %s. \n' % (r[2],row_count) )

						if r[9]:
							tags = r[9].split(',')
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

	def check_valid_tag_ids(self, array1, array2):
		"""
			valid tag if:
				1. array1 has intersection with array2
				2. no elements in arary1 are not in array2
		"""
		array1 = set(array1)
		array2 = set(array2)

		has_intersect = bool( array1.intersection(array2) )
		no_unique = not bool( array1 - array1.intersection(array2) )

		if has_intersect and no_unique:
			return True
		return False

	@api.multi
	def get_product_price(self, product_id, partner_id, date, tag_ids=[]):
		"""
			use date by default to find price.
			if tag_ids exist and has a result use that pirce
			if no result, back to default
		"""
		print ('get product price %s %s %s %s' % (product_id, partner_id, date, tag_ids))

		query_tmp = """
			SELECT * FROM (
				SELECT
					i.id,i.product_id,i.partner_id,i.material,i.amount,i.currency,i.uom,i.valid_from,i.valid_to
					,array_agg(tr.tag_id) as tags
					,p.active
				FROM dmpi_crm_product_price_list_item i
				LEFT JOIN dmpi_crm_product_price_list p on p.id = i.version_id
				LEFT JOIN price_item_tag_rel tr on tr.item_id = i.id
				GROUP BY i.id,i.product_id,i.partner_id,i.material,i.valid_from,i.valid_to,i.amount,i.currency,i.uom,p.active
			) A
			WHERE A.product_id = %s and A.partner_id = %s
				and ('%s'::DATE between A.valid_from and A.valid_to)
				and A.active is true
				%s
			LIMIT 1
		"""

		rule_id = False
		price = 0
		uom = 'CAS'
		valid = False

		if not all([product_id, partner_id, date]):
			return rule_id, price, uom

		if tag_ids:
			where_clause = """and ARRAY%s && tags""" % tag_ids
			query = query_tmp % (product_id, partner_id, date, where_clause)
			self._cr.execute(query)
			res = self._cr.dictfetchall()

			if res:
				price_tags = res[0]['tags']
				valid = self.check_valid_tag_ids(tag_ids, price_tags)

		if not tag_ids or not valid:
			query = query_tmp % (product_id, partner_id, date, "")
			self._cr.execute(query)
			res = self._cr.dictfetchall()

		if res:
			rule_id = res[0]['id']
			price = res[0]['amount']
			uom = res[0]['uom']

		return rule_id, price, uom


class DmpiCrmProductPriceListItem(models.Model):
	_name = 'dmpi.crm.product.price.list.item'


	@api.multi
	@api.depends('partner_id')
	def get_allowed_products(self):
		for rec in self:
			rec.allowed_products = rec.partner_id.product_ids

	version_id = fields.Many2one('dmpi.crm.product.price.list','Versin ID', ondelete="cascade")
	product_id = fields.Many2one('dmpi.crm.product',"Product ID")
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

class DmpiCRMPaymentTerms(models.Model):
	_name = 'dmpi.crm.payment.terms'
	_description = 'Payment Terms'

	name = fields.Char("Code")
	days = fields.Integer("Days Due")


class DmpiSAPPriceUpload(models.Model):
	_name = 'dmpi.sap.price.upload'

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

	name = fields.Char("Activity")
	description = fields.Text("Log")
	log_type = fields.Selection([('success','Success'),('fail','Fail'),('warning','Warning'),('note','Note')],"Type")
	model_id = fields.Many2one('ir.model',"Model")
	record_id = fields.Integer("Record ID")



class DmpiCrmDialogWizard(models.TransientModel):
	_name = 'dmpi.crm.dialog.wizard'

	name = fields.Char('Name')
	description = fields.Char('Description')



class DmpiCRMResPartner(models.Model):
	_name = 'dmpi.crm.res.partner'

	name = fields.Char('Name')
	function = fields.Char('Function')





