# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import time
from datetime import datetime,date
from odoo.exceptions import Warning, RedirectWarning, UserError
import xlsxwriter
from io import BytesIO
import codecs
import re
import json

# REPORTS CONFIGURATIONS
class DmpiCrmTemplate(models.Model):
	_name = 'dmpi.crm.template'
	_sql_constraints = [
		('unique_template', 'UNIQUE (name)', _('Similar template already exists!'))
	]

	@api.multi
	@api.depends('tmpl_lines.weight')
	def _get_total(self):
		for rec in self:
			rec.ext_weight = sum([w.weight for w in rec.tmpl_lines.filtered(lambda l: l.type == 'external')])
			rec.int_weight = sum([w.weight for w in rec.tmpl_lines.filtered(lambda l: l.type == 'internal')])
			rec.pack_weight = sum([w.weight for w in rec.tmpl_lines.filtered(lambda l: l.type == 'packaging')])
			rec.total_weight = rec.ext_weight + rec.int_weight + rec.pack_weight

			print (rec.ext_weight, rec.int_weight, rec.pack_weight, rec.total_weight)

	name = fields.Char('Template Name')
	ext_rule = fields.Char('External')
	int_rule = fields.Char('Internal')
	pack_rule = fields.Char('Packaging')
	overall_rule = fields.Char('Overall Rule')
	ext_hold = fields.Boolean('External')
	int_hold = fields.Boolean('Internal')
	pack_hold = fields.Boolean('Packaging')
	
	active = fields.Boolean('Active', default=True)
	tmpl_lines = fields.One2many('dmpi.crm.template.line','tmpl_id','Weight Factors')

	ext_weight = fields.Float('Total External Weight', compute="_get_total")
	int_weight = fields.Float('Total Internal Weight', compute="_get_total")
	pack_weight = fields.Float('Total Packaging Weight', compute="_get_total")
	total_weight = fields.Float('Total Weight', compute="_get_total")


class DmpiCrmTemplateLine(models.Model):
	_name = 'dmpi.crm.template.line'
	_rec_name = 'factor_id'
	_sql_constraints = [
		('unique_factor', 'UNIQUE (factor_id, tmpl_id)', _('Similar weight factor already exists!'))
	]

	sequence = fields.Integer('Sequence', help="Important! Determines order in Shipment Reports")
	factor_id = fields.Many2one('dmpi.crm.factor', string='Factor')
	type = fields.Selection(string='Operation', related='factor_id.type', readonly=True)
	code = fields.Char(string='Code', related='factor_id.code', readonly=True)
	weight = fields.Float(string='Weight (%)')
	rule = fields.Char(string='Rule')
	is_hold = fields.Boolean(string='To Hold', help='On hold factors sets Operation Class to "HOLD"')
	tmpl_id = fields.Many2one('dmpi.crm.template', string='Pre-Shipment Template', ondelete='cascade')


class DmpiCrmFactor(models.Model):
	_name = 'dmpi.crm.factor'
	_description = 'Product Characteristics'
	_order = 'type'

	# sequence = fields.Integer('Sequence', help="Important! Determines order in Shipment Reports")
	name = fields.Char(string='Factor')
	code = fields.Char(string='Code')
	type = fields.Selection([('external','External Quality'),('internal','Internal Quality'),('packaging','Packing Quality')], string='Operation')
	active = fields.Boolean('Active', default=True)

# REPORTS MODELS
class DmpiCrmPreshipReport(models.Model):
	_name = 'dmpi.crm.preship.report'
	_rec_name = 'series_no'
	_order = 'series_no desc'

	@api.model
	def create(self, vals):
		vals['series_no'] = self.env['ir.sequence'].next_by_code('dmpi.crm.preship.report')
		res = super(DmpiCrmPreshipReport, self).create(vals)
		return res

	# @api.depends('dr_id')
	# def _get_container(self):
	# 	for rec in self:
	# 		if rec.dr_id:
	# 			rec.container = rec.dr_id.dr_lines[0].container

	@api.onchange('dr_id')
	def onchange_dr_id(self):
		try:
			self.container = self.dr_id.clp_ids[0].container_no
		except:
			pass

	dr_id = fields.Many2one('dmpi.crm.dr', 'DR Reference')
	tmpl_id = fields.Many2one('dmpi.crm.template', 'Pre-Shipment Template')
	img = fields.Binary('Image Attachment')

	date_issue = fields.Datetime('Date Issue', default=fields.Datetime.now())
	issuer = fields.Char('Issued By')
	# container = fields.Char('Container No', compute='_get_container', store=True) # COMPUTED AUTOMATIC VALUE ONCHANGE FROM DR
	container = fields.Char('Container No') # COMPUTED AUTOMATIC VALUE ONCHANGE FROM DR
	customer = fields.Char('Customer')

	# product_sc = fields.Char('SC')
	# product_ps = fields.Char('PS/Count')
	shell_color = fields.Char('Shell Color')
	pack_size = fields.Char('Pack Size / Count')

	date_pack = fields.Char('Pack Date')
	market = fields.Char('Market')

	series_no = fields.Char('Series No', default=_("New"), readonly=True)
	date_load = fields.Date('Date Loaded')
	inspector = fields.Char('QA Inspector')
	no_box = fields.Integer('No. of Boxes')

	field_source = fields.Char('Field Source')

	temp_start = fields.Float('Supply Temp Starting')
	temp_end = fields.Float('Supply Temp Upon Departure')
	van_temp_start = fields.Float('Van Temp Before Stuffing')
	van_temp_end = fields.Float('Van Temp Setting')

	pre_pc = fields.Char('Before PC')
	post_pc = fields.Char('After PC')
	cold_store = fields.Char('Cold Storage')
	pulp_temp_first = fields.Float('Pulp Temp 1st')
	pulp_temp_mid = fields.Float('Pulp Temp Mid')
	pulp_temp_last = fields.Float('Pulp Temp Last')
	no_pallet = fields.Integer('No of Pallets')
	remarks = fields.Text('Remarks')

	# FG certificate
	variety = fields.Char('Variety')
	allergen = fields.Char('Allergen Declaration')
	supervisor = fields.Char('QA Supervisor')

	state = fields.Selection([('draft','Draft'),('confirm','Confrimed'),('cancel','Cancelled')], default='draft')

	total_score = fields.Float('Score')
	total_class = fields.Char('Class')


	def print_preship_report(self):
		user = self.env.user

		values = {
			'type': 'ir.actions.report',
			'report_name': 'preship_cert_report',
			'report_type': 'xlsx',
			'name': 'Pre-Shipment Certificate',
		}
		return values

	def print_fg_cert_report(self):
		user = self.env.user

		values = {
			'type': 'ir.actions.report',
			'report_name': 'fg_cert_report',
			'report_type': 'xlsx',
			'name': 'FG Certificate',
		}
		return values

