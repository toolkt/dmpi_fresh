from odoo import _
from odoo import models, api, fields, tools
from odoo.exceptions import ValidationError, AccessError, UserError
from odoo.tools.mimetypes import guess_mimetype
from datetime import datetime, timedelta
import odoo.addons.decimal_precision as dp
from odoo.http import request

import xlsxwriter, base64
# https://xlsxwriter.readthedocs.io/working_with_cell_notation.html
from xlsxwriter.utility import xl_rowcol_to_cell
import io

# pip3 install Fabric3
from fabric.api import *
import paramiko
import socket
import os
import glob
import csv

from tempfile import TemporaryFile
# from io import BytesIO
import re
import pprint
import base64
import pandas as pd
import numpy as np

from xlrd import open_workbook
import mmap


CROWN = [('C','w/Crown'),('CL','Crownless')]
FILE_TYPE_DICT = {
    'text/csv': ('csv','SAP'),
    'application/octet-stream': ('csv','SAP'),
    'application/vnd.ms-excel': ('xl','AS400'),
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ('xl','AS400')
}

def read_data(data):
    if data:
        fileobj = TemporaryFile("w+")
        fileobj.write(base64.b64decode(data).decode('utf-8'))
        fileobj.seek(0)
        line = csv.reader(fileobj, quotechar='"', delimiter=',', quoting=csv.QUOTE_ALL, skipinitialspace=True)
        return line

def read_xls_to_dict(excel_file_field,sheet_name):
        book    = open_workbook(file_contents=base64.b64decode(excel_file_field))
        sheet   = book.sheet_by_name(sheet_name)
        headers = dict( (i, sheet.cell_value(0, i) ) for i in range(sheet.ncols) ) 

        return ( dict( (headers[j], sheet.cell_value(i, j)) for j in headers ) for i in range(1, sheet.nrows) )




