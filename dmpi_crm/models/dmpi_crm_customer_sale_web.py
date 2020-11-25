# -*- coding: utf-8 -*-

from odoo import _
from odoo.osv import expression
from odoo import models, api, fields
from odoo.exceptions import  Warning, RedirectWarning, ValidationError, AccessError, UserError
from datetime import datetime, timedelta
from dateutil.parser import parse
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from textwrap import TextWrapper

from fabric.api import *
import csv
import sys
import math
import io

import base64
from tempfile import TemporaryFile
import tempfile
import re
import json

CONTRACT_STATE = [
        ('draft','Draft'),
        ('submitted','Submitted'),
        ('confirm','For Confirmation'),
        ('confirmed','Confirmed'),
        ('soa','Statement of Account'),
        ('approved','Approved'),
        ('processing','Processing'),
        ('processed','Processed'),
        ('enroute','Enroute'),
        ('received','Received'),
        ('cancel','Cancelled')]


class DmpiCrmCustomerSaleContract(models.Model):
    _name = 'dmpi.crm.customer.sale.contract'
    _description = "Customer Sale Contract"
    _inherit = ['mail.thread']


    def action_submit_contract(self):
        for rec in self:
            rec.contract_id.action_submit_contract()
            #print("Submit")


    @api.model
    def create(self, vals):
        res = super(DmpiCrmCustomerSaleContract, self).create(vals)
        contract = self.env['dmpi.crm.sale.contract'].create({
                'partner_id': vals['partner_id'],
                'customer_ref': vals['customer_ref'],
            })
        res.write({'contract_id':contract.id})
        res.contract_id.on_change_partner_id()
        res.contract_id.on_change_po_date()

        return res


    def _partner_id_domain(self):
        if self.env.user.has_group('dmpi_crm.group_custom_crm_customer'):
            return [('function_ids.code','=','SLD'),('id', 'in', [u.id for u in self.env.user.partner_ids])]
        else:
            return [('function_ids.code','=','SLD')]


    name = fields.Char("Contract No", related='contract_id.name')
    note = fields.Char("Note")
    state = fields.Selection(CONTRACT_STATE, string="Status", related='contract_id.state')
    upload_file = fields.Binary("Upload File")

    partner_id = fields.Many2one('dmpi.crm.partner',"Customer", domain=_partner_id_domain)
    customer_ref = fields.Char("Customer Reference", copy=False)
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Contract Reference")