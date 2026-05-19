"""
AuditContextMiddleware — populates the thread-local audit context with
per-request fields (user, retail, IP, session, request_id) so signal
handlers can stamp them onto every AuditEvent without view code changes.

Must come AFTER:
  - SessionMiddleware (so request.session.session_key exists)
  - AuthenticationMiddleware (so request.user is set)
  - mastersconfig.RetailMiddleware (so request.retail is set)
"""
import uuid

from . import _context as _ctx


class AuditContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        state = _ctx._get_state()  # noqa: SLF001 — internal access by design
        state['request_id']     = uuid.uuid4()
        state['correlation_id'] = state['request_id']
        state['parent_emitted'] = False
        state['forced_parents'] = set()

        # Stash the live request so signal handlers can pull the *current*
        # user/retail at fire time. DRF Token authentication runs during
        # view dispatch (not in middleware), so request.user is still
        # AnonymousUser at this point — resolving lazily is the only way
        # to capture the authenticated user.
        state['request']    = request
        state['ip']         = _client_ip(request)
        state['user_agent'] = (request.META.get('HTTP_USER_AGENT', '') or '')[:255]
        # Pre-fill from middleware-time state as fallback (overwritten lazily).
        state['user']       = None
        state['username']   = ''
        state['session_key'] = ''
        state['retail']     = getattr(request, 'retail', None)
        state['source']     = None
        state['reason']     = None
        state['bulk_active'] = False
        state['bulk_summary'] = None

        try:
            return self.get_response(request)
        finally:
            _ctx.clear()


def _client_ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR')
    if fwd:
        return fwd.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
