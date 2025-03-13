from django.db.models import Q
from django.urls import reverse

from mindframe.models import Transition, Step, Intervention


def mermaid_diagram(obj: Intervention, highlight: Step = None):
    """
    Renders a Mermaid diagram for the intervention.
    """
    # Generate Mermaid syntax for the diagram
    steps = obj.steps.all()
    for i in steps:
        i.highlight = i == highlight
    transitions = Transition.objects.filter(
        Q(from_step__intervention=obj) | Q(to_step__intervention=obj)
    )

    diagram = [
        """
---
config:
  look: handDrawn
  theme: neutral
---


graph TD

classDef conditions fill:none,color:green,stroke:none, font-size:10px;
classDef judgement fill:none,color:red,stroke:none, font-size:10px;
classDef smallText fill:none,color:black,stroke:none, font-size:10px;linkStyle default stroke-width:1px,font-size:10px;
classDef highlighted fill:#ffeeee,color:red,stroke:red,stroke-width:2px;
        linkStyle default stroke-width:1px,font-size:10px;
classDef conditionText fill:none,color:green,stroke:none, font-size:12px;



"""
    ]

    for step in steps:
        diagram.append(
            f'{step.slug.replace("-", "_")}["{step.title}{step.highlight and " *" or ""}"]'
        )
        diagram.append(
            f'click {step.slug.replace("-", "_")} "{reverse("step_detail", args=[step.pk])}" "Goog"'
        )
        if step.highlight:
            diagram.append(f'class {step.slug.replace("-", "_")} highlighted;')

    for transition in transitions:
        from_slug = transition.from_step.slug.replace("-", "_")
        to_slug = transition.to_step.slug.replace("-", "_")
        conditions = transition.conditions or "No conditions set!!"
        # Escape quotes in conditions
        conditions = conditions.replace('"', "'")
        diagram.append(f'{from_slug} -->|"{conditions}"| {to_slug}')

        judgement_str = "&nbsp;" + "<br>".join(
            [i.variable_name for i in transition.from_step.judgements.all()]
        )
        diagram.append(f"{from_slug}_judgements -.- {from_slug}")
        diagram.append(f"class {from_slug}_judgements judgement;")
        diagram.append(f"{from_slug}_judgements({judgement_str})")

        if not transition.from_step:
            judgement_str = "J:" + "<br>".join(
                [i.variable_name for i in transition.to_step.judgements.all()]
            )
            diagram.append(f"{to_slug}_judgements -.-> {to_slug}")
            diagram.append(f"class {to_slug}_judgements judgement;")
            diagram.append(f"{to_slug}_judgements({judgement_str})")

    mermaid_code = "\n".join(diagram)

    # Render Mermaid container and script
    return mermaid_code
