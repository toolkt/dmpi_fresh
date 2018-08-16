# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, date
from pytz import timezone
from odoo.exceptions import Warning, RedirectWarning, UserError
from io import BytesIO
from xlsxwriter.utility import xl_rowcol_to_cell, xl_cell_to_rowcol, xl_range
import xlsxwriter
import re
import time
import codecs

class PreShipmentCertificateReport(models.AbstractModel):
	_name = 'report.preship_cert_summary_report'
	_inherit = 'report.report_xlsx.abstract'


	def generate_xlsx_report(self, workbook, data, obj):

		for o in obj:
			sheet = workbook.add_worksheet('Loaded Vans Summary')

			# PRINT SETTINGS
			sheet.hide_gridlines(1) #hide on print only
			sheet.center_horizontally()
			sheet.set_default_row(16.5)

			# SET COLUMN WIDTHS
			widths = []
			fmt = workbook.add_format({'font_name':'Arial'})
			sheet.set_column(6, 6, 46, fmt) # for remarks
			sheet.set_column(7, 7, 22, fmt) # for cusomter name

			# SET ROW HEIGHTS
			rh = [17.25, 20.25, 15.25, 15.25, 66, 33]
			for i,h in enumerate(rh):
				sheet.set_row(i, h)

			# # SET CELL FORMATS
			phead = workbook.add_format({
				'font_size': 10,
				'font_name':'Arial',
				'valign':'vcenter'
			})
			phead_bold = workbook.add_format({
				'font_size': 10,
				'font_name':'Arial',
				'bold':True
			})
			phead_blue = workbook.add_format({
				'font_size': 10,
				'italic':True,
				'font_color':'#1510C4',
				'font_name':'Arial'
			})

			head_name = workbook.add_format({
				'font_size': 8,
				'font_name':'Arial',
				'align':'center',
				'valign':'vcenter',
				'bold':True,
				'border':1,
				'border_color': "#808080",
				'bg_color': "#D9E1F2",
				'text_wrap':1
			})

			sub_head_name = workbook.add_format({
				'font_size': 8,
				'font_name':'Arial',
				'color': '#FF0000',
				'align':'center',
				'valign':'vcenter',
				'text_wrap':1
			})

			dname = workbook.add_format({
				'font_size': 8,
				'font_name':'Arial',
				'align':'center',
				'valign':'vcenter',
				'border': 7,
			})

			ddate = workbook.add_format({
				'font_size': 8,
				'font_name':'Arial',
				'align':'center',
				'valign':'vcenter',
				'border': 7,
				'num_format':'dd/mm/yyyy',
			})

			dpercent = workbook.add_format({
				'font_size': 8,
				'font_name':'Arial',
				'align':'center',
				'valign':'vcenter',
				'border': 7,
				'num_format':'0.0%'
			})

			sheet.write('C1','PHILPACK', phead_bold)
			sheet.write('C2','Fresh Fruit Quality Assurance', phead)
			sheet.write('C3','PRE-SHIPMENT LOADED VANS SUMMARY', phead_bold)
			sheet.write('C4','(This form is uncontrolled when printed)', phead_blue)
			sheet.write('H1','F-QUA-013,02', phead)
			sheet.write('H2','Effectivity date:', phead)

			# INSERT IMAGE LOGO
			img = self.env['ir.attachment'].search([('datas_fname','like','philpack_logo.png')]).datas
			try:
				img = codecs.decode(img, 'base64')
				image_data = BytesIO(img)
				sheet.insert_image('A1', '', {'image_data':image_data, 'x_offset':20.0, 'x_scale':0.9, 'y_scale':0.98})
			except:
				pass

			# REPORT HEADERS
			# (column name, sub header, row detail format)
			header_vals = [
				('PH', '(from Pre-shipment certificate)', dname),
				('Date Loaded', '(from Pre-shipment certificate)', ddate),
				('Date Packed', '(from Pre-shipment certificate)', dname),
				('Start \n Pack Date', '(from Pre-shipment certificate)', ddate),
				('Container No.', '(from Pre-shipment certificate)', dname),
				('Series Number', '(from Pre-shipment certificate)', dname),
				('Remarks', '(from Pre-shipment certificate)', dname),
				('Customer', '(from Pre-shipment certificate)', dname),
				('Market', '(from Pre-shipment certificate)', dname),
				('Shell Color', '(from Pre-shipment certificate)', dname),
				('Pack Size', '(from Pre-shipment certificate)', dname),
				('No. of Boxes', '(from Pre-shipment certificate)', dname),
				('# of Pallets or Boxes per pack date', '(Manual)', dname),
				('P5', '(PManual)', dname),
				('P6', '(PManual)', dname),
				('P7', '(PManual)', dname),
				('P8', '(PManual)', dname),
				('P9', '(PManual)', dname),
				('P10', '(PManual)', dname),
				('P12', '(PManual)', dname),
				('P5/C7', '(PManual)', dname),
				('P6/C8', '(PManual)', dname),
				('P7/C9', '(PManual)', dname),
				('P8/C10', '(PManual)', dname),
				('P9/C11', '(PManual)', dname),
				('P10/C12', '(PManual)', dname),
				('P12/C20', '(PManual)', dname),
				('Score, %', '(from Pre-shipment certificate)', dpercent),
				('Class', '(from Pre-shipment certificate)', dname),
				('Van Loading QA', '(from Pre-shipment certificate)', dname),
				('Data Analyst', '(from Pre-shipment certificate)', dname),
				('Supervisor', '(from Pre-shipment certificate)', dname),
				('No. of Boxes', '(from Pre-shipment certificate)', dname),
				('Simul Pack Date', '(from Pre-shipment certificate)', dname),
				('Simul box No.', '(from Pre-shipment certificate)', dname),
				('Vessel ETD', '(from Pre-shipment certificate)', ddate),
				('AOP @ ETD', '(Manual)', dname),
				('ETA @ POD', '(from Pre-shipment certificate)', ddate),
				('Transit Time', '(Manual)', dname),
				('AOP @ ETA', '(Manual)', dname),
			]
			sheet.write_row('A5:AI5', [i[0] for i in header_vals], head_name)
			sheet.write_row('A6:AI6', [i[1] for i in header_vals], sub_head_name)


			# INSERT DATA HERE
			tmpl_ids = []
			if o.filter_template == 'template' and o.tmpl_id:
				tmpl_ids.append(o.tmpl_id.id)
			else:
				tmpl_ids = self.env['dmpi.crm.template'].search([('active','=',True)]).ids
			tmpl_ids = tuple(tmpl_ids)

			query = """
				SELECT
					cp.dr_id
					,cp.plant
					,to_char(ps.date_load::TIMESTAMP, 'dd/mm/yyyy') date_load
					,ps.date_pack
					,to_char(to_timestamp(cp.date_start, 'yyyymmdd/hhmiss')::TIMESTAMP, 'dd/mm/yyyy') date_start
					,ps.container
					,ps.series_no
					,ps.remarks
					,ps.customer
					,ps.market
					,ps.shell_color
					,ps.pack_size
					,ps.no_box
					,ps.total_score
					,ps.total_class
					,ps.inspector_name
					,ps.issuer_name
					,ps.supervisor_name
					,cp.boxes
					,to_char(cp.simul_pack_date::TIMESTAMP, 'dd/mm/yyyy') simul_pack_date
					,cp.simul_no
					,to_char(to_timestamp(cp.date_depart, 'yyyymmdd')::TIMESTAMP, 'dd/mm/yyyy') date_depart
					,to_char(to_timestamp(cp.date_arrive, 'yyyymmdd')::TIMESTAMP, 'dd/mm/yyyy') date_arrive
				from dmpi_crm_preship_report ps
				left join dmpi_crm_clp cp on cp.id = ps.clp_id
				where ps.date_load between '%s'::DATE and '%s'::DATE
					and ps.tmpl_id in %s
			""" % (o.date_start, o.date_end, str(tmpl_ids))
			print(query)
			self._cr.execute(query)
			result = self._cr.fetchall()

			row = 6
			for rec in result:
				# set row values
				dr_id = rec[0]
				dr = self.env['dmpi.crm.dr'].search([('id','=',dr_id)], limit=1)
				customer = dr.contract_id.partner_id

				pqty = []
				psd = ['P5' ,'P6' ,'P7' ,'P8' ,'P9' ,'P10' ,'P12' ,'P5C7' ,'P6C8' ,'P7C9' ,'P8C10' ,'P9C11' ,'P10C12' ,'P12C20']
				for p in psd:
					if customer:
						query = """
							SELECT max(dl.qty) as qty, pp.code, dl.dr_line_item_no
								from dmpi_crm_dr_line dl
								left join dmpi_crm_product pp on pp.sku = dl.material
								where dl.dr_id = %s and pp.code = '%s' and pp.partner_id = %s
							group by pp.code, dl.dr_line_item_no
							LIMIT 1
						""" % (dr_id, p, customer.id)
						print (query)
						self._cr.execute(query)
						result = self._cr.fetchall()

						if result:
							pqty.append(result[0][0])
						else:
							pqty.append(0)
					else:
						pass

				print (pqty)

				pqty = iter(pqty)
				rec = iter(rec[1:])
				col = 0

				aop_etd = '=AE%s-D%s' % (row+1, row+1)
				trans_time = '=AG%s-AE%s' % (row+1, row+1)
				aop_eta_time = '=AG%s-D%s' % (row+1, row+1)

				for h in header_vals:
					if h[1] == '(Manual)':

						if h[0] == 'AOP @ ETD':
							sheet.write(row, col, aop_etd, h[2])
						elif h[0] == 'Transit Time':
							sheet.write(row, col, trans_time, h[2])
						elif h[0] == 'AOP @ ETA':
							sheet.write(row, col, aop_eta_time, h[2])
						else:
							sheet.write(row, col, '', h[2])

					elif h[1] == '(PManual)':
						sheet.write(row, col, next(pqty), h[2])

					else:
						sheet.write(row, col, next(rec), h[2])

					col += 1
				row += 1


