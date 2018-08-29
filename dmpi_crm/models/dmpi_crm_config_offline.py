# -*- coding: utf-8 -*-

###################################################################################
# 
#    Copyright (C) 2017 MuK IT GmbH
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
# 
###################################################################################

from odoo import _
from odoo import models, api, fields
from odoo.exceptions import ValidationError, AccessError, UserError
from datetime import datetime, timedelta

import odoo.addons.decimal_precision as dp

from odoo.http import request

# pip3 install Fabric3
from fabric.api import *
import paramiko
import socket
import os
import glob
import csv

import tempfile
from io import BytesIO
import re
import pprint
import base64


#@parallel
def file_send(localpath,remotepath):
    with settings(warn_only=True):
        put(localpath,remotepath,use_sudo=True)


#@parallel
def change_permission(path):
    with cd(path):
        cmd = 'chmod 777 -R *'
        sudo(cmd)

#@parallel
def file_get(remotepath, localpath):
    with settings(warn_only=True):
        get(remotepath,localpath)

#@parallel
def transfer_files(from_path, to_path):
    with settings(warn_only=True):
        mv = "mv %s %s" % (from_path,to_path)
        sudo(mv)

#@parallel
def test_remote():
    result = run("ls -l /tmp")
    print (result)


def read_file(file_path, encoding='utf-8'):
    io_obj = BytesIO()
    with settings(warn_only=True):
        get(file_path, io_obj)
        return io_obj.getvalue().decode(encoding)
    return False


def read_file_pdf(file_path, encoding='utf-8'):
    with settings(warn_only=True):
        io_obj = BytesIO()
        get(file_path, io_obj)
        return io_obj.getvalue()
    return False

def list_dir(dir_=None,file_prefix=""):
    """returns a list of files in a directory (dir_) as absolute paths"""
    with settings(warn_only=True):
        with hide('output'):
            if dir_ is not None and not dir_.endswith("/"):
                dir_ += "/"
            dir_ = dir_ or env.cwd
            string_ = run("for i in %s%s*; do echo $i; done" % (dir_,file_prefix))
            files = string_.replace("\r","").split("\n")
        return files

def sap_string_to_float(number_str):
    if '-' in number_str:
        number_str = '-%s' % number_str.replace("-","")
    return float(number_str)

