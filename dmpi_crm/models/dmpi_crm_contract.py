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


CONTRACT_STATE = [
        ('draft','Draft'),
        ('submitted','Submitted'),
        ('confirmed','Confirmed'),
        ('soa','Statement of Account'),
        ('approved','Approved'),
        ('processed','Processed'),
        ('enroute','Enroute'),
        ('received','Received'),
        ('cancel','Cancelled')]


def read_data(data):
    if data:
        fileobj = TemporaryFile("w+")
        fileobj.write(base64.b64decode(data).decode('utf-8'))
        fileobj.seek(0)

        rows = csv.reader(fileobj, quotechar='"', delimiter=',')

        return rows



class DmpiCrmContractType(models.Model):
    _name = 'dmpi.crm.contract.type'

    name = fields.Char("Code")
    description = fields.Char("Description")
    default = fields.Boolean("Default")

class DmpiCrmProductType(models.Model):
    _name = 'dmpi.crm.product.type'
    _order = 'sequence,id'

    name = fields.Char("Code")
    description = fields.Char("Description")
    sequence = fields.Integer("Sequence", default=1)
    sequence_disp = fields.Integer("Sequence", related='sequence')
    product_map = fields.Char("Product Map")


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


    def _get_contract_type(self):
        group = 'contract_type'
        query = """SELECT t.name as select_name,t.name as select_value from dmpi_crm_contract_type t """
        self.env.cr.execute(query)
        result = self.env.cr.dictfetchall()
        res = [(r['select_value'],r['select_name']) for r in result]
        return res

    def _get_contract_type_default(self):
        res = self.env['dmpi.crm.contract.type'].search([('default','=',True)],limit=1)[0].name
        return res



    contract_id = fields.Many2one("dmpi.crm.contract","Contract")
    destination_id = fields.Many2one("dmpi.crm.ship.to","Ship To")
    product_id = fields.Many2one("dmpi.crm.product.type","Product Type")
    qty = fields.Integer("Quantity")



    po_display_number = fields.Char("PO Numbers", compute="_get_po_display_number")
    
    #Contract Details
    name = fields.Char("ContractNo", default="Draft")
    sap_cn_no = fields.Char("SAP Contract no.")
    customer_ref = fields.Char("Customer Reference")
    partner_id = fields.Many2one('dmpi.crm.partner',"Customer")
    contract_type = fields.Selection(_get_contract_type,"Contract Type", default=_get_contract_type_default)
    po_date = fields.Date("PO Date", default=fields.Date.context_today)
    valid_from = fields.Date("Valid From", default=fields.Date.context_today)
    valid_to = fields.Date("Valid To")
    week_no = fields.Integer("Week No", default=lambda *a:datetime.now().isocalendar()[1])

    #Line Items
    contract_line_ids = fields.One2many('dmpi.crm.contract.line', 'contract_id','Contract Lines')
    sheet_data = fields.Text("Sheet Data")

    #Upload Details
    upload_file = fields.Binary("Upload")

    #Status
    state = fields.Selection(CONTRACT_STATE,string="State", default='draft')
    active = fields.Boolean("Active", default=True)


    @api.multi
    def action_upload(self):
        for rec in self:
            body = "Uploaded file"
            rec.message_post(body=body)


    @api.multi
    def action_submit(self):
        for rec in self:
            print (rec)


    @api.onchange('upload_file')
    def onchange_upload_file(self):
        if self.upload_file:
            rows = read_data(self.upload_file)
            for r in rows:
                print(r)



class DmpiCrmShipTo(models.Model):
    _name = 'dmpi.crm.ship.to'


    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('destination', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        accounts = self.search(domain + args, limit=limit)
        return accounts.name_get()


    @api.multi
    @api.depends('name', 'destination')
    def name_get(self):
        result = []
        for rec in self:
            destination = ''
            if rec.destination:
                destination = rec.destination
            name = destination+' [' + rec.name+ ']'
            result.append((rec.id, name))
        return result


    name = fields.Char("Ship to Code", required=True)
    name_disp = fields.Char("Ship to Code", placeholder="Shipto Code", related='name')
    customer_name = fields.Char("Corporate Name")
    customer_code = fields.Char("Customer Code")
    registered_address = fields.Text("Registered Address")
    contact_no = fields.Char("Contact No")
    contact_person = fields.Char("Contact Person")
    contact_person_email = fields.Char("Contact Email")
    destination = fields.Char("Destination")
    notify_party = fields.Char("Notify Party")
    notify_party_detail = fields.Text("Notify Party Details")
    ship_to = fields.Char("Consignee / Ship to")
    ship_to_detail = fields.Text("Consignee / Ship to Details")
    incoterm = fields.Char("Incoterm")
    mailing_address = fields.Text("Mailing Address")




class DmpiCrmContractLine(models.Model):
    _name = 'dmpi.crm.contract.line'


    def _get_p1(self):
        name = self.env['dmpi.crm.product.type'].search([('product_map','=','P1')],limit=1)[0].name
        res = name
        if not name:
            res = "P1"
        return "P5"


    contract_id = fields.Many2one("dmpi.crm.contract","Contract")
    destination_id = fields.Many2one("dmpi.crm.ship.to","Ship To")
    product_id = fields.Many2one("dmpi.crm.product.type","Product Type")

    qty = fields.Integer("Quantity")





