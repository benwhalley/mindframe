import logging
import json
from django.urls import reverse
from django.utils.html import escape
from mindframe.helpers import get_ordered_queryset, generate_color_palette
from mindframe.settings import BranchReasons
import hashlib

logger = logging.getLogger(__name__)


def conversation_history(node):
    """
    Get the conversation history as an iterable of turns, starting from
    the end point
    """
    from mindframe.models import Turn

    turns = reversed(list(iter_conversation_path(node, direction="up")))
    return get_ordered_queryset(Turn, [i.pk for i in turns])


def iter_conversation_path(start_turn, direction="down"):
    """
    A generator that walks the conversation tree from `start_turn` either 'up' (towards ancestors)
    or 'down' (towards descendants). This version checks for branches and chooses the
    "later" branch if it exists.

    In 'down' mode (from root to leaves), if a Turn has multiple children and one or more
    are marked `branch=True`, we pick the last-created or "latest" branch child as the next step.
    This effectively restarts the conversation along the branch path.
    """
    if direction == "up":
        node = start_turn
        while node:
            yield node
            node = node.get_parent()
    else:
        stack = [start_turn]
        while stack:
            node = stack.pop()
            yield node
            # Grab any branch children ordered by timestamp
            # Also get the non-branch children
            children = node.get_children()
            branch_child = children.filter(branch=True).last()
            if branch_child:
                # If there's a branch, go down that path only
                stack.append(branch_child)
            else:
                # Otherwise pick the first main child (if any)
                first_main = children.filter(branch=False).order_by("timestamp").first()
                first_main and stack.append(first_main)


def create_branch(turn, reason=BranchReasons.PLAY):
    """
    Create a new 'branch' Turn that is a sibling of self (i.e. a child of self's parent).
    The new Turn is effectively a copy of the current Turn's content, but is flagged as branch=True.
    This lets us "restart" the conversation from self's parent, following this new Turn instead of
    the old one.

    It's slighly inefficient/ugly to copy the Turn in this way, but otherwise it's hard to
    keep the branching logic here rather than in views and webhook code?
    """
    parent = turn.get_parent()

    if parent is None:
        logger.warning("Can't branch at the root Turn.")
        return turn

    # Create the new child Turn, copying fields from 'self'
    new_turn = parent.add_child(
        conversation=turn.conversation,
        speaker=turn.speaker,
        text=turn.text,
        text_source=turn.text_source,
        step=turn.step,
        metadata=None,
        branch=True,
        branch_reason=reason,
    )
    new_turn.save()

    logger.info(
        f"Created a new branch Turn {new_turn.uuid} as sibling of {turn.uuid} from parent {parent.uuid}."
    )
    return new_turn


def generate_mermaid_tree(root):
    """
    Recursively generates a Mermaid.js graph definition from a Treebeard tree.
    Nodes are color-coded based on `node.step.intervention`, using sanitized class names.
    Opacity is controlled using `fill-opacity`.
    """
    edges = []
    nodes = {}
    intervention_colors = {}

    # Define a color palette (distinct hues)
    color_palette = [
        "#E63946",
        "#F4A261",
        "#2A9D8F",
        "#264653",
        "#E9C46A",
        "#9B5DE5",
        "#F15BB5",
        "#00BBF9",
        "#00F5D4",
        "#8AC926",
    ]

    def sanitize_intervention_name(intervention):
        intervention = str(intervention)
        """Converts an intervention name into a valid Mermaid.js class name."""
        clean_name = "".join(c if c.isalnum() else "_" for c in intervention)
        if len(clean_name) > 20:  # Keep it short if needed
            hash_suffix = hashlib.md5(intervention.encode()).hexdigest()[:6]
            clean_name = clean_name[:14] + "_" + hash_suffix
        return clean_name

    def get_color_for_intervention(intervention):
        """Assign a unique color to each intervention."""
        sanitized_name = sanitize_intervention_name(intervention)
        if sanitized_name not in intervention_colors:
            color = color_palette[len(intervention_colors) % len(color_palette)]
            intervention_colors[sanitized_name] = color
        return intervention_colors[sanitized_name], sanitized_name

    def traverse(node):
        """Recursively process the tree"""
        node_id = f"node_{node.pk}"
        safe_label = escape(f"{node.uuid[:5]}: {node.text}")
        node_link = reverse("conversation_detail", args=[node.uuid])

        intervention = getattr(node.step, "intervention", "default")
        node_color, sanitized_name = get_color_for_intervention(intervention)

        nodes[node_id] = (
            f'{node_id}["<a href="{node_link}">{safe_label}</a>"]:::intervention_{sanitized_name}'
        )

        for child in node.get_children():
            child_id = f"node_{child.pk}"
            edges.append(f"{node_id} --> {child_id}")
            traverse(child)

    traverse(root)

    mermaid_code = "graph TD;\n" + "\n".join(nodes.values()) + "\n" + "\n".join(edges)

    # Add style definitions with fill-opacity
    for sanitized_name, color in intervention_colors.items():
        mermaid_code += f"\nclassDef intervention_{sanitized_name} fill:{color},stroke:#333,stroke-width:2px,fill-opacity:0.3;"

    return mermaid_code


def generate_d3_tree_data(root):
    """
    Recursively builds a JSON structure for D3.js tree layout.
    """

    def traverse(node):
        """Recursive function to build the tree structure."""
        return {
            "name": escape(f"{node.uuid[:5]}: {node.text}"),
            "url": reverse("conversation_detail", args=[node.uuid]),
            "children": [traverse(child) for child in node.get_children()],
        }

    tree_data = traverse(root)
    return json.dumps(tree_data, indent=2)  # Pretty-print for debugging


def generate_treant_tree_data(root):
    """
    Recursively builds a JSON structure suitable for Treant.js.
    """

    step_ids = root.conversation.turns.all().values_list("step__pk", flat=True)
    pal = generate_color_palette(len(step_ids))
    step_colors = dict(zip(step_ids, pal))

    def traverse(node):
        """Recursive function to build tree structure."""
        return {
            # Provide the custom innerHTML outside the text dict so Treant will use it.
            "innerHTML": f"""
                <div class="node-content">
                    <a id="node-{node.uuid}" />
                    <a href="{reverse('conversation_detail', args=[node.uuid])}"
                        style="color:{step_colors.get(node.step and node.step.pk or None)};"
                       class="node-title">{node.uuid[:4]}
                    </a>
                    <div class="node-description">
                    {node.speaker.username.upper()}:
                    {node.text}
                    </div>
                </div>
            """,
            # "text": {
            #     # These can serve as fallback values.
            #     "name": f"{node.uuid[:5]}",
            #     "desc": node.text,
            # },
            # "link": {"href": reverse("conversation_detail", args=[node.uuid])},
            "HTMLclass": "turn",
            "children": [traverse(child) for child in node.get_children()],
        }

    tree_data = {
        "chart": {
            "container": "#tree-container",
            "rootOrientation": "NORTH",  # Tree grows downwards
            "nodeAlign": "TOP",
            "connectors": {"type": "curve"},
            "collapsable": True,
            "animation": {"nodeAnimation": "easeOutBounce", "connectorsAnimation": "bounce"},
        },
        "nodeStructure": traverse(root),
    }

    return json.dumps(tree_data, indent=2)


if False:
    from mindframe.models import Turn
    from mindframe.tree import generate_mermaid_tree

    print(generate_mermaid_tree(Turn.objects.get(uuid="7nsthysqh8a8wcxpeh3qr6rdx1").get_root()))
