from ipaddress import ip_address


class ProxyFix(object):
    """This is a slightly modified version of werkzeug's ProxyFix.

    Instead of using a fixed number of proxies it uses a list of trusted IP
    addresses.

    This middleware can be applied to add HTTP proxy support to an
    application that was not designed with HTTP proxies in mind.  It
    sets `REMOTE_ADDR`, `HTTP_HOST` from `X-Forwarded` headers.

    The original values of `REMOTE_ADDR` and `HTTP_HOST` are stored in
    the WSGI environment as `werkzeug.proxy_fix.orig_remote_addr` and
    `werkzeug.proxy_fix.orig_http_host`.

    :param app: the WSGI application
    :param num_proxies: the number of proxy servers in front of the app.
    """

    def __init__(self, app):
        self.wsgi = app.wsgi_app
        proxies = app.config.get('PROXYFIX_TRUSTED', ['127.0.0.1'])
        self.trusted = frozenset(ip_address(p.strip()) for p in proxies)

    def get_remote_addr(self, forwarded_for, remote):
        """Selects the new remote addr from the given list of ips in
        X-Forwarded-For. It picks the "rightmost" untrusted IP address.
        """
        for ip_str in reversed([remote] + forwarded_for):
            ip_str = ip_str.strip()
            try:
                if not ip_address(ip_str) in self.trusted:
                    return ip_str
            except ValueError:
                return ip_str
        return remote

    def update_environ(self, environ):
        env = environ.get
        forwarded_proto = env('HTTP_X_FORWARDED_PROTO', '')
        forwarded_for = env('HTTP_X_FORWARDED_FOR', '').split(',')
        forwarded_host = env('HTTP_X_FORWARDED_HOST', '')
        environ.update({
            'werkzeug.proxy_fix.orig_wsgi_url_scheme': env('wsgi.url_scheme'),
            'werkzeug.proxy_fix.orig_remote_addr':     env('REMOTE_ADDR'),
            'werkzeug.proxy_fix.orig_http_host':       env('HTTP_HOST')
        })

        if ip_address(env('REMOTE_ADDR')) in self.trusted:
            if forwarded_host:
                environ['HTTP_HOST'] = forwarded_host
            if forwarded_proto:
                https = 'https' in forwarded_proto.lower()
                environ['wsgi.url_scheme'] = 'https' if https else 'http'

        remote_addr = self.get_remote_addr(forwarded_for, env('REMOTE_ADDR'))
        if remote_addr is not None:
            environ['REMOTE_ADDR'] = remote_addr

    def __call__(self, environ, start_response):
        self.update_environ(environ)
        return self.wsgi(environ, start_response)
