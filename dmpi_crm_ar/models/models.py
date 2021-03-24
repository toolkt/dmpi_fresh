# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools


class DmpiCrmAnalyticsARDate(models.Model):
    _name = 'dmpi.crm.analytics.ar.date'
    _description = "CRM Analytics AR"

    date = fields.Date("Date")

    @api.multi
    def get_date_id(self, args=None):
        date_id = self.env['dmpi.crm.analytics.ar.date'].search([],limit=1)
        return date_id.id

class DmpiCrmAnalyticsAR(models.Model):
    _name = 'dmpi.crm.analytics.ar'
    _description = "CRM Analytics AR"
    _auto = False


    comp_code = fields.Char(string="Comp Code")
    debitor = fields.Char(string="Debitor")
    partner_id = fields.Many2one('dmpi.crm.partner',"Partner")
    ac_doc_no = fields.Char(string="AC Doc No")
    clr_doc_no = fields.Char(string="CLR Doc No")
    due_date = fields.Date(string="Due Date")
    pstng_date = fields.Date(string="Posting Date")
    clear_date = fields.Date(string="Clear Date")
    total_ar = fields.Float(string="Total AR Balance")
    total_overdue = fields.Float(string="Total Overdue")
    days_overdue = fields.Integer(string="Days Overdue")
    ar_0 = fields.Float(string="0")
    ar_30 = fields.Float(string="1-30")
    ar_60 = fields.Float(string="31-60")
    ar_90 = fields.Float(string="61-90")
    ar_120 = fields.Float(string="91-120")
    ar_240 = fields.Float(string="121-240")
    ar_360 = fields.Float(string="241-360")
    ar_g360 = fields.Float(string=">360")



    def _query(self):
        query = """
SELECT row_number() OVER () AS id, *,
CASE WHEN days_overdue <= 0 then total_0ar END as ar_0,
CASE WHEN days_overdue > 0 AND days_overdue <= 30  then total_ar END as ar_30,
CASE WHEN days_overdue > 30 AND days_overdue <= 60  then total_ar END as ar_60,
CASE WHEN days_overdue > 60 AND days_overdue <= 90  then total_ar END as ar_90,
CASE WHEN days_overdue > 90 AND days_overdue <= 120  then total_ar END as ar_120,
CASE WHEN days_overdue > 120 AND days_overdue <= 240  then total_ar END as ar_240,
CASE WHEN days_overdue > 240 AND days_overdue <= 360  then total_ar END as ar_360,
CASE WHEN days_overdue > 360 then total_ar END as ar_g360,
CASE WHEN days_overdue > 0 then total_ar END as total_overdue


FROM (
SELECT c.id as partner_id, ar.comp_code, ar.debitor, ar.ac_doc_no, ar.clr_doc_no, ar.due_date, ar.pstng_date, ar.clear_date,
( (SELECT date from dmpi_crm_analytics_ar_date limit 1) - ar.due_date) as days_overdue,

SUM((CASE WHEN fi_docstat = 'O' and pstng_date <= (SELECT date from dmpi_crm_analytics_ar_date limit 1) then deb_cre_lc else 0 END)+
(CASE WHEN pstng_date <= (SELECT date from dmpi_crm_analytics_ar_date limit 1) and clear_date > (SELECT date from dmpi_crm_analytics_ar_date limit 1) then deb_cre_lc else 0 END)) as total_ar,

SUM((CASE WHEN fi_docstat = 'O' and pstng_date <= (SELECT date from dmpi_crm_analytics_ar_date limit 1) and due_date >= (SELECT date from dmpi_crm_analytics_ar_date limit 1) then deb_cre_lc else 0 END)+
(CASE WHEN pstng_date <= (SELECT date from dmpi_crm_analytics_ar_date limit 1) and clear_date > (SELECT date from dmpi_crm_analytics_ar_date limit 1) and due_date >= (SELECT date from dmpi_crm_analytics_ar_date limit 1) then deb_cre_lc else 0 END)) as total_0ar,


 FROM v_ar_redshift_001 ar
 left join dmpi_crm_partner c on c.customer_code = LTRIM(ar.debitor,'0')
 where c.id > 1 
 --and ar.due_date <= (SELECT date from dmpi_crm_analytics_ar_date limit 1) 
 group by c.id,ar.comp_code, ar.debitor, ar.ac_doc_no, ar.clr_doc_no, ar.due_date,ar.pstng_date, ar.clear_date
) as Q1
        """
        return query


    def _query_materialized(self):
        query = """
CREATE materialized view if not exists v_ar_redshift_001 as 
SELECT *
FROM dblink('pg_redshift', $REDSHIFT$
select comp_code, debitor, ac_doc_no, clr_doc_no, "/bic/zduedate" AS due_date, fi_docstat, pstng_date, deb_cre_lc, clear_date
from bw_zcpfiar001;
$REDSHIFT$) AS t1 (comp_code varchar, debitor varchar, ac_doc_no varchar, clr_doc_no varchar, due_date date, fi_docstat varchar, pstng_date date, deb_cre_lc float, clear_date date);
"""
        return query


    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # self.env.cr.execute(self._query_materialized())
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as ( 
            %s
            ) """ % (self._table, self._query()))


    @api.multi
    def get_as_of_date(self):
        print("Get As of Date")

# class dmpi_crm_ar(models.Model):
#     _name = 'dmpi_crm_ar.dmpi_crm_ar'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         self.value2 = float(self.value) / 100