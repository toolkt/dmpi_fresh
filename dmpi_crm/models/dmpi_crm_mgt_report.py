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
            'A2' as product_class,
            '' as prod_code,
            0 as sequence,
            so.shell_color,
            '' as product_crown,
            0 as psd,
            0 as qty
    from dmpi_crm_sale_order_line sol
    left join dmpi_crm_sale_order so on so.id = sol.order_id
    left join dmpi_crm_partner shp on shp.id = so.ship_to_id
    left join dmpi_crm_partner shp on shp.id = so.ship_to_id
    left join dmpi_crm_sale_contract ctr on ctr.id = so.contract_id
    left join dmpi_crm_partner cust on cust.id = ctr.partner_id
    left join dmpi_crm_product prod on prod.id = sol.product_id
    left join dmpi_crm_product_code pc on pc.name = sol.product_code
    left join dmpi_crm_country cc on cc.id = shp.country
    where ctr.week_no like '%%%s%%'
    group by so.id,so.week_no,cc.name,so.name,cust.name,shp.name,so.shell_color

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
    left join dmpi_crm_partner shp on shp.id = so.ship_to_id
    left join dmpi_crm_sale_contract ctr on ctr.id = so.contract_id
    left join dmpi_crm_partner cust on cust.id = ctr.partner_id
    left join dmpi_crm_product prod on prod.id = sol.product_id
    left join dmpi_crm_product_code pc on pc.name = sol.product_code
    left join dmpi_crm_country cc on cc.id = shp.country
    where ctr.week_no like '%%%s%%'
    group by so.id,so.week_no,cc.name,so.name,cust.name,shp.name,prod.product_class,pc.name,pc.sequence,so.shell_color,pc.product_crown,prod.psd

)




        """  % (week_no,week_no)

        print (query)
        self.env.cr.execute(query)
        result = self.env.cr.dictfetchall()

        df = pd.DataFrame.from_dict(result)
        pd_res = pd.pivot_table(df, values='qty', index=['so_id','country','so_no','customer','ship_to','product_class'], 
            columns=['sequence','prod_code'],fill_value=0, aggfunc=np.sum, margins=True)
        print(pd_res)


        pd_res_vals = pd_res.reset_index().values
        return pd_res_vals



    def get_so_summary(self,week_no):

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
            'A2' as product_class,
            '' as prod_code,
            0 as sequence,
            so.shell_color,
            '' as product_crown,
            0 as psd,
            0 as qty
    from dmpi_crm_sale_order_line sol
    left join dmpi_crm_sale_order so on so.id = sol.order_id
    left join dmpi_crm_partner shp on shp.id = so.ship_to_id
    left join dmpi_crm_sale_contract ctr on ctr.id = so.contract_id
    left join dmpi_crm_partner cust on cust.id = ctr.partner_id
    left join dmpi_crm_product prod on prod.id = sol.product_id
    left join dmpi_crm_product_code pc on pc.name = sol.product_code
    left join dmpi_crm_country cc on cc.id = shp.country
    where ctr.week_no like '%%%s%%'
    group by so.id,so.week_no,cc.name,so.name,cust.name,shp.name,so.shell_color

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
    left join dmpi_crm_partner shp on shp.id = so.ship_to_id
    left join dmpi_crm_sale_contract ctr on ctr.id = so.contract_id
    left join dmpi_crm_partner cust on cust.id = ctr.partner_id
    left join dmpi_crm_product prod on prod.id = sol.product_id
    left join dmpi_crm_product_code pc on pc.name = sol.product_code
    left join dmpi_crm_country cc on cc.id = shp.country
    where ctr.week_no like '%%%s%%'
    group by so.id,so.week_no,cc.name,so.name,cust.name,shp.name,prod.product_class,pc.name,pc.sequence,so.shell_color,pc.product_crown,prod.psd

)

        """  % (week_no,week_no)

        print (query)
        self.env.cr.execute(query)
        result = self.env.cr.dictfetchall()

        df = pd.DataFrame.from_dict(result)
        pd_res = pd.pivot_table(df, values='qty', index=['so_id','country','so_no','customer','ship_to','product_class'], 
            columns=['sequence','prod_code'],fill_value=0, aggfunc=np.sum, margins=True)
        print(pd_res)


        pd_res_index = pd_res.reset_index()
        pd_res_vals = pd_res.reset_index().values  
        pd_res_dict = []      

        headers = []
        for c in pd_res_index:
            if c[1] == '':
                headers.append(c[0])
            else:
                headers.append(c[1])


        for row in pd_res_vals:
            pd_res_dict.append( dict(zip(headers, row)) )


        return headers,pd_res_vals,pd_res_dict




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
                        td_data.append(th(l[4]))
                        td_data.append(th(l[5]))
                        

                        for d in l[7:]:
                            d = round(d)
                            td_data.append(th(d))
                            # col_totals.append({'prod_code': , 'qty':d})

                        trow_data = """<tr class="o_data_row"> %s </tr>""" % ''.join(td_data)
                        trow.append(trow_data)

                    else:
                        td_data.append(td(l[1]))
                        td_data.append(td(a(l[0],l[2])))
                        td_data.append(td(l[4]))
                        td_data.append(td(l[5]))
                        
                        for d in l[7:]:
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

            h1 = workbook.add_format({'bold': True,'bg_color': '#BFDFFF'})
            h2 = workbook.add_format({'bold': True,'bg_color': '#73B9FF'})
            alt_1 = workbook.add_format({'bg_color': '#FFEFBF'})
            alt_2 = workbook.add_format({'bg_color': '#FFFFBF'})

            row1 = 0
            col1 = 0
            row = row1
            col = col1
            result_row1 = row1+5
            summary_start = summary_end = []

            headers, pd_res_vals, pd_res_dict  = self.get_so_summary(rec[0].week_no)
            
            # print (headers)
            # print (pd_res_vals)
            # print (pd_res_dict)
            #Print Results
            col = col1
            row = result_row1
            pcol_start = 0
            for h in headers:
                if h == 'so_id':
                    h = 'SO ID'
                if h == 'country':
                    h = 'Country'
                if h == 'so_no':
                    h = 'So No'
                if h == 'customer':
                    h = 'Customer'
                if h == 'ship_to':
                    h = 'Ship To'
                if h == 'product_class':
                    h = 'Class'
                if h == 'All':
                    h = 'TOTAL'
                if h == 0:
                    pcol_start = col
                else:
                    details.write(row,col,h,h1) 
                    summary.write(0,col,h) 
                    col += 1 
                details.write(row,col, 'STATUS',h1)
                summary.write(0,col,'STATUS')  

            so_idx = 0
            so_id = 0
            summary_start = [result_row1,col1]
            for r in pd_res_dict:
                col = col1
                if r['so_id'] != 0:
                    if r['so_id'] != 'All':
                        row += 1
                        if r['so_id'] != so_id: #Check if Even or Odd
                            so_idx += 1
                            so_id = r['so_id']

                        for h in headers:
                            if h != 0:
                                if h != 'All':
                                    if (so_idx % 2) == 0:
                                        details.write(row,col,r[h],alt_1)  
                                    else:
                                        details.write(row,col,r[h],alt_2)
                                else:
                                    totals = "=SUM(%s:%s)" % (xl_rowcol_to_cell(row,pcol_start),xl_rowcol_to_cell(row,col-1))
                                    if (so_idx % 2) == 0:
                                        details.write(row,col,totals,alt_1)  
                                    else:
                                        details.write(row,col,totals,alt_2)
                                col += 1
                    
                        

                    else:
                        col = 0
                        row += 1
                        for h in headers:
                            if h != 'All':
                                if col >= pcol_start:
                                    # print ("PCOLSTART: %s" % pcol_start)
                                    totals = "=SUM(%s:%s)" % (xl_rowcol_to_cell(result_row1+1,col),xl_rowcol_to_cell(row-1,col))
                                    details.write(row,col,totals,h2)
                                    details.write(result_row1-2,col,totals,h2)
                                else:
                                    if col == 0:
                                        details.write(row,col,"TOTAL",h2)
                                        details.write(result_row1-2,col,"TOTAL",h2)
                                    else:
                                        details.write(row,col,"",h2)  
                                        details.write(result_row1-2,col,"",h2)  
                            col += 1

                    summary_end = [row,col-1]

                          
            # print(summary_start,summary_end)
            row = 1
            for r in range(summary_start[0]+1,summary_end[0]):
                # print (r)
                col = 0
                for c in range(summary_start[1],summary_end[1]+1):
                    val = "=Details"
                    summary.write(row,col,"=Details!%s" % xl_rowcol_to_cell(r,c))
                    col += 1

                row += 1



            col = 0
            factor_row = result_row1-1
            for h in headers:
                if h != 'All':
                    if h != 0:
                        if col >= pcol_start:
                            print ("%s PCOLSTART: %s" % (h,pcol_start))
                            vals = self.env['dmpi.crm.product.code'].search([('name','=',h)]).factor
                            details.write(factor_row,col,vals,h2)  
                        else:
                            if col == 0:
                                details.write(factor_row,col,"FACTORS",h2)
                            else:
                                details.write(factor_row,col,"",h2)  
                        col += 1
                else:
                    details.write(factor_row,col,"",h2) 

            row = summary_end[0]+1
            col = 0
            details.write(row,col, 'ALLOCATIONS') 
            details.write(result_row1-3,col, 'ALLOCATIONS') 
            col += pcol_start
            total_col1 = col
            for r in self.get_allocations(rec.id):
                d = round(r['qty'],2)
                details.write(row,col, d, h1)
                details.write(result_row1-3,col, d, h1)
                col += 1
            totals = "=SUM(%s:%s)" % (xl_rowcol_to_cell(row,total_col1),xl_rowcol_to_cell(row,col-1))
            details.write(row,col, totals, h1)
            details.write(result_row1-3,col,totals, h1) 


            row += 1


            col = 0
            details.write(row,col, 'VARIANCE', h1) 
            details.write(result_row1-4,col, 'VARIANCE', h1) 
            col += pcol_start
            total_col1 = col
            for r in self.get_allocations(rec.id):
                variance = "=%s-%s" % (xl_rowcol_to_cell(row-1,col),xl_rowcol_to_cell(row-2,col))
                details.write(row,col, variance, h1)
                details.write(result_row1-4,col, variance, h1)
                col += 1

            details.freeze_panes(result_row1+1, pcol_start)



            #--------------COMMON CASES---------------

            col = 0
            active_products = self.env['dmpi.crm.product.code'].search([('active','=',True)],order='sequence')
            number_of_active_products = len(active_products)            
            cc_col = []
            for p in active_products:                 
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

            #Common cases Header
            cc_col1 = summary_end[1]
            cc_col1 += 4
            row = result_row1
            details.write(row-5,cc_col1, 'COMMON CASES',h1) 
            # print(cc_col)
            h_col = cc_col1
            for i in cc_col:
                details.write(row,h_col,i['psd'],h1) 
                h_col += 1
            row += 1

            # print(summary_start,summary_end)
            for r in range(summary_start[0]+1,summary_end[0]):
                # print (r)
                col = cc_col1
                for c in range(summary_start[1],summary_end[1]+1):
                    val = "=Details"
                    summary.write(row,col,"=Details!%s" % xl_rowcol_to_cell(r,c))
                    col += 1

                row += 1




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



    @api.multi
    def upload_market_allocations(self):
        self.ensure_one()
        template = self.env.ref('dmpi_crm.view_crm_market_allocation_upload_form')
        return {
            'name': 'Upload Market Allocations',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'crm.market.allocation.upload',
            'views': [(template.id, 'form')],
            'view_id': template.id,
            'target': 'new',
        }



    @api.onchange('allocation_file')
    def onchange_upload_file(self):
        if self.allocation_file:
            rows = read_data(self.allocation_file)
            print (rows)
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
    def update_so(self):
        print('Process GO')

        th = lambda x: """<th data-original-title="" title="" style="text-align: center; color:#FFF; background-color: #78717e;" >%s</th>""" % x 
        td = lambda x: """<td class="o_data_cell o_list_number">%s</td>""" % x

        for rec in self:
            if rec.excel_file:

                book    = open_workbook(file_contents=base64.b64decode(rec.excel_file))
                sheet   = book.sheet_by_name('Summary')

                trow = []
                h1 = []
                num_cols = sheet.ncols 
                for row_idx in range(0, sheet.nrows): 
                    td_data = []
                    for col_idx in range(0, num_cols): 
                        val = sheet.cell_value(row_idx, col_idx)
                        if col_idx not in (2,3):
                            if row_idx == 0: #Header
                                h1.append(th(val))
                            else:
                                if (col_idx > 5 and col_idx < num_cols-1) or (col_idx == 0):
                                    val = int(sheet.cell_value(row_idx, col_idx))
                                td_data.append(td(val))

                    trow_data = """<tr class="o_data_row"> %s </tr>""" % ''.join(td_data)
                    trow.append(trow_data)


                
            rec.html_report = """
                <table class="o_list_view table table-condensed table-striped o_list_view_ungrouped">
                    <thead><tr> %s </tr></thead>
                    <tbody> %s </tbody>
                </table>
            """ %(''.join(h1),''.join(trow))                                      


    @api.multi
    def process_go(self):
        print('Process GO')
        for rec in self:
            if rec.excel_file:
                
                (file_extension,source) = FILE_TYPE_DICT.get(guess_mimetype(base64.b64decode(rec.excel_file)), (None,None))
                #check if Excel File
                if file_extension == 'xl':
                    data = read_xls_to_dict(self.excel_file,'Summary')

                    active_products = self.env['dmpi.crm.product.code'].search([('active','=',True)],order='sequence')
                    number_of_active_products = len(active_products)
                    products = []
                    for h in active_products:
                        products.append(h.name)


                    so_id = 0
                    
                    items = []
                    for d in data:

                        if d['so_id'] != so_id and so_id != 0:

                            d['so_id'] != so_id                            
                        print (d)
                        counter += 1






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
    sale_order_ids = fields.Many2many('dmpi.crm.sale.order','allocation_sale_order_rel','allocation_id','so_id','Sale Orders')



