
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string



def generate_setup_link(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    path = reverse(
        'password_reset_confirm',
        kwargs={'uidb64': uid, 'token': token}
    )

    return request.build_absolute_uri(path)


def send_welcome_email(request, user):
    setup_link = generate_setup_link(request, user)

    message = render_to_string(
        'accounts/welcome_email.txt',
        {
            'first_name': user.first_name or user.username,
            'username': user.username,
            'setup_link': setup_link
        }
    )

    send_mail(
        'Welcome to Inventory System',
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email]
    )


