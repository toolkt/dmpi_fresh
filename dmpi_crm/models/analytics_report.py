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



