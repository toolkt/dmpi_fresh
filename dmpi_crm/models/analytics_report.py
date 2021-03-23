# -*- encoding: utf-8 -*-
from odoo import tools
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError
from datetime import datetime
from datetime import timedelta
import base64
import re
import json
import pandas as pd
import numpy as np


# pip3 install Fabric3
import logging
from fabric.api import *
import paramiko
import socket
import os
import glob


#@parallel
def file_send(localpath,remotepath):
    with settings(warn_only=True):
        put(localpath,remotepath,use_sudo=True)


class DmpiCrmAnalyticsHistorical(models.Model):
    _name = 'dmpi.crm.analytics.historical'
    _description = "CRM Historical Data"

    customer = fields.Char(string="Customer")
    customer_code = fields.Char(string="Customer Code")
    fiscal_year = fields.Char(string="Fiscal Year")
    date = fields.Date(string="Date")
    week_no = fields.Char(string="Week No")
    category = fields.Char(string="Category")
    sku = fields.Char(string="SKU")
    type = fields.Char(string="Type")
    brand = fields.Char(string="Brand")
    qty = fields.Float(string="Quantity")
    amount = fields.Float(string="Amount")
    uom = fields.Char(string="UOM")


class DmpiCrmAnalyticsARDate(models.Model):
    _name = 'dmpi.crm.analytics.ar.date'
    _description = "CRM Analytics AR"

    date = fields.Date("Date")


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
    total_ar = fields.Float(string="Amount")
    ar_0 = fields.Float(string="0")
    ar_30 = fields.Float(string="1-30")
    ar_60 = fields.Float(string="31-60")
    ar_90 = fields.Float(string="61-90")
    ar_240 = fields.Float(string="91-120")
    ar_120 = fields.Float(string="121-360")
    ar_360 = fields.Float(string=">360")



    def _query(self):
        query = """
SELECT row_number() OVER () AS id, *,
CASE WHEN days_overdue = 0 then total_ar END as ar_0,
CASE WHEN days_overdue > 0 AND days_overdue <= 30  then total_ar END as ar_30,
CASE WHEN days_overdue > 30 AND days_overdue <= 60  then total_ar END as ar_60,
CASE WHEN days_overdue > 60 AND days_overdue <= 90  then total_ar END as ar_90,
CASE WHEN days_overdue > 90 AND days_overdue <= 120  then total_ar END as ar_120,
CASE WHEN days_overdue > 120 AND days_overdue <= 240  then total_ar END as ar_240,
CASE WHEN days_overdue > 240 AND days_overdue <= 360  then total_ar END as ar_360,
CASE WHEN days_overdue > 360 then total_ar END as ar_g360

FROM (
SELECT c.id as partner_id, ar.comp_code, ar.debitor, ar.ac_doc_no, ar.clr_doc_no, ar.due_date, 
( (SELECT date from dmpi_crm_analytics_ar_date limit 1) - ar.due_date) as days_overdue,
SUM((CASE WHEN fi_docstat = 'O' and pstng_date <= due_date then deb_cre_lc else 0 END)+(CASE WHEN pstng_date <= due_date and clear_date > due_date then deb_cre_lc else 0 END)) as total_ar
 FROM v_ar_redshift_001 ar
 left join dmpi_crm_partner c on c.customer_code = LTRIM(ar.debitor,'0')
 where c.id > 1 
 group by c.id,ar.comp_code, ar.debitor, ar.ac_doc_no, ar.clr_doc_no, ar.due_date
) as Q1
limit 5
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




class DmpiCrmAnalyticsData(models.Model):
    _name = 'dmpi.crm.analytics.data'
    _description = "CRM Analytics Data"
    _auto = False


    rdd = fields.Date(string="Date")
    contract_no = fields.Char(string="Receive Type")
    partner = fields.Char(string="Donor")
    country = fields.Char(string="Donor Sector")
    customer_ref = fields.Char(string="Country")
    week_no = fields.Char(string="Beneficiary")
    psd = fields.Char(string="Donation Type")
    demand_qty = fields.Float(string="Donation")
    confirmed_qty = fields.Float(string="Reported by")


    def _query(self):
        query = """
