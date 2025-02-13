import logging

from mindframe.helpers import get_ordered_queryset
from mindframe.settings import BranchReasons

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
        return None

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
