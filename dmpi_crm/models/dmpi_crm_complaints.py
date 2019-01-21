# -*- coding: utf-8 -*-

from odoo import _
from odoo.osv import expression
from odoo import models, api, fields
from odoo.exceptions import  Warning, RedirectWarning, ValidationError, AccessError, UserError
from datetime import datetime, timedelta
from dateutil.parser import parse
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT



class DmpiCrmComplaintClaimNature(models.Model):
    _name = 'dmpi.crm.complaint.claim.nature'
    _description = 'Nature of Claim'

    name = fields.Char("Name")
    code = fields.Char("Code")

class DmpiCrmComplaintMarket(models.Model):
    _name = 'dmpi.crm.complaint.market'
    _description = 'Market'

    name = fields.Char("Name")
    code = fields.Char("Code")

class DmpiCrmComplaintPH(models.Model):
    _name = 'dmpi.crm.complaint.ph'
    _description = 'PH'

    name = fields.Char("Name")
    code = fields.Char("Code")

class DmpiCrmComplaintReport(models.Model):
    _name = 'dmpi.crm.complaint.report'
    _description = 'Fresh Fruits Complaint Reports FFCR'
    _inherit = ['mail.thread']


    @api.depends('date_arrival','pack_date','date_pullout','date_inspection','date_last_doc_completed','date_claim_endorsement_receipt')
    def get_compute_data(self):
        for rec in self:
            if not(not(rec.date_arrival) or not(rec.pack_date)):
                date_arrival = datetime.strptime(rec.date_arrival, "%Y-%m-%d")
                pack_date = datetime.strptime(rec.pack_date, "%Y-%m-%d")
                rec.aop_ata = (pack_date-date_arrival).days

            if not(not(rec.date_pullout) or not(rec.pack_date)):
                date_pullout = datetime.strptime(rec.date_pullout, "%Y-%m-%d")
                pack_date = datetime.strptime(rec.pack_date, "%Y-%m-%d")
                rec.aop_pull_out = (date_pullout-pack_date).days

            if not(not(rec.date_inspection) or not(rec.pack_date)):
                pack_date = datetime.strptime(rec.pack_date, "%Y-%m-%d")
                date_inspection = datetime.strptime(rec.date_inspection, "%Y-%m-%d")
                rec.aop_inspect = (date_inspection-pack_date).days
                

            if not(not(rec.date_last_doc_completed) or not(rec.date_claim_endorsement_receipt)):
                date_last_doc_completed = datetime.strptime(rec.date_last_doc_completed, "%Y-%m-%d")
                date_claim_endorsement_receipt = datetime.strptime(rec.date_claim_endorsement_receipt, "%Y-%m-%d")
                rec.total_days_processed = (date_last_doc_completed-date_claim_endorsement_receipt).days


    @api.model
    def create(self, vals):
        s = self.env['dmpi.crm.complaint.report'].search([],order='ffcr_series_no desc', limit=1).ffcr_series_no + 1
        series_no = '%03d' % s
        series_year = datetime.now().year
        vals['ffcr_series_no'] = s
        vals['ffcr_series_year'] = series_year
        vals['name'] = "FCR%s-%s" % (series_no,series_year)
        res = super(DmpiCrmComplaintReport, self).create(vals)
        return res


    name = fields.Char("FFCR SERIES NO.")
    ffcr_series_no = fields.Integer('Series No')
    ffcr_series_year = fields.Integer('Series Year')
    clp_id = fields.Many2one('dmpi.crm.clp', string='CLP No.')
    customer = fields.Char(string="CUSTOMER", related='clp_id.customer')
    market = fields.Char("MARKET", related='clp_id.port_destination')
    plant = fields.Char("PH", related='clp_id.plant')
    container_no = fields.Char("CONTAINER NO.", related='clp_id.container_no')
    claim_nature_id = fields.Many2one('dmpi.crm.complaint.claim.nature',"NATURE OF CLAIM")
    description = fields.Char("Complaint description")
    pack_date = fields.Date("PACK DATE")
    box_affected = fields.Integer("NO OF BOXES AFFECTED")
    claim_amount = fields.Float("CLAIM AMOUNT, USD")
    month_claimed = fields.Date("MONTH CLAIMED", default=fields.Datetime.now())
    date_arrival = fields.Date("DATE OF ARRIVAL")
    date_pullout = fields.Date("DATE OF PULL - OUT")
    date_inspection = fields.Date("DATE OF INSPECTION")
    aop_ata = fields.Integer("AOP AT ATA", compute='get_compute_data')
    aop_pull_out = fields.Integer("AOP AT PULL-OUT", compute='get_compute_data')
    aop_inspect = fields.Integer("AOP AT INSPECTION", compute='get_compute_data')
    date_qc_report_receipt = fields.Date("QC REPORT RECEIPT")
    date_claim_notif = fields.Date("DATE OF CLAIM NOTIFICATION")
    date_claim_bill_receipt = fields.Date("DATE OF CLAIM BILL RECEIPT")
    date_temp_logger_receipt = fields.Date("DATE OF TEMP LOGGER RECEIPT")
    date_claim_endorsement_receipt = fields.Date("DATE OF CLAIM ENDORSEMENT RECEIPT")
    date_last_doc_completed = fields.Date("DATE LAST DOCUMENT COMPLETED")
    date_sent_mc_mgr = fields.Date("DATE SENT TO MARKET COMMERCIAL MGR")
    date_routed_for_sig = fields.Date("DATE ROUTED FOR SIGNATURE")
    date_sent_to_fin_sing = fields.Date("DATE SENT TO FINANCE SINGAPORE")
    total_days_processed = fields.Integer("TOTAL NO. OF DAYS PROCESSED", compute='get_compute_data')
    date_ffcr_sgd_copy_received = fields.Date("DATE FFCR SIGNED COPY RECEIVED")
    date_cn_note_issued = fields.Date("DATE CN NOTE ISSUED")
    cn_no = fields.Char("CN NO.")
    cn_amount = fields.Char("CN AMOUNT, USD")
    state = fields.Selection([('draft','Draft'),('resolution','For Resolution'),('done','Done')], default='draft', string="State", track_visibility='onchange')
    car_id = fields.One2many('dmpi.crm.corrective.action', 'ffcr_id', "CAR IDS", ondelete='cascade')