SELECT rdd,contract_no,partner,country,customer_ref,week_no,psd,
sum(demand_qty) as demand_qty,sum(confirmed_qty) as confirmed_qty
FROM (
    Select 
    so.requested_delivery_date as rdd, sc.name as contract_no, 
    cp.name as partner, cc.name as country, 
    sc.customer_ref, sc.week_no,
    sol.product_code, 
    'P'||pcode.psd as psd,
    sol.qty as demand_qty, 0 as confirmed_qty
    from customer_crm_sale_order_line sol
    left join dmpi_crm_product prod on prod.id = sol.product_id
    left join dmpi_crm_product_code pcode on pcode.id = prod.code_id
    left join customer_crm_sale_order so on so.id = sol.order_id
    left join dmpi_crm_sale_contract sc on sc.id = so.contract_id
    left join dmpi_crm_partner cp on cp.id = sc.partner_id 
    left join dmpi_crm_country cc on cc.id = cp.country
    WHERE sc.state not in ('cancel','draft') 

    UNION ALL

    Select so.requested_delivery_date as rdd, sc.name as contract_no, 
    cp.name as partner, cc.name as country, 
    sc.customer_ref, sc.week_no,
    sol.product_code, 
    'P'||pcode.psd as psd,
    0 as demand_qty, sol.qty as confirmed_qty
    from dmpi_crm_sale_order_line sol
    left join dmpi_crm_product prod on prod.id = sol.product_id    
    left join dmpi_crm_product_code pcode on pcode.id = prod.code_id
    left join dmpi_crm_sale_order so on so.id = sol.order_id
    left join dmpi_crm_sale_contract sc on sc.id = so.contract_id
    left join dmpi_crm_partner cp on cp.id = sc.partner_id 
    left join dmpi_crm_country cc on cc.id = cp.country
    WHERE sc.state not in ('cancel','draft') 
) AS Q1
GROUP BY rdd,contract_no,partner,country,customer_ref,week_no,psd
ORDER BY rdd, contract_no
        """
        return query


    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as ( 
            %s
            ) """ % (self._table, self._query()))


