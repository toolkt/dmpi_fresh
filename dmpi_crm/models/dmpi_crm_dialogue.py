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

    