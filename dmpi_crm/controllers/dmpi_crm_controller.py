# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
import werkzeug

from collections import OrderedDict
from werkzeug.exceptions import NotFound

from odoo import fields
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import get_records_pager, CustomerPortal, pager as portal_pager
from odoo.addons.http_routing.models.ir_http import slug, unslug
from odoo.addons.website.models.ir_http import sitemap_qs2dom
from odoo.addons.website_partner.controllers.main import WebsitePartnerPage
from odoo.osv.expression import OR
import base64



class FreshCustomerPortal(CustomerPortal):

    #dmpi_crm_sale_customer_web.xml
    MANDATORY_CONTRACT_FIELDS = ["customer_ref", "partner_id"]
    OPTIONAL_CONTRACT_FIELDS = ["note", "upload_file"]

    def get_domain_my_contracts(self, user):
        return [
            ('partner_id', 'in', [u.id for u in user.partner_ids]),
        ]


    def _prepare_portal_layout_values(self):
        values = super(FreshCustomerPortal, self)._prepare_portal_layout_values()
        contract_count = request.env['dmpi.crm.customer.sale.contract'].search_count(self.get_domain_my_contracts(request.env.user))
        values.update({
            'contract_count': contract_count,
        })
        return values


    @http.route(['/my/contracts', '/my/contracts/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_contracts(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, search=None, search_in='name', **kw):
        values = self._prepare_portal_layout_values()
        record_obj = request.env['dmpi.crm.customer.sale.contract']
        domain = self.get_domain_my_contracts(request.env.user)


        searchbar_filters = {
            'all': {'label': 'All', 'domain': []},
            'draft': {'label': 'Draft', 'domain': [('state', '=', 'draft')]},
        }

        searchbar_sortings = {
            'date': {'label': 'Newest', 'order': 'create_date desc'},
            'name': {'label': 'Contract No.', 'order': 'name'},
        }

        searchbar_inputs = {
            'name': {'input': 'name', 'label': 'Search in Contract'},
            'customer': {'input': 'customer', 'label': 'Search in Customer'},
            'all': {'input': 'all', 'label': 'Search in All'},
        }

        # default filter by value
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # default sort by value
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # search
        if search and search_in:
            search_domain = []
            if search_in in ('name', 'all'):
                search_domain = OR([search_domain, ['|', ('name', 'ilike', search), ('customer_ref', 'ilike', search)]])
            if search_in in ('customer', 'all'):
                search_domain = OR([search_domain, [('partner_id', 'ilike', search)]])
            domain += search_domain



        # archive groups - Default Group By 'create_date'
        archive_groups = self._get_archive_groups('dmpi.crm.customer.sale.contract', domain)
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]
        # pager
        record_count = record_obj.search_count(domain)
        pager = request.website.pager(
            url="/my/contracts",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=record_count,
            page=page,
            step=self._items_per_page
        )
        # content according to pager and archive selected
        records = record_obj.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_contract_history'] = records.ids[:100]

        values.update({
            'date': date_begin,
            'records': records,
            'page_name': 'contracts',
            'archive_groups': archive_groups,
            'default_url': '/my/contracts',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_inputs': searchbar_inputs,
            'sortby': sortby,
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'filterby': filterby,            
        })
        return request.render("dmpi_crm.portal_my_contracts", values)


    @http.route(["/my/contract/<int:contract_id>"], type='http', auth="user", website=True)
    def portal_my_contract(self, contract_id, **kw):
        record = request.env['dmpi.crm.customer.sale.contract'].browse(contract_id)
        record.check_access_rights('read')
        record.check_access_rule('read')

        values = {
            'record': record,
            'user': request.env.user
        }
        history = request.session.get('my_contract_history', [])
        values.update(get_records_pager(history, record))
        return request.render("dmpi_crm.portal_my_contract", values)



    @http.route(['/my/contract/<string:mode>','/my/contract/<string:mode>/<int:rec_id>'], type='http', auth='user', website=True)
    def contract_new(self, redirect=None, mode='new', rec_id=None, **post):
        values = self._prepare_portal_layout_values()
        contract_obj = request.env['dmpi.crm.customer.sale.contract']
        contract = contract_obj.browse(rec_id)

        values.update({
            'error': {},
            'error_message': [],
        })

        if post:
            # print(post)
            # error, error_message = self.details_form_validate(post)
            error, error_message = {}, []
            values.update({'error': error, 'error_message': error_message})
            values.update(post)

            if not error:
                values = {key: post[key] for key in self.MANDATORY_CONTRACT_FIELDS}
                values.update({key: post[key] for key in self.OPTIONAL_CONTRACT_FIELDS if key in post})
                if post.get('upload_file'):
                    values.update({'upload_file': base64.encodestring(post.get('upload_file').read())})
                print(values)
                # contract_id = contract.contract_id.id
                if mode == 'new':
                    contract = contract_obj.sudo().create(values)

                if values['upload_file']:
                    contract_checker = request.env['dmpi.crm.sale.contract.upload'].sudo().check_upload_file(contract,values['upload_file'])

                    if contract_checker:
                        for c in contract_checker:
                            if c.error_count > 0:
                                values.update({'error': True, 'error_message': c.error})


                if redirect:
                    return request.redirect(redirect)                    
                return request.redirect('/my/contract/%s' % contract.id)

        partner_ids = request.env.user.partner_ids
        
        if mode == 'edit':
            post = contract.read()[0]
            values = {key: post[key] for key in self.MANDATORY_CONTRACT_FIELDS}
            values.update({key: post[key] for key in self.OPTIONAL_CONTRACT_FIELDS if key in post})


        values.update({
            'partner_ids': partner_ids,
            'redirect': redirect,
            'page_name': 'new_contract',
        })


        response = request.render("dmpi_crm.portal_my_new_contract", values)
        response.headers['X-Frame-Options'] = 'DENY'
        return response


    def details_form_validate(self, data):
        error = dict()
        error_message = []

        # Validation
        for field_name in self.MANDATORY_BILLING_FIELDS:
            if not data.get(field_name):
                error[field_name] = 'missing'



        # error message for empty required fields
        if [err for err in error.values() if err == 'missing']:
            error_message.append(_('Some required fields are empty.'))

        unknown = [k for k in data if k not in self.MANDATORY_BILLING_FIELDS + self.OPTIONAL_BILLING_FIELDS]
        if unknown:
            error['common'] = 'Unknown field'
            error_message.append("Unknown field '%s'" % ','.join(unknown))

        return error, error_message
