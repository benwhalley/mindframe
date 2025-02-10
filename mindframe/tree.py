from mindframe.helpers import get_ordered_queryset

# TODO: add annotations


def conversation_history(node):
    """
    Get the conversation history as an iterable of turns, starting from
    the an end point
    """
    from mindframe.models import Turn

    turns = iter_conversation_path(node.get_root(), direction="down")
    return get_ordered_queryset(Turn, [i.pk for i in turns])


def iter_conversation_path(node, direction="down"):
    """
    Iterates through a conversation tree in a given direction.

    - If `direction="down"` (default), it follows the first path from root to tip.
    - If `direction="up"`, it follows the path from a given node back to the root.

    Always returns the starting node as the first in the iterable.

    :param node: The starting node (root for down, tip for up).
    :param direction: "down" (default) for depth-first, "up" for parent traversal.
    :return: An iterator over nodes in the specified order.
    """
    if direction == "down":
        while node:
            yield node
            children = node.get_children()
            node = children.first() if children.exists() else None  # Take first child
    elif direction == "up":
        while node:
            yield node
            node = node.get_parent()  # Move to parent
    else:
        raise ValueError("Invalid direction. Use 'down' or 'up'.")
