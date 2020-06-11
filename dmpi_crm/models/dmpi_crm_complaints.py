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


    @api.depends('date_arrival','first_pack_date','date_pullout','date_inspection','date_last_doc_completed','date_claim_endorsement_receipt')
    def get_compute_data(self):
        for rec in self:
            if not(not(rec.date_arrival) or not(rec.first_pack_date)):
                date_arrival = datetime.strptime(rec.date_arrival, "%Y-%m-%d")
                first_pack_date = datetime.strptime(rec.first_pack_date, "%Y-%m-%d")
                rec.aop_ata = (date_arrival-first_pack_date).days

            if not(not(rec.date_pullout) or not(rec.first_pack_date)):
                date_pullout = datetime.strptime(rec.date_pullout, "%Y-%m-%d")
                first_pack_date = datetime.strptime(rec.first_pack_date, "%Y-%m-%d")
                rec.aop_pull_out = (date_pullout-first_pack_date).days

            if not(not(rec.date_inspection) or not(rec.first_pack_date)):
                first_pack_date = datetime.strptime(rec.first_pack_date, "%Y-%m-%d")
                date_inspection = datetime.strptime(rec.date_inspection, "%Y-%m-%d")
                rec.aop_inspect = (date_inspection-first_pack_date).days
                

            if not(not(rec.date_last_doc_completed) or not(rec.date_claim_endorsement_receipt)):
                date_last_doc_completed = datetime.strptime(rec.date_last_doc_completed, "%Y-%m-%d")
                date_claim_notif = datetime.strptime(rec.date_claim_notif, "%Y-%m-%d")
                rec.total_days_processed = (date_last_doc_completed-date_claim_notif).days


    # @api.model
    # def create(self, vals):
    #     s = self.env['dmpi.crm.complaint.report'].search([],order='ffcr_series_no desc', limit=1).ffcr_series_no + 1
    #     series_no = '%03d' % s
    #     series_year = datetime.now().year
    #     vals['ffcr_series_no'] = s
    #     vals['ffcr_series_year'] = series_year
    #     vals['name'] = "FCR%s-%s" % (series_no,series_year)
    #     res = super(DmpiCrmComplaintReport, self).create(vals)
    #     return res

    @api.multi
    def action_submit_complaint(self):
        for rec in self:
            rec.state = 'resolution'

    @api.onchange('preship_id')
    def on_change_preship_id(self):
        print ("Onchange Preship")
        self.variety = self.preship_id.variety.name
        self.week = self.clp_id.week
        self.vessel = self.clp_id.vessel_name 
        self.total_score = self.preship_id.total_score
        self.total_class = self.preship_id.total_class
        self.pack_size = self.preship_id.pack_size
        self.market = self.clp_id.port_destination
        self.customer = self.clp_id.customer

    @api.onchange('claim_nature_ids')
    def on_change_claim_nature_ids(self):
        claim_nature_desc = []
        for d in self.claim_nature_ids:
            claim_nature_desc.append(d.name)
        self.claim_nature_desc = ','.join([x for x in claim_nature_desc])
        

    @api.onchange('clp_id')
    def on_change_clp_id(self):
        print ("Onchange Preship")
        preship_ids = [x.id for x in self.clp_id.preship_ids]
        if len(preship_ids) > 0:
            self.preship_id = preship_ids[0]


    name = fields.Char("FFCR Series No.")
    preship_id = fields.Many2one('dmpi.crm.preship.report', string='Preship No.')
    clp_id = fields.Many2one('dmpi.crm.clp', string='CLP No.')

    ffcr_series_no = fields.Integer('Series No')
    ffcr_series_year = fields.Integer('Series Year')

    report_count = fields.Integer('Count')
    report_type = fields.Selection([('Complaint','Complaint'),('Feedback','Feedback')],"Report Type")
    
    customer = fields.Char(string="Customer")
    market = fields.Char("Market")
    plant = fields.Char("PH", related='clp_id.plant')
    variety = fields.Char(string='Variety')
    pack_size = fields.Char(string='Pack Size')
    pack_type = fields.Char(string='Pack Type')
    container_no = fields.Char("Container No.", related='clp_id.container_no')
    week = fields.Char("Week")

    # claim_nature_id = fields.Many2one('dmpi.crm.complaint.claim.nature',"Nature of Claim")
    claim_nature_ids = fields.Many2many('dmpi.crm.complaint.claim.nature','ffcr_claim_rel','ffcr_id','claim_nature_id',"Nature of Claim")
    claim_nature_desc = fields.Char("Nature of Claim Desc")
    description = fields.Char("Complaint description")
    pack_date = fields.Char("Pack Date", related='preship_id.date_pack')
    first_pack_date = fields.Date("First Pack Date")
    box_affected = fields.Integer("No of Boxes Affected")
    box_code = fields.Char("Box Code")
    claim_amount = fields.Float("Claim Amount (USD)")
    po_no = fields.Char("PO No.")
    inv_no = fields.Char("Invoice No.")
    month_claimed = fields.Date("Month Claimed", default=fields.Datetime.now())
    
    incoterm = fields.Char("Incoterm")
    date_atd_pol = fields.Date("ATD at POL")
    date_arrival = fields.Date("Date of Arrival")
    date_pullout = fields.Date("Date of Pull-out")
    date_inspection = fields.Date("Date of Inspection")
    aop_ata = fields.Integer("AOP at ATA", compute='get_compute_data')
    aop_pull_out = fields.Integer("AOP at Pull-out", compute='get_compute_data')
    aop_inspect = fields.Integer("AOP at Inspection", compute='get_compute_data')
    feeder_vessel = fields.Char("Feeder Vessel")
    delay_reason = fields.Char("Reason for Delay")
    temp_reading = fields.Text("Temperature Reading")

    date_qc_report_receipt = fields.Date("QC Report Receipt")
    date_claim_notif = fields.Date("Date of Claim Notification")
    date_claim_bill_receipt = fields.Date("Date of Claim Bill Receipt")
    date_temp_logger_receipt = fields.Date("Date of Temp Logger Receipt")
    date_claim_endorsement_receipt = fields.Date("Date of Claim Endorsement Receipt")
    date_last_doc_completed = fields.Date("Date of Last Document Completed")
    date_sent_mc_mgr = fields.Date("Date sent to Market Commercial Mgr")
    date_routed_for_sig = fields.Date("Date routed for signature")
    date_sent_to_fin_sing = fields.Date("Date sent to Finance Singapore")
    total_days_processed = fields.Integer("Total no of days processed", compute='get_compute_data')
    date_ffcr_sgd_copy_received = fields.Date("Date FFCR signed copy received")
    date_cn_note_issued = fields.Date("Date of CN Note issued")
    cn_no = fields.Char("CN No.")
    cn_amount = fields.Char("CN Amount (USD)")
    state = fields.Selection([('draft','Draft'),('resolution','For Resolution'),('done','Done')], default='draft', string="State", track_visibility='onchange')
    car_id = fields.One2many('dmpi.crm.corrective.action', 'ffcr_id', "CAR Ids", ondelete='cascade')


    total_score = fields.Char("Preship Score")
    total_class = fields.Char("Preship Class")
    preship_eval = fields.Text("Preship Evaluation")
    post_harvest_tmnt = fields.Text("Post-harvest Treatment")
    remarks = fields.Text("Remarks")
    simulation_eval = fields.Text("Simulation Evaluation")
    date_simul_eval = fields.Date("Date Simulation Evavluated")
    aop_upon_simul = fields.Char("AOP upon Simulation")
    date_mqa_eval = fields.Date("Date MQA Evavluation")
    mqa_eval_result = fields.Text("MQA Evaluation Result")
    aop_mqa_evaluation = fields.Char("AOP at MQA Evaluation")
    deviation_exception = fields.Text("Deviation/Exceptions")
    qa_recommendation = fields.Text("QA Recommendations")




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



                                                                                            


