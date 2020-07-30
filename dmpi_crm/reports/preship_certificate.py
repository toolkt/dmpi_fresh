# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, date
from pytz import timezone
from dateutil.parser import parse
from odoo.exceptions import Warning, RedirectWarning
from io import BytesIO
from xlsxwriter.utility import xl_rowcol_to_cell, xl_cell_to_rowcol, xl_range
import xlsxwriter
import re
import time
import codecs

class PreShipmentCertificateReport(models.AbstractModel):
	_name = 'report.preship_cert_report'
	_inherit = 'report.report_xlsx.abstract'


	def _get_class(self, rule, w, s, typ):
		rules = rule[1:-1].split('),(')
		for r in rules:
			r = (re.sub(',=,',',==,',r)).split(',')
			t = '%s %s (%s*%s/100)' % (s, r[1], w, r[2])

			print (typ, t)
			if eval(t):
				return r[0]


	def _to_hold(self, h, c):
		if h == True and c == 'C':
			return 'HOLD'
		else:
			return ''


	def generate_xlsx_report(self, workbook, data, obj):
		for o in obj:

			config = self.env['dmpi.crm.config'].search([('active','=',True)], limit=1)[0]

			date_issue = parse(o.date_issue)
			date_issue = datetime.strftime(date_issue, '%Y%m%d')
			sheet = workbook.add_worksheet('Pre-Ship Cert_%s_%s' % (o.container,date_issue))

			# PRINT SETTINGS
			sheet.hide_gridlines(2)
			sheet.print_area('A1:K68')
			sheet.set_portrait()
			sheet.center_horizontally()
			sheet.fit_to_pages(1,1)

			# SET COLUMN WIDTHS
			cols = 'ABCDEFGHIJK'
			widhts = [14.67, 13.83, 8.67, 10.67, 8.83, 7.5, 7.83, 11.67, 9.67, 7.33, 10]
			fmt = workbook.add_format({'font_name':'Arial'})
			for i,w, in enumerate(widhts):
				sheet.set_column(cols[i]+':'+cols[i], w, fmt)
			
			# SET ORIGINS
			ext_r = 15
			int_r = 21
			pack_r = 28
			foot_r = 35
			img_attach_r = 35

			# SET ROW HEIGHTS
			for i in range(1,52):
				if i in [ext_r, int_r, pack_r]:
					sheet.set_row(i, 22)
				else:
					sheet.set_row(i, 12)

			# SET CELL FORMATS
			phead = workbook.add_format({'font_size': 10, 'font_name':'Arial'})
			phead_bold = workbook.add_format({'font_size': 10, 'font_name':'Arial', 'bold':True})
			phead_blue = workbook.add_format({'font_size': 10, 'italic':True, 'font_color':'#1510C4', 'font_name':'Arial'})
			phead_line = workbook.add_format({'font_size': 10, 'top':3, 'font_name':'Arial'})

			head_name = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'align':'left'})
			head_center = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'align':'center'})
			head_center_percent = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'align':'center', 'num_format':'0.0%'})
			head_dash = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'align':'left', 'border':3})
			head_tot = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'align':'center', 'top':1, 'left':1, 'right':1, 'bold':True})
			head_tot_val = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'align':'center', 'left':1, 'right':1, 'num_format':'0.0%'})
			head_tot_class = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'align':'center', 'bottom':1, 'left':1, 'right':1, 'bold':True})

			head_mrg_top = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'align':'center', 'top':1, 'left':1, 'right':1, 'bold':True})
			head_mrg_bot = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'align':'center', 'bottom':1, 'left':1, 'right':1, 'bold':True})

			dhead = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'align':'center', 'valign':'vcenter', 'border':1, 'text_wrap':1})
			dhead_bold = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'bold':True, 'border':1, 'valign':'vcenter'})
			rhead = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'border':1})
			ddata = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'border':1, 'align':'center', 'valign':'vcenter'})
			ddata_percent = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'border':1, 'align':'center', 'valign':'vcenter', 'num_format':'0.0%'})
			ddata_avg = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'border':1, 'align':'center', 'valign':'vcenter', 'font_color':'#0070C0', 'bold':True})

			mrg_left = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'border':1, 'align':'left', 'valign':'vcenter'})
			mrg_center = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'border':1, 'align':'center', 'valign':'vcenter', 'text_wrap':1})
			mrg_center_bold = workbook.add_format({'font_size': 8, 'font_name':'Arial', 'border':1, 'align':'center', 'valign':'vcenter', 'text_wrap':1, 'bold':True})

			sheet.write('C1',config.preship_header_l1, phead) #phead_bold
			sheet.write('C2',config.preship_header_l2, phead)
			sheet.write('C3',config.preship_header_l3, phead)
			# sheet.write('C2','Fresh Fruit Quality Assurance', phead)
			sheet.write('C4','(This form is uncontrolled when printed)', phead_blue)
			sheet.write('I1',o.tmpl_id.doc_num, phead)
			# sheet.write('I2','Effectivity date:', phead)

			try:
				
				img = config.preship_logo
				# img = self.env['ir.attachment'].search([('datas_fname','like','philpack_logo.png')]).datas
				img = codecs.decode(img, 'base64')
				image_data = BytesIO(img)
				scale = config.preship_logo_scale/100 or 1
				sheet.insert_image('B1', '', {'image_data':image_data, 'x_offset':-25.0, 'x_scale':scale, 'y_scale':scale})
			except:
				pass

			for c in cols:
				sheet.write(c+'5', '', phead_line)

			# # REPORT HEADERS
			sheet.write('A6','DATE OF ISSUE:',head_name)
			sheet.write('A7','TIME OF ISSUE:',head_name)
			sheet.write('A8','ISSUED BY:',head_name)
			sheet.write('A9','CONTAINER NO:',head_name)
			sheet.write('A10','CUSTOMER:',head_name)
			sheet.write('D6','PRODUCT SPECIFICATIONS:',head_name)
			sheet.write('D7','SC:',head_name)
			sheet.write('D8','SC:',head_name)
			sheet.write('D8','PS/ COUNT:',head_name)
			sheet.write('D9','PACK DATE:',head_name)
			sheet.write('D10','MARKET:',head_name)
			sheet.write('H7','SERIES NO:',head_name)
			sheet.write('H8','DATE LOADED:',head_name)
			sheet.write('H9','QA INSPECTOR:',head_name)
			sheet.write('H10','NO. OF BOXES:',head_name)
			sheet.write('A13','OVERALL SCORE', head_name)
			sheet.write('A14','OVERALL CLASS', head_name)
			sheet.write('B12','TOTAL', head_tot)

			sheet.write('C12','EXTERNAL', head_center)
			sheet.write('D12','INTERNAL', head_center)
			sheet.write('E12','PACKAGING', head_center)

			# DETAILS COLUMN HEADER
			sheet.write(ext_r,0,'EXTERNAL QUALITY', dhead_bold)
			sheet.write(int_r,0,'INTERNAL QUALITY', dhead_bold)
			sheet.write(pack_r,0,'PACKAGING QUALITY', dhead_bold)

			# # # DETAILS ROW HEADER
			dt_head = ['Frts w/ defect', '% w/ defect', 'External score:', 'Class:']
			for i,d in enumerate(dt_head):
				sheet.write(ext_r+i+1,0,d, rhead)

			dt_head = ['Frts w/ defect', '% w/ defect', 'Average', 'External score:', 'Class:']
			for i,d in enumerate(dt_head):
				sheet.write(int_r+i+1,0,d, rhead)

			dt_head = ['Frts w/ defect', '% w/ defect', 'External score:', 'Class:']
			for i,d in enumerate(dt_head):
				sheet.write(pack_r+i+1,0,d, rhead)

			# SET DETAIL FORMATS
			sheet.write('B9','', head_dash)
			sheet.write('B10','', head_dash)
			sheet.write('B13','', head_tot_val)
			sheet.write('B14','', head_tot_class)
			sheet.merge_range('G12:H12','FIELD SOURCE:', head_mrg_top)

			# FOOTER
			r = foot_r
			# sheet.merge_range('A%s:B%s'%(r,r),'SUPPLY TEMP STARTING:', mrg_left)
			# sheet.merge_range('A%s:B%s'%(r+1,r+1),'SUPPLY TEMP UPON DEPARTURE:', mrg_left)
			# sheet.merge_range('A%s:B%s'%(r+2,r+2),'VAN TEMP BEFORE STUFFING:', mrg_left)
			# sheet.merge_range('A%s:B%s'%(r+3,r+3),'VAN TEMP SETTING:', mrg_left)

			# sheet.merge_range('A%s:A%s'%(r+4,r+5),'PACK DATE', mrg_center)
			# sheet.merge_range('B%s:B%s'%(r+4,r+5),'BEFORE PC', mrg_center)
			# sheet.merge_range('C%s:C%s'%(r+4,r+5),'AFTER PC', mrg_center)
			# sheet.merge_range('D%s:D%s'%(r+4,r+5),'COLD STORAGE', mrg_center)
			# sheet.merge_range('E%s:G%s'%(r+4,r+5),'PULP TEMP', mrg_center)
			# sheet.merge_range('H%s:H%s'%(r+4,r+5),'# OF PALLETS', mrg_center)
			# sheet.write('E%s'%(r+5),'1ST', mrg_center)
			# sheet.write('F%s'%(r+5),'MID', mrg_center)
			# sheet.write('G%s'%(r+5),'LAST', mrg_center)

			# INSERT DATA HERE
			query = """
WITH totals as (
				-- get total samples per operation type
				-- problem may exist if no_sample
				select b.type, sum(b.total_sample) as total_sample
				from (
							select a.lot, a.type, max(a.no_sample) as total_sample
							from (
										SELECT
											CASE
												WHEN trim(dil.type) ilike '%%external%%' THEN 'external'
												WHEN trim(dil.type) ilike '%%internal%%' THEN 'internal'
												WHEN trim(dil.type) ilike '%%pack%%' THEN 'packaging'
											END as type
											,dil.lot, dil.factor, dil.factor_num, dil.no_sample
										FROM dmpi_crm_preship_inspection_lot dil
										WHERE dil.preship_id = %s
							) as a
							group by a.lot, a.type
							order by a.lot, a.type
				) as b
				group by b.type
)

,inspection_lots_mean as (
			-- get inspections lots mean data
			SELECT dil.*, f.is_mean, f.parent_id
			FROM (
							SELECT
								CASE
									WHEN trim(dil.type) ilike '%%external%%' THEN 'external'
									WHEN trim(dil.type) ilike '%%internal%%' THEN 'internal'
									WHEN trim(dil.type) ilike '%%pack%%' THEN 'packaging'
								END as type,
								dil.factor_num, dil.factor, sum(dil.no_sample) as no_sample, sum(dil.no_defect) as no_defect, avg(dil.value) as average
							FROM dmpi_crm_preship_inspection_lot dil
							WHERE dil.preship_id = %s
							GROUP BY dil.type, dil.factor, dil.factor_num
			) as dil
			LEFT JOIN dmpi_crm_factor f on (f.code = dil.factor_num and f.type = dil.type)
			WHERE f.is_mean is true and f.parent_id is not null
			ORDER BY dil.type, dil.factor_num
)


,inspection_lots as (
			-- get inspections lots data
			SELECT dil.*
			FROM (
							SELECT
								CASE
									WHEN trim(dil.type) ilike '%%external%%' THEN 'external'
									WHEN trim(dil.type) ilike '%%internal%%' THEN 'internal'
									WHEN trim(dil.type) ilike '%%pack%%' THEN 'packaging'
								END as type,
								dil.factor_num, dil.factor, sum(dil.no_sample) as no_sample, sum(dil.no_defect) as no_defect
							FROM dmpi_crm_preship_inspection_lot dil
							WHERE dil.preship_id = %s
							GROUP BY dil.type, dil.factor, dil.factor_num
			) as dil
			LEFT JOIN dmpi_crm_factor f on (f.code = dil.factor_num and f.type = dil.type)
			WHERE f.is_mean is false and f.parent_id is null
			ORDER BY dil.type, dil.factor_num
)

select f.id as factor_id
	,tl.sequence
	,f.type
	,f.name as factor
	,f.code as factor_code
	,il.no_sample
	,il.no_defect
-- 	,il.average
	,case
				when ilm.average is null then 0
				else ilm.average
	end average
	,tot.total_sample
	,tl.rule
	,tl.weight
	,tl.is_hold
	,count(f.*) over (partition by f.type) as count
from dmpi_crm_factor f
left join dmpi_crm_template_line tl on tl.factor_id = f.id
left join inspection_lots il on (il.type = f.type and il.factor_num = f.code)
-- ) il on (il.type = f.type and il.factor = f.name )
left join totals tot on tot.type = f.type
left join inspection_lots_mean ilm on ilm.parent_id = f.id
where tl.tmpl_id = %s
order by type, factor_code
			""" % (o.id, o.id, o.id, o.tmpl_id.id)
			print(query)
			self._cr.execute(query)
			result = self._cr.dictfetchall()

			# initialize counters
			cols = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
			r = ext_r
			col = 1
			grp_weight = 0
			grp_score = 0
			grp_clss = ''
			total_score = 0
			total_clss = ''

			for rec in result:
				# compute score and class
				name = rec['factor']
				col_end = rec['count']
				no_defect = int(rec['no_defect'] or 0)
				total_sample = int(rec['total_sample'] or 1)
				percent_defect = no_defect / total_sample
				avg = float(rec['average'] or 0)
				weight = float(rec['weight'] or 0) / 100.
				score = weight * (1. - percent_defect)
				rule = rec['rule']
				clss = self._get_class(rule, weight, score, 'factor') if rule else ''
				grp_clss = self._to_hold(rec['is_hold'] or False, clss)

				if rec['type'] == 'external':

					# write data
					data = [name, no_defect, percent_defect, score, clss]
					fmt = [dhead, ddata, ddata_percent, ddata_percent, ddata_percent]
					i = 0
					for d,f in zip(data, fmt):
						sheet.write(r+i, col, d, f)
						i += 1

					# next column
					grp_weight += weight
					grp_score += score
					col += 1

					if col == (col_end + 1):
						if grp_clss != 'HOLD':
							grp_rule = o.tmpl_id.ext_rule
							grp_clss = self._get_class(grp_rule, grp_weight, grp_score, 'grp')
						elif (o.tmpl_id.ext_hold):
							total_clss = 'HOLD'

						# write totals
						data = ['TOTAL', no_defect, percent_defect, score, grp_clss]
						fmt = [dhead, ddata, ddata_percent, ddata_percent, ddata]
						i = 0
						for d,f in zip(data, fmt):
							if not (i==0 or i==len(data)-1):
								d = '=SUM(%s%s:%s%s)' % (cols[1], r+i+1, cols[col-1], r+i+1)
							sheet.write(r+i, col, d, f)
							i += 1

						sheet.write('C13', '=%s%s' % (cols[col], r+4), head_center_percent)
						sheet.write('C14', '=%s%s' % (cols[col], r+5), head_center)

						col += 1
						sheet.write(r, col, 'FRUITS EVALUATED', dhead)
						sheet.write(r+1, col, total_sample, ddata)
						sheet.write(r+2, col, '', ddata)
						sheet.write(r+3, col, '', ddata)
						sheet.write(r+4, col, '', ddata)

						# reset/update counters
						total_score += grp_score
						r = int_r
						col = 1
						grp_weight = 0
						grp_score = 0
						grp_clss = ''

				if rec['type'] == 'internal':

					# write data
					data = [name, no_defect, percent_defect, avg, score, clss]
					fmt = [dhead, ddata, ddata_percent, ddata_avg if avg != 0 else ddata, ddata_percent, ddata_percent]
					i = 0
					for d,f in zip(data, fmt):
						sheet.write(r+i, col, d, f)
						i += 1

					# next column
					grp_weight += weight
					grp_score += score
					col += 1

					if col == (col_end + 1):
						if grp_clss != 'HOLD':
							grp_rule = o.tmpl_id.ext_rule
							grp_clss = self._get_class(grp_rule, grp_weight, grp_score, 'grp')
						elif (o.tmpl_id.int_hold):
							total_clss = 'HOLD'

						# write totals
						data = ['TOTAL', no_defect, percent_defect, '', score, grp_clss]
						fmt = [dhead, ddata, ddata_percent, ddata, ddata_percent, ddata]
						i = 0
						for d,f in zip(data, fmt):
							if not (i==0 or i==len(data)-1 or i==3):
								d = '=SUM(%s%s:%s%s)' % (cols[1], r+i+1, cols[col-1], r+i+1)
							sheet.write(r+i, col, d, f)
							i += 1

						sheet.write('D13', '=%s%s' % (cols[col], r+5), head_center_percent)
						sheet.write('D14', '=%s%s' % (cols[col], r+6), head_center)

						col += 1
						sheet.write(r, col, 'FRUITS EVALUATED', dhead)
						sheet.write(r+1, col, total_sample, ddata)
						sheet.write(r+2, col, '', ddata)
						sheet.write(r+3, col, '', ddata)
						sheet.write(r+4, col, '', ddata)
						sheet.write(r+5, col, '', ddata)

						# reset/update counters
						total_score += grp_score
						r = pack_r
						col = 1
						grp_weight = 0
						grp_score = 0
						grp_clss = ''


				if rec['type'] == 'packaging':

					# write data
					data = [name, no_defect, percent_defect, score, clss]
					fmt = [dhead, ddata, ddata_percent, ddata_percent, ddata_percent]
					i = 0
					for d,f in zip(data, fmt):
						sheet.write(r+i, col, d, f)
						i += 1

					# next column
					grp_weight += weight
					grp_score += score
					col += 1

					if col == (col_end + 1):
						if grp_clss != 'HOLD':
							grp_rule = o.tmpl_id.ext_rule
							grp_clss = self._get_class(grp_rule, grp_weight, grp_score, 'grp')
						elif (o.tmpl_id.pack_hold):
							total_clss = 'HOLD'

						# write totals
						data = ['TOTAL', no_defect, percent_defect, score, grp_clss]
						fmt = [dhead, ddata, ddata_percent, ddata_percent, ddata]
						i = 0
						for d,f in zip(data, fmt):
							if not (i==0 or i==len(data)-1):
								d = '=SUM(%s%s:%s%s)' % (cols[1], r+i+1, cols[col-1], r+i+1)
							sheet.write(r+i, col, d, f)
							i += 1

						sheet.write('E13', '=%s%s' % (cols[col], r+4), head_center_percent)
						sheet.write('E14', '=%s%s' % (cols[col], r+5), head_center)

						col += 1
						sheet.write(r, col, 'BOXES EVALUATED', dhead)
						sheet.write(r+1, col, total_sample, ddata)
						sheet.write(r+2, col, '', ddata)
						sheet.write(r+3, col, '', ddata)
						sheet.write(r+4, col, '', ddata)

						total_score += grp_score

			# # WRITE TOTALS
			total_weight = o.tmpl_id.total_weight / 100.
			overall_rule = o.tmpl_id.overall_rule
			print (total_clss, total_weight, total_score)

			if total_clss != 'HOLD':
				total_clss = self._get_class(overall_rule, total_weight, total_score, 'total')
			print (total_clss, total_weight, total_score)

			# update record
			# o.total_score = total_score
			# o.total_class = total_clss
			o.total_score = round(total_score,3)
			o.total_class = total_clss

			# total_clss = '=IF(OR(C14="HOLD",D14="HOLD"),"HOLD",(IF(B13>=94%%*%s%%,"AA",IF(B13>88%%*%s%%,"A","C"))))' % (total_weight,total_weight)
			sheet.write('B13', '=SUM(C13:E13)', head_tot_val)
			sheet.write('B14', total_clss, head_tot_class)

			# # OTHERS
			d = datetime.strptime(o.date_issue, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone('UTC'))
			d_local = d.astimezone(timezone(o.create_uid.tz or 'Asia/Manila'))
			date_issue = datetime.strftime(d_local, '%d/%m/%Y')
			time_issue = datetime.strftime(d_local, '%H:%M %p')

			sheet.write('B6', date_issue or '', head_name)
			sheet.write('B7', time_issue or '', head_name)
			sheet.write('B8', o.issuer.name or '', head_name)
			sheet.write('B9', o.container or '', head_dash)
			sheet.write('B10', o.customer or '', head_dash)

			# sheet.write('E7', o.product_sc or '', head_name)
			# sheet.write('E8', o.product_ps or '', head_name)
			sheet.write('E7', o.shell_color or '', head_name)
			sheet.write('E8', o.pack_size or '', head_name)
			sheet.write('E9', o.date_pack or '', head_name)
			sheet.write('E10', o.market or '', head_name)

			sheet.write('I7', o.series_no or '', head_name)
			sheet.write('I8', o.date_load or '', head_name)
			sheet.write('I9', o.inspector.name or '', head_name)
			sheet.write('I10', o.no_box or '', head_name)

			sheet.merge_range('G13:H13',o.field_source or '', head_mrg_bot)

			# r = foot_r
			# sheet.merge_range('C%s:H%s'%(r,r),o.temp_start or '', mrg_center_bold)
			# sheet.merge_range('C%s:H%s'%(r+1,r+1),o.temp_end or '', mrg_center_bold)
			# sheet.merge_range('C%s:H%s'%(r+2,r+2),o.van_temp_start or '', mrg_center_bold)
			# sheet.merge_range('C%s:H%s'%(r+3,r+3),o.van_temp_end or '', mrg_center_bold)

			# sheet.merge_range('A%s:A%s'%(r+6,r+7),o.date_pack or '', mrg_center)
			# sheet.merge_range('B%s:B%s'%(r+6,r+7),o.pre_pc or '', mrg_center)
			# sheet.merge_range('C%s:C%s'%(r+6,r+7),o.post_pc or '', mrg_center)
			# sheet.merge_range('H%s:H%s'%(r+6,r+7),o.no_pallet or '', mrg_center)

			# sheet.merge_range('D%s:D%s'%(r+6,r+11),o.cold_store or '', mrg_center)
			# sheet.merge_range('E%s:E%s'%(r+6,r+11),o.pulp_temp_first or '', mrg_center)
			# sheet.merge_range('F%s:F%s'%(r+6,r+11),o.pulp_temp_mid or '', mrg_center)
			# sheet.merge_range('G%s:G%s'%(r+6,r+11),o.pulp_temp_last or '', mrg_center)

			# for c in 'ABCH':
			# 	sheet.merge_range('%s%s:%s%s'%(c,r+8,c,r+9),'', mrg_center)
			# 	sheet.merge_range('%s%s:%s%s'%(c,r+10,c,r+11),'', mrg_center)

			# ADD ATTACHMENT
			
			r = img_attach_r
			try:
				img = o.img
				img = codecs.decode(img, 'base64')
				image_data = BytesIO(img)
				# sheet.insert_image('A%s' % (r+13), '', {'image_data':image_data})
				sheet.insert_image('A%s' % (r), '', {'image_data':image_data})
			except:
				pass