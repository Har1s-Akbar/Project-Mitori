from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Custom Daemon for registering trades in postgres"

    def handle(self, *args,**options):
        print('This is a hello from the daemon')