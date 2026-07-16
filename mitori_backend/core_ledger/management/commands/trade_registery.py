from django.core.management.base import BaseCommand

class register(BaseCommand):
    help = "Custom Daemon for registering trades in postgres"

    def hello ():
        return "This is a hello from the daemon"