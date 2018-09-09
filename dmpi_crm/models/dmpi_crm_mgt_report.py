from odoo import _
from odoo import models, api, fields
from odoo.exceptions import ValidationError, AccessError, UserError
from datetime import datetime, timedelta

import odoo.addons.decimal_precision as dp

from odoo.http import request

# pip3 install Fabric3
from fabric.api import *
import paramiko
import socket
import os
import glob
import csv

import tempfile
from io import BytesIO
import re
import pprint
import base64
import pandas as pd
import numpy as np


class DmpiCrmMarketAllocation(models.Model):
    _name = 'dmpi.crm.market.allocation'
    _inherit = ['mail.thread']


    @api.multi
    def action_generate_report(self):
        for rec in self:

            th = lambda x: """<th data-original-title="" title="" style="text-align: center; color:#FFF; background-color: #78717e;" >%s</th>""" % x 
            td = lambda x: """<td class="o_data_cell o_list_number">%s</td>""" % x

            query = """ SELECT psd
                    FROM dmpi_crm_product_code pc WHERE active=TRUE 
                    GROUP BY psd ORDER BY psd
                """
            # print (query)
            self.env.cr.execute(query)
            result = self.env.cr.fetchall()  

            h1 = []
            h1.append(th('Customer/ PSD'))
            h1.append(th('Shell Color'))
            for p in result:
                h1.append(th(p))
            h1.append(th('TOTAL'))
            h1.append(th('# of FCL'))
            h1.append(th('PO Quantity'))
            # print(psd)

            query = """ SELECT 
                            so.week_no, 
                            cust.name as customer, 
                            shp.name as ship_to,  
                            prod.psd, 
                            so.shell_color,
                            prod.product_crown, 
                            sum(sol.qty) as qty
                        from dmpi_crm_sale_order_line sol
                        left join dmpi_crm_sale_order so on so.id = sol.order_id
                        left join dmpi_crm_ship_to shp on shp.id = so.ship_to_id
                        left join dmpi_crm_sale_contract ctr on ctr.id = so.contract_id
                        left join dmpi_crm_partner cust on cust.id = ctr.partner_id
                        left join dmpi_crm_product prod on prod.id = sol.product_id
                        where so.week_no like '%%%s%%'
                        group by so.week_no,cust.name,shp.name,prod.psd,so.shell_color,prod.product_crown
                        ORDER BY cust.name,shp.name, prod.psd
            """ % rec[0].week_no

            query = """
                SELECT
                        so.week_no,
                        cust.name as customer,
                        shp.name as ship_to,
                        prod.psd,
                        so.shell_color,
                        prod.product_crown,
                        sum(sol.qty) as qty
                from dmpi_crm_sale_order_line sol
                left join dmpi_crm_sale_order so on so.id = sol.order_id
                left join dmpi_crm_ship_to shp on shp.id = so.ship_to_id
                left join dmpi_crm_sale_contract ctr on ctr.id = so.contract_id
                left join dmpi_crm_partner cust on cust.id = ctr.partner_id
                left join dmpi_crm_product prod on prod.id = sol.product_id
                where so.week_no like '%33%'
                group by so.week_no,cust.name,shp.name,prod.psd,so.shell_color,prod.product_crown

                UNION ALL

                SELECT '' as week_no,'' as customer,'' as ship_to, psd,'' as shell_color,'' as product_crown, 0 as qty
                FROM dmpi_crm_product_code pc WHERE active=TRUE 
                GROUP BY psd ORDER BY psd
            """

            print (query)
            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()

            df = pd.DataFrame.from_dict(result)
            pd_res = pd.pivot_table(df, values='qty', index=['week_no','customer','ship_to'], columns=['psd','product_crown'],fill_value=0, aggfunc=np.sum)
            print(pd_res)

            headers = []
            skus = []
            rows = []
            total_amount = 0
            total_qty = 0
            for l in result:
                print(l)
                # for p in psd:
                #     if l['psd'] == p: 

                # total_amount += l['amount'] or 0
                # total_qty += l['qty'] or 0

   #              if l['psd'] == '5': rec.p101 = l['qty'] 
   #              if l['psd'] == '6': rec.p102 = l['qty']
   #              if l['psd'] == '7': rec.p103 = l['qty']
   #              if l['psd'] == '8': rec.p104 = l['qty']
   #              if l['psd'] == '9': rec.p105 = l['qty']
   #              if l['psd'] == '10': rec.p106 = l['qty']
   #              if l['psd'] == '12': rec.p107 = l['qty']
   #              if l['psd'] == '14': rec.p108 = l['qty']
   #              if l['psd'] == '15': rec.p109 = l['qty']
   #              if l['psd'] == '16': rec.p110 = l['qty']

   #              if l['code'] == 'P5C7': rec.p201 = l['qty']
   #              if l['code'] == 'P6C8': rec.p202 = l['qty']
   #              if l['code'] == 'P7C9': rec.p203 = l['qty']
   #              if l['code'] == 'P8C10': rec.p204 = l['qty']
   #              if l['code'] == 'P9C11': rec.p205 = l['qty']
   #              if l['code'] == 'P10C12': rec.p206 = l['qty']
   #              if l['code'] == 'P12C20': rec.p207 = l['qty']
   #              if l['code'] == 'P': rec.p208 = l['qty']
   #              if l['code'] == 'P': rec.p209 = l['qty']
   #              if l['code'] == 'P': rec.p210 = l['qty']

   #              headers.append("""<th data-original-title="" title="" style="text-align: center; color:#FFF; background-color: #78717e;" >%s</th>""" % l['code'])
   #              # skus.append("""<th data-original-title="" title="" style="text-align: center; color:#FFF; background-color: #999999;" >%s</th>""" % '7AOB19912')# l['sku'])
   #              rows.append("""<td class="o_data_cell o_list_number">%s</td>""" % l['qty'])

            rec.html_report = """
                <table class="o_list_view table table-condensed table-striped o_list_view_ungrouped">
                    <thead><tr> %s </tr></thead>
                    <tbody> <tr class="o_data_row"> %s </tr> </tbody>
                </table>
            """ %(''.join(h1),''.join(h1))


    name = fields.Char("Name")
    notes = fields.Text("Notes")
    html_report = fields.Html("Report")
    html_report_disp = fields.Html("Report Display", related='html_report')
    week_no = fields.Char("Week No")
    date_from = fields.Date("Date From")
    date_to = fields.Date("Date To")
    line_ids = fields.One2many('dmpi.crm.market.allocation.line','allocation_id','Allocations', copy=True)
    state = fields.Selection([('draft','Draft'),('final','Done'),('cancel','Cancelled')], "State")



class DmpiCrmMarketAllocationLine(models.Model):
    _name = 'dmpi.crm.market.allocation.line'

    @api.depends('crop','dmf','sb')
    def _get_total(self):
    	for rec in self:
    		rec.total = rec.crop + rec.dmf + rec.sb 

    def _get_product_crown(self):
        group = 'product_crown'
        query = """SELECT cs.select_name,cs.select_value
                from dmpi_crm_config_selection cs
                left join dmpi_crm_config cc on cc.id = cs.config_id
                where select_group = '%s'  and cc.active is True and cc.default is True
                order by sequence 
                """ % group
        self.env.cr.execute(query)
        result = self.env.cr.dictfetchall()
        res = [(r['select_value'],r['select_name']) for r in result]
        return res


    # name = fields.Char("Name")
    psd = fields.Integer("PSD")
    allocation_id = fields.Many2one('dmpi.crm.market.allocation',"Allocation ID")
    grade = fields.Selection([('EX','Export'),('B','Class B'),('BA','Class B to A')], "Grade")
    product_crown   = fields.Selection(_get_product_crown,'Crown')
    crop = fields.Float("Crop")
    dmf = fields.Float("DMF")
    sb = fields.Float("SB")
    total = fields.Float("Total",compute='_get_total')







