from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.activity_log.models import ActivityLog

from .models import User
from .permissions import IsSuperAdmin
from .serializers import LoginSerializer, UserCreateSerializer, UserSerializer


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class LoginView(APIView):
    """POST /auth/login/ — returns JWT tokens + user info. No auth required."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        tokens = get_tokens_for_user(user)
        ActivityLog.objects.create(
            user=user,
            action='Logged in',
            method='POST',
            path='/api/auth/login/',
            status_code=200,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000],
            metadata={},
        )
        return Response(
            {
                'tokens': tokens,
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """GET /auth/me/ — returns the current authenticated user's profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD for User accounts.
    - create / update / partial_update / destroy: super_admin only
    - list / retrieve: any authenticated user (non-admins see only themselves)
    """

    queryset = User.objects.all().order_by('id')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsSuperAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'super_admin':
            return User.objects.all().order_by('id')
        # Non-admins can only see themselves
        return User.objects.filter(pk=user.pk)
