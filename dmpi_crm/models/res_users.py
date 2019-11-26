# -*- coding: utf-8 -*-

from odoo import _
from odoo import models, api, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    partner_ids = fields.Many2many('dmpi.crm.partner','res_users_partner_rel','user_id','partner_id',string="Partners")


