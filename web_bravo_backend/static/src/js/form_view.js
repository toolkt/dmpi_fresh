odoo.define('web_bravo_backend.FormView', function (require) {
"use strict";

var config = require('web.config');
var FormRenderer = require('web.FormRenderer');
var FormView = require('web.FormView');
var MobileFormRenderer = require('web_bravo_backend.MobileFormRenderer');

FormView.include({

    getRenderer: function () {
        this.config.Renderer = config.device.isMobile ? MobileFormRenderer : FormRenderer;
        return this._super.apply(this, arguments);
    }
});

});

odoo.define('web_bravo_backend.MobileFormRenderer', function (require) {
"use strict";

var core = require('web.core');
var FormRenderer = require('web.FormRenderer');

var qweb = core.qweb;

var MobileFormRenderer = FormRenderer.extend({

    _renderHeaderButtons: function (node) {
        var $headerButtons = $();
        var buttonChildren = _.filter(node.children, {tag: 'button'});
        var buttons = _.map(buttonChildren, this._renderHeaderButton.bind(this));

        if (buttons.length) {
            $headerButtons = $(qweb.render('StatusbarButtons'));
            var $dropdownMenu = $headerButtons.find('.dropdown-menu');
            _.each(buttons, function ($button) {
                $dropdownMenu.append($('<li>').append($button));
            });
        }

        return $headerButtons;
    },
});

return MobileFormRenderer;

});