class DmpiCrmAnalyticsDataSplit(models.Model):
    _name = 'dmpi.crm.analytics.data.split'
    _description = "CRM Analytics Data Split"
    _auto = False


    rdd = fields.Date(string="Date")
    contract_no = fields.Char(string="Receive Type")
    partner = fields.Char(string="Donor")
    country = fields.Char(string="Donor Sector")
    customer_ref = fields.Char(string="Country")
    week_no = fields.Char(string="Beneficiary")
    psd = fields.Char(string="Donation Type")
    qty = fields.Float(string="Quantity")
    order_type = fields.Char(string="Order Type")


    def _query(self):
        query = """
    SELECT 
    so.requested_delivery_date as rdd, sc.name as contract_no, 
    cp.name as partner, cc.name as country, 
    sc.customer_ref, sc.week_no,
    sol.product_code, 
    'P'||pcode.psd as psd,
    sol.qty, 'Demand' as order_type
    from customer_crm_sale_order_line sol
    left join dmpi_crm_product prod on prod.id = sol.product_id
    left join dmpi_crm_product_code pcode on pcode.id = prod.code_id
    left join customer_crm_sale_order so on so.id = sol.order_id
    left join dmpi_crm_sale_contract sc on sc.id = so.contract_id
    left join dmpi_crm_partner cp on cp.id = sc.partner_id 
    left join dmpi_crm_country cc on cc.id = cp.country
    WHERE sc.state not in ('cancel','draft') 

    UNION ALL

    SELECT 
    so.requested_delivery_date as rdd, sc.name as contract_no, 
    cp.name as partner, cc.name as country, 
    sc.customer_ref, sc.week_no,
    sol.product_code, 
    'P'||pcode.psd as psd,
    sol.qty, 'Confirmed' as order_type
    from dmpi_crm_sale_order_line sol
    left join dmpi_crm_product prod on prod.id = sol.product_id    
    left join dmpi_crm_product_code pcode on pcode.id = prod.code_id
    left join dmpi_crm_sale_order so on so.id = sol.order_id
    left join dmpi_crm_sale_contract sc on sc.id = so.contract_id
    left join dmpi_crm_partner cp on cp.id = sc.partner_id 
    left join dmpi_crm_country cc on cc.id = cp.country
    WHERE sc.state not in ('cancel','draft') 
        """
        return query


    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as ( 
            %s
            ) """ % (self._table, self._query()))



class DmpiCrmAnalyticsHistorical(models.Model):
    _name = 'dmpi.crm.analytics.data.historical'
    _description = "CRM Analytics Data Historical"
    _auto = False

    
    date = fields.Date(string="Date")
    cdate = fields.Char(string="Date String")
    fiscal_year = fields.Char(string="Fiscal Year")
    record_type = fields.Char(string="Record")
    customer = fields.Char(string="Customer")
    customer_code = fields.Char(string="Code")
    sales_org = fields.Char(string="Sales Org")
    week_no = fields.Char(string="Week No")
    category = fields.Char(string="Category")
    brand = fields.Char(string="Brand")
    type = fields.Char(string="Type")
    product_code = fields.Char(string="Product")
    psd = fields.Char(string="PSD")
    qty = fields.Float(string="Qty")
    region = fields.Char(string="Region")
    region_description = fields.Char(string="Region Desc")


    def _query(self):
        query = """

        SELECT
        ROW_NUMBER () OVER (
                ORDER BY record_type
        ) as ID, *
        FROM (

        SELECT 
        NULL as date,
        h.fiscal_year,
        '' as cdate,
        'Plan' as record_type,
        cp.name as customer,
        h.customer_code,
        cp.sales_org,
        h.week_no,
        h.category,
        h.brand as brand,
        h.type,
        '' as product_code,
        '' as psd,
        h.qty,
        cc.code as region,
        cc.name as region_description
        from dmpi_crm_analytics_historical h 
        left join dmpi_crm_partner cp on cp.customer_code = h.customer_code and cp.active = true
        left join dmpi_crm_country cc on cc.id = cp.country
        
        UNION ALL
                
                                
        (SELECT 
        so.requested_delivery_date::DATE as date,
        TO_CHAR(so.requested_delivery_date::DATE + interval '1 year' * 1 - interval '1 month' * 4, 'yyyy') as fiscal_year,
        TO_CHAR(so.requested_delivery_date::DATE , 'mm/dd/yyyy') as cdate,
        'Transactional' as record_type,
        cp.name as customer,
        cp.customer_code,
        cp.sales_org,
        sc.week_no::varchar(255),
        pr.category as category,
        pr.brand as brand,
        'ORDER' as "type",
        sol.product_code,
        'P'||pc.psd as psd,
        SUM(sol.qty * pr.case_factor),
        cc.code as region,
        cc.name as region_description
        from customer_crm_sale_order_line sol
        left join customer_crm_sale_order so on so.id = sol.order_id
        left join dmpi_crm_product pr on pr.id = sol.product_id
        left join dmpi_crm_product_code pc on pc.id = pr.code_id
        left join dmpi_crm_sale_contract sc on sc.id = so.contract_id
        left join dmpi_crm_partner cp on cp.id = sc.partner_id and cp.active = true
        left join dmpi_crm_country cc on cc.id = cp.country
        where so.requested_delivery_date >= '2020-09-01'::DATE
        group by so.requested_delivery_date,cp.name, cp.customer_code,sc.week_no,pr.category,cc.code, cc.name,sol.product_code,cp.sales_org,pc.psd,pr.brand
        order by so.requested_delivery_date)
                                
                                
                UNION ALL               
                                
                                
        (SELECT 
        so.requested_delivery_date::DATE as date,
        TO_CHAR(so.requested_delivery_date::DATE + interval '1 year' * 1 - interval '1 month' * 4, 'yyyy') as fiscal_year,
        TO_CHAR(so.requested_delivery_date::DATE , 'mm/dd/yyyy') as cdate,
        'Transactional' as record_type,
        cp.name as customer,
        cp.customer_code,
        cp.sales_org,
        sc.week_no::varchar(255),
        pr.category as category,
                pr.brand as brand,
        'SALE' as "type",
        sol.product_code,
        'P'||pc.psd as psd,
        SUM(sol.qty * pr.case_factor),
        cc.code as region,
        cc.name as region_description
        from dmpi_crm_sale_order_line sol
        left join dmpi_crm_sale_order so on so.id = sol.order_id
        left join dmpi_crm_product pr on pr.id = sol.product_id
        left join dmpi_crm_product_code pc on pc.id = pr.code_id
        left join dmpi_crm_sale_contract sc on sc.id = so.contract_id
        left join dmpi_crm_partner cp on cp.id = sc.partner_id and cp.active = true
        left join dmpi_crm_country cc on cc.id = cp.country
        where so.requested_delivery_date >= '2020-09-01'::DATE
        group by so.requested_delivery_date,cp.name, cp.customer_code,sc.week_no,pr.category,cc.code, cc.name,sol.product_code,cp.sales_org,pc.psd,pr.brand
        order by so.requested_delivery_date)
                
        UNION ALL
        
        (SELECT 
        i.inv_create_date::DATE as date,
        TO_CHAR(i.inv_create_date::DATE + interval '1 year' * 1 - interval '1 month' * 4, 'yyyy') as fiscal_year,
        TO_CHAR(i.inv_create_date::DATE , 'mm/dd/yyyy') as cdate,
        'Transactional' as record_type,
        cp.name as customer,
        cp.customer_code,
        cp.sales_org,
        sc.week_no::varchar(255),
        pr.category as category,
                pr.brand as brand,
        'INVOICE' as "type",
        pc.name as product_code,
        'P'||pc.psd as psd,
        SUM(il.qty * pr.case_factor),
        cc.code as region,
        cc.name as region_description
        FROM dmpi_crm_invoice_line il
        left join dmpi_crm_product pr on pr.sku = il.material
        left join dmpi_crm_product_code pc on pc.id = pr.code_id                
        left join dmpi_crm_invoice i on i.id = il.inv_id
        left join dmpi_crm_sale_order so on so.sap_so_no = i.sap_so_no
        left join dmpi_crm_sale_contract sc on sc.id = so.contract_id
        left join dmpi_crm_partner cp on cp.id = sc.partner_id and cp.active = true
        left join dmpi_crm_country cc on cc.id = cp.country
        where i.inv_create_date::DATE >= '2020-09-01'::DATE and i.source ='500'
        group by i.inv_create_date,cp.name,cp.customer_code,cp.sales_org,sc.week_no,pr.category,pc.name,pc.psd,cc.code,cc.name,pr.brand
        order by i.inv_create_date::DATE)
                ) as Q1

        """
        return query


    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as ( 
            %s
            ) """ % (self._table, self._query()))





    @api.multi
    def action_send_analytics_to_sap(self):
        filename = 'COMMERCIAL_ODOO_DATA.csv'
        path = '/tmp/%s' % filename

        historical_data = self.env['dmpi.crm.analytics.data.historical'].search([])

        data = [{
            'Date': d.cdate if d.cdate else '',
            'Record Type': d.record_type if d.record_type else '',
            'Customer Code': d.customer_code if d.customer_code else '',
            'Customer Description': d.customer if d.customer else '',
            'Region Code': d.region if d.region else '',
            'Region Description': d.region_description if d.region_description else '',
            'Sales Org': d.sales_org if d.sales_org else '',
            'Week No.': d.week_no if d.week_no else '',
            'Fiscal Year': d.fiscal_year if d.fiscal_year else '',
            'Brand': d.brand if d.brand else '',
            'Type': d.type if d.type else '',
            'Product Code': d.product_code if d.product_code else '',
            'PSD': d.psd if d.psd else '',
            'Qty': d.qty if d.qty else '',
        } for d in historical_data]

        df = pd.DataFrame
        cols = ['Date','Record Type','Customer Code','Customer Description','Region Code','Region Description','Sales Org','Week No.','Fiscal Year','Brand','Type','Product Code','PSD','Qty']
        data_df = df(data, columns=cols)
        data_df.to_csv(path, index=False)
        #print(data_df)
        
        
        #TRANSFER TO REMOTE SERVER
        h = self.env['dmpi.crm.config'].search([('default','=',True)],limit=1)
        host_string = h.ssh_user + '@' + h.ssh_host + ':22'
        env.hosts.append(host_string)
        env.passwords[host_string] = h.ssh_pass

        localpath = path
        path = '%s/%s' % (h.inbound_analytics,filename)
        remotepath = path

        execute(file_send,localpath,remotepath)
