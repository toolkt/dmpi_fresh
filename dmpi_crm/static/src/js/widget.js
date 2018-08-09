var core = require('web.core');
var Widget= require('web.Widget');
var widgetRegistry = require('web.widget_registry');
var FieldManagerMixin = require('web.FieldManagerMixin');

var JSheet = Widget.extend(FieldManagerMixin, {
    init: function (parent, model, state) {
        this._super(parent);
        FieldManagerMixin.init.call(this);
        // init code here
    },
    start: function () {
         //codes        
    },
    events: {
        "click button.ct_button_filter": "open_search_dialog",
    },
    open_search_dialog: function () {
        //codes...
    },
    display_filter: function () {
        //codes...
    },
});

widgetRegistry.add(
    'jsheet', JSheet
);