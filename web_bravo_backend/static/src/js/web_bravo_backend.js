/* Copyright 2016 LasLabs Inc.
 * License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl). */
odoo.define('web_bravo_backend', function(require) {
	'use strict';
	var Menu = require('web.Menu');
	var Class = require('web.Class');
	var SearchView = require('web.SearchView');
	var core = require('web.core');
	var config = require('web.config');
	var FieldOne2Many = core.form_widget_registry.get('one2many');
	var ViewManager = require('web.ViewManager');
	Menu.include({

		reflow: function() {
			this._super('all_outside');
		},

		open_menu: function(id, allowOpen) {
			this._super(id);
			if(allowOpen) {
				return;
			};
			var $clicked_menu = this.$secondary_menus.find('a[data-menu=' + id + ']');
			$clicked_menu.parents('.oe_secondary_submenu').css('display', '');
		}
	});
	SearchView.include({

		toggle_visibility: function(is_visible) {
			$('div.oe_searchview_input').last().one('focus', $.proxy(this.preventMobileFocus, this));
			return this._super(is_visible);
		},

		preventMobileFocus: function(event) {
			if(this.isMobile()) {
				event.preventDefault();
			}
		},

		isMobile: function() {
			try {
				document.createEvent('TouchEvent');
				return true;
			} catch(ex) {
				return false;
			}
		}
	});
	var AppChanger = Class.extend({
		LEFT: 'left',
		RIGHT: 'right',
		UP: 'up',
		DOWN: 'down',
		isOpen: false,
		keyBuffer: '',
		keyBufferTime: 500,
		keyBufferTimeoutEvent: false,
		dropdownHeightFactor: 0.90,
		initialized: false,
		init: function() {
			this.directionCodes = {
				'left': this.LEFT,
				'right': this.RIGHT,
				'up': this.UP,
				'pageup': this.UP,
				'down': this.DOWN,
				'pagedown': this.DOWN,
				'+': this.RIGHT,
				'-': this.LEFT
			};
			this.initChanger();
			var $clickZones = $('.odoo_webclient_container, ' + 'a.oe_menu_leaf, ' + 'a.oe_menu_toggler');
			$clickZones.click($.proxy(this.handleClickZones, this));
			core.bus.on('resize', this, this.handleWindowResize);
			core.bus.on('keydown', this, this.handleNavKeys);
		},

		initChanger: function() {
			this.$el = $('.changer');
			this.$el.changer();
			this.$el.one('changer.opened', $.proxy(this.onChangerOpen, this));
			this.$el.on('changer.opened', function setIScrollProbes() {
				var onIScroll = function() {
					var transform = this.iScroll.y ? this.iScroll.y * -1 : 0;
					$(this).find('#appChangerAppPanelHead').css('transform', 'matrix(1, 0, 0, 1, 0, ' + transform + ')');
				};
				this.iScroll.options.probeType = 2;
				this.iScroll.on('scroll', $.proxy(onIScroll, this));
			});
			this.initialized = true;
		},

		handleClickZones: function() {
			this.$el.changer('close');
			$('.o_sub_menu_content').parent().collapse('hide');
		},

		handleWindowResize: function() {
			$('.dropdown-scrollable').css('max-height', $(window).height() * this.dropdownHeightFactor);
		},

		handleNavKeys: function(e) {
			if(!this.isOpen) {
				return;
			}
			var directionCode = $.hotkeys.specialKeys[e.keyCode.toString()];
			if(Object.keys(this.directionCodes).indexOf(directionCode) !== -1) {
				var $link = this.findAdjacentAppLink(this.$el.find('a:first, a:focus').last(), this.directionCodes[directionCode]);
				this.selectAppLink($link);
			} else if($.hotkeys.specialKeys[e.keyCode.toString()] === 'esc') {
				this.handleClickZones();
			} else {
				var buffer = this.handleKeyBuffer(e.keyCode);
				this.selectAppLink(this.searchAppLinks(buffer));
			}
		},

		handleKeyBuffer: function(keyCode) {
			this.keyBuffer += String.fromCharCode(keyCode);
			if(this.keyBufferTimeoutEvent) {
				clearTimeout(this.keyBufferTimeoutEvent);
			}
			this.keyBufferTimeoutEvent = setTimeout($.proxy(this.clearKeyBuffer, this), this.keyBufferTime);
			return this.keyBuffer;
		},
		clearKeyBuffer: function() {
			this.keyBuffer = '';
		},

		onChangerClose: function() {
			core.bus.trigger('changer.closed');
			this.$el.one('changer.opened', $.proxy(this.onChangerOpen, this));
			this.isOpen = false;

			this.$el.css("overflow", "");
		},

		onChangerOpen: function() {
			this.$appLinks = $('.app-changer-icon-app').parent();
			this.selectAppLink($(this.$appLinks[0]));
			this.$el.one('changer.closed', $.proxy(this.onChangerClose, this));
			core.bus.trigger('changer.opened');
			this.isOpen = true;
		},

		selectAppLink: function($appLink) {
			if($appLink) {
				$appLink.focus();
			}
		},

		searchAppLinks: function(query) {
			return this.$appLinks.filter(function() {
				return $(this).data('menuName').toUpperCase().startsWith(query);
			}).first();
		},

		findAdjacentAppLink: function($appLink, direction) {
			var obj = [],
				$objs = this.$appLinks;
			switch(direction) {
				case this.LEFT:
					obj = $objs[$objs.index($appLink) - 1];
					if(!obj) {
						obj = $objs[$objs.length - 1];
					}
					break;
				case this.RIGHT:
					obj = $objs[$objs.index($appLink) + 1];
					if(!obj) {
						obj = $objs[0];
					}
					break;
				case this.UP:
					$objs = this.getRowObjs($appLink, this.$appLinks);
					obj = $objs[$objs.index($appLink) - 1];
					if(!obj) {
						obj = $objs[$objs.length - 1];
					}
					break;
				case this.DOWN:
					$objs = this.getRowObjs($appLink, this.$appLinks);
					obj = $objs[$objs.index($appLink) + 1];
					if(!obj) {
						obj = $objs[0];
					}
					break;
			}
			if(obj.length) {
				event.preventDefault();
			}
			return $(obj);
		},

		getRowObjs: function($obj, $grid) {

			function filterWithin(left, right) {
				return function() {
					var $this = $(this),
						thisMiddle = $this.offset().left + $this.width() / 2;
					return thisMiddle >= left && thisMiddle <= right;
				};
			}
			var left = $obj.offset().left,
				right = left + $obj.outerWidth();
			return $grid.filter(filterWithin(left, right));
		}
	});

	core.bus.on('web_client_ready', null, function() {
		new AppChanger();
	});

	ViewManager.include({
		get_default_view: function() {
			var default_view = this._super()
			if(config.device.size_class <= config.device.SIZES.XS && default_view.type !== 'kanban' && this.views.kanban) {
				default_view.type = 'kanban';
			};
			return default_view;
		},
	});
	return {
		'AppChanger': AppChanger,
		'SearchView': SearchView,
		'Menu': Menu,
		'ViewManager': ViewManager,
	};
});