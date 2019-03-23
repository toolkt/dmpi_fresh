# -*- coding: utf-8 -*-

from odoo import _
from odoo import models, api, fields
from odoo.exceptions import ValidationError, AccessError, UserError
from odoo import http
from odoo.http import content_disposition, dispatch_rpc, request, serialize_exception as _serialize_exception, Response

import base64
from tempfile import TemporaryFile
from datetime import datetime
import tempfile
import re
import json
