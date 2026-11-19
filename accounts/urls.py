"""Account URLs."""

from django.urls import path

from accounts.views import ProfileView, RegisterView, SignInView, SignOutView

app_name = "accounts"

urlpatterns = [
    path("cadastro/", RegisterView.as_view(), name="register"),
    path("entrar/", SignInView.as_view(), name="login"),
    path("sair/", SignOutView.as_view(), name="logout"),
    path("perfil/", ProfileView.as_view(), name="profile"),
]