class DmpiCrmMarketAllocation(models.Model):
    _name = 'dmpi.crm.market.allocation'
    _inherit = ['mail.thread']



    def get_so_summary_table(self,week_no):

        query = """
(
    SELECT
            0 as so_id,
            '' as week_no,
            '' as country,
            '' as so_no,
            '' as customer,
            '' as ship_to,
            '' as product_class,
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
                        prod.product_class,
            pc.name as prod_code,
            pc.sequence,
            so.shell_color,
            pc.product_crown,
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
    where ctr.week_no like '%%%s%%'
    group by so.id,so.week_no,cc.name,so.name,cust.name,shp.name,prod.product_class,pc.name,pc.sequence,so.shell_color,pc.product_crown,prod.psd

)

        """  % week_no

        print (query)
        self.env.cr.execute(query)
        result = self.env.cr.dictfetchall()

        df = pd.DataFrame.from_dict(result)
        pd_res = pd.pivot_table(df, values='qty', index=['so_id','country','so_no','customer','ship_to','product_class'], 
            columns=['sequence','prod_code'],fill_value=0, aggfunc=np.sum, margins=True)
        print(pd_res)


        pd_res_vals = pd_res.reset_index().values
        return pd_res_vals

    def get_allocations(self,allocation_id):
        query = """
SELECT prod_code, SUM(qty) AS qty
FROM (
    (SELECT 
    pc.sequence,
    pc.name as prod_code,
    pc.psd,
    0 as qty
    FROM dmpi_crm_product_code pc where pc.active is True
    order by pc.sequence)

    UNION ALL

    (SELECT  
    pc.sequence,
    pc.name as prod_code,
    pc.psd,
    Sum(al.corp + al.sb + al.dmf) as qty
    from  dmpi_crm_market_allocation_line al
    JOIN dmpi_crm_product_code pc on (pc.product_crown = al.product_crown and pc.psd = al.psd)
    where allocation_id = %s and pc.active is True
    group by pc.name,pc.sequence,pc.psd
    order by pc.sequence)
)AS Q1
GROUP BY prod_code, sequence, psd
ORDER BY sequence
        """ % allocation_id
        print (query)
        self.env.cr.execute(query)
        result = self.env.cr.dictfetchall()   
        # print(result) 
        return result    



    @api.multi
    def action_generate_report(self):
        for rec in self:

            th = lambda x: """<th data-original-title="" title="" style="text-align: center; color:#FFF; background-color: #78717e;" >%s</th>""" % x 
            td = lambda x: """<td class="o_data_cell o_list_number">%s</td>""" % x
            a = lambda x,y: """<a href="/web#id=%s&view_type=form&model=dmpi.crm.sale.order&menu_id=96&action=107" target="self">%s</a> """ % (x,y) 

            pd_res_vals = self.get_so_summary_table(rec[0].week_no)


            h1 = []
            h1.append(th('Country'))
            h1.append(th('SO No'))
            h1.append(th('Ship To'))
            h1.append(th('Class'))

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
                        td_data.append(th(l[5]))
                        

                        for d in l[6:]:
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
                        td_data.append(td(l[5]))
                        
                        for d in l[6:]:
                            d = round(d)
                            td_data.append(td(d))

                        trow_data = """<tr class="o_data_row"> %s </tr>""" % ''.join(td_data)
                        trow.append(trow_data)




            alloc_data = []
            alloc_data.append(th('Allocations'))
            alloc_data.append(th(''))
            alloc_data.append(th(''))
            alloc_data.append(th(''))
            alloc_data.append(th(''))

            for r in self.get_allocations(rec.id):
                d = round(r['qty'])
                alloc_data.append(th(d))

            alloc_data = """<tr class="o_data_row"> %s </tr>""" % ''.join(alloc_data)
            trow.append(alloc_data)



            # print (col_totals)
            # print (result)

                    #Compute Totals

            # msg = """<a href="/web?#id=87&view_type=form&model=dmpi.crm.sale.contract&menu_id=84&action=97" target="self">test link</a> """

            rec.html_report = """
                <table class="o_list_view table table-condensed table-striped o_list_view_ungrouped">
                    <thead><tr> %s </tr></thead>
                    <tbody> %s </tbody>
                </table>
            """ %(''.join(h1),''.join(trow))




    @api.multi
    def print_market_allocations(self):
        for rec in self:
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output)
            details = workbook.add_worksheet('Details')
            summary = workbook.add_worksheet('Summary')

            row1 = 4
            col1 = 0
            row = row1
            col = col1

            first_row = row1
            first_col = col1
            last_row = 0
            last_col = 0

            #Generate Header 1
            col = 0
            active_products = self.env['dmpi.crm.product.code'].search([('active','=',True)],order='sequence')
            number_of_active_products = len(active_products)


            details.write(row1-1,col, 'FACTORS') 
            columns = ['SO ID','Country','So No','Customer','Ship To','Class']
            for c in columns:
                details.write(row,col, c) 
                col += 1
            cc_col = []
            for p in active_products: 
                details.write(row1-1,col,p.factor) #Factors
                details.write(row,col,p.name)
                
                exist = False
                for c in cc_col:
                    if c['psd'] == p.psd:
                        exist = True

                if exist:
                    for c in cc_col:
                        if c['psd'] == p.psd:                    
                            if c['col1'] > 0:
                                c['col2'] = col
                else:
                    cc_col.append({'psd':p.psd, 'col1':col})

                col += 1

            
            details.write(row,col, 'TOTAL') 
            col += 1
            details.write(row,col, 'STATUS') 
            last_col = col

            #Common cases Header
            cc_col1 = col
            cc_col1 += 4
            details.write(row-1,cc_col1, 'COMMON CASES') 
            # print(cc_col)
            h_col = cc_col1
            for i in cc_col:
                details.write(row,h_col,i['psd']) 
                h_col += 1
            row += 1


            pd_res_vals = self.get_so_summary_table(rec[0].week_no)

            for r in pd_res_vals:
                col = 0
                
                if r[0] != 0:
                    if r[0] != 'All':
                        for c in r:
                            details.write(row,col, c)
                            col += 1
                        totals = "=SUM(%s:%s)" % (xl_rowcol_to_cell(row,len(columns)),xl_rowcol_to_cell(row,col-2)) #Totals Side
                        details.write(row,col-1, totals) 

                        #CommonCases Conversions
                        cc_val_col1 = cc_col1
                        for i in cc_col:
                            # print(i)
                            vals = ""
                            if 'col2' in i.keys():
                                vals = "=%s*%s+%s*%s" % (
                                        xl_rowcol_to_cell(row,i['col1']),xl_rowcol_to_cell(row1-1,i['col1']),
                                        xl_rowcol_to_cell(row,i['col2']),xl_rowcol_to_cell(row1-1,i['col2'])
                                    )
                            else:
                                vals = "=%s*%s" % (
                                        xl_rowcol_to_cell(row,i['col1']),xl_rowcol_to_cell(row1-1,i['col1'])
                                    )
                            details.write(row,cc_val_col1,vals) 
                            cc_val_col1 += 1

                        total = "=SUM(%s:%s)" % (xl_rowcol_to_cell(row,cc_col1),xl_rowcol_to_cell(row,cc_val_col1-1))
                        details.write(row,cc_val_col1,total) 

                        row += 1
                    else:
                        details.write(row,col, 'TOTAL') 
                        details.write(row1-2,col, 'TOTAL') #Top Totals
                        col += len(columns)
                        total_col1 = col
                        for p in active_products: 
                            total = "=SUM(%s:%s)" % (xl_rowcol_to_cell(row1+1,col),xl_rowcol_to_cell(row-1,col))
                            details.write(row,col,total)
                            details.write(row1-2,col,total) #Top Totals
                            col += 1
                        totals = "=SUM(%s:%s)" % (xl_rowcol_to_cell(row,total_col1),xl_rowcol_to_cell(row,col-1))
                        details.write(row,col, totals)                            
                        

                        #CommonCases Conversions TOTALS
                        cc_val_col1 = cc_col1
                        for i in cc_col:
                            # print(i)
                            # Totals
                            vals = "=SUM(%s:%s)" % (xl_rowcol_to_cell(row1+1,cc_val_col1),xl_rowcol_to_cell(row-1,cc_val_col1))
                            details.write(row,cc_val_col1,vals) 
                            details.write(row1-2,cc_val_col1,vals) #Top Totals
                            cc_val_col1 += 1

                        last_row = row
                        row += 1


            col = 0
            details.write(row,col, 'ALLOCATIONS') 
            details.write(row1-3,col, 'ALLOCATIONS') 
            col += len(columns)
            total_col1 = col
            for r in self.get_allocations(rec.id):
                d = round(r['qty'],2)
                details.write(row,col, d)
                details.write(row1-3,col, d)
                col += 1
            totals = "=SUM(%s:%s)" % (xl_rowcol_to_cell(row,total_col1),xl_rowcol_to_cell(row,col-1))
            details.write(row,col, totals)
            
            #CommonCases Conversions Allocations
            cc_val_col1 = cc_col1
            for i in cc_col:
                # print(i)
                vals = ""
                if 'col2' in i.keys():
                    vals = "=%s+%s" % (xl_rowcol_to_cell(row,i['col1']), xl_rowcol_to_cell(row,i['col2']))
                else:
                    vals = "=%s" % ( xl_rowcol_to_cell(row,i['col1']) )
                details.write(row,cc_val_col1,vals) 
                details.write(row1-3,cc_val_col1,vals)
                cc_val_col1 += 1

            row += 1


            col = 0
            details.write(row,col, 'VARIANCE') 
            details.write(row1-4,col, 'VARIANCE') 
            col += len(columns)
            total_col1 = col
            for r in self.get_allocations(rec.id):
                variance = "=%s-%s" % (xl_rowcol_to_cell(row-1,col),xl_rowcol_to_cell(row-2,col))
                details.write(row,col, variance)
                details.write(row1-4,col, variance)
                col += 1

            #CommonCases Conversions Allocations
            cc_val_col1 = cc_col1
            for i in cc_col:
                variance = "=%s-%s" % (xl_rowcol_to_cell(row-1,cc_val_col1),xl_rowcol_to_cell(row-2,cc_val_col1))
                details.write(row,cc_val_col1, variance)
                details.write(row1-4,cc_val_col1, variance)
                cc_val_col1 += 1


            # summary_cells = "Summary Cells: %s %s" % (xl_rowcol_to_cell(row1,col1) , xl_rowcol_to_cell(last_row,last_col))
            # print (summary_cells)
            #GET SO IDS start from Zero
            summary_row = 0
            for r in range(first_row,last_row):
                # print (summary_row)
                summary_col = 0
                summary.write(summary_row,summary_col,"=Details!%s" % xl_rowcol_to_cell(r,first_col))
                

                summary_col = 1
                for c in range(5,last_col+1):
                    summary.write(summary_row,summary_col,"=Details!%s" % xl_rowcol_to_cell(r,c))
                    summary_col += 1
                summary_row += 1




            workbook.close()
            output.seek(0)
            xy = output.read()
            file = base64.encodestring(xy)
            self.write({'excel_file':file})


            button = {
                'type' : 'ir.actions.act_url',
                'url': '/web/content/dmpi.crm.market.allocation/%s/excel_file/market_allocation.xlsx?download=true'%(rec.id),
                'target': 'new'
                }
            return button



    @api.onchange('allocation_file')
    def onchange_upload_file(self):
        if self.allocation_file:
            rows = read_data(self.allocation_file)

            row_count = 0
            error_count = 0
            line_items = []
            for r in rows:
                errors = []
                if r[0] != '':
                    if row_count == 0: 
                        print (r)
                    else:
                        item = {
                            'psd': r[0],
                            'product_crown': r[1],
                            'grade': r[2],
                            'corp': float(r[3].replace(',','')),
                            'dmf': float(r[4].replace(',','')),
                            'sb': float(r[5].replace(',','')),
                        }

                        #Add Error Checking
                        print(item)
                        line_items.append((0,0,item))
                row_count+=1
            
            if len(line_items) > 0:
                self.line_ids.unlink() 
                self.line_ids = line_items


    @api.onchange('excel_file')
    def onchange_upload_final_file(self):
        if self.excel_file:
            
            (file_extension,source) = FILE_TYPE_DICT.get(guess_mimetype(base64.b64decode(self.excel_file)), (None,None))
            #check if Excel File
            # print ('mimetype = ',guess_mimetype(base64.b64decode(self.upload_file)))
            if file_extension == 'xl':
                wb = open_workbook(file_contents=base64.b64decode(self.excel_file))
                # sheet_names = wb.sheet_names()
                summary_sheet = wb.sheet_by_name('Summary')


                num_cols = summary_sheet.ncols   # Number of columns
                row_counter = 0
                for r in range(1, summary_sheet.nrows):    # Iterate through rows
                    for c in range(0, num_cols):  # Iterate through columns
                        cell_obj = summary_sheet.cell(r, c)  # Get cell object by row, col
                        print ('Column: [%s] cell_obj: [%s]' % (c, cell_obj))
                    row_counter += 1





    @api.multi
    def process_go(self):
        print('Process GO')
        for rec in self:
            if rec.excel_file:
                
                (file_extension,source) = FILE_TYPE_DICT.get(guess_mimetype(base64.b64decode(rec.excel_file)), (None,None))
                #check if Excel File
                if file_extension == 'xl':
                    data = read_xls_to_dict(self.excel_file,'Summary')

                    for d in data:
                        print (d)







    @api.multi
    def process_all(self):
        print('Process ALL')


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
    excel_file = fields.Binary(string='Excel File')
    allocation_file = fields.Binary(string='Allocation File')
    allocation_error = fields.Text("ERROR")



class DmpiCrmMarketAllocationLine(models.Model):
    _name = 'dmpi.crm.market.allocation.line'

    @api.depends('corp','dmf','sb')
    def _get_total(self):
    	for rec in self:
    		rec.total = rec.corp + rec.dmf + rec.sb 

    # def _get_product_crown(self):
    #     query = """SELECT pc.name, pc.description 
    #                 from dmpi_crm_product_code pc 
    #                 where active is True order by sequence
    #             """
    #     # print(query)
    #     self.env.cr.execute(query)
    #     result = self.env.cr.dictfetchall()
    #     res = [(r['name'],r['description']) for r in result]
    #     return res


    # name = fields.Char("Name")
    psd = fields.Integer("PSD")
    allocation_id = fields.Many2one('dmpi.crm.market.allocation',"Allocation ID", ondelete='cascade')
    grade = fields.Selection([('EX','Export'),('B','Class B'),('BA','Class B to A')], "Grade")
    product_crown   = fields.Selection(CROWN,'Crown')
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






