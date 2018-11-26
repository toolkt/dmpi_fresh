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
    _name = 'dmpi.crm.config'
    _inherit = ['mail.thread']

    name        = fields.Char("Setting Description", track_visibility='onchange')
    date      = fields.Date("Date", default=fields.date.today(), track_visibility='onchange')
    active      = fields.Boolean("Active", default=True, track_visibility='onchange')
    default     = fields.Boolean("Default", track_visibility='onchange')

    #PREFIX SETTINGS
    cn_no_prefix   = fields.Char("CN No. Prefix", track_visibility='onchange')
    po_no_prefix    = fields.Char("PO No. Prefix", track_visibility='onchange')
    so_no_prefix    = fields.Char("SO No. Prefix", track_visibility='onchange')
    dr_no_prefix    = fields.Char("DR No. Prefix", track_visibility='onchange')
    inv_no_prefix   = fields.Char("INV No. Prefix", track_visibility='onchange')


    #TABLE RELATIONS
    selection_ids   = fields.One2many('dmpi.crm.config.selection','config_id',"Selection Settings", copy=True)


    #Defaults
    default_validity = fields.Integer("Default Validity")


    #Directories
    ssh_user    = fields.Char("SSH User")
    ssh_pass    = fields.Char("SSH Pass")
    ssh_host    = fields.Char("Host")


    # FCL configuration
    fcl_config_ids = fields.One2many('dmpi.crm.fcl.config','config_id','FCL Config Ids')

    #CONTRACT
    inbound_k                           = fields.Char("Contract")
    inbound_k_success                   = fields.Char("Contract Success")
    inbound_k_fail                      = fields.Char("Contract Fail")
    inbound_k_log_success               = fields.Char("Contract Log Success")
    inbound_k_log_success_sent          = fields.Char("Contract Log Success Sent")
    inbound_k_log_success_error_send    = fields.Char("Contract Log Success Error Send")
    inbound_k_log_fail                  = fields.Char("Contract Log Fail")
    inbound_k_log_fail_sent             = fields.Char("Contract Log Fail Sent")


    #SO
    inbound_so                          = fields.Char("SO")
    inbound_so_success                  = fields.Char("SO Success")
    inbound_so_fail                     = fields.Char("SO Fail")
    inbound_so_log_success              = fields.Char("SO Log Success")
    inbound_so_log_success_sent         = fields.Char("SO Log Success Sent")
    inbound_so_log_success_error_send   = fields.Char("SO Log Success Error Send")
    inbound_so_log_fail                 = fields.Char("SO Log Fail")
    inbound_so_log_fail_sent            = fields.Char("SO Log Fail Sent")

    inbound_so_success_offline           = fields.Char("SO Success Offline")


    #AR
    outbound_ar_success                 = fields.Char("AR Success")
    outbound_ar_success_sent            = fields.Char("AR Success Sent")
    outbound_ar_fail                    = fields.Char("AR Fail")
    outbound_ar_fail_sent               = fields.Char("AR Fail Snt")


    #DR
    outbound_dr_success                 = fields.Char("DR Success")
    outbound_dr_success_sent            = fields.Char("DR Success Sent")
    outbound_dr_fail                    = fields.Char("DR Fail")
    outbound_dr_fail_sent               = fields.Char("DR Fail Snt")


    #SHP
    outbound_shp_success                 = fields.Char("SHP Success")
    outbound_shp_success_sent            = fields.Char("SHP Success Sent")
    outbound_shp_fail                    = fields.Char("SHP Fail")
    outbound_shp_fail_sent               = fields.Char("SHP Fail Snt") 


    #INV
    outbound_inv_success                 = fields.Char("INV Success")
    outbound_inv_success_sent            = fields.Char("INV Success Sent")
    outbound_inv_fail                    = fields.Char("INV Fail")
    outbound_inv_fail_sent               = fields.Char("INV Fail Snt") 


    #INV
    outbound_inv2_success                 = fields.Char("INV2 Success")
    outbound_inv2_success_sent            = fields.Char("INV2 Success Sent")
    outbound_inv2_fail                    = fields.Char("INV2 Fail")
    outbound_inv2_fail_sent               = fields.Char("INV2 Fail Snt") 


    #INV
    outbound_inv1_success                 = fields.Char("INV1 Success")
    outbound_inv1_success_sent            = fields.Char("INV1 Success Sent")
    outbound_inv1_fail                    = fields.Char("INV1 Fail")
    outbound_inv1_fail_sent               = fields.Char("INV1 Fail Snt") 


    #PRC
    outbound_prc_success                 = fields.Char("PRC Success")
    outbound_prc_success_sent            = fields.Char("PRC Success Sent")
    outbound_prc_fail                    = fields.Char("PRC Fail")
    outbound_prc_fail_sent               = fields.Char("PRC Fail Snt") 


    @api.model
    def _cron_execute_queue(self):
        print("AR CRON JOB WORKING")
        try:
            self.search([('default','=',True)],limit=1)[0].process_ar()
        except:
            pass

        try:
            self.search([('default','=',True)],limit=1)[0].process_cl()
        except:
            pass


    @api.model
    def _cron_process_contract(self):
        print("CONTRACT CRON JOB WORKING")
        try:
            self.search([('default','=',True)],limit=1)[0].process_fail_contract()
        except:
            pass

        try:
            self.search([('default','=',True)],limit=1)[0].process_success_contract()
        except:
            pass


    @api.model
    def _cron_process_so(self):
        print("SO CRON JOB WORKING")
        try:
            self.search([('default','=',True)],limit=1)[0].process_so()
        except:
            pass


    @api.model
    def _cron_process_dr(self):
        print("DR & SHIPMENT CRON JOB WORKING")
        try:
            self.search([('default','=',True)],limit=1)[0].process_dr()
        except:
            pass

        try:
            self.search([('default','=',True)],limit=1)[0].process_shp()
        except:
            pass



    @api.model
    def _cron_process_invoice(self):
        print("INVOICE CRON JOB WORKING")
        try:
            self.search([('default','=',True)],limit=1)[0].process_inv()
        except:
            pass
        
        try:
            self.search([('default','=',True)],limit=1)[0].process_inv1()
        except:
            pass

        try:
            self.search([('default','=',True)],limit=1)[0].process_inv2()
        except:
            pass
        
        try:
            self.search([('default','=',True)],limit=1)[0].process_inv2_pdf()
        except:
            pass







    @api.multi
    def test(self):
        print("TEST")
        for rec in self:
            try:
                
                host_string = rec.ssh_user + '@' + rec.ssh_host + ':22'
                env.hosts.append(host_string)
                env.passwords[host_string] = rec.ssh_pass
                execute(test_remote)
                # execute(file_send,localpath,remotepath)
            except:
                pass




    @api.multi
    def process_success_contract(self):
        print("Create Contract")

        for rec in self:
            print("GET SUCCESS")
            outbound_path= rec.inbound_k_log_success
            outbound_path_success= rec.inbound_k_log_success_sent
            outbound_path_fail= rec.inbound_k_log_success_error_send


            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass
            
            files = execute(list_dir,outbound_path,'L_ODOO_PO_PO')
            for f in files[host_string]:

                try:
                    result = execute(read_file,f)[host_string]
                    # print(result)
                    if result:
                        #Extract the PO number from the Filename
                        po_no = f.split('/')[-1:][0].split('_')[3]
                        print(po_no)

                        contract = False
                        line = result.split('\r\n')
                        for l in line:
                            row = l.split('\t')
                            contract = self.env['dmpi.crm.sale.contract'].search([('name','=',po_no)])
                            cn_no = re.sub('[^ a-zA-Z0-9]','',row[0])
                            contract.sap_cn_no = cn_no

                            if contract:
                                for so in contract.sale_order_ids:
                                    so.submit_so_file(so)

                            

                        execute(transfer_files,f, outbound_path_success)
                        rec.write({'state':'processed'})

                        log = { 'name':"CONTRACT SUCCESS", 'log_type':"success",
                                'description':"Transferred %s to %s " % (f,outbound_path_success)
                            }
                        self.env['dmpi.crm.activity.log'].create(log)

                except:
                    print("GET FAIL - FAILED")
                    pass
                    


    @api.multi
    def process_fail_contract(self):
        print("Create Contract")

        for rec in self:
            print("GET SUCCESS")
            outbound_path= rec.inbound_k_log_success
            outbound_path_success= rec.inbound_k_log_success_sent


            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass


            #GET FAIL

            outbound_path_fail= rec.inbound_k_log_fail
            outbound_path_fail_sent= rec.inbound_k_log_fail_sent

            try:
                print("GET FAIL")
                files = execute(list_dir,outbound_path_fail,'L_ODOO_PO_PO')
                for f in files[host_string]:
                    result = execute(read_file,f)[host_string]
                    if result:
                        po_no = f.split('/')[-1:][0].split('_')[3]
                        contract = self.env['dmpi.crm.sale.contract'].search([('name','=',po_no)],limit=1)
                        contract.message_post("ERROR: <br/>%s" % result)
                        # print(contract)
                        rec.write({'state':'hold'})
                        execute(transfer_files,f, outbound_path_fail_sent)


                        log = { 'name':"CONTRACT FAIL", 'log_type':"success",
                                'description':"Transferred %s to %s " % (f,outbound_path_fail_sent)
                            }
                        self.env['dmpi.crm.activity.log'].create(log)

            except:
                print("GET FAIL - FAILED")
                pass




    @api.multi
    def process_so(self):
        print("Create SO")

        for rec in self:

            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass

            outbound_path= rec.inbound_so_log_success
            outbound_path_success= rec.inbound_so_log_success_sent


            try:
                files = execute(list_dir,outbound_path,'L_ODOO_SO_SO')
                for f in files[host_string]:
                    result = execute(read_file,f)[host_string]

                    print (result)

                    #Extract the PO number from the Filename 
                    so_no = f.split('/')[-1:][0].split('_')[3]
                    print(so_no)

                    line = result.split('\r\n')
                    for l in line:
                        if len(l) > 0:
                            row = l.split('\t')
                            print (row)
                            so = self.env['dmpi.crm.sale.order'].search([('name','=',so_no)])
                            if so:
                                sap_so_date = datetime.strptime(row[1], '%m/%d/%Y')
                                sap_so_date = sap_so_date.strftime('%Y-%m-%d')

                                for s in so:
                                    so_details = {'sap_so_no':row[0], 'sap_so_date': sap_so_date }
                                    s.write(so_details)
                                # print("-------%s-------\n%s\n%s" % (contract,f,outbound_path_success))
                                # print(f)
                                # print(outbound_path_fail_sent)

                    execute(transfer_files,f, outbound_path_success)
            except:
                print("ERROR SO")
                pass


            #GET FAIL

            outbound_path_fail= rec.inbound_so_log_fail
            outbound_path_fail_sent= rec.inbound_so_log_fail_sent

            try:
                files = execute(list_dir,outbound_path_fail,'L_ODOO_SO_SO')
                for f in files[host_string]:
                    result = execute(read_file,f)[host_string]

                    #Extract the PO number from the Filename 
                    so_no = f.split('/')[-1:][0].split('_')[3]
                    contract = self.env['dmpi.crm.sale.order'].search([('name','=',so_no)],limit=1).contract_id
                    contract.message_post("ERROR: <br/>%s" % result)


                    execute(transfer_files,f, outbound_path_fail_sent)
            except:
                pass



    @api.multi
    def process_ar(self):
        print("Read AR")

        for rec in self:

            outbound_path= rec.outbound_ar_success
            outbound_path_success= rec.outbound_ar_success_sent
            outbound_path_fail = rec.outbound_ar_fail

            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass

            files = execute(list_dir,outbound_path,'ODOO_AR_OPENAR')

            for f in files[host_string]:
                try:
                    result = execute(read_file,f)[host_string]

                    line = result.split('\n')

                    vals = []
                    line_vals = []
                    for l in line:
                        row = l.split('\t')
                        val = ""
                        if len(row) and len(row) == 24: 
                            print(row)
                            # print(len(row))
                            partner_id = 0
                            try:
                                partner_id = self.env['dmpi.crm.partner'].search([('customer_code','=',int(row[1].lstrip('0')))], limit=1)[0].id
                            except:
                                pass


                            name = "%s-%s" % (row[16],row[4])
                            if row[18] == 'H':
                                amt_in_loc_cur = float(row[11].replace(',','')) * -1
                                amt_in_loc_cur2 = float(row[19].replace(',','')) * -1
                            else:
                                amt_in_loc_cur = float(row[11].replace(',',''))
                                amt_in_loc_cur2 = float(row[19].replace(',',''))

                            val = """('%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s',%s,'%s','%s','%s','%s',
                                '%s','%s','%s',%s,'%s','%s','%s','%s',%s)""" % (name, row[0], row[1], 
                                row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10], 
                                amt_in_loc_cur, row[12], row[13], row[14], row[15], row[16], row[17], row[18], 
                                amt_in_loc_cur2, row[20], row[21], row[22], row[23], partner_id)

                            
                            if row[17] and row[17] == 'D':
                                vals.append(val)
                            else:
                                line_vals.append(val)


                    query = """INSERT INTO dmpi_crm_partner_ar (name, company_code, customer_no, assignment_no, fiscal_year,
                        acct_doc_no, psting_date, doc_date, local_curr, ref_doc, doc_type, fiscal_period, 
                        amt_in_loc_cur, base_line_date, terms,cash_disc_days, acct_doc_no2, acct_doc_num_line,
                        acct_type, debit_credit, amt_in_loc_cur2, assign_no, gl_acct_no, gl_acct_no2, customer_no2, partner_id
                        ) VALUES %s""" % ','.join(vals)

                    # print (query)
                    q1 = """DELETE from dmpi_crm_partner_ar;"""
                    q2 = """SELECT setval('dmpi_crm_partner_ar_id_seq', COALESCE((SELECT MAX(id)+1 FROM dmpi_crm_partner_ar), 1), false);"""


                    if len(vals)>0:
                        self.env.cr.execute(q1)
                        self.env.cr.execute(q2)
                        self.env.cr.execute(query)


                    queryl = """INSERT INTO dmpi_crm_partner_ar_line (name, company_code, customer_no, assignment_no, fiscal_year,
                        acct_doc_no, psting_date, doc_date, local_curr, ref_doc, doc_type, fiscal_period, 
                        amt_in_loc_cur, base_line_date, terms,cash_disc_days, acct_doc_no2, acct_doc_num_line,
                        acct_type, debit_credit, amt_in_loc_cur2, assign_no, gl_acct_no, gl_acct_no2, customer_no2, partner_id
                        ) VALUES %s""" % ','.join(line_vals)


                    # print (query)
                    ql1 = """DELETE from dmpi_crm_partner_ar_line;"""
                    ql2 = """SELECT setval('dmpi_crm_partner_ar_line_id_seq', COALESCE((SELECT MAX(id)+1 FROM dmpi_crm_partner_ar_line), 1), false);"""


                    if len(line_vals)>0:
                        self.env.cr.execute(ql1)
                        self.env.cr.execute(ql2)
                        self.env.cr.execute(queryl)


                    execute(transfer_files,f, outbound_path_success)

                    log = { 'name':"ODOO_AR_OPENAR", 'log_type':"success",
                            'description':"Transferred %s to %s " % (f,outbound_path_success)
                        }
                    self.env['dmpi.crm.activity.log'].create(log)

                except Exception as e:

                    execute(transfer_files,f, outbound_path_fail)
                    log = { 'name':"ODOO_AR_OPENAR", 'log_type':"fail",
                            'description':"ERROR: %s \nTransferred %s to %s " % (e,f,outbound_path_fail)
                        }
                    self.env['dmpi.crm.activity.log'].create(log)
                    # print("-------%s-------\n" % (e))
                    # pass



    @api.multi
    def process_cl(self):
        print("Read Credit Limit")

        for rec in self:
            outbound_path= rec.outbound_ar_success
            outbound_path_success= rec.outbound_ar_success_sent
            outbound_path_fail = rec.outbound_ar_fail

            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass

            files = execute(list_dir,outbound_path,'ODOO_AR_CRDLMT')
            
            for f in files[host_string]:
                try:
                    result = execute(read_file,f)[host_string]

                    line = result.split('\n')

                    vals = []
                    for l in line:
                        row = l.split('\t')

                        if len(row) > 0 and row[0] != '':  
                            customer_code = int(row[0].lstrip("0"))
                            print (customer_code)

                            print (customer_code,f)
                            exist = self.env['dmpi.crm.partner.credit.limit'].search([('customer_code','=',customer_code)],limit=1)
                            partner = self.env['dmpi.crm.partner'].search([('customer_code','=',customer_code)],limit=1)[0]
                            credit_limit = sap_string_to_float(row[2].replace(',',''))
                            credit_exposure = sap_string_to_float(row[3].replace(',',''))



                            if partner:
                                val = """(%s,'%s','%s',%s,%s,'%s')""" % (partner.id,str(customer_code),str(row[1]),credit_limit,credit_exposure,row[4])
                                vals.append(val)
                            else:
                                val = """(%s,'%s','%s',%s,%s,'%s')""" % (False,str(customer_code),str(row[1]),credit_limit,credit_exposure,row[4])
                                vals.append(val)


                    query = """INSERT INTO dmpi_crm_partner_credit_limit (partner_id,customer_code, credit_control_no,credit_limit,credit_exposure,currency) VALUES %s """ % ','.join(vals)

                    print (query)

                    # print (query)
                    q1 = """DELETE from dmpi_crm_partner_credit_limit;"""
                    q2 = """SELECT setval('dmpi_crm_partner_credit_limit_id_seq', COALESCE((SELECT MAX(id)+1 FROM dmpi_crm_partner_credit_limit), 1), false);"""

                    if len(vals)>0:
                        self.env.cr.execute(q1)
                        self.env.cr.execute(q2)
                        self.env.cr.execute(query)

                        execute(transfer_files,f, outbound_path_success)

                        log = { 'name':"ODOO_AR_CRDLMT", 'log_type':"success",
                                'description':"Transferred %s to %s " % (f,outbound_path_success)
                            }
                        self.env['dmpi.crm.activity.log'].create(log)

                except Exception as e:
                    execute(transfer_files,f, outbound_path_fail)
                    log = { 'name':"ODOO_AR_CRDLMT", 'log_type':"fail",
                            'description':"ERROR: %s \nTransferred %s to %s " % (e,f,outbound_path_fail)
                        }
                    self.env['dmpi.crm.activity.log'].create(log)
                    # print("-------%s-------\n" % (e))
                    # pass




    # @api.multi
    # def process_prc(self):
    #     print("Process Price")

    #     for rec in self:

    #         outbound_path= rec.outbound_prc_success
    #         outbound_path_success= rec.outbound_prc_success_sent

    #         h = self.search([('default','=',True)],limit=1)
    #         host_string = h.ssh_user + '@' + h.ssh_host + ':22'
    #         env.hosts.append(host_string)
    #         env.passwords[host_string] = h.ssh_pass

    #         try:
    #             files = execute(list_dir,outbound_path,'DMS_A910_PRICEDOWNLOAD')
    #             for f in files[host_string]:
    #                 result = execute(read_file,f)[host_string]

    #                 line = result.split('\n')

                
    #                 for l in line:
    #                     row = l.split('\t')

    #                     # print ("-----------ODOO_AR_OPENAR-------------")
    #                     valid_to = False
    #                     try:
    #                         date = datetime.strptime(row[5], '%m/%d/%Y')
    #                         print (date.year)
    #                         if date.year > 2100:
    #                             valid_to = datetime(2100, date.month, date.day)
    #                         else:
    #                             valid_to = date
    #                     except:
    #                         print("Date ERROR %s",row)
    #                         pass
                    
    #                     if row[0] != '':

    #                         name = "%s-%s-%s-%s%s%s%s" % (row[4],row[3],row[5],row[0],row[1],row[2],row[6])
    #                         amount = row[7].replace(',', '')

    #                         prc = {
    #                             'name' : name,
    #                             'application' : row[0],
    #                             'condition_type' : row[1],
    #                             'sales_org' : row[2],
    #                             'customer' : row[3],
    #                             'material' : row[4],
    #                             'valid_to' :  valid_to,
    #                             'valid_to_sap' :  row[5],
    #                             'condition_record' : row[6],
    #                             'condition_rate' : amount,
    #                             'condition_currency' : row[8],
    #                             'uom' : row[9],
    #                         }

    #                         #print(prc)

    #                         exist = self.env['dmpi.sap.price.upload'].search([('name','=',name)],limit=1)
    #                         if exist:
    #                             print("EXIST %s" % exist)
    #                             exist.write(prc)
    #                         else:
    #                             prc_id = self.env['dmpi.sap.price.upload'].create(prc)
    #                             print("NEW %s" % prc_id)


    #                 execute(transfer_files,f, outbound_path_success)
    #         except Exception as e:
    #             print("-------%s-------\n" % e)
    #             pass





    @api.multi
    def process_dr(self):
        print("Read DR")

        for rec in self:

            outbound_path= rec.outbound_dr_success
            outbound_path_success= rec.outbound_dr_success_sent
            outbound_path_fail= rec.outbound_dr_fail

            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass

            files = execute(list_dir,outbound_path,'ODOO_DR')            
            for f in files[host_string]:
                try:
                    result = execute(read_file,f)[host_string]

                    line = result.split('\n')
                    odoo_po_no = ""
                    dr_id = 0
                    raw = []
                    clp = False


                    sap_dr_no = ""
                    dr = {}
                    dr_lines = []
                    alt_items = []
                    insp_lots = []
                    clp = {}
                    clp_lines =[]
                    dr_tr_item = []

                    contract_id = ''
                    for l in line:
                        raw.append(l)
                        row = l.split('\t')
                        if row[0] != '':
                            if row[0] == 'Header':

                                contract = self.env['dmpi.crm.sale.contract'].search([('name','=',row[1])],limit=1)
                                if contract:
                                    contract_id = contract.id
                                    
                                sap_dr_no = row[4]
                                so = self.env['dmpi.crm.sale.order'].search([('sap_so_no','=',row[3])], limit=1)

                                if so:
                                    contract = so.contract_id
                                    contract_id = contract.id


                                dr = {
                                    'contract_id' : contract_id,
                                    'odoo_po_no' : row[1],
                                    'odoo_so_no' : row[2],
                                    'sap_so_no' : row[3],
                                    'sap_dr_no' : row[4],
                                    'sap_delivery_no' : row[4],
                                    'ship_to' : row[5],
                                    'delivery_creation_date' : row[6],
                                    'gi_date' : row[7],
                                    'shipment_no' : row[8],
                                    'fwd_agent' :  row[9],
                                    'van_no' : row[10],
                                    'vessel_name' : row[11],
                                    'truck_no' : row[12],   
                                    'load_no' : row[13],
                                    'booking_no' : row[14], 
                                    'seal_no' : row[15],
                                    'port_origin' : row[16],
                                    'port_destination' : row[17], 
                                    'port_discharge' : row[18],
                                }

                                try:
                                    dr['sto_no'] = row[19]
                                except:
                                    pass


                            if row[0] == 'Item' and (row[1],row[9]) not in dr_tr_item:
                                line = {
                                    'dr_line_item_no' : row[1],
                                    'sku' : row[2],
                                    'qty' : row[3].replace(',', ''),
                                    'uom' : row[4],
                                    'plant' : row[5],
                                    'wh_no' : row[6],
                                    'storage_loc' : row[7],
                                    'to_num' : row[8],
                                    'tr_order_item' : row[9],
                                    'material' : row[10],
                                    'plant2' : row[11],
                                    'batch' : row[12],
                                    'stock_category' : row[13],
                                    'source_su' : row[14],
                                    'sap_delivery_no' : row[15],
                                }

                                dr_lines.append((0,0,line))
                                dr_tr_item.append((row[1], row[9]))
                                #print(row)

                            if row[0].upper() == 'ALTTOITM':

                                line = {
                                    'sap_so_no' : row[1],
                                    'sap_so_line_no' : row[2],
                                    'material' : row[3],
                                    'qty' : row[4].replace(',', ''),
                                    'uom' : row[5],
                                    'plant' : row[6],
                                    'rejection_reason' : row[7],
                                    # 'alt_usage' : row[8],
                                }

                                alt_items.append((0,0,line))

                                # print("-------%s-------" % row[0])
                                # print(row)


                            #Inspection Lot
                            if row[0].upper() == 'IL': 
                                # print("-------%s-------" % row[0])
                                # print(row)

                                line = {
                                    'dr_line_item_no' : row[1],
                                    # 'sap_so_no' : row[2],
                                    'stock_unit' : row[2],
                                    # 'sku' : row[3],
                                    'lot' : row[4],
                                    'node_num' : row[5],
                                    'type' : row[6],
                                    'factor_num' : row[7],
                                    'factor' : row[8],
                                    'no_sample' : row[9].replace(',', ''),
                                    'no_defect' : row[10].replace(',', ''),
                                    'value' : row[11].replace(',', ''),
                                }

                                insp_lots.append((0,0,line))

                                # print("-------%s-------" % row[0])
                                # print(row)

                            
                            if row[0].upper() == 'CLPHEADER1':
                                # print("-------%s-------" % row[0])
  
                                clp['layout_name'] = row[1]
                                clp['container_no'] = row[2]
                                clp['seal_no'] = row[3]
                                clp['vessel_name'] = row[4]
                                clp['plant'] = row[5]
                                clp['port_origin'] = row[6]
                                clp['port_destination'] = row[7]
                                clp['customer'] = row[8]
                                clp['shell_color'] = so.shell_color


                            if row[0].upper() == 'CLPHEADER2':

                                clp['week'] = row[1]
                                clp['brand'] = row[2]
                                clp['description'] = row[3]
                                clp['boxes'] = float(row[4].replace(',', ''))



                            if row[0].upper() == 'CLPITEM':

                                line = {
                                    'tag_no' : row[1],
                                    'pack_code' : row[2],
                                    'pack_size' : row[3],
                                    'product_crown'  : row[4],
                                    'qty'  : row[5].replace(',', ''),
                                    'position'  : row[6],
                                }


                                clp_lines.append((0,0,line))                                               

                            if row[0].upper() == 'CLPFTR':
                                # print("-------%s-------" % row[0])
                                # print(row)

                                clp['date_start'] = row[1]
                                clp['date_end'] = row[2]
                                clp['date_depart'] = row[3]
                                clp['date_arrive'] = row[4]
                                clp['control_no'] = row[5]

                                case_summary = []
                                rl = len(row)
                                for i in range(6,rl):
                                    case_summary.append(row[i])

                                clp['case_summary'] = '\n'.join(case_summary)
                                # clp['summary_case_a'] = row[6]
                                # clp['summary_case_b'] = row[7]
                                # clp['summary_case_c'] = row[8]

                    if contract_id:
                        # do not create if no dr_lines (remove)
                        success = True
                        # if len(dr_lines) == 0:
                            # success = False

                        if success:
                            dr['dr_lines'] = dr_lines
                            dr['alt_items'] = alt_items
                            dr['insp_lots'] = insp_lots

                            clp['clp_line_ids'] = clp_lines
                            dr['clp_ids'] = [(0,0,clp)]

                            # pprint.pprint(dr, width=4)

                            exist = self.env['dmpi.crm.dr'].search([('sap_dr_no','=',sap_dr_no)],limit=1)
                            if exist:
                                exist.dr_lines.unlink()
                                exist.alt_items.unlink()
                                exist.insp_lots.unlink()
                                exist.clp_ids.unlink()

                                exist.write(dr)
                                dr_id = exist.id

                                print ('DR ALREADY EXISTS')
                            else:
                                new_dr = self.env['dmpi.crm.dr'].create(dr) 
                                dr_id = new_dr.id
                                print ('DR SUCCESSFULLY CREATED')


                            execute(transfer_files,f, outbound_path_success)
                        else:
                            print ('NO DR LINES')
                            execute(transfer_files,f, outbound_path_fail)


                except Exception as e:
                    print(e)
                    pass




    @api.multi
    def process_shp(self):
        print("Read Shipment")

        for rec in self:

            outbound_path= rec.outbound_shp_success
            outbound_path_success= rec.outbound_shp_success_sent

            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass

            try:
                files = execute(list_dir,outbound_path,'ODOO_SHP')
                
                for f in files[host_string]:
                    result = execute(read_file,f)[host_string]

                    line = result.split('\n')
                    odoo_po_no = ""
                    sap_dr_no = ""
                    raw = []


                    shp_no = ''
                    shp = {}
                    shp_lines = []
                    contract_id = ''
                    for l in line:
                        raw.append(l)
                        row = l.split('\t')

                        if row[0].upper() == 'HEADER':

                            # contract_id = ''
                            contract = self.env['dmpi.crm.sale.contract'].search([('name','=',row[1])],limit=1)
                            if contract:
                                contract_id = contract.id

                            shp_no = row[8]
                            shp = {
                                'contract_id':contract_id,
                                'odoo_po_no':row[1],
                                'odoo_so_no':row[2],   
                                'sap_so_no':row[3],  
                                'sap_dr_no':row[4],   
                                'ship_to':row[5],
                                'dr_create_date' :row[6],  
                                'gi_date':row[7],
                                'shp_no' :row[8],
                                'fwd_agent':row[9],  
                                'van_no':row[10],
                                'vessel_no' :row[11],    
                                'truck_no':row[12],    
                                'load_no':row[13],
                                'booking_no' :row[14], 
                                'seal_no':row[15],
                                'origin':row[16],  
                                'destination':row[17], 
                                'discharge':row[18], 
                            }

                        if row[0].upper() == 'ALTTOITM':
                            print(row)
                            line = {
                                'sap_so_no':row[1],
                                'so_line_no':row[2],
                                'material':row[3],
                                'qty': float(re.sub('\,','',row[4])),
                                'uom':row[5],
                                'plant':row[6],
                                'reject_reason':row[7],
                                'alt_item':row[8],
                                'usage':row[9],
                            }

                            shp_lines.append((0,0,line))


                    shp['shp_lines'] = shp_lines
                    
                    if contract_id > 0:
                        pprint.pprint(shp, width=4)
                        exist = self.env['dmpi.crm.shp'].search([('shp_no','=',shp_no)],limit=1)
                        if exist:
                            exist.shp_lines.unlink()
                            exist.write(shp)
                        else:
                            new_dr = self.env['dmpi.crm.shp'].create(shp) 

                        contract.write({'state':'enroute'})
                        execute(transfer_files,f, outbound_path_success)

            except Exception as e:
                print(e)
                pass





    @api.multi
    def process_inv(self):
        print("Read Inv")

        for rec in self:


            outbound_path= rec.outbound_inv_success
            outbound_path_success= rec.outbound_inv_success_sent

            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass

            try:
                files = execute(list_dir,outbound_path,'ODOO_DMPI_INV')
                
                for f in files[host_string]:
                    result = execute(read_file,f)[host_string]

                    line = result.split('\n')


                    inv_lines = []
                    inv = {}
                    name = ''
                    contract_id = ''

                    for l in line:
                        row = l.split('\t')

                        if row[0] != '':

                            inv_no = []
                            inv_no.append('500')
                            if row[5] != '':
                                inv_no.append(row[5])
                            if row[6] != '':
                                inv_no.append(row[6])
                            if row[7] != '':
                                inv_no.append(row[7])

                            name = "/".join(inv_no)

                                # inv_no
                                # dmpi_sap_inv_no
                                # contract_id
                                # raw


                            contract = self.env['dmpi.crm.sale.contract'].search([('name','=',row[0])],limit=1)
                            if contract:
                                contract_id = contract.id


                            inv = {
                                'contract_id' : contract_id,
                            	'source':'500',
                                'name': name,
                                'odoo_po_no' : row[0],
                                'odoo_so_no' : row[1],
                                'sap_so_no': row[2],
                                'sap_dr_no': row[3],
                                'shp_no' : row[4],
                                'dmpi_inv_no': row[5],
                                'dms_inv_no': row[6],
                                'sbfti_inv_no': row[7],
                                'payer': row[8],
                                'inv_create_date': row[9],
                                'header_net': row[10],
                            }


                            inv_line = {
                                'so_line_no' : row[11], 
                                'inv_line_no' : row[12],
                                'material' : row[13], 
                                'qty' : float(row[14].replace(',','')),
                                'uom' : row[15],
                                'line_net_value' : float(row[16].replace(',','')),
                            }

                            inv_lines.append((0,0,inv_line))



                    inv['inv_lines'] = inv_lines

                    if contract_id > 0 and len(inv_lines) > 0:
                        pprint.pprint(inv, width=4)

                        exist = self.env['dmpi.crm.invoice'].search([('name','=',name)],limit=1)

                        if exist:
                            exist.inv_lines.unlink()
                            exist.write(inv)
                            print("EXIST WRITE")
                        else:
                            new_dr = self.env['dmpi.crm.invoice'].create(inv) 
                            print("NOT EXIST NEW")
                            
                        execute(transfer_files,f, outbound_path_success)

            except Exception as e:
                print(e)
                pass


    @api.multi
    def process_inv1(self):
        print("Read Inv1")

        for rec in self:

            outbound_path= rec.outbound_inv1_success
            outbound_path_success= rec.outbound_inv1_success_sent

            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass

            try:
                files = execute(list_dir,outbound_path,'ODOO_DMPI_INV')
                
                for f in files[host_string]:
                    print("\n\n---------%s" % f)
                    result = execute(read_file,f)[host_string]

                    line = result.split('\n')


                    inv_lines = []
                    inv = {}
                    name = ''

                    for l in line:
                        row = l.split('\t')

                        if len(row) > 1:

                            inv_no = []
                            inv_no.append('570')
                            if row[5] != '':
                                inv_no.append(row[5])
                            if row[6] != '':
                                inv_no.append(row[6])
                            if row[7] != '':
                                inv_no.append(row[7])

                            name = "/".join(inv_no)

                                # inv_no
                                # dmpi_sap_inv_no
                                # contract_id
                                # raw

                            inv = {
                                'source':'570',
                                'name': name,
                                'dmpi_inv_no': row[5],
                                'dms_inv_no': row[6],
                                'sbfti_inv_no': row[7],
                                'payer': row[8],
                                'inv_create_date': row[9],
                                'header_net': row[10],
                            }

                            source = self.env['dmpi.crm.invoice'].search([('dmpi_inv_no','=',row[5]),('source','=','500')],limit=1)
                            if source:
                                inv['odoo_po_no'] = source.odoo_po_no
                                inv['odoo_so_no'] = source.odoo_so_no
                                inv['sap_so_no'] = source.sap_so_no
                                inv['sap_dr_no'] = source.sap_dr_no
                                inv['shp_no'] = source.shp_no
                                inv['contract_id'] = source.contract_id.id

                            inv_line = {
                                'so_line_no' : row[11], 
                                'inv_line_no' : row[12],
                                'material' : row[13], 
                                'qty' : float(row[14].replace(',','')),
                                'uom' : row[15],
                                'line_net_value' : float(row[16].replace(',','')),
                            }


                            inv_lines.append((0,0,inv_line))

                    inv['inv_lines'] = inv_lines

                    pprint.pprint(inv, width=4)

                    if len(inv_lines) > 0:
                        exist = self.env['dmpi.crm.invoice'].search([('name','=',name)],limit=1)
                        if exist:
                            exist.inv_lines.unlink()
                            exist.write(inv)
                        else:
                            new_dr = self.env['dmpi.crm.invoice'].create(inv) 
                            
                        execute(transfer_files,f, outbound_path_success)

            except Exception as e:
                print(e)
                pass



    @api.multi
    def process_inv2(self):
        print("Read Inv2")

        for rec in self:

            outbound_path= rec.outbound_inv2_success
            outbound_path_success= rec.outbound_inv2_success_sent

            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass

            try:
                files = execute(list_dir,outbound_path,'ODOO_DMPI_INV')
                
                for f in files[host_string]:
                    print("\n\n---------%s" % f)
                    result = execute(read_file,f)[host_string]

                    line = result.split('\n')


                    inv_lines = []
                    inv = {}
                    name = ''

                    for l in line:
                        row = l.split('\t')

                        if len(row) > 1 and row[6] != '':

                            inv_no = []
                            inv_no.append('530')
                            if row[5] != '':
                                inv_no.append(row[5])
                            if row[6] != '':
                                inv_no.append(row[6])
                            if row[7] != '':
                                inv_no.append(row[7])


                            source = self.env['dmpi.crm.invoice'].search([('dmpi_inv_no','=',row[5]),('source','=','500')],limit=1)

                            name = "/".join(inv_no)

                                # inv_no
                                # dmpi_sap_inv_no
                                # contract_id
                                # raw

                            inv = {
                                'contract_id': source.contract_id.id,
                                'source':'530',
                                'name': name,
                                'odoo_po_no' : source.odoo_po_no or False,
                                'odoo_so_no' : source.odoo_so_no or False,
                                'sap_so_no': source.sap_so_no or False,
                                'sap_dr_no': source.sap_dr_no or False,
                                'shp_no' : source.shp_no or False,
                                'dmpi_inv_no': row[5],
                                'dms_inv_no': row[6],
                                'sbfti_inv_no': row[7],
                                'payer': row[8],
                                'inv_create_date': row[9],
                                'header_net': row[10],
                            }


                            inv_line = {
                                'so_line_no' : row[11], 
                                'inv_line_no' : row[12],
                                'material' : row[13], 
                                'qty' : float(row[14].replace(',','')),
                                'uom' : row[15],
                                'line_net_value' : float(row[16].replace(',','')),
                            }

                            inv_lines.append((0,0,inv_line))

                    inv['inv_lines'] = inv_lines

                    #pprint.pprint(inv, width=4)
                    if inv['contract_id'] != '' and len(inv_lines) > 0:
                        exist = self.env['dmpi.crm.invoice'].search([('name','=',name)],limit=1)
                        if exist:
                            exist.inv_lines.unlink()
                            exist.write(inv)
                        else:
                            new_dr = self.env['dmpi.crm.invoice'].create(inv) 
                            
                        execute(transfer_files,f, outbound_path_success)

            except Exception as e:
                print(e)
                pass




    @api.multi
    def process_inv2_pdf(self):
        print("Read Inv2 PDF")

        for rec in self:

            outbound_path= rec.outbound_inv2_success
            outbound_path_success= rec.outbound_inv2_success_sent

            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass


            try:
                files = execute(list_dir,outbound_path,'ODOO_ZMAL')
                
                for f in files[host_string]:

                    result = execute(read_file_pdf,f)[host_string]
                    file_base64 = base64.b64encode(result)

                    #Extract the PO number from the Filename
                    filename = f.split('/')[-1:][0]
                    dms_inv_no = filename.split('_')[2]
                    print("\n\n------%s" % filename)
                    #print (result)
                    


                    exist = self.env['dmpi.crm.invoice'].search([('dms_inv_no','=',dms_inv_no)],limit=1)
                    if exist:
                        print(exist)
                        exist.write({'invoice_file':file_base64, 'invoice_filename':filename})
                        execute(transfer_files,f, outbound_path_success)

            except Exception as e:
                print(e)
                pass







    @api.multi
    def process_inv2_old(self):
        print("Read Inv2")

        for rec in self:

            outbound_path= rec.outbound_inv2_success
            outbound_path_success= rec.outbound_inv2_success_sent

            h = self.search([('default','=',True)],limit=1)
            host_string = h.ssh_user + '@' + h.ssh_host + ':22'
            env.hosts.append(host_string)
            env.passwords[host_string] = h.ssh_pass

            try:
                files = execute(list_dir,outbound_path,'')
                
                for f in files[host_string]:
                    result = execute(read_file,f)[host_string]

                    line = result.split('\n')


                    inv_lines = []
                    inv = {}
                    name = ''

                    for l in line:
                        row = l.split('\t')

                        if row[0] != '':

                            inv_no = []
                            if row[5] != '':
                                inv_no.append(row[5])
                            if row[6] != '':
                                inv_no.append(row[6])
                            if row[7] != '':
                                inv_no.append(row[7])

                            name = "/".join(inv_no)

                                # inv_no
                                # dmpi_sap_inv_no
                                # contract_id
                                # raw

                            inv = {

                                'name': name,
                                'odoo_po_no' : row[0],
                                'odoo_so_no' : row[1],
                                'sap_so_no': row[2],
                                'sap_dr_no': row[3],
                                'shp_no' : row[4],
                                'dmpi_inv_no': row[5],
                                'dms_inv_no': row[6],
                                'sbfti_inv_no': row[7],
                                'payer': row[8],
                                'inv_create_date': row[9],
                                'header_net': row[10],
                            }


                            inv_line = {
                                'so_line_no' : row[11], 
                                'inv_line_no' : row[12],
                                'material' : row[13], 
                                'qty' : row[14],
                                'uom' : row[15],
                                'line_net_value' : row[16],
                            }

                            inv_lines.append((0,0,inv_line))



                    inv['inv_lines'] = inv_lines

                    pprint.pprint(inv, width=4)

                    exist = self.env['dmpi.crm.invoice'].search([('name','=',name)],limit=1)
                    if exist:
                        exist.inv_lines.unlink()
                        exist.write(inv)
                    else:
                        new_dr = self.env['dmpi.crm.invoice'].create(inv) 
                        
                    execute(transfer_files,f, outbound_path_success)

            except Exception as e:
                print(e)
                pass


class DmpiCrmConfigSelection(models.Model):
    _name = 'dmpi.crm.config.selection'
    _rec_name = 'select_value'
    _order = 'select_group'

    config_id = fields.Many2one('dmpi.crm.config',"Config ID")
    sequence = fields.Integer('Sequence')
    select_group = fields.Char("Group")
    select_name = fields.Char("Select Name", track_visibility='onchange')
    select_value = fields.Char("Select Value", track_visibility='onchange')
    default = fields.Boolean("Default")



class DmpiCrmConfigContractState(models.Model):
    _name = 'dmpi.crm.config.contract.state'

    name = fields.Char("State")




class DmpiCRMFCLConfig(models.Model):
    _name = 'dmpi.crm.fcl.config'

    name = fields.Char('Description')
    pallet = fields.Char('Pallet Distribution')
    cases = fields.Integer('Total Cases')
    active = fields.Boolean('Active', default=True)
    config_id = fields.Many2one('dmpi.crm.config', string='Config ID')

