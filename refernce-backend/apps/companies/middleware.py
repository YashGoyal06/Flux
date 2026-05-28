from django.utils.deprecation import MiddlewareMixin
from companies.models import CompanyAdminProfile, RecruiterProfile

class TenantMiddleware(MiddlewareMixin):
    """
    Middleware that attaches the current tenant (Company) to the request
    object based on the authenticated user.
    """
    def process_request(self, request):
        request.company = None
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Check if user is a Company Admin
            admin_profile = CompanyAdminProfile.objects.filter(user=request.user).first()
            if admin_profile:
                request.company = admin_profile.company
                return
            
            # Check if user is a Recruiter
            recruiter_profile = RecruiterProfile.objects.filter(user=request.user).first()
            if recruiter_profile:
                request.company = recruiter_profile.company
                return
