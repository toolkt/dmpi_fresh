# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, date
from pytz import timezone
from odoo.exceptions import Warning, RedirectWarning
from io import BytesIO
import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell
import re
import time
import codecs

class PreShipmentCertificateReport(models.AbstractModel):
	_name = 'report.fg_cert_report'
	_inherit = 'report.report_xlsx.abstract'

	def generate_xlsx_report(self, workbook, data, obj):
		for o in obj:
			sheet = workbook.add_worksheet('FG Cert %s' % o.dr_id.name)

			# PRINT SETTINGS
			sheet.hide_gridlines(2)
			sheet.print_area('A1:K35')
			sheet.set_portrait()
			sheet.center_horizontally()
			sheet.fit_to_pages(1,1)

			# SET COLUMN WIDTHS
			cols = 'ABCDEFGHIJK'
			w = [8.67, 10]
			fmt = workbook.add_format({'font_name':'Tahoma', 'font_size':12})
			for i in range(1,10):
				sheet.set_column(cols[i]+':'+cols[i], w[0], fmt)
			sheet.set_column('A:A', 10.1, fmt)
			sheet.set_column('K:K', 10.1, fmt)

			# SET ROW HEIGHTS
			for i in range(1,40):
				if i in [0,7]:
					sheet.set_row(i, 18)
				elif i in [1,5,6,8]:
					sheet.set_row(i, 15)
				elif i in [2,3]:
					sheet.set_row(i, 13)
				elif i in [4]:
					sheet.set_row(i, 5)
				else:
					sheet.set_row(i, 17)

			# SET CELL FORMATS
			head_title = workbook.add_format({'font_size': 16, 'font_name':'Tahoma', 'bold': True, 'align':'center'})
			head_title_sub = workbook.add_format({'font_size': 14, 'font_name':'Tahoma', 'bold': True, 'align':'center'})
			head_it = workbook.add_format({'font_size': 10, 'font_name':'Tahoma', 'italic': True, 'align':'center'})
			head_line = workbook.add_format({'font_size': 10, 'font_name':'Tahoma', 'align':'center', 'bottom':1})

			dtitle = workbook.add_format({'font_size': 15, 'font_name':'Tahoma', 'bold':True,'align':'center'})
			dtitle_blue = workbook.add_format({'font_size': 9.5, 'font_name':'Tahoma', 'italic':True, 'align':'center', 'color':'#3F3ED0'})

			dmerge = workbook.add_format({'font_size': 13, 'font_name':'Tahoma', 'align':'justify', 'valign':'top', 'text_wrap':1})
			dbold = workbook.add_format({'font_size': 13, 'font_name':'Tahoma', 'bold':True})
			dunder = workbook.add_format({'font_size': 13, 'font_name':'Tahoma', 'underline':True})
			dnormal = workbook.add_format({'font_size': 13, 'font_name':'Tahoma'})

			footer = workbook.add_format({'font_size': 12, 'font_name':'Tahoma', 'bold':True, 'align':'left'})
			footer_line = workbook.add_format({'font_size': 12, 'font_name':'Tahoma', 'bottom':1})
			footer_supervisor = workbook.add_format({'font_size': 12, 'font_name':'Tahoma', 'bottom':1, 'align':'left'})

			# REPORT HEADER
			sheet.write('F1','CORPORATE QUALITY ASSURANCE', head_title)
			sheet.write('F2','Fresh Fruit Operations', head_title_sub)
			sheet.write('F3','Global GAP Certified (GGN 4052852226059)', head_it)
			sheet.write('F4','Certified ISO 9001:2008', head_it)

			img = self.env['ir.attachment'].search([('datas_fname','like','philpack_logo.png')]).datas
			try:
				img = codecs.decode(img, 'base64')
				image_data = BytesIO(img)
				sheet.insert_image('B1', '', {'image_data':image_data, 'y_offset':18.0, 'x_scale':1.08, 'y_scale':1.15})
			except:
				pass

			for i in range(11):
				sheet.write(cols[i]+'5','', head_line)

			# BODY
			sheet.write('F8','PRODUCT CERTIFICATE', dtitle)
			sheet.write('F9','(This form is uncontrolled when printed)', dtitle_blue)

			s = "This is to certify that products of this shipment, %s Fresh Pineapples, with Container # " % (o.variety.name or '')
			s2 = ", contain traces of "
			s3 = """\n\nThe said food additives are approved for use by Food and Drug Administration (of the US, Philippines and Japan) and are judiciously used according to approved specified application and handling. \n
Further, planting, growing, harvesting and packing of this product are in accrodance with  Global G.A.P. (Good Agricultural Practices) and standard protocols to avoid the risk of biological, chemical and physical contaminations.\n\n
This certification is issued in compliance with GMP and HACCP Requirements. \n\n\n\n
Certified true and correct: """

			sheet.merge_range('B12:J31','', dmerge)
			sheet.write_rich_string('B12', s,
				dunder, o.container or ' ',
				dnormal, s2,
				dbold, o.allergen or ' ',
				dnormal, s3,
				dmerge)

			# FOOTER
			sheet.write('B34','Fresh Fruit Quality Assurance', footer)
			sheet.write('B33',o.supervisor.name or ' ', footer_supervisor)

			for i in range(2,4):
				sheet.write(cols[i]+'33','', footer_line)
