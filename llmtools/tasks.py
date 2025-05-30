from celery import shared_task

from .models import Job


@shared_task
def run_job(pk):
    obj = Job.objects.get(id=pk)
    if obj.ready_to_run():
        obj.run()


@shared_task
def clear_incomplete_jobs():
    # Logic to clear incomplete jobs
    incomplete_jobs = Job.objects.filter(completed__isnull=True)
    count = incomplete_jobs.count()
    incomplete_jobs.delete()
    print(f"Cleared {count} incomplete jobs.")


@shared_task
def run_incomplete_jobs():
    # TODO ADD SOME RETRY LOGIC HERE TO PREVENT RUNNING FOREVER

    # Logic to clear incomplete jobs
    incomplete_jgs = set(
        Job.objects.filter(completed__isnull=True).values_list("group__id", flat=True)
    )
    for i in incomplete_jgs.order_by("-created"):
        for j in i.jobs.all():
            run_job.delay(j.pk)