class DmpiCrmConfig(models.Model):
    _inherit = 'dmpi.crm.config'

    inbound_k_success_offline           = fields.Char("Contract Success Offline")
    inbound_k_log_success_offline        = fields.Char("Contract Log Success Offline")

    inbound_so_success_offline           = fields.Char("SO Success Offline")
    inbound_so_log_success_offline        = fields.Char("SO Log Success Offline")


    @api.multi
    def process_offline_contract(self):
        print("Create Offline Contract")

        for rec in self:
            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass


            #Get Success PO
            #outbound_path_success= rec.inbound_k_log_success_sent
            files = execute(list_dir,rec.inbound_k_log_success,'L_ODOO_PO_PU')
            for f_po_suc in files[host_string]:
                try:
                    result = execute(read_file,f_po_suc)[host_string]
                    #Get PoNo from filename
                    po_no = f_po_suc.split('/')[-1:][0].split('_')[3]
                    #Get contract no from data in file
                    cn_no = False
                    line = result.split('\r\n')
                    for l in line:
                        row = l.replace('"', '').split('\t')
                        cn_no = re.sub('[^ a-zA-Z0-9]','',row[0])

                    #Get Equivalent PO in the success folder
                    po_file = 'ODOO_PO_%s' % po_no
                    files = execute(list_dir,rec.inbound_k_success,po_file)
                    for f_po in files[host_string]:
                        if result:
                            result = execute(read_file,f_po)[host_string]
                            line = result.replace('"', '').split('\r\n')

                            po = {}
                            for l in line:
                                row = l.split('\t')
                                if row[0] != '':

                                    partner = self.env['dmpi.crm.partner'].search([('customer_code','=',row[5])],limit=1)[0]
                                    
                                    po = {
                                        'name': row[0],
                                        # 'odoo_po_no' : row[0],
                                        'sap_doc_type' : row[1],
                                        'sales_org' : row[2],
                                        'dist_channel' : row[3],
                                        'division' : row[4],
                                        'partner_id' : partner.id,
                                        'customer_ref' : row[7],
                                        'po_date' : datetime.strptime(row[8], '%Y%m%d').strftime('%Y-%m-%d'),
                                        'valid_from' : datetime.strptime(row[9], '%Y%m%d').strftime('%Y-%m-%d'),
                                        'valid_to' : datetime.strptime(row[10], '%Y%m%d').strftime('%Y-%m-%d'),
                                        'sap_cn_no': cn_no,
                                        'state': 'processing',
                                    }

                                    # line = {
                                    #     'ship_to_id' : ship_to_id,
                                    #     'notify_id' : ship_to_id,
                                    #     'po_line_no' : row[12],
                                    #     'material' : row[13],
                                    #     'qty' : row[14],
                                    #     'uom' : row[15],
                                    # }
                                    # cust_so_line.append(line)
                            po_exist = self.env['dmpi.crm.sale.contract'].search([('name','=',po_no)],limit=1)

                            if po_exist:
                                po_exist.write(po)
                                print("Exist updated")
                            else:
                                po_id = po_exist.create(po)
                                print("Does not Exist, Created PO %s" % po_id)

                    execute(transfer_files,f_po_suc, rec.inbound_k_log_success_offline)
                    execute(transfer_files,f_po, rec.inbound_k_success_offline)
                    print(f_po+f_po_suc)        


                except Exception as e:
                    print("Error %s" % e)
                    pass


    @api.multi
    def process_offline_so(self):
        print("Create Offline SO")

        for rec in self:
            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass


            #Get Success PO
            #outbound_path_success= rec.inbound_k_log_success_sent
            files = execute(list_dir,rec.inbound_so_log_success,'L_ODOO_SO_SU')
            for f_so_suc in files[host_string]:
                #Get Successful SO from Suc File
                try:
                    result = execute(read_file,f_so_suc)[host_string]
                    #Get PoNo from filename
                    so_no = f_so_suc.split('/')[-1:][0].split('_')[3]
                    #Get contract no from data in file
                    sap_so_no = False
                    line = result.split('\r\n')
                    for l in line:
                        row = l.replace('"', '').split('\t')
                        sap_so_no = re.sub('[^ a-zA-Z0-9]','',row[0])

                    #Get Equivalent PO in the success folder
                    so_file = 'ODOO_SO_%s' % so_no
                    files = execute(list_dir,rec.inbound_so_success,so_file)
                    for f_so in files[host_string]:
                        if result:
                            result = execute(read_file,f_so)[host_string]
                            line = result.split('\n')

                            so = {}
                            so_line = []
                            for l in line:
                                row = l.replace('"', '').split('\t')
                                if row[0] != '':     
                                    contract_id = 0
                                    contract = self.env['dmpi.crm.sale.contract'].search([('name','=',row[0])],limit=1)[0]
                                    ship_to_id = 0
                                    ship_to = self.env['dmpi.crm.ship.to'].search([('ship_to_code','=',row[8])],limit=1)[0]
                                    
                                    if contract:

                                        so['sap_so_no'] = sap_so_no
                                        so['name'] = row[2]
                                        so['sap_doc_type'] = row[3] 
                                        so['sales_org'] = row[4]
                                        so['plant'] = row[17]
                                        so['requested_delivery_date'] = datetime.strptime(row[11], '%Y%m%d').strftime('%Y-%m-%d')
                                        so['ship_to_id'] = ship_to.id
                                        so['notify_id'] = ship_to.id
                                        # 'ref_po_no' : row[9],  
                                        # 'po_date' : row[10],
                                        so['contract_id'] = contract.id


                                    #product = self.env['dmpi.crm.product'].search([('sku','=',row[14])],limit=1)[0]
                                    product = self.env['dmpi.crm.product'].search([('sku','=',row[14]),('partner_id','=',contract.partner_id.id)],limit=1)[0]
                                    #print(product)
                                    
                                    sol = {
                                        'contract_line_no' : row[12],
                                        'so_line_no' : row[13], 
                                        'product_id' : product.id,
                                        'product_code' : product.code,
                                        'qty' : int(row[15]),
                                        'uom' : row[16], 
                                    }

                                    so_line.append((0,0,sol.copy()))
                            so['order_ids'] = so_line
                            
                            cust_so_exist = self.env['customer.crm.sale.order'].search([('name','=',so_no)],limit=1)

                            #print (so)
                            if cust_so_exist:
                                cust_so_exist.unlink()
                                # cust_so_exist.write(so)
                                # for o in cust_so_exist.order_ids:
                                #     o.onchange_product_id()
                                # print("Exist updated")
                            # else:
                            po_id = cust_so_exist.create(so)
                            for o in po_id.order_ids:
                                o.onchange_product_id()
                            #print("Does not Exist, Created PO %s" % po_id)

                            so_exist = self.env['dmpi.crm.sale.order'].search([('name','=',so_no)],limit=1)
                            
                            if so_exist:
                                so_exist.unlink()
                            #     so['state'] = 'confirmed'
                            #     so_exist.write(so)
                            #     for o in so_exist.order_ids:
                            #         o.onchange_product_id()
                            #     print("Exist updated")
                            # else:
                            so['state'] = 'confirmed'
                            po_id = so_exist.create(so)
                            for o in po_id.order_ids:
                                o.onchange_product_id()
                            #print("Does not Exist, Created PO %s" % po_id)

                    execute(transfer_files,f_so_suc, rec.inbound_so_log_success_offline)
                    execute(transfer_files,f_so, rec.inbound_so_success_offline)
                    # print(f_so+f_so_suc) 

                except Exception as e:
                    print("Error %s" % e)
                    pass


