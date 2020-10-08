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




class DmpiCrmDr(models.Model):
    _name = 'dmpi.crm.dr'
    _inherit = ['mail.thread']
    _order = 'id desc'

    @api.model
    def create(self, vals):

        # check duplicates
        sap_dr_no = vals.get('sap_dr_no',False)
        if sap_dr_no:
            is_duplicate, dr_count = self.check_duplicates(sap_dr_no, 'create')
            vals['is_duplicate'] = is_duplicate

        return super(DmpiCrmDr, self).create(vals)

    @api.multi
    def unlink(self):

        # check duplicates
        sap_drs = list(set( self.mapped('sap_dr_no') ))
        res = super(DmpiCrmDr, self).unlink()
        for sap_dr_no in sap_drs:
            is_duplicate, dr_count = self.check_duplicates(sap_dr_no, 'unlink')

        return res


    @api.multi
    def get_shipment_details(self):
        for rec in self:
            print ("GET DR %s" % rec.ship_to)
            shp_id = False
            try:
                shp_id = self.env['dmpi.crm.shp'].search([('sap_dr_no','=',rec.name)], limit=1, order='id desc')[0]
            except:
                pass

            try:
                shp_id = self.env['dmpi.crm.shp'].search(['|',('name','=',rec.shipment_no),('sap_dr_no','=',rec.name)], limit=1, order='id desc')[0]
            except:
                pass
                
            if shp_id:
                rec.write({
                        'ship_to':shp_id.ship_to,
                        'fwd_agent':shp_id.fwd_agent,
                        'shipment_no': shp_id.name,
                        'vessel_name': shp_id.vessel_no,
                        'van_no': shp_id.van_no,
                        'truck_no': shp_id.truck_no,
                        'load_no': shp_id.load_no,
                        'booking_no': shp_id.booking_no,
                        'seal_no': shp_id.seal_no,
                        'port_origin': shp_id.origin,
                        'port_destination': shp_id.destination,
                        'port_discharge': shp_id.discharge,
                    })

                for clp in rec.clp_ids:
                    clp.write({
                            'container_no': shp_id.van_no,
                            'seal_no': shp_id.seal_no,
                            'feeder_vessel': shp_id.vessel_no,
                            'vessel_name': shp_id.vessel_no,
                            'port_origin': shp_id.origin,
                            'port_destination': rec.port_destination,
                            'delay_reason':shp_id.delay_reason,
                            'temp_reading':shp_id.temp_reading,
                            'date_start':shp_id.date_start,
                            'date_end':shp_id.date_end,
                            'date_depart':shp_id.date_depart,
                            'date_atd_pol':shp_id.date_atd_pol,
                            'date_arrive':shp_id.date_arrive,
                            'incoterm':shp_id.incoterm,
                            'incoterm_description':shp_id.incoterm_description,
                            
                        })
                    # try:
                    #     clp.write({'date_inspection':shp_id.date_inspection})
                    # except:
                    #     pass

                    # try:
                    #     clp.write({'date_pullout':shp_id.date_pullout})
                    # except:
                    #     pass

                    # try:
                    #     clp.write({'date_arrival':shp_id.date_arrive})
                    # except:
                    #     pass


            else:
                raise UserError(_("No Shipment Details Found"))
            print(shp_id)


    @api.multi
    def check_duplicates(self, sap_dr_no, typ):
        # type = 'create' or 'unlink'
        similar_dr = self.env['dmpi.crm.dr'].search([('sap_dr_no','=',sap_dr_no)])
        dr_count = len(similar_dr)

        if dr_count > 0 and typ == 'create':
            for rec in similar_dr:
                rec.is_duplicate = True
            return True, dr_count

        if dr_count == 1 and typ == 'unlink':
            similar_dr.is_duplicate = False
            return True, dr_count

        return False, dr_count


    @api.multi
    @api.depends('sap_so_no')
    def _get_odoo_doc(self):
        for rec in self:
            
            so_id = False
            contract_id = False
            sap_so_no = rec.sap_so_no

            if sap_so_no:
                so = self.env['dmpi.crm.sale.order'].search([('sap_so_no','=',rec.sap_so_no)], limit=1)

                if so:
                    so_id = so
                    contract_id = so.contract_id

            rec.so_id = so_id
            rec.contract_id = contract_id



    # odoo docs
    name = fields.Char("DR No.", related='sap_dr_no', store=True)
    odoo_po_no = fields.Char("Odoo PO No.")
    odoo_so_no  = fields.Char("Odoo SO No.")
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Oodoo PO", compute='_get_odoo_doc', store=True)
    so_id = fields.Many2one('dmpi.crm.sale.order', 'Odoo SO', compute='_get_odoo_doc', store=True)

    # sap docs
    sap_so_no = fields.Char("SAP SO No.")
    sap_dr_no = fields.Char("SAP DR No.")
    sap_delivery_no  = fields.Char("SAP Delivery No.")
    sto_no = fields.Char("STO No.")

    # headers
    ship_to  = fields.Char("Ship To")
    shipment_no  = fields.Char("Shipment No.")
    fwd_agent  = fields.Char("Forward Agent")
    van_no  = fields.Char("Container No.")
    vessel_name  = fields.Char("Vessel Name / Voyage")
    truck_no  = fields.Char("Truck No.")
    load_no  = fields.Char("Load no.")
    booking_no  = fields.Char("Booking No.")
    seal_no  = fields.Char("Seal No.")
    delivery_creation_date  = fields.Char("Delivery Create Date")
    gi_date  = fields.Char("GI Date")
    port_origin  = fields.Char("Port of Origin")
    port_destination  = fields.Char("Port of Destination")
    port_discharge = fields.Char("Port of Discharge")

    # others
    raw = fields.Text("Raw")
    state = fields.Selection([('generated','SAP Generated'),('cancelled','Cancelled')], default="generated", string="Status", track_visibility='onchange')
    is_duplicate = fields.Boolean('Duplicate', default=False)

    dr_lines = fields.One2many('dmpi.crm.dr.line', 'dr_id', 'DR Lines')
    alt_items = fields.One2many('dmpi.crm.alt.item', 'dr_id', 'Alt Items')
    insp_lots = fields.One2many('dmpi.crm.inspection.lot', 'dr_id', 'Insp Lots')
    clp_ids = fields.One2many('dmpi.crm.clp', 'dr_id', 'CLP')
    preship_ids = fields.One2many('dmpi.crm.preship.report', 'dr_id', 'Preship Report')

    @api.multi
    def action_cancel(self):
        for rec in self:
            rec.write({'state':'cancelled'})


    @api.multi
    def action_generated(self):
        for rec in self:
            rec.write({'state':'generated'})

