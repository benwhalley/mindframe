from mindframe.models import Turn, CustomUser, Transition, LLM, Note
import traceback
import logging
from itertools import islice
from mindframe.settings import mfuuid
from mindframe.helpers import make_data_variable, get_ordered_queryset
from llmtools.llm_calling import chatter
from mindframe.tree import conversation_history, iter_conversation_path


logger = logging.getLogger(__name__)


def pick_speaker_for_next_response(turn: Turn):
    try:
        hist = iter_conversation_path(turn, direction="up")
        _, previous = next(hist), next(hist)
        return previous.speaker
    except Exception as e:
        logger.error("No previous speaker found in conversation history.")
        logger.error(str(e))
        logger.error(str(traceback.format_exc()))
        # TODO: don't raise?
        raise
    # TODO:
    # - implement logic for choosing a speaker in group conversations
    # - pick a therapist?


def transition_permitted(transition, turn) -> bool:
    # Test whether the conditions for a Transition are met at this Turn

    # we can only use the speaker context
    # (we don't know what the client thought, just what they said)
    ctx_data = speaker_context(turn).get("data")

    # clean up the conditions (defined as strings) and evaluate them
    clean_conditions = list(map(str.strip, filter(bool, transition.conditions.split("\n"))))
    try:
        condition_evals = [(c, eval(c, {}, ctx_data)) for c in clean_conditions]
        logger.info(f"Transition condition evaluations for {transition}:\n {condition_evals}")
        return all([i[1] for i in condition_evals])
    except Exception as e:
        logger.error(str(e))
        return False


def evaluate_judgement(judgement, turn):
    ctx = speaker_context(turn)
    # TODO: fix this model pick
    model = LLM.objects.filter(model_name="gpt-4o-mini").first()
    llmres = chatter(
        judgement.prompt_template,
        model=model,
        context=ctx,
    )
    nt = Note.objects.create(turn=turn, judgement=judgement, data=llmres)
    return nt

def complete_the_turn(turn):
    # use context so far to complete a Step in a conversation; Return the completed Turn

    ctx = speaker_context(turn)
    # TODO: fix this model pick
    model = LLM.objects.filter(model_name="gpt-4o-mini").first()
    llmres = chatter(
        turn.step.prompt_template,
        model=model,
        context=ctx,
    )
    turn.metadata = llmres
    turn.text = llmres.response
    turn.save()
    return turn
    

def possible_transitions(turn: Turn):
    history_list = list(iter_conversation_path(turn.get_root(), direction="down"))
    history = get_ordered_queryset(Turn, [i.pk for i in history_list])
    possibles = turn.step.transitions_from.all()
    for i in possibles:
        i.permitted = transition_permitted(i, turn)
    return Transition.objects.filter(pk__in=[i.pk for i in possibles if i.permitted == True])


def speaker_context(turn):

    # a Turn is created with a history of previous turns, and for a specific speaker
    # this means we can navigate up the tree to identify context which this speaker
    # would have access to when making their contribution

    history_list = list(iter_conversation_path(turn.get_root(), direction="down"))
    history = get_ordered_queryset(Turn, [i.pk for i in history_list])

    speaker_turns = history.filter(speaker=turn.speaker)
    speaker_notes = Note.objects.filter(turn__pk__in=[i.pk for i in speaker_turns])

    context = {
        "current_turn": turn,
        "turns": history,
        "speaker_turns": speaker_turns,
        "data": make_data_variable(speaker_notes),
    }
    return context


def respond(turn: Turn, as_speaker: CustomUser = None):
    """
    Respond to a particular turn in the conversation. Returns the new completed Turn object.

    If `as_speaker` is not provided, the system will pick the last-but-one speaker in the conversation.

    """

    if not as_speaker:
        as_speaker = pick_speaker_for_next_response(turn)

    # get turns made by this speaker and the step they are on
    spkr_history = conversation_history(turn).filter(speaker=as_speaker)
    speakers_prev_step = spkr_history and list(reversed(list(spkr_history))).pop().step or None
    if not speakers_prev_step:
        raise NotImplementedError("No Step/intervention found to use for response.")

    # prepare an 'empty' turn ready for completion
    new_turn = turn.add_child(
        uuid=mfuuid(),
        conversation=turn.conversation,
        speaker=as_speaker,
        text="... thinking ...",
        step=speakers_prev_step,
    )
    # turn = new_turn
    # run all the judgements and make notes
    judgments_to_make = new_turn.step.judgements.all()
    notes = [evaluate_judgement(j, new_turn) for j in judgments_to_make]
    
    # get the possible transitions, and if there is one possible, mutate the new_turn: 
    # jump to that step and save before completing the turn
    transitions_possible = possible_transitions(new_turn)
    if transitions_possible.count() > 1:
        new_turn.step = transitions_possible.first().to_step
        new_turn.save()
    
    new_turn_complete = complete_the_turn(new_turn)
    return new_turn_complete
