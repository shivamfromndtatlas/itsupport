from .models import ActivityLog


class ActivityLogMiddleware:
    EXCLUDED_PREFIXES = (
        '/admin/',
        '/media/',
        '/static/',
    )
    EXCLUDED_PATHS = (
        '/api/auth/me/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._log_request(request, response)
        return response

    def _log_request(self, request, response):
        path = request.path or ''
        if not request.user.is_authenticated:
            return
        if any(path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES):
            return
        if path in self.EXCLUDED_PATHS:
            return
        if path.startswith('/api/activity-log/'):
            return

        action = self._build_action(request, response)
        if not action:
            return

        ActivityLog.objects.create(
            user=request.user,
            action=action,
            method=request.method,
            path=path,
            status_code=getattr(response, 'status_code', None),
            ip_address=self._get_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000],
            metadata={
                'query_string': request.META.get('QUERY_STRING', ''),
            },
        )

    def _build_action(self, request, response):
        path = request.path
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return f'{request.method} {path}'
        if getattr(response, 'status_code', 200) >= 400:
            return f'{request.method} {path} failed'
        return f'Viewed {path}'

    def _get_ip(self, request):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
