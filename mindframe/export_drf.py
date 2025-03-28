# TODO FIX BROKEN SERIALIZATION

import hashlib
import io
import itertools
import os
from collections import defaultdict

from django.db import transaction
from rest_framework import serializers
from ruamel.yaml import YAML

from mindframe.models import (
    Example,
    Intervention,
    Judgement,
    Step,
    StepJudgement,
    Transition,
)

yaml = YAML()


def yaml_dumps(data):
    stream = io.StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


def yaml_loads(yaml_string):
    stream = io.StringIO()
    stream.write(yaml_string)
    stream.seek(0)
    return yaml.load(stream)


class TransitionSerializer(serializers.ModelSerializer):
    from_step = serializers.SlugRelatedField(
        queryset=Step.objects.all(),
        slug_field="slug",
    )
    to_step = serializers.SlugRelatedField(
        queryset=Step.objects.all(),
        slug_field="slug",
    )

    class Meta:
        model = Transition
        fields = ["from_step", "to_step", "conditions"]


class JudgementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Judgement
        fields = ["title", "variable_name", "prompt_template"]


class StepJudgementSerializer(serializers.ModelSerializer):
    judgement = JudgementSerializer()

    class Meta:
        model = StepJudgement
        fields = ["judgement", "when", "once"]


class StepSerializer(serializers.ModelSerializer):
    transitions_from = TransitionSerializer(many=True)

    class Meta:
        model = Step
        fields = ["title", "slug", "prompt_template", "transitions_from"]


class ExampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Example
        fields = ["title", "text"]


class InterventionSerializer(serializers.ModelSerializer):
    steps = StepSerializer(many=True)
    judgements = serializers.SerializerMethodField()
    stepjudgements = serializers.SerializerMethodField()
    examples = ExampleSerializer(many=True)
    transitions = serializers.SerializerMethodField()

    class Meta:
        model = Intervention
        fields = [
            "title",
            "short_title",
            "sem_ver",
            "judgements",
            "stepjudgements",
            "steps",
            "examples",
            "transitions",
        ]

    def get_transitions(self, obj):
        transitions = Transition.objects.filter(
            Q(from_step__intervention=obj) | Q(to_step__intervention=obj)
        )
        return TransitionSerializer(transitions, many=True).data

    def get_judgements(self, obj):
        judgements = Judgement.objects.filter(step__intervention=obj)
        return JudgementSerializer(judgements, many=True).data

    def get_stepjudgements(self, obj):
        sj = StepJudgement.objects.filter(step__intervention=obj)
        return StepJudgementSerializer(sj, many=True).data


def intervention_serialised(intervention):
    with transaction.atomic():
        serializer = InterventionSerializer(intervention)
        serialized_data = serializer.data
        return dict(serialized_data)


xx = intervention_serialised(Intervention.objects.first())
# pprint(xx, indent=2)
# pprint(xx['judgements'], indent=2)
# pprint(xx['steps'], indent=2)
pprint(xx["stepjudgements"], indent=2)


def load_serialised_intervention(data):

    # Create or update the main Intervention object
    d = {
        "title": data["title"],
        "short_title": data["short_title"],
        "sem_ver": data["sem_ver"] + "-COPY",
    }
    intervention = Intervention.objects.create(**d)

    for d in data["judgements"]:
        d.update({"intervention": intervention})
        j = Judgement.objects.create(**d)
        print(j)

    for d in data["steps"]:
        d.update({"intervention": intervention})
        judgements = d.pop("judgements")
        raise Exception(d)
        # step = Step.objects.create(**d)

    for d in data["examples"]:
        d.update({"intervention": intervention})
        example = Example.objects.create(**d)
        print(example)
    return intervention


xx = intervention_serialised(Intervention.objects.first())

xx["steps"]

yy = load_serialised_intervention(xx)
pprint(intervention_serialised(yy))
