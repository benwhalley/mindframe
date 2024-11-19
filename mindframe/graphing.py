def generate_intervention_mermaid_diagram(intervention):
    """
    Generates a Mermaid diagram for an intervention, showing steps as nodes and transitions as edges
    labeled with their conditions.

    Args:
        intervention: An Intervention object to generate the diagram for.

    Returns:
        A string representing the Mermaid diagram.
    """
    steps = intervention.steps.all()
    transitions = Transition.objects.filter(
        Q(from_step__intervention=intervention) | Q(to_step__intervention=intervention)
    )

    # Start the Mermaid diagram
    diagram = ["graph TD"]
    diagram.append(
        f'    title("{intervention.title} ({intervention.sem_ver}/{intervention.ver()})")'
    )

    # Add nodes for each step
    for step in steps:
        diagram.append(f'    {step.slug}["{step.title}"]')

    # Add edges for each transition
    for transition in transitions:
        from_slug = transition.from_step.slug
        to_slug = transition.to_step.slug
        cnd = transition.conditions.replace('"', "").replace("'", "").split("\n") or []
        print(transition.conditions)
        conditions = "; ".join(cnd)
        diagram.append(f'    {from_slug} -->|"{conditions}"| {to_slug}')

    return "\n".join(diagram)


# Example usage
intervention = Intervention.objects.get(pk=22)
print(generate_intervention_mermaid_diagram(intervention))
