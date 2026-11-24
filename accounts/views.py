from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import SignupForm, ProfileEditForm
from .models import CustomUser
from documents.models import LandDocument
from duplicates.models import DuplicateCandidate


class SignupView(CreateView):
    form_class = SignupForm
    template_name = 'accounts/signup.html'
    success_url = reverse_lazy('dashboard:home')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, 'Welcome to BhoomiAI! Your workspace is ready.')
        return response


@login_required
def profile(request):
    docs = LandDocument.objects.filter(owner=request.user)
    return render(request, 'accounts/profile.html', {
        'document_count': docs.count(),
        'validated_count': docs.filter(status='done').count(),
        'duplicate_count': DuplicateCandidate.objects.filter(
            document__owner=request.user, reviewed=False
        ).count(),
    })


class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = ProfileEditForm
    template_name = 'accounts/profile_edit.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, 'Profile updated.')
        return super().form_valid(form)
