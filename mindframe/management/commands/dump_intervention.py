import os
import json
from django.core.serializers import serialize
from django.db import transaction
from django.core.management.base import BaseCommand

from mindframe.models import Intervention, Step, Transition, Judgement, Example, LLM, StepJudgement


class Command(BaseCommand):
    help = "Export a single intervention as fixtures and revert changes"

    def add_arguments(self, parser):
        parser.add_argument(
            "intervention_slug", type=str, help="Slug of the intervention to export"
        )
        parser.add_argument("output_file", type=str, help="Path to the output file for the fixture")

    def handle(self, *args, **kwargs):
        intervention_slug = kwargs["intervention_slug"]
        output_file = kwargs["output_file"]

        try:
            with transaction.atomic():
                # Identify the target intervention
                intervention = Intervention.objects.get(slug=intervention_slug)

                # Filter related objects for the intervention
                steps = Step.objects.filter(intervention=intervention)
                step_judgements = StepJudgement.objects.filter(step__in=steps)

                transitions = Transition.objects.filter(
                    from_step__in=steps
                ) | Transition.objects.filter(to_step__in=steps)
                judgements = Judgement.objects.filter(intervention=intervention)
                examples = Example.objects.filter(intervention=intervention)
                llms = LLM.objects.filter(id__in=[intervention.default_conversation_model.id])

                # Serialize all the related data
                data = serialize(
                    "yaml",
                    [intervention]
                    + list(steps)
                    + list(transitions)
                    + list(judgements)
                    + list(examples)
                    + list(step_judgements)
                    + list(llms),
                    indent=2,
                )

                # Write to the specified output file
                with open(output_file, "w") as f:
                    f.write(data)

                # Any changes made here will be reverted after exiting the transaction.atomic block
                self.stdout.write(self.style.SUCCESS(f"Fixtures saved to {output_file}"))

        except Intervention.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(f"Intervention with slug '{intervention_slug}' does not exist.")
            )
        except Exception as e:
            # raise
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
