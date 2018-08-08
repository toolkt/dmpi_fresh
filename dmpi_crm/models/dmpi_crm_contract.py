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




class DmpiCrmContract(models.Model):
    _name = 'dmpi.crm.contract'
    _inherit = ['mail.thread']

    @api.model
    def create(self, vals):
        contract_seq  = self.env['ir.sequence'].next_by_code('dmpi.crm.contract')
        vals['name'] = contract_seq
        print(contract_seq)
        res = super(DmpiCrmContract, self).create(vals)
        return res

    @api.depends('name','sap_cn_no')
    def _get_po_display_number(self):
        if self.name:
            sap_cn_no = ""
            if self.sap_cn_no:
                sap_cn_no = "/%s" % self.sap_cn_no
            self.po_display_number = "%s%s" % (self.name, sap_cn_no)

    po_display_number = fields.Char("PO Numbers", compute="_get_po_display_number")
    active = fields.Boolean("Active", default=True)

    name = fields.Char("ContractNo", default="Draft")
    sap_cn_no = fields.Char("SAP Contract no.")
    customer_ref = fields.Char("Customer Reference")
    partner_id = fields.Many2one('dmpi.crm.partner',"Customer")

    contract_type = fields.Selection(_get_contract_type,"Contract Type", default=_get_contract_type_default)
    po_date = fields.Date("PO Date", default=fields.Date.context_today)
    valid_from = fields.Date("Valid From", default=fields.Date.context_today)
    valid_to = fields.Date("Valid To")

    upload_file = fields.Binary("Upload")


class DmpiCrmContractLine(models.Model):
    _name = 'dmpi.crm.contract.line'


    destination     = fields.
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