class DmpiCrmDrLine(models.Model):
    _name = 'dmpi.crm.dr.line'
    _rec_name = 'sku'

    container = fields.Char('Container')
    partner = fields.Char('Partner')
    
    lot = fields.Char('Inspection Lot')
    type = fields.Char('Operation Type')
    factor = fields.Char('Factor')
    no_sample = fields.Integer('No of Samples')
    no_defect = fields.Integer('No of Defects')
    dr_id = fields.Many2one('dmpi.crm.dr', 'DR ID', ondelete='cascade')


    dr_line_item_no = fields.Integer("Line No")
    sku = fields.Char('SKU')
    qty = fields.Float('Qty')
    uom = fields.Char('UOM')
    plant = fields.Char('Plant')
    wh_no = fields.Char('Warehouse No.')
    storage_loc = fields.Char('Storage Location')
    to_num = fields.Char('TO No.')
    tr_order_item = fields.Char('TR No.')
    material = fields.Char('Material')
    plant2 = fields.Char('Plant2')
    batch = fields.Char('Batch')
    stock_category = fields.Char('Tr Order item')
    source_su = fields.Char('Tr Order item')
    sap_delivery_no  = fields.Char("SAP Delivery No.")


class DmpiCrmAltItem(models.Model):
    _name = 'dmpi.crm.alt.item'

    sap_so_no = fields.Char('SAP SO No.')
    sap_so_line_no = fields.Char('So Line No.')
    material = fields.Char('Material')
    qty = fields.Float('Qty')
    uom = fields.Char('UOM')
    plant = fields.Char('Plant')
    rejection_reason = fields.Char('Rejection Reason')
    alt_item = fields.Char('SO Alternative item')
    usage = fields.Char('Usage')

    dr_id = fields.Many2one('dmpi.crm.dr', 'DR ID', ondelete='cascade')


class DmpiCrmInspectionLot(models.Model):
    _name = 'dmpi.crm.inspection.lot'

    dr_line_item_no = fields.Char('Del Line item No.')  
    sap_so_no = fields.Char('SU Material')
    stock_unit = fields.Char('Stock Unit')
    lot = fields.Char('Inspection Lot')  
    node_num = fields.Char('Node (Operation) Number') 
    type = fields.Char('Node (Operation) Description')    
    factor_num = fields.Char('Characteristic Number')  
    factor = fields.Char('Characteristic Short Text')  
    no_sample = fields.Integer('No of Samples')
    no_defect = fields.Integer('No of Defects') 
    value = fields.Float('Mean Value')

    dr_id = fields.Many2one('dmpi.crm.dr', 'DR ID', ondelete='cascade')


class DmpiCrmPreshipInspectionLot(models.Model):
    _name = 'dmpi.crm.preship.inspection.lot'

    dr_line_item_no = fields.Char('Del Line item No.')
    sap_so_no = fields.Char('SU  Material')
    lot = fields.Char('Inspection Lot')
    node_num = fields.Char('Node (Operation) Number')
    type = fields.Char('Node (Operation) Description')
    factor_num = fields.Char('Characteristic Number')
    factor = fields.Char('Characteristic Short Text')  
    no_sample = fields.Integer('No of Samples')
    no_defect = fields.Integer('No of Defects') 
    value = fields.Float('Mean Value')

    # dr_id = fields.Many2one('dmpi.crm.dr', 'DR ID', ondelete='cascade')
    preship_id = fields.Many2one('dmpi.crm.preship.report', 'Preshipment Report', ondelete='cascade')

