# rules.py
import rules


@rules.predicate
def is_job_owner(user, obj):
    return obj.owner == user


rules.add_rule("can_cancel_jobgroup", is_job_owner)
rules.add_perm("llmtools.cancel_jobgroup", is_job_owner)
