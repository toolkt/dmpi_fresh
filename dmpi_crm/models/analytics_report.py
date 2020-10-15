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
        '' as cdate,
        'historical' as record_type,
        cp.name as customer,
        h.customer_code,
        cp.sales_org,
        h.week_no,
        h.category,
        h.category as brand,
        h."type",
        '' as product_code,
        '' as psd,
        h.qty,
        cc.code as region,
        cc.name as region_description
        from dmpi_crm_analytics_histroical h 
        left join dmpi_crm_partner cp on cp.customer_code = h.customer_code
        left join dmpi_crm_country cc on cc.id = cp.country
        
        UNION ALL
                
                                
        (SELECT 
        so.requested_delivery_date as date,
        TO_CHAR(so.requested_delivery_date::DATE , 'mm/dd/yyyy') as cdate,
        'transaction' as record_type,
        cp.name as customer,
        cp.customer_code,
        cp.sales_org,
        sc.week_no::varchar(255),
        pr.category as category,
        pr.brand as brand,
        'ORDER' as "type",
        sol.product_code,
        'P'||pc.psd as psd,
        SUM(sol.qty),
        cc.code as region,
        cc.name as region_description
        from customer_crm_sale_order_line sol
        left join customer_crm_sale_order so on so.id = sol.order_id
        left join dmpi_crm_product pr on pr.id = sol.product_id
        left join dmpi_crm_product_code pc on pc.id = pr.code_id
        left join dmpi_crm_sale_contract sc on sc.id = so.contract_id
        left join dmpi_crm_partner cp on cp.id = sc.partner_id 
        left join dmpi_crm_country cc on cc.id = cp.country
        where so.requested_delivery_date >= '2020-08-01'::DATE
        group by so.requested_delivery_date,cp.name, cp.customer_code,sc.week_no,pr.category,cc.code, cc.name,sol.product_code,cp.sales_org,pc.psd,pr.brand
        order by so.requested_delivery_date)
                                
                                
                UNION ALL               
                                
                                
        (SELECT 
        so.requested_delivery_date as date,
        TO_CHAR(so.requested_delivery_date::DATE , 'mm/dd/yyyy') as cdate,
        'transaction' as record_type,
        cp.name as customer,
        cp.customer_code,
        cp.sales_org,
        sc.week_no::varchar(255),
        pr.category as category,
                pr.brand as brand,
        'SALE' as "type",
        sol.product_code,
        'P'||pc.psd as psd,
        SUM(sol.qty),
        cc.code as region,
        cc.name as region_description
        from dmpi_crm_sale_order_line sol
        left join dmpi_crm_sale_order so on so.id = sol.order_id
        left join dmpi_crm_product pr on pr.id = sol.product_id
        left join dmpi_crm_product_code pc on pc.id = pr.code_id
        left join dmpi_crm_sale_contract sc on sc.id = so.contract_id
        left join dmpi_crm_partner cp on cp.id = sc.partner_id 
        left join dmpi_crm_country cc on cc.id = cp.country
        where so.requested_delivery_date >= '2020-08-01'::DATE
        group by so.requested_delivery_date,cp.name, cp.customer_code,sc.week_no,pr.category,cc.code, cc.name,sol.product_code,cp.sales_org,pc.psd,pr.brand
        order by so.requested_delivery_date)
                
        UNION ALL
        
        (SELECT 
        i.inv_create_date::DATE as date,
        TO_CHAR(i.inv_create_date::DATE , 'mm/dd/yyyy') as cdate,
        'transaction' as record_type,
        cp.name as customer,
        cp.customer_code,
        cp.sales_org,
        sc.week_no::varchar(255),
        pr.category as category,
                pr.brand as brand,
        'INVOICE' as "type",
        pc.name as product_code,
        'P'||pc.psd as psd,
        SUM(il.qty),
        cc.code as region,
        cc.name as region_description
        FROM dmpi_crm_invoice_line il
        left join dmpi_crm_product pr on pr.sku = il.material
        left join dmpi_crm_product_code pc on pc.id = pr.code_id                
        left join dmpi_crm_invoice i on i.id = il.inv_id
        left join dmpi_crm_sale_order so on so.sap_so_no = i.sap_so_no
        left join dmpi_crm_sale_contract sc on sc.id = so.contract_id
        left join dmpi_crm_partner cp on cp.id = sc.partner_id 
        left join dmpi_crm_country cc on cc.id = cp.country
        where i.inv_create_date::DATE >= '2020-08-01'::DATE and i.source ='500'
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






class DmpiCrmAnalyticsHistorical(models.Model):
    _name = 'dmpi.crm.analytics.histroical'
    _description = "CRM Historical Data"

    customer = fields.Char(string="Customer")
    customer_code = fields.Char(string="Customer Code")
    date = fields.Date(string="Date")
    week_no = fields.Char(string="Week No")
    category = fields.Char(string="Category")
    sku = fields.Char(string="SKU")
    type = fields.Char(string="Type")
    qty = fields.Float(string="Quantity")
    amount = fields.Float(string="Amount")