class DmpiCrmShp(models.Model):
    _name = 'dmpi.crm.shp'
    _inherit = ['mail.thread']
    _order = 'id desc'
    # _rec_name = 'shp_no'

    @api.model
    def create(self, vals):

        # check duplicates
        shp_no = vals.get('shp_no',False)
        if shp_no:
            is_duplicate, shp_count = self.check_duplicates(shp_no, 'create')
            vals['is_duplicate'] = is_duplicate

        return super(DmpiCrmShp, self).create(vals)

    @api.multi
    def unlink(self):

        # check duplicates
        shp_nos = list(set( self.mapped('shp_no') ))
        res = super(DmpiCrmShp, self).unlink()
        for shp_no in shp_nos:
            is_duplicate, shp_count = self.check_duplicates(shp_no, 'unlink')

        return res


    @api.multi
    def check_duplicates(self, shp_no, typ):
        # type = 'create' or 'unlink'
        similar_shp = self.env['dmpi.crm.shp'].search([('shp_no','=',shp_no)])
        shp_count = len(similar_shp)

        if shp_count > 0 and typ == 'create':
            for rec in similar_shp:
                rec.is_duplicate = True
            return True, shp_count

        if shp_count == 1 and typ == 'unlink':
            similar_shp.is_duplicate = False
            return True, shp_count

        return False, shp_count


    @api.multi
    @api.depends('sap_so_no')
    def _get_odoo_doc(self):
        for rec in self:
            
            so_id = False
            contract_id = False
            sap_so_no = rec.sap_so_no

            if sap_so_no:
                so = self.env['dmpi.crm.sale.order'].search([('sap_so_no','=',rec.sap_so_no)], limit=1)

                if so:
                    so_id = so
                    contract_id = so.contract_id

            rec.so_id = so_id
            rec.contract_id = contract_id

    # odoo docs
    name = fields.Char("Shipment No.", related="shp_no", store=True)
    odoo_po_no = fields.Char("Odoo PO No.")
    odoo_so_no = fields.Char("Odoo SO No.")
    contract_id = fields.Many2one('dmpi.crm.sale.contract', "Odoo PO", compute="_get_odoo_doc", store=True)
    so_id = fields.Many2one('dmpi.crm.sale.order', 'Odoo SO', compute="_get_odoo_doc", store=True)

    # sap docs
    shp_no  = fields.Char("Shipment No.")
    sap_so_no = fields.Char("SAP SO No.")
    sap_dr_no = fields.Char("SAP DR No.")

    # headers
    ship_to = fields.Char("Ship To")
    dr_create_date = fields.Char("Delivery Create Date")
    gi_date = fields.Char("GI Date")
    fwd_agent = fields.Char("Forward Agent")
    van_no  = fields.Char("Container No.")
    vessel_no = fields.Char("Vessel Name / Voyage")
    truck_no = fields.Char("Truck No.")
    load_no  = fields.Char("Load No.")
    booking_no  = fields.Char("Boking No.")
    seal_no  = fields.Char("Seal No.")
    origin = fields.Char("Port of Origin")
    destination = fields.Char("Port of Destination")
    discharge = fields.Char("Port of Discharge")

    # additional fields
    delay_reason = fields.Char("Reason for Delay") # 19
    temp_reading = fields.Char("Temperature Reading") # 20
    date_start = fields.Char('Start') #Date time 22 23
    date_end = fields.Char('Finish') # Loading End 24 25
    date_depart = fields.Char('ETD') # 26 27
    date_atd_pol = fields.Date("ATD at POL") #28 29
    date_arrive = fields.Char('ETA') #30 31
    incoterm = fields.Char("Incoterm") # 32
    incoterm_description = fields.Char("Incoterm Description") # 33
    date_pullout = fields.Char("Date of Pull-out") #34 35
    date_inspection = fields.Char("Date of Inspection") #36 37



    # others
    raw = fields.Text("Raw")
    is_duplicate = fields.Boolean('Duplicate', default=False)

    shp_lines = fields.One2many('dmpi.crm.shp.line', 'shp_id', 'SHP Lines')
    

class DmpiCrmShpLine(models.Model):
    _name = 'dmpi.crm.shp.line'

    sap_so_no  = fields.Char("SAP SO No.")   
    so_line_no  = fields.Char("SO Line item No.")
    material  = fields.Char("Material")    
    qty  = fields.Float("SO Order Qty")
    uom  = fields.Char("SO UoM")
    plant  = fields.Char("Plant")   
    reject_reason = fields.Char("Rejection Reason")    
    alt_item   = fields.Char("SO Alternative item")   
    usage = fields.Char("Usage") 

    shp_id = fields.Many2one('dmpi.crm.shp', 'SHP ID', ondelete='cascade')