class DmpiCrmMarketAllocationLine(models.Model):
    _name = 'dmpi.crm.market.allocation.line'

    @api.depends('corp','dmf','sb')
    def _get_total(self):
        for rec in self:
            rec.total = rec.corp + rec.dmf + rec.sb

    # name = fields.Char("Name")
    psd = fields.Integer("PSD")
    allocation_id = fields.Many2one('dmpi.crm.market.allocation',"Allocation ID", ondelete='cascade')
    grade = fields.Selection([('EX','Export'),('B','Class B'),('BA','Class B to A')], "Grade")
    product_crown   = fields.Selection(CROWN,'Crown')
    corp = fields.Float("CORP")
    dmf = fields.Float("DMF")
    sb = fields.Float("SB")
    total = fields.Float("Total",compute='_get_total')



class CrmMarketAllocationUpload(models.TransientModel):
    """
    This wizard will confirm the all the selected draft invoices
    """

    _name = "crm.market.allocation.upload"
    _description = "Upload Wizard for Market Allocation"


    upload_file = fields.Binary(string='Upload File')
    html_display = fields.Html("Result")


    @api.onchange('upload_file')
    def onchange_upload_final_file(self):
        if self.upload_file:
            print ("Upload Excel File")


    @api.multi
    def process_upload(self):
        print ("Process Uplaod")

    






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
        nt.name as notify_party,
        st.name as ship_to,
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
left join dmpi_crm_partner st on st.id = so.ship_to_id
left join dmpi_crm_partner nt on nt.id = so.notify_id
left join dmpi_crm_product pr on pr.id = sol.product_id 
left join dmpi_crm_product_code pc on pc.name = sol.product_code
left join dmpi_crm_country cc on cc.id = st.country


            )
            """)






