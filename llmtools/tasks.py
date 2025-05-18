from celery import shared_task
from .models import Job, JobGroup


@shared_task
def run_job_group(job_group_id):
    # Logic to run the JobGroup
    job_group = JobGroup.objects.get(id=job_group_id)
    job_group.run()
    print(f"Running JobGroup with ID: {job_group_id}")


@shared_task
def clear_incomplete_jobs():
    # Logic to clear incomplete jobs
    incomplete_jobs = Job.objects.filter(completed__isnull=True)
    count = incomplete_jobs.count()
    incomplete_jobs.delete()
    print(f"Cleared {count} incomplete jobs.")


@shared_task
def run_incomplete_jobs():
    # Logic to clear incomplete jobs
    incomplete_jgs = set(
        Job.objects.filter(completed__isnull=True).values_list("group__id", flat=True)
    )
    for i in incomplete_jgs:
        run_job_group.delay(i)
