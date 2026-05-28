import jwt
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework import exceptions
from companies.models import CompanyAdminProfile, RecruiterProfile, Company

class SupabaseJWTAuthentication(authentication.BaseAuthentication):
    """
    Custom authentication backend that verifies JWT tokens issued by Supabase.
    """
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None

        token = parts[1]
        
        # If the JWT secret is placeholder (dev mode) or not set, allow dev mode bypass
        # or parse token properties insecurely for testing/local-run out-of-the-box convenience.
        jwt_secret = getattr(settings, 'SUPABASE_JWT_SECRET', '')
        
        try:
            # First, check if the token is a valid SimpleJWT token (representing a Recruiter).
            # If so, return None so Django REST framework simplejwt JWTAuthentication can process it.
            from rest_framework_simplejwt.authentication import JWTAuthentication as SimpleJWTAuthentication
            try:
                SimpleJWTAuthentication().get_validated_token(token)
                return None
            except Exception:
                pass

            if not jwt_secret or jwt_secret == 'placeholder-jwt-secret-placeholder-jwt-secret-placeholder-jwt-secret' or settings.DEBUG:
                # Local dev / test bypass: decode without verifying signature
                payload = jwt.decode(token, options={"verify_signature": False})
            else:
                # Decodes using Supabase HS256 secret key
                decoded_secret = jwt_secret.encode('utf-8') if isinstance(jwt_secret, str) else jwt_secret
                payload = jwt.decode(token, decoded_secret, algorithms=['HS256'], audience='authenticated')
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            # Return None to allow fallback to other auth classes in the chain
            return None

        # Extract claims
        supabase_uid = payload.get('sub')
        email = payload.get('email')
        
        if not supabase_uid:
            # Return None to allow fallback to other auth classes if it's not a Supabase token
            return None

        # Get or create User associated with Supabase UID
        try:
            user = User.objects.get(username=supabase_uid)
        except User.DoesNotExist:
            user = User.objects.create_user(
                username=supabase_uid,
                email=email,
                password=None # Passwordless user
            )
            # Extracted names from metadata or email
            user_metadata = payload.get('user_metadata', {})
            full_name = user_metadata.get('full_name', '')
            if full_name:
                parts = full_name.split(' ', 1)
                user.first_name = parts[0]
                if len(parts) > 1:
                    user.last_name = parts[1]
            user.save()

        # Resolve Company / Tenant context
        # If the admin profile doesn't exist, create a default company for them based on email domain
        # or return a clean company setup.
        admin_profile = CompanyAdminProfile.objects.filter(user=user).first()
        if not admin_profile:
            # Check if recruiter profile exists instead (if recruiters authenticate via standard JWT)
            recruiter_profile = RecruiterProfile.objects.filter(user=user).first()
            if recruiter_profile:
                request.company = recruiter_profile.company
            else:
                # For new Company Admins, we create a default Company
                domain = email.split('@')[1] if email and '@' in email else 'default.com'
                company_name = domain.split('.')[0].capitalize()
                
                # Check if company with this domain exists or create new
                company, _ = Company.objects.get_or_create(
                    domain=domain,
                    defaults={
                        'name': f"{company_name} Corp",
                        'industry': 'Technology',
                        'size': '10-50'
                    }
                )
                admin_profile = CompanyAdminProfile.objects.create(
                    user=user,
                    company=company
                )
                request.company = company
        else:
            request.company = admin_profile.company

        return (user, token)

from rest_framework_simplejwt.authentication import JWTAuthentication

class RecruiterJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication class that resolves the multi-tenant Company context
    for recruiters authenticated via standard SimpleJWT.
    """
    def authenticate(self, request):
        auth_res = super().authenticate(request)
        if auth_res is not None:
            user, token = auth_res
            # Resolve Company context
            recruiter_profile = RecruiterProfile.objects.filter(user=user).first()
            if recruiter_profile:
                request.company = recruiter_profile.company
            else:
                admin_profile = CompanyAdminProfile.objects.filter(user=user).first()
                if admin_profile:
                    request.company = admin_profile.company
            return (user, token)
        return None
