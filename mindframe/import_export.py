import io
import os

from rest_framework import serializers
from mindframe.models import Intervention, Step, Judgement, Example, Transition, StepJudgement

from ruamel.yaml import YAML

yaml = YAML()
# yaml.default_flow_style = False  # Use block style
# yaml.width = 4096  # Avoid wrapping long lines into multiple lines
# yaml.representer.add_representer(
#     str, lambda dumper, data: dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
# )


def yaml_dumps(data):
    """
    Serialize Python objects to a YAML-formatted string.

    Args:
        data (dict): The data to serialize.

    Returns:
        str: The serialized YAML string.
    """
    stream = io.StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


class TransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transition
        fields = ["from_step", "to_step", "conditions"]


class JudgementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Judgement
        fields = ["title", "variable_name", "prompt_template"]  # Specify fields manually


class StepJudgementSerializer(serializers.ModelSerializer):
    judgement = JudgementSerializer()

    class Meta:
        model = StepJudgement
        fields = ["judgement", "when", "once"]


class StepSerializer(serializers.ModelSerializer):
    judgements = StepJudgementSerializer(source="stepjudgements", many=True)
    transitions_from = TransitionSerializer(
        many=True,
    )

    class Meta:
        model = Step
        fields = [
            "title",
            "prompt_template",
            "judgements",
            "transitions_from",
        ]  # Specify fields manually


class ExampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Example
        fields = ["title", "text"]  # Specify fields manually


class InterventionSerializer(serializers.ModelSerializer):
    steps = StepSerializer(many=True)
    examples = ExampleSerializer(many=True)

    class Meta:
        model = Intervention
        fields = ["title", "short_title", "sem_ver", "steps", "examples"]  # Specify fields manually


def intervention_serial(intervention_id):
    intervention = Intervention.objects.prefetch_related(
        "steps",
        # "examples",
        "steps__stepjudgements__judgement",
        "steps__transitions_from",
    ).get(id=intervention_id)
    serializer = InterventionSerializer(intervention)

    return serializer.data


with open(os.path.expanduser("~/Downloads/intervention.yaml"), "w") as f:
    f.write(yaml_dumps(intervention_serial(22)))
