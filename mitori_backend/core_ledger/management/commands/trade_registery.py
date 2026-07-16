from django.core.management.base import BaseCommand
import redis
import time

class Command(BaseCommand):
    help = "Custom Daemon for registering trades in postgres"

    def handle(self, *args,**options):

        redis_server = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        stream_name = "executed_trades_stream"
        group_name = "django_workers"
        worker_name = "django_database_worker"
        try:
            redis_server.xgroup_create(name=stream_name,groupname=group_name,id=0,mkstream=False)
            self.stdout(self.style.SUCCESS(f"Created with consumer group {group_name}"))
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP Consumer Group name already exists" not in str(e):
                raise e
        self.stdout.write(self.style.SUCCESS(f"Starting Streaming consumer loop"))
        while True:
            try:

                executed_trades = redis_server.xreadgroup(groupname=group_name,consumername=worker_name, streams={stream_name:'>'},block=3000)
                if executed_trades:
                    for stream_key,messages in executed_trades:
                        for ticker , data in messages:
                            print(f"{ticker} with data {data}")
                time.sleep(0.1)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"error : {e}"))
                time.sleep(5)


if __name__ == "__tade_registery__":
    Command()