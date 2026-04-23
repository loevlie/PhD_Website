"""Public authentication surface: signup, login, logout.

Signup is intentionally minimal:
  * Any visitor can create an account with username + email + password.
  * New accounts are plain users — `is_staff=False`, `is_superuser=False`.
  * A freshly signed-up user has zero access to editor endpoints until
    an admin grants it by adding them to `Post.collaborators`.

Why a public signup at all on a personal portfolio: it lets the site
owner point a would-be collaborator at a signup link ("make an account,
send me the username") and then promote them from the admin — faster
than creating users manually, and gives the collaborator their own
password from the start (no emailed temp-password dance).

Login + logout reuse Django's built-in `LoginView` / `LogoutView` via
`django.contrib.auth.urls`, wired in portfolio/urls.py.
"""
from __future__ import annotations

from django import forms
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render


class _PublicSignupForm(UserCreationForm):
    """UserCreationForm + required email. We store the email so an
    admin can contact the user (e.g., to tell them a post is ready to
    edit) without digging through logs."""

    email = forms.EmailField(
        required=True,
        help_text='Required. An admin may contact you at this address.',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'password1', 'password2')


def signup(request):
    """GET/POST /accounts/signup/ — create a new non-staff user.

    On success: auto-login and redirect to /accounts/profile/ (a tiny
    landing page with the user's posts + status). No email verification
    — this is a low-volume personal site, not a mass-signup product."""
    if request.user.is_authenticated:
        return redirect('accounts_profile')
    if request.method == 'POST':
        form = _PublicSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Defensive: ensure signup never escalates privileges.
            if user.is_staff or user.is_superuser:
                user.is_staff = False
                user.is_superuser = False
                user.save(update_fields=['is_staff', 'is_superuser'])
            login(request, user)
            next_url = request.GET.get('next') or request.POST.get('next') or 'accounts_profile'
            if next_url == 'accounts_profile':
                return redirect('accounts_profile')
            return HttpResponseRedirect(next_url)
    else:
        form = _PublicSignupForm()
    return render(request, 'portfolio/accounts/signup.html', {
        'form': form,
        'next': request.GET.get('next', ''),
    })


_AVATAR_MAX_BYTES = 2 * 1024 * 1024  # 2 MB


class _UserProfileForm(forms.ModelForm):
    """Trim the auto-generated ModelForm down to the fields we actually
    surface on the self-serve edit page. Validation relies on the
    model's own field constraints, plus a size ceiling on the avatar
    upload so a 20 MB camera-roll dump doesn't end up in object
    storage."""
    class Meta:
        from portfolio.models import UserProfile
        model = UserProfile
        fields = ('display_name', 'bio', 'avatar', 'homepage_url')
        widgets = {
            'bio': forms.TextInput(attrs={'maxlength': 280, 'placeholder': 'e.g. PhD student · writes about tabular foundation models'}),
            'display_name': forms.TextInput(attrs={'placeholder': 'e.g. Alice Young'}),
            'homepage_url': forms.URLInput(attrs={'placeholder': 'https://alice.example'}),
        }
        help_texts = {
            'avatar': 'Square image works best (cropped to a circle). 2 MB max. JPEG / PNG / WebP.',
        }

    def clean_avatar(self):
        f = self.cleaned_data.get('avatar')
        if f and hasattr(f, 'size') and f.size > _AVATAR_MAX_BYTES:
            raise forms.ValidationError(
                f'Avatar is {f.size // 1024} KB — please keep it under 2 MB.'
            )
        return f


def profile(request):
    """GET/POST /accounts/profile/ — the user's home after login.

    GET renders the landing + a self-serve edit form for the user's
    UserProfile (display name, avatar, one-line bio, homepage).
    POST handles the form (multipart for the avatar upload).
    Staff users see a pointer to /site/studio/; collaborators see a
    list of posts they've been granted edit access to. Fresh signup
    with no assignments sees a "waiting for admin" message."""
    if not request.user.is_authenticated:
        return redirect(f'/accounts/login/?next=/accounts/profile/')
    from portfolio.models import UserProfile
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = _UserProfileForm(request.POST, request.FILES, instance=profile_obj)
        if form.is_valid():
            form.save()
            return redirect(f"{request.path}?saved=1")
    else:
        form = _UserProfileForm(instance=profile_obj)

    editable = []
    if not request.user.is_staff:
        editable = list(request.user.edit_posts.all().order_by('-modified_at'))
    return render(request, 'portfolio/accounts/profile.html', {
        'editable': editable,
        'profile': profile_obj,
        'profile_form': form,
        'just_saved': request.GET.get('saved') == '1',
    })
