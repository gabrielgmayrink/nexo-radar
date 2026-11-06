"""Deployment identity for this independent Radar installation."""
import os
from urllib.parse import urlparse


def app_url():
    value = os.environ.get('RADAR_APP_URL') or 'https://radar-daltton-gerico.example.invalid'
    value = value.rstrip('/')
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('Invalid Radar origin')
    return value