class DmpiCrmClp(models.Model):
    _name = 'dmpi.crm.clp'
    _rec_name = 'control_no'
    _order = 'control_no desc'

    @api.model
    def create(self, vals):
        vals['control_no'] = self.env['ir.sequence'].next_by_code('dmpi.crm.clp')
        res = super(DmpiCrmClp, self).create(vals)
        return res

    def print_clp(self):
        user = self.env.user

        report_obj = self.env['ir.actions.report'].search([('report_name','=','dmpi_crm.clp_report'),('report_type','=','pentaho')], limit=1)
        report_obj.name = 'CLP_%s_%s' % (self.container_no,self.date_start)

        values = {
            'type': 'ir.actions.report',
            'report_name': 'dmpi_crm.clp_report',
            'report_type': 'pentaho',
            'name': 'Container Load Plan',
            # 'print_report_name': 'CLP_%s_%s' % (self.container_no,self.date_start),
            'datas': {
                'output_type': 'pdf',
                'variables': {
                    'user': user.name,
                    'ids': self.ids,
                    'dr_id': self.dr_id.id
                },
            },
        }

        return values

    # headers
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


    # signatories
    encoder_id = fields.Many2one('res.users','Encoder')
    outbound_checker_id = fields.Many2one('res.users','Outbound Checker')
    supervisor_id = fields.Many2one('res.users','Supervisor')
    prod_load_counter_id = fields.Many2one('res.users','Production Loading Counter')
    inspector_id = fields.Many2one('res.users','QA Inspector')

    encoder_name = fields.Char('Encoder', related="encoder_id.partner_id.name", store=True)
    outbound_checker_name = fields.Char('Outbound Checker', related="outbound_checker_id.partner_id.name", store=True)
    supervisor_name = fields.Char('Supervisor', related="supervisor_id.partner_id.name", store=True)
    prod_load_counter_name = fields.Char('Production Loading Counter', related="prod_load_counter_id.partner_id.name", store=True)
    inspector_name = fields.Char('QA Inspector', related="inspector_id.partner_id.name", store=True)

    # loading date
    date_start = fields.Char('Start')
    date_end = fields.Char('Finish')
    date_depart = fields.Char('ETD')
    date_arrive = fields.Char('ETA')

    # summary of cases
    summary_case_a = fields.Char('Summary of Cases A')
    summary_case_b = fields.Char('Summary of Cases B')
    summary_case_c = fields.Char('Summary of Cases C')

    # container temperatures
    # container_temp = fields.Text('Container Temp Details')
    simul_no = fields.Char('Simulation No')
    first_temp = fields.Char('First Temp')
    mid_temp = fields.Char('Mid Temp')
    last_temp = fields.Char('Last Temp')
    van_temp = fields.Char('Van Temp')

    # container temperatures (manual input)
    pulp_room_temp = fields.Text('Pulp Room Temp Details')


    remarks = fields.Text('Remarks')

    dr_id = fields.Many2one('dmpi.crm.dr', 'DR ID', ondelete='cascade')
    clp_line_ids = fields.One2many('dmpi.crm.clp.line', 'clp_id', "CLP Line Ids")


    def action_view_clp(self):

    	action = self.env.ref('dmpi_crm.action_dmpi_crm_clp').read()[0]
    	action.update({
    		'views': [(self.env.ref('dmpi_crm.view_dmpi_crm_clp_form').id, 'form')],
    		'res_id' : self.id,
    	})

    	return action

class DmpiCrmClpLine(models.Model):
    _name = 'dmpi.crm.clp.line'
    _rec_name = 'tag_no'
    _order = 'position'

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



class DmpiCrmPreshipSummary(models.TransientModel):
	_name = 'dmpi.crm.preship.summary'
	_description = 'Pre-Shipment Loaded Vans Summary'

	date_start = fields.Date('From')
	date_end = fields.Date('To')

	@api.onchange('date_start')
	def onchange_date_start(self):
		if self.date_start and not self.date_end:
			self.date_end = self.date_start

	filter_template = fields.Selection([
		('template','Select Pre-Shipment Template'),
		('all','All')
		], string='Filter Template', default='all')

	tmpl_id = fields.Many2one('dmpi.crm.template', string='Pre-Shipment Template')


	def print_preship_summary(self):
		user = self.env.user

		values = {
			'type': 'ir.actions.report',
			'report_name': 'preship_cert_summary_report',
			'report_type': 'xlsx',
			'name': 'Pre-Shipment Load Vans Summary',
		}

		return values