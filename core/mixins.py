"""Access mixins."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a view to authenticated staff members (the shop owner).

    Anonymous visitors are redirected to the login page, authenticated
    customers get a 403 instead of a redirect loop.
    """

    permission_denied_message = "Área restrita ao dono da pizzaria."

    def test_func(self) -> bool:
        return bool(self.request.user.is_staff)

    def handle_no_permission(self) -> HttpResponseRedirect:
        if self.request.user.is_authenticated:
            raise PermissionDenied(self.permission_denied_message)
        return super().handle_no_permission()
