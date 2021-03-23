odoo.define('dmpi_crm_ar.tree_view_button', function (require){
"use strict";

    var core = require('web.core');
    var ListView = require('web.ListView');
    var ListController = require('web.ListController');
    var QWeb = core.qweb;

    ListController.include({       

        renderButtons: function($node) {
                console.log("tree_view_action_loaded_render_button");
                var self = this;
                this._super($node);
                    this.$buttons.find('.o_list_analytics_ar_button').click(this.proxy('tree_view_action'));
        },

        tree_view_action: function () {           
            console.log("tree_view_action_loaded_tree_view_action");
            var self = this;

            this._rpc({
                model: "dmpi.crm.analytics.ar.date",
                method: 'get_date_id',
                //The event can be called by a view that can have another context than the default one.
                args: [{}],
            }).then(function (date_id) {
                self.do_action({
                    type:'ir.actions.act_window',
                    res_id: date_id,
                    res_model: "dmpi.crm.analytics.ar.date",
                    views: [[false,'form']],
                    target: 'new',
                    view_type : 'form',
                    view_mode : 'form',
                    flags: {'form': {'action_buttons': true, 'options': {'mode': 'edit'}}}
                });
            });




            // var self = this;
            // console.log(this.modelName);
            // this.do_action({
            //     type: 'ir.actions.act_window',
            //     res_model: this.modelName,
            //     views: [[this.formViewId || false, 'form']],
            //     target: 'current',
            //     context: context,
            // });

        return { 'type': 'ir.actions.client','tag': 'reload', } } 

    });

    console.log("tree_view_action_loaded_render_button");
});





