from django.db.models import Q
from mindframe.models import Transition


def mermaid_diagram(obj):
    """
    Renders a Mermaid diagram for the intervention.
    """
    # Generate Mermaid syntax for the diagram
    steps = obj.steps.all()
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
"""
    ]

    for step in steps:
        diagram.append(f'{step.slug.replace("-", "_")}["{step.title}"]')
        diagram.append(f'click {step.slug.replace("-", "_")} "{step.get_absolute_url()}" "Goog"')

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
        diagram.append(f"{from_slug}_judgements --> {from_slug}")
        diagram.append(f"class {from_slug}_judgements,{from_slug} noArrow;")
        diagram.append(f"class {from_slug}_judgements judgement;")
        diagram.append(f"{from_slug}_judgements({judgement_str})")

        if not transition.from_step:
            judgement_str = "J:" + "<br>".join(
                [i.variable_name for i in transition.to_step.judgements.all()]
            )
            diagram.append(f"{to_slug}_judgements --> {to_slug}")
            diagram.append(f"class {to_slug}_judgements,{to_slug} noArrow;")
            diagram.append(f"class {to_slug}_judgements judgement;")
            diagram.append(f"{to_slug}_judgements({judgement_str})")

    diagram.append(
        """
classDef judgement fill:none,color:red,stroke:none, font-size:10px;
classDef smallText fill:none,color:black,stroke:none, font-size:10px;linkStyle default stroke-width:1px,font-size:10px;
classDef noArrow dotted;

"""
    )

    mermaid_code = "\n".join(diagram)

    # Render Mermaid container and script
    return mermaid_code
