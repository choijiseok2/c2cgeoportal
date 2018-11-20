# -*- coding: utf-8 -*-

# Copyright (c) 2011-2018, Camptocamp SA
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.


import urllib.parse
from c2cgeoportal_commons import models
from c2cgeoportal_commons.models import main
from c2cgeoportal_geoportal.lib.cacheversion import get_cache_version
from pyramid.view import view_config
from sqlalchemy import func


class DynamicView:

    def __init__(self, request):
        self.request = request
        self.settings = request.registry.settings
        self.interfaces_config = self.settings['interfaces_config']

    @view_config(route_name="dynamic", renderer="c2cgeoportal_geoportal:templates/dynamic.js")
    def dynamic(self):
        
        interface_name = self.request.params.get('interface')
        if interface_name not in self.settings.get('interfaces'):
            interface_name = self.settings.get('default_interface')
        interface_config = self.interfaces_config[interface_name]

        dynamic = {
            'interface': interface_name,
            'cache_version': get_cache_version(),
            'lang_urls': {
                lang: self.request.static_url('{package}_geoportal:static-ngeo/build/{lang}.json'.format(
                    package=self.request.registry.settings["package"], lang=lang
                ))
                for lang in self.request.registry.settings["available_locale_names"]
            },
            'fulltextsearch_groups': [
                group[0] for group in models.DBSession.query(
                    func.distinct(main.FullTextSearch.layer_name)
                ).filter(main.FullTextSearch.layer_name.isnot(None)).all()
            ],
        }

        constants = {name: value for name, value in interface_config.get('constants', {}).items()}
        constants.update({
            name: dynamic[value]
            for name, value in interface_config.get('dynamic_constants', {}).items()
        })
        constants.update({
            name: self.request.static_url(static_)
            for name, static_ in interface_config.get('static', {}).items()
        })

        routes = dict(currentInterfaceUrl=interface_name)
        routes.update(interface_config.get('routes', {}))
        for constant, config in routes.items():
            params = {}
            params.update(config.get('params', {}))
            for name, dyn in config.get('dynamic_params', {}):
                params[name] = dynamic[dyn]
            constants[constant] = self.request.route_url(config['name'], _query=params)

        do_redirect = False
        url = None
        if 'redirect_interface' in interface_config:
            no_redirect_query = {
                'no_redirect': 't'
            }
            if 'query' in self.request.params:
                query = urllib.parse.parse_qs(self.request.params['query'][1:])
                no_redirect_query.update(query)
            else:
                query = {}
            if 'themes' in self.request.matchdict:
                url = self.request.route_url(
                    interface_config['redirect_interface'] + 'theme',
                    themes=self.request.matchdict['themes'],
                    _query=no_redirect_query
                )
            else:
                url = self.request.route_url(
                    interface_config['redirect_interface'],
                    _query=no_redirect_query
                )

            if 'no_redirect' in query:
                constants['redirectUrl'] = ''
            else:
                if interface_config.get('do_redirect', False):
                    do_redirect = True
                else:
                    constants['redirectUrl'] = url

        return {
            'constants': constants,
            'interface_name': interface_name,
            'do_redirect': do_redirect,
            'redirect_url': url,
            'other_constants': {
                'angularLocaleScript': self.request.static_url(
                    self.request.registry.settings['package'] + '_geoportal:static-ngeo/build/'
                ) + 'angular-locale_{{locale}}.js',
            }
        }
