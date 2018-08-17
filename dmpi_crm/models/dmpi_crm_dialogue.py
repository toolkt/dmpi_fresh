# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError


class CrmProcessSaleOrder(models.TransientModel):
    """
    This wizard will confirm the all the selected draft invoices
    """

    _name = "crm.process.sale.order"
    _description = "CRM Process Sale Order"

    @api.multi
    def process_so_hold(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        
        for record in self.env['dmpi.crm.sale.order'].browse(active_ids):
            if record.state != 'draft':
                record.write({'state':'hold'})
        return {'type': 'ir.actions.act_window_close'}


    @api.multi
    def process_so_confirm(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        for record in self.env['dmpi.crm.sale.order'].browse(active_ids):
            if record.state != 'draft':
                record.write({'state':'confirmed'})
        return {'type': 'ir.actions.act_window_close'}


    @api.multi
    def process_so_send_to_sap(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        
        for record in self.env['dmpi.crm.sale.order'].browse(active_ids):
            if record.state == 'confirmed' and record.contract_id.sap_cn_no != '' :
                print (record[0])
                record[0].submit_so_file(record[0])
            else:
                raise UserError(_("You can only send Confirmed SOs whose POs were already Processed"))
        return {'type': 'ir.actions.act_window_close'}





    @api.multi
    def process_po_confirm(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        for record in self.env['dmpi.crm.sale.order'].browse(active_ids):
            if record.contract_id.state in ['confirmed','submitted']:
                record.contract_id.action_confirm_contract()
            else:
                raise UserError(_("You can only confirm POs that are either Submitted or For Confirmation"))
        return {'type': 'ir.actions.act_window_close'}



    @api.multi
    def process_po_approve(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        for record in self.env['dmpi.crm.sale.order'].browse(active_ids):
            if record.contract_id.state == 'confirmed':
                record.contract_id.action_approve_contract()
            else:
                raise UserError(_("You can only approve POs that are Confirmed"))
        return {'type': 'ir.actions.act_window_close'}



    @api.multi
    def process_po_send_to_sap(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        for record in self.env['dmpi.crm.sale.order'].browse(active_ids):
            if record.contract_id.state == 'approved':
                record.contract_id.action_send_contract_to_sap()
            else:
                raise UserError(_("You can only Send POs to SAP if the POs are already approved"))
        return {'type': 'ir.actions.act_window_close'}



class CrmProcessSaleContract(models.TransientModel):
    """
    This wizard will confirm the all the selected draft invoices
    """

    _name = "crm.process.sale.contract"
    _description = "CRM Process Sale Contract"

    @api.multi
    def process_so_hold(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        
        for record in self.env['dmpi.crm.sale.contract'].browse(active_ids):
            if record.state != 'draft':
                record.write({'state':'hold'})
            else:
                raise UserError(_("You can only send Confirmed SOs whose POs were already Processed"))
        return {'type': 'ir.actions.act_window_close'}



    