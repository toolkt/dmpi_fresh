from odoo import _
from odoo import models, api, fields, tools
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


CROWN = [('C','w/Crown'),('CL','Crownless')]

class DmpiCrmMarketAllocation(models.Model):
    _name = 'dmpi.crm.market.allocation'
    _inherit = ['mail.thread']



    @api.multi
    def action_generate_report(self):
        for rec in self:

            th = lambda x: """<th data-original-title="" title="" style="text-align: center; color:#FFF; background-color: #78717e;" >%s</th>""" % x 
            td = lambda x: """<td class="o_data_cell o_list_number">%s</td>""" % x
            a = lambda x,y: """<a href="/web#id=%s&view_type=form&model=dmpi.crm.sale.order&menu_id=96&action=107" target="self">%s</a> """ % (x,y) 


            query = """
(
    SELECT 
            0 as so_id,
            '' as week_no,
            '' as country,
            '' as so_no,
            '' as customer,
            '' as ship_to, 
            name as prod_code,
            sequence,
            '' as shell_color,
            product_crown, 
                        psd,
            0 as qty
    FROM dmpi_crm_product_code pc WHERE active=TRUE 
    ORDER BY pc.sequence
)

UNION ALL

(
    SELECT
            so.id as so_id,
            so.week_no,
            cc.name as country,
            so.name as so_no,
            cust.name as customer,
            shp.name as ship_to,
            pc.name as prod_code,
            pc.sequence,
            so.shell_color,
            prod.product_crown,
            prod.psd,
            sum(sol.qty) as qty
    from dmpi_crm_sale_order_line sol
    left join dmpi_crm_sale_order so on so.id = sol.order_id
    left join dmpi_crm_ship_to shp on shp.id = so.ship_to_id
    left join dmpi_crm_sale_contract ctr on ctr.id = so.contract_id
    left join dmpi_crm_partner cust on cust.id = ctr.partner_id
    left join dmpi_crm_product prod on prod.id = sol.product_id
    left join dmpi_crm_product_code pc on pc.name = sol.product_code
    left join dmpi_crm_country cc on cc.id = shp.country_id
    where so.week_no like '%%%s%%'
    group by so.id,so.week_no,cc.name,so.name,cust.name,shp.name,pc.name,pc.sequence,so.shell_color,prod.product_crown,prod.psd

)
            """  % rec[0].week_no

            # print (query)
            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()

            df = pd.DataFrame.from_dict(result)
            pd_res = pd.pivot_table(df, values='qty', index=['so_id','country','so_no','customer','ship_to'], 
                columns=['sequence','prod_code'],fill_value=0, aggfunc=np.sum, margins=True)
            print(pd_res)
            pd_res_vals = pd_res.reset_index().values

            h1 = []
            h1.append(th('Country'))
            h1.append(th('SO No'))
            h1.append(th('Ship To'))

            active_products = self.env['dmpi.crm.product.code'].search([('active','=',True)],order='sequence')
            number_of_active_products = len(active_products)
            for h in active_products:
                h1.append(th(h.name))
                
            h1.append(th('TOTAL'))
                
            trow = []
            col_totals = []
            for l in pd_res_vals:
                td_data = []
                # print (l)
                if l[0] != 0:
                    if l[0] == 'All':
                        td_data.append(th(l[1]))
                        td_data.append(th(a(l[0],l[2])))
                        td_data.append(th(l[3]))
                        td_data.append(th(l[4]))
                        

                        for d in l[5:]:
                            d = round(d)
                            td_data.append(th(d))
                            # col_totals.append({'prod_code': , 'qty':d})

                        trow_data = """<tr class="o_data_row"> %s </tr>""" % ''.join(td_data)
                        trow.append(trow_data)

                    else:
                        td_data.append(td(l[1]))
                        td_data.append(td(a(l[0],l[2])))
                        td_data.append(td(l[3]))
                        td_data.append(td(l[4]))
                        
                        for d in l[5:]:
                            d = round(d)
                            td_data.append(td(d))

                        trow_data = """<tr class="o_data_row"> %s </tr>""" % ''.join(td_data)
                        trow.append(trow_data)



            query = """
SELECT prod_code, SUM(qty) AS qty
FROM (
    (SELECT 
    pc.sequence,
    pc.name as prod_code,
    0 as qty
    FROM dmpi_crm_product_code pc where pc.active is True
    order by pc.sequence)

    UNION ALL

    (SELECT  
    pc.sequence,
    pc.name as prod_code,
    Sum(al.crop + al.sb + al.dmf) as qty
    from  dmpi_crm_market_allocation_line al
    JOIN dmpi_crm_product_code pc on (pc.product_crown = al.product_crown and pc.psd = al.psd)
    where allocation_id = 1
    group by pc.name,pc.sequence
    order by pc.sequence)
)AS Q1
GROUP BY prod_code, sequence
ORDER BY sequence
            """
            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()


            print (col_totals)
            print (result)

                    #Compute Totals

            # msg = """<a href="/web?#id=87&view_type=form&model=dmpi.crm.sale.contract&menu_id=84&action=97" target="self">test link</a> """

            

            rec.html_report = """
                <table class="o_list_view table table-condensed table-striped o_list_view_ungrouped">
                    <thead><tr> %s </tr></thead>
                    <tbody> %s </tbody>
                </table>
            """ %(''.join(h1),''.join(trow))


    name = fields.Char("Name")
    notes = fields.Text("Notes")
    html_report = fields.Html("Report")
    html_report_disp = fields.Html("Report Display", related='html_report')
    week_no = fields.Char("Week No")
    date_from = fields.Date("Date From")
    date_to = fields.Date("Date To")
    line_ids = fields.One2many('dmpi.crm.market.allocation.line','allocation_id','Allocations', copy=True)
    state = fields.Selection([('draft','Draft'),('final','Done'),('cancel','Cancelled')], "State")
    tag_ids = fields.Many2many('dmpi.crm.product.price.tag', 'market_allocation_tag_rel', 'allocation_id', 'tag_id', string='Price Tags', copy=True)




class DmpiCrmMarketAllocationLine(models.Model):
    _name = 'dmpi.crm.market.allocation.line'

    @api.depends('corp','dmf','sb')
    def _get_total(self):
    	for rec in self:
    		rec.total = rec.corp + rec.dmf + rec.sb 

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
    allocation_id = fields.Many2one('dmpi.crm.market.allocation',"Allocation ID", ondelete='cascade')
    grade = fields.Selection([('EX','Export'),('B','Class B'),('BA','Class B to A')], "Grade")
    product_crown   = fields.Selection(_get_product_crown,'Crown')
    corp = fields.Float("CORP")
    dmf = fields.Float("DMF")
    sb = fields.Float("SB")
    total = fields.Float("Total",compute='_get_total')


class DmpiCrmReportOrderLines(models.Model):
    _name = 'dmpi.crm.report.order.lines'
    _auto = False
    _order = 'product_code_seq'


    sold_to = fields.Char("Sold To")
    notify_party = fields.Char("Notify Party")
    ship_to = fields.Char("Ship To")
    destination = fields.Char("Destination")
    odoo_po_no = fields.Char("Odoo Po No")
    sap_cn_no = fields.Char("SAP Cn No")
    customer_ref = fields.Char("Customer Ref")
    po_date = fields.Date("PO Date")
    state = fields.Char("State")
    week_no = fields.Char("Week No")
    shell_color = fields.Char("Shell Color")
    description = fields.Char("Description")
    qty = fields.Integer("QTY")
    product_code = fields.Char("Product Code")
    product_code_seq = fields.Integer("Product Sequence")
    product_crown = fields.Selection(CROWN,"Product Crown")
    psd = fields.Integer("PSD")
    price = fields.Float("Price")
    amount = fields.Float("Amount")
    country = fields.Char("Country")

    @api.model_cr
    def init(self):
        tools.drop_view_if_exists(self._cr, 'dmpi_crm_report_order_lines')
        self._cr.execute(""" create view dmpi_crm_report_order_lines as (
SELECT 
        sol.id,
                            so.id as so_id,
        cp.name as sold_to,
        nt.customer_name as notify_party,
        st.customer_name as ship_to,
        so.destination,
        co.name as odoo_po_no,
        co.sap_cn_no,
        co.customer_ref,
        co.po_date,
        so.state,
        so.week_no,
        so.shell_color,
        sol.name as description, 
        sol.qty, 
        sol.product_code,
        pc.sequence::INT as product_code_seq,
        pc.product_crown,
        pr.psd,
        sol.price,
        sol.qty * sol.price as amount,
        cc.name as country
FROM dmpi_crm_sale_order_line sol
left join dmpi_crm_sale_order so on so.id = sol.order_id
left join dmpi_crm_sale_contract co on co.id = so.contract_id
left join dmpi_crm_partner cp on cp.id = co.partner_id
left join dmpi_crm_ship_to st on st.id = so.ship_to_id
left join dmpi_crm_ship_to nt on nt.id = so.notify_id
left join dmpi_crm_product pr on pr.id = sol.product_id 
left join dmpi_crm_product_code pc on pc.name = sol.product_code
left join dmpi_crm_country cc on cc.id = st.country_id


            )
            """)






