/* Copyright 2016 LasLabs Inc.
 * License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl). */

odoo.define_section('web_bravo_backend', ['web_bravo_backend'], function(test) {
    "use strict";
    
    // It provides a base changer compatible interface for testing
    self.initInterface = function(AppChanger) {
        
        var $el = $('<div class="changer changer--left">');
        $el.append(
            $('<header role="banner">')
                .append(
                    $('<button class="changer-toggle"><span class="changer-hamburger-icon">')
                )
                .append(
                    $('<nav class="changer-nav"><ul class="changer-menu"><li class="changer-menu-item">')
                )
                .append(
                    $('<div class="panel-title" id="appChangerAppPanelHead">')
                )
        ).append($('<main role="main">'));
        
        self.$clickZone = $('<a class="oe_menu_leaf">');
        
        self.$secondaryMenu = $('<div><div class="o_sub_menu_content">');
        
        self.$dropdown = $('<div class="dropdown-scrollable">');
    
        $el.append(self.$clickZone)
            .append(self.$secondaryMenu)
            .append(self.$dropdown);
        
        var $document = $("#qunit-fixture");
        $document.append($el);
        
        self.changer = new AppChanger.AppChanger();
        
        return $document;
        
    };
    
    self.linkGrid = function() {
        for(var i=0; i < 3; i++){
            self.changer.$el.append(
                $('<div class="row">').append(
                    $('<a class="col-md-6" id="a_' + i + '"><span class="app-changer-icon-app /></a>' +
                      '<a class="col-md-6" id="b_' + i + '"><span class="app-changer-icon-app /></a>'
                      )
                )
            );
            self.changer.$appLinks = $('a.col-md-6');
        }
    };
    
    test('It should set initialized after success init',
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            assert.ok(self.changer.initialized);
         }
    );
    
    test('It should close changer after click on clickZone',
         {asserts: 1},
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            self.$clickZone.click();
            var d = $.Deferred();
            setTimeout(function() {
                assert.ok(self.changer.$el.hasClass('changer-close'));
                d.resolve();
            }, 100);
            return d;
         }
    );
    
    test('It should collapse open secondary menus during handleClickZones',
         {asserts: 1},
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            self.$clickZone.click();
            var d = $.Deferred();
            setTimeout(function() {
                assert.equal(self.$secondaryMenu.attr('aria-expanded'), 'false');
                d.resolve();
            }, 100);
            return d;
         }
    );
    
    test('It should update max-height on scrollable dropdowns',
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            self.changer.handleWindowResize();
            var height = $(window).height() * self.changer.dropdownHeightFactor;
            assert.equal(
                self.$dropdown.css('max-height'),
                height + 'px'
            );
         }
    );
    
    test('It should return keybuffer + new key',
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            self.changer.keyBuffer = 'TES';
            var res = self.changer.handleKeyBuffer(84);
            assert.equal(res, 'TEST');
         }
    );
    
    test('It should clear keybuffer after timeout',
         {asserts: 1},
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            self.changer.keyBuffer = 'TES';
            self.changer.keyBufferTime = 10;
            self.changer.handleKeyBuffer(84);
            var d = $.Deferred();
            setTimeout(function() {
                assert.equal(self.changer.keyBuffer, "");
                d.resolve();
            }, 100);
            return d;
         }
    );
    
    test('It should trigger core bus event for changer close',
         ['web.core'], {asserts: 1},
         function(assert, AppChanger, core) {
            self.initInterface(AppChanger);
            self.changer.onChangerOpen();
            var d = $.Deferred();
            core.bus.on('changer.closed', this, function() {
                assert.ok(true);
                d.resolve();
            });
            self.changer.$el.trigger({type: 'changer.closed'});
            return d;
         }
    );
    
    test('It should set isOpen to false when closing',
         {asserts: 1},
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            self.changer.onChangerOpen();
            var d = $.Deferred();
            setTimeout(function() {
                assert.equal(self.changer.isOpen, false);
                d.resolve();
            });
            self.changer.$el.trigger({type: 'changer.closed'});
            return d;
         }
    );
    
    test('It should set isOpen to true when opening',
         {asserts: 1},
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            var d = $.Deferred();
            self.changer.$el.trigger({type: 'changer.opened'});
            setTimeout(function() {
                assert.ok(self.changer.isOpen);
                d.resolve();
            });
            return d;
         }
    );
    
    test('It should trigger core bus event for changer open',
         ['web.core'], {asserts: 1},
         function(assert, AppChanger, core) {
            self.initInterface(AppChanger);
            self.changer.onChangerOpen();
            var d = $.Deferred();
            core.bus.on('changer.opened', this, function() {
                assert.ok(true);
                d.resolve();
            });
            self.changer.$el.trigger({type: 'changer.opened'});
            return d;
         }
    );
    
    test('It should choose link to right',
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            self.linkGrid();
            var $appLink = $('#a_1'),
                $expect = $('#a_2'),
                $res = self.changer.findAdjacentAppLink(
                    $appLink, self.changer.RIGHT
                );
            assert.equal($res[0].id, $expect[0].id);
         }
    );
    
    test('It should choose link to left',
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            self.linkGrid();
            var $appLink = $('#a_2'),
                $expect = $('#a_1'),
                $res = self.changer.findAdjacentAppLink(
                    $appLink, self.changer.LEFT
                );
            assert.equal($res[0].id, $expect[0].id);
         }
    );
    
    test('It should choose link above',
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            self.linkGrid();
            var $appLink = $('#a_1'),
                $expect = $('#a_0'),
                $res = self.changer.findAdjacentAppLink(
                    $appLink, self.changer.UP
                );
            assert.equal($res[0].id, $expect[0].id);
         }
    );
    
    test('It should choose link below',
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            self.linkGrid();
            var $appLink = $('#a_1'),
                $expect = $('#a_2'),
                $res = self.changer.findAdjacentAppLink(
                    $appLink, self.changer.DOWN
                );
            assert.equal($res[0].id, $expect[0].id);
         }
    );
    
    test('It should choose first link if next on last',
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            self.linkGrid();
            var $appLink = $('#b_2'),
                $expect = $('#a_0'),
                $res = self.changer.findAdjacentAppLink(
                    $appLink, self.changer.RIGHT
                );
            assert.equal($res[0].id, $expect[0].id);
         }
    );
    
    test('It should choose bottom link if up on top',
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            self.linkGrid();
            var $appLink = $('#a_0'),
                $expect = $('#a_2'),
                $res = self.changer.findAdjacentAppLink(
                    $appLink, self.changer.UP
                );
            assert.equal($res[0].id, $expect[0].id);
         }
    );
    
    test('It should choose top link if down on bottom',
         function(assert, AppChanger) {
            self.initInterface(AppChanger);
            self.linkGrid();
            var $appLink = $('#a_2'),
                $expect = $('#a_0'),
                $res = self.changer.findAdjacentAppLink(
                    $appLink, self.changer.DOWN
                );
            assert.equal($res[0].id, $expect[0].id);
         }
    );
    
});