class DmpiCrmCorrectiveAction(models.Model):
    _name = 'dmpi.crm.corrective.action'
    _descriptions = 'Corrective Actions Report CAR'
    _inherit = ['mail.thread']



    @api.depends('date_replied','date_issued')
    def get_compute_data(self):
        for rec in self:
            date_replied = datetime.strptime(rec.date_replied, "%Y-%m-%d")
            date_issued = datetime.strptime(rec.date_issued, "%Y-%m-%d")
            # print ((date2-date1).days)
            rec.aop_ata = (pack_date-date_arrival).days



    @api.model
    def create(self, vals):
        s = self.env['dmpi.crm.corrective.action'].search([],order='car_series_no desc', limit=1).car_series_no + 1
        series_no = '%04d' % s
        series_year = datetime.now().year
        ph = self.env['dmpi.crm.complaint.ph'].search([('id','=',vals['ph'])], limit=1).name
        vals['car_series_no'] = s
        vals['car_series_year'] = series_year
        vals['name'] = "CAR-%s-%s-%s" % (ph,series_year,series_no)
        res = super(DmpiCrmCorrectiveAction, self).create(vals)
        return res



    name = fields.Char("CAR no.")
    ph = fields.Many2one('dmpi.crm.complaint.ph', "PH", required=True)
    car_series_no = fields.Integer('Series No')
    car_series_year = fields.Integer('Series Year')
    ffcr_id = fields.Many2one('dmpi.crm.complaint.report',"FFCR ID")
    initiator = fields.Char("Initiator")
    date_issued = fields.Date("Date issued", default=fields.Datetime.now())
    date_replied = fields.Date("Date replied")
    no_response_time = fields.Char("No. of response time")
    ffcr_no = fields.Char("FFCR no.", related='ffcr_id.name')
    desription_non_conf = fields.Char("Description of Non-conformity")
    complaint_feedback_plantation = fields.Text("Complaint / Feedback / Deviation")
    dept_area_affected = fields.Char("Department / Area affected")
    source_non_conformity = fields.Char("Source of Non-conformity")
    root_cause = fields.Char("Root Cause")
    corrective_actions = fields.Char("Corrective Actions")
    responsible = fields.Char("Responsible")
    timeline_week = fields.Integer("Timeline (Week)")
    timeline_date = fields.Date("Timeline (Commited Date)")
    date_verified = fields.Char("Date Verified")
    verified_by = fields.Char("Verified By")
    corrective_action_status = fields.Selection([('draft','Open'),('in_progress','In Progress'),('done','Done')], default='draft', string="Corrective Action Status", track_visibility='onchange')
    non_conformity_status = fields.Selection([('open','Open'),('close','Closed')], default='open', string="Non Conformity Status", track_visibility='onchange')
    remarks = fields.Text("Other remarks")



                                                                                            


