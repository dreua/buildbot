# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from twisted.internet import defer
from twisted.internet import reactor

from buildbot import config
from buildbot.process.buildstep import FAILURE
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import BuildStep

# use the 'requests' lib: https://requests.readthedocs.io/en/master/
try:
    import txrequests
    import requests
except ImportError:
    txrequests = None


# This step uses a global Session object, which encapsulates a thread pool as
# well as state such as cookies and authentication.  This state may pose
# problems for users, where one step may get a cookie that is subsequently used
# by another step in a different build.

_session = None


def getSession():
    global _session
    if _session is None:
        _session = txrequests.Session()
        reactor.addSystemEventTrigger("before", "shutdown", closeSession)
    return _session


def setSession(session):
    global _session
    _session = session


def closeSession():
    global _session
    if _session is not None:
        _session.close()
        _session = None


class HTTPStep(BuildStep):

    name = 'HTTPStep'
    description = 'Requesting'
    descriptionDone = 'Requested'
    requestsParams = ["params", "data", "json", "headers",
                      "cookies", "files", "auth",
                      "timeout", "allow_redirects", "proxies",
                      "hooks", "stream", "verify", "cert"]
    renderables = requestsParams + ["method", "url"]
    session = None

    def __init__(self, url, method, **kwargs):
        if txrequests is None:
            config.error(
                "Need to install txrequest to use this step:\n\n pip install txrequests")

        if method not in ('POST', 'GET', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'):
            config.error("Wrong method given: '{}' is not known".format(method))

        self.method = method
        self.url = url

        for param in self.requestsParams:
            setattr(self, param, kwargs.pop(param, None))

        super().__init__(**kwargs)
        if self.__class__.__name__ not in ['POST', 'PUT', 'GET', 'DELETE', 'HEAD', 'OPTIONS']:
            self.warn_deprecated_if_oldstyle_subclass('HTTPStep')

    @defer.inlineCallbacks
    def run(self):
        # create a new session if it doesn't exist
        self.session = getSession()

        requestkwargs = {
            'method': self.method,
            'url': self.url
        }

        for param in self.requestsParams:
            value = getattr(self, param, None)
            if value is not None:
                requestkwargs[param] = value

        log = yield self.addLog('log')

        # known methods already tested in __init__

        yield log.addHeader('Performing {} request to {}\n'.format(self.method, self.url))
        if self.params:
            yield log.addHeader('Parameters:\n')
            params = requestkwargs.get("params", {})
            if params:
                params = sorted(params.items(), key=lambda x: x[0])
                requestkwargs['params'] = params
            for k, v in params:
                yield log.addHeader('\t{}: {}\n'.format(k, v))
        data = requestkwargs.get("data", None)
        if data:
            yield log.addHeader('Data:\n')
            if isinstance(data, dict):
                for k, v in data.items():
                    yield log.addHeader('\t{}: {}\n'.format(k, v))
            else:
                yield log.addHeader('\t{}\n'.format(data))

        try:
            r = yield self.session.request(**requestkwargs)
        except requests.exceptions.ConnectionError as e:
            yield log.addStderr('An exception occurred while performing the request: {}'.format(e))
            return FAILURE

        if r.history:
            yield log.addStdout('\nRedirected %d times:\n\n' % len(r.history))
            for rr in r.history:
                yield self.log_response(log, rr)
                yield log.addStdout('=' * 60 + '\n')

        yield self.log_response(log, r)

        yield log.finish()

        self.descriptionDone = ["Status code: %d" % r.status_code]
        if (r.status_code < 400):
            return SUCCESS
        else:
            return FAILURE

    @defer.inlineCallbacks
    def log_response(self, log, response):

        yield log.addHeader('Request Header:\n')
        for k, v in response.request.headers.items():
            yield log.addHeader('\t{}: {}\n'.format(k, v))

        yield log.addStdout('URL: {}\n'.format(response.url))

        if response.status_code == requests.codes.ok:
            yield log.addStdout('Status: {}\n'.format(response.status_code))
        else:
            yield log.addStderr('Status: {}\n'.format(response.status_code))

        yield log.addHeader('Response Header:\n')
        for k, v in response.headers.items():
            yield log.addHeader('\t{}: {}\n'.format(k, v))

        yield log.addStdout(' ------ Content ------\n{}'.format(response.text))
        content_log = yield self.addLog('content')
        yield content_log.addStdout(response.text)


class POST(HTTPStep):

    def __init__(self, url, **kwargs):
        super().__init__(url, method='POST', **kwargs)
        self.warn_deprecated_if_oldstyle_subclass('POST')


class GET(HTTPStep):

    def __init__(self, url, **kwargs):
        super().__init__(url, method='GET', **kwargs)
        self.warn_deprecated_if_oldstyle_subclass('GET')


class PUT(HTTPStep):

    def __init__(self, url, **kwargs):
        super().__init__(url, method='PUT', **kwargs)
        self.warn_deprecated_if_oldstyle_subclass('PUT')


class DELETE(HTTPStep):

    def __init__(self, url, **kwargs):
        super().__init__(url, method='DELETE', **kwargs)
        self.warn_deprecated_if_oldstyle_subclass('DELETE')


class HEAD(HTTPStep):

    def __init__(self, url, **kwargs):
        super().__init__(url, method='HEAD', **kwargs)
        self.warn_deprecated_if_oldstyle_subclass('HEAD')


class OPTIONS(HTTPStep):

    def __init__(self, url, **kwargs):
        super().__init__(url, method='OPTIONS', **kwargs)
        self.warn_deprecated_if_oldstyle_subclass('OPTIONS')
