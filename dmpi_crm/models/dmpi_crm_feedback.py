# -*- coding: utf-8 -*-

from odoo import _
from odoo.osv import expression
from odoo import models, api, fields
from odoo.exceptions import  Warning, RedirectWarning, ValidationError, AccessError, UserError
from datetime import datetime, timedelta
from dateutil.parser import parse
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class DmpiCrmFeedback(models.Model):
    _name = 'dmpi.crm.feedback'
    _description = 'CRM Feedback'
    _inherit = ['mail.thread']


    name = fields.Char("Subject")
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Contract ID")
    note_type = fields.Selection([('message','Message'),('feedback','Feedback'),('quality','Quality Control')], default='message',string="Note Type")
    user = fields.Many2one('res.users', related='create_uid', default=lambda self: self.env.user)
    date = fields.Datetime("Date", default=fields.Datetime.now())
    body_html = fields.Text('Contents', default='', sanitize_style=True, strip_classes=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'message_attachment_rel',
        'message_id', 'attachment_id',
        string='Attachments',
        help='Attachments are linked to a document through model / res_id and to the message '
             'through this field.')


class DmpiCrmFiles(models.Model):
    _name = 'dmpi.crm.files'
    _description = 'CRM Files'

    name = fields.Char("Name")
    description = fields.Char("Description")
    attachment_ids = fields.Many2many(
        'ir.attachment', 'message_attachment_rel',
        'message_id', 'attachment_id',
        string='Attachments',
        help='Attachments are linked to a document through model / res_id and to the message '
             'through this field.')