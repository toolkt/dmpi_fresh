# -*- encoding: utf-8 -*-
from odoo import tools
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError
from datetime import datetime
from datetime import timedelta

class DmpiCrmDiscount(models.Model):
	_name = 'dmpi.crm.discount'
	_description = "List of Supplies Delivered"
	_auto = False


	inv_create_date = fields.Date(string="Date")
	contract = fields.Char("Contract")
	sale_order = fields.Char("Sale Order")
	partner_id = fields.Many2one("dmpi.crm.partner", "Partner")
	# product_id = fields.Many2one("product.product", "Product")
	material = fields.Char("Material")
	qty = fields.Integer("Qty")
	line_net_value = fields.Float("Net Value")
	invoice_price = fields.Float("Invoice Price")
	base_price = fields.Float("Base Price")

	def _query(self):
# Create Idexes
# CREATE INDEX idx_dmpi_crm_product_sku on dmpi_crm_product(sku);
# CREATE INDEX idx_dmpi_crm_product_price_list_item_partner_id_product_id on dmpi_crm_product_price_list_item(partner_id,product_id);
# CREATE INDEX idx_dmpi_crm_invoice_inv_create_date on dmpi_crm_invoice(inv_create_date);
# CREATE INDEX idx_dmpi_crm_invoice_line_material on dmpi_crm_invoice_line(material);
# CREATE INDEX idx_price_item_tag_rel_tag_id on price_item_tag_rel(tag_id);



		query = """
			SELECT il.id,i.inv_create_date, cc.name as contract, so.name as sale_order, 
				so.partner_id,cp.id as product_id, il.material,il.qty,il.line_net_value, 
				il.line_net_value/NULLIF(il.qty,0) as invoice_price,
				(SELECT amount
				from dmpi_crm_product_price_list_item pli
				left join price_item_tag_rel tr on tr.item_id = pli.id
				left join dmpi_crm_product_price_tag pt on pt.id = tr.tag_id
				where partner_id = so.partner_id and product_id = cp.id 
				--and i.inv_create_date::DATE BETWEEN sap_from AND sap_to
				and pt.parent_id is null
				limit 1) AS base_price
			from dmpi_crm_invoice_line il
			left join dmpi_crm_product cp on cp.sku = il.material
			left join dmpi_crm_invoice i on i.id = il.inv_id
			left join dmpi_crm_sale_order so on so.id = i.so_id
			left join dmpi_crm_sale_contract cc on cc.id = i.contract_id
			where so.name is not null
		"""
		return query


	def init(self):
		tools.drop_view_if_exists(self.env.cr, self._table)
		self.env.cr.execute("""CREATE or REPLACE VIEW %s as ( 
			%s
			) """ % (self._table, self._query()))


