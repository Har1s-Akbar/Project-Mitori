from django.core.management.base import BaseCommand
import redis

class Command(BaseCommand):
    help = "Custom Daemon for registering trades in postgres"

    def handle(self, *args,**options):

        redis_server = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        stream_name = "executed_trades_stream"
        group_name = "django_workers"

        try:
            redis_server.xgroup_create(name=stream_name,groupname=group_name,id=0,mkstream=False)
            redis_server.std.out(self.style.SUCCESS(f"Created with consumer group {group_name}"))
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP Consumer Group name already exists" not in str(e):
                raise e
        self.stf.out(self.style.SUCCESS(f"Starting Streaming consumer loop"))