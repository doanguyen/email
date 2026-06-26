import os

from config.django.base import *  # noqa

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Required to allow OAuth over plain HTTP in local development
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
