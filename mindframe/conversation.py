from typing import Optional
from collections import OrderedDict
import pprint
from django.db.models import QuerySet
from mindframe.models import (
    Turn,
    CustomUser,
    Transition,
    LLM,
    Note,
    Conversation,
    Intervention,
    Step,
)
from mindframe.silly import silly_user
import traceback
import logging
from itertools import cycle
from django.shortcuts import get_object_or_404
from mindframe.settings import mfuuid, StepJudgementFrequencyChoices, RoleChoices
from mindframe.helpers import make_data_variable, get_ordered_queryset
from llmtools.llm_calling import chatter
from mindframe.tree import conversation_history, iter_conversation_path
from mindframe.settings import (
    TurnTextSourceTypes,
    DEFAULT_CONVERSATION_MODEL_NAME,
    DEFAULT_JUDGEMENT_MODEL_NAME,
)
from langfuse.decorators import langfuse_context, observe

from celery import shared_task

logger = logging.getLogger(__name__)


def pick_speaker_for_next_response(turn: Turn):
    """Decide who should respond next in the conversation.

    In simple cases this should be really straightforward: the bot alternates
    with the client. However, in (future) group conversations between humans
    and multiple bots we might want additional logic here.
    """

    # return the previous-but-one speaker
    try:
        hist = conversation_history(turn)
        prev_speaker = hist.exclude(speaker=turn.speaker).last().speaker
        return prev_speaker
    except Exception as e:
        logger.error("No speaker found to respond with.")
        logger.error(str(e))
        logger.error(str(traceback.format_exc()))
    # TODO:
    # - implement logic for choosing a speaker in group conversations
    # - pick a therapist?


def transition_permitted(transition, turn) -> bool:
    # Test whether the conditions for a Transition are met at this Turn

    ctx_data = speaker_context(turn).get("data")
    logger.info(f"Checking transition {transition} with context data: {ctx_data}")
    clean_conditions = [cond.strip() for cond in transition.conditions.splitlines() if cond.strip()]

    condition_evals = []
    for cond in clean_conditions:
        logger.info(f"Evaluating condition '{cond}'")
        logger.info(pprint.pformat(ctx_data, width=1))
        try:
            result = eval(cond, {}, ctx_data)
            logger.info(f"{cond} is {result}")
            condition_evals.append((cond, result))
        except Exception as e:
            logger.error(f"Error evaluating condition '{cond}': {e}")
            condition_evals.append((cond, False))

    return all(result for _, result in condition_evals)


def get_model_for_turn(turn, type_="conversation") -> LLM:

    interv = turn.step and turn.step.intervention or None
    if type_.startswith("con"):
        return LLM.objects.filter(
            model_name=turn.step
            and interv.default_conversation_model
            or DEFAULT_CONVERSATION_MODEL_NAME
        ).first()
    elif type_.startswith("jud"):
        return LLM.objects.filter(
            model_name=turn.step and interv.default_judgement_model or DEFAULT_JUDGEMENT_MODEL_NAME
        ).first()
    else:
        raise NotImplementedError("Model type not recognised.")


@observe(capture_input=False, capture_output=False)
def evaluate_judgement(judgement, turn):
    ctx = speaker_context(turn)
    # TODO: fix this model pick

    model = get_model_for_turn(turn, "judgement")
    llmres = chatter(
        judgement.prompt_template,
        model=model,
        context=ctx,
    )
    nt = Note.objects.create(turn=turn, judgement=judgement, data=llmres)
    return nt


@observe(capture_input=False, capture_output=False)
def complete_the_turn(turn) -> Turn:
    """
    Make an AI-generated completion.

    Use context so far to complete a Step in a conversation. Return the completed Turn.
    """

    ctx = speaker_context(turn)
    model = get_model_for_turn(turn, "conversation")
    llmres = chatter(
        turn.step.prompt_template,
        model=model,
        context=ctx,
    )
    turn.metadata = llmres
    turn.text = llmres.response
    turn.save()
    return turn


def possible_transitions(turn: Turn) -> QuerySet[Transition]:
    history_list = list(iter_conversation_path(turn.get_root(), direction="down"))
    history = get_ordered_queryset(Turn, [i.pk for i in history_list])
    possibles = turn.step.transitions_from.all()
    for i in possibles:
        i.permitted = transition_permitted(i, turn)

    pos_trans_qs = Transition.objects.filter(
        pk__in=[i.pk for i in possibles if i.permitted == True]
    )
    logger.info(f"Possible transitions: {pos_trans_qs}")
    return pos_trans_qs


def speaker_context(turn) -> dict:
    # a Turn is created with a history of previous turns, and for a specific speaker
    # this means we can navigate up the tree to identify context which this speaker
    # would have access to when making their contribution

    history_list = conversation_history(turn)
    history = get_ordered_queryset(Turn, [i.pk for i in history_list])

    speaker_turns = history.filter(speaker=turn.speaker)
    speaker_notes = Note.objects.filter(turn__pk__in=[i.pk for i in speaker_turns])

    # find the first turn with the same step, then count how many descendents it has in the history to count N turns from the start of this Step; +1 to include the first in the count
    try:
        n_turns_step = (
            history.filter(depth__gt=history.filter(step=turn.step).first().depth).count() + 1
        )
    except:
        n_turns_step = None

    context = {
        "current_turn": turn,
        "turns": history,
        "n_turns_step": n_turns_step,
        "n_turns": history.count(),
        "speaker_turns": speaker_turns,
        "data": make_data_variable(speaker_notes),
    }
    logger.info(f"Prompt context:\n{pprint.pformat(context, width=1)}")
    return context


def listen(turn, text, speaker) -> Turn:
    """Accept user input in response to a Turn, return a new Turn which saves it."""

    return turn.add_child(conversation=turn.conversation, speaker=speaker, text=text)


@observe(capture_input=False, capture_output=False)
def respond(turn: Turn, as_speaker: CustomUser = None, with_intervention_step=None) -> Turn:
    """
    Respond to a particular turn in the conversation. Returns the new completed Turn object.

    If `as_speaker` is not provided, the system will pick the last-but-one speaker in the conversation.

    """

    if not as_speaker:
        as_speaker = pick_speaker_for_next_response(turn)

    if not with_intervention_step:
        # get turns made by this speaker and the step they are on
        spkr_history = conversation_history(turn).filter(speaker=as_speaker)
        speakers_prev_turn = spkr_history.filter(step__isnull=False).last()
        speakers_prev_step = speakers_prev_turn and speakers_prev_turn.step or None
        if not speakers_prev_step:
            if turn.conversation.synthetic_client:
                speakers_prev_step = turn.conversation.synthetic_client.steps.all().first()
                logger.info(
                    f"Using synthetic client intervention's first step: {speakers_prev_step}"
                )
            else:
                raise NotImplementedError("No Step/intervention found to use for response.")
        with_intervention_step = speakers_prev_step

    # prepare an 'empty' turn ready for completion
    new_turn = turn.add_child(
        uuid=mfuuid(),
        conversation=turn.conversation,
        speaker=as_speaker,
        text="... thinking ...",
        step=with_intervention_step,
        text_source=TurnTextSourceTypes.GENERATED,
    )
    new_turn.save()
    logger.info(f"New turn created: {new_turn.uuid}")

    # run all the judgements to be made every Turn and ignore the Notes they produce
    judgements_to_make = [
        i.judgement
        for i in new_turn.step.stepjudgements.filter(when=StepJudgementFrequencyChoices.TURN)
    ]
    [evaluate_judgement(j, new_turn) for j in judgements_to_make]

    # get the possible transitions, and if there is one possible
    transitions_possible = possible_transitions(new_turn)
    new_turn = apply_step_transition_and_judgements(new_turn, transitions_possible)

    # do the final completion, using all the new context available from Judgements
    new_turn_complete = complete_the_turn(new_turn)
    logger.info(f"Finalized new turn UUID: {new_turn_complete.uuid}")

    run_offline_judgements(new_turn_complete.pk)

    # ensure all the langfuse traces are identifiable by the Turn uuid
    langfuse_context.update_current_observation(
        name=f"Response in turn: {new_turn_complete.uuid}",  # Use new turn ID
        session_id=new_turn_complete.uuid,  # Make sure the session ID is correct
        output=new_turn_complete.text,
    )
    langfuse_context.flush()

    return new_turn_complete


def apply_step_transition_and_judgements(turn, transitions_possible) -> Turn:
    """
    Update progress in the conversation.
    Take a Turn and a list of transitions. Mutate the Turn to change the Step for the
    Turn if needed, running the appropriate Judgements first.
    """

    if transitions_possible.count() == 0:
        logger.info("No possible transitions found for this step.")
    else:
        # run the Turn-exit judgements
        judgements_to_make = [
            i.judgement
            for i in turn.step.stepjudgements.filter(when=StepJudgementFrequencyChoices.EXIT)
        ]
        [evaluate_judgement(j, turn) for j in judgements_to_make]
        transition_selected = transitions_possible.first()
        turn.step = transition_selected.to_step
        turn.save()
        logger.warning(
            f"Moved to new step: {transition_selected.to_step} from {transition_selected.from_step} "
        )

        # run the Turn-enter judgements
        judgements_to_make = [
            i.judgement
            for i in turn.step.stepjudgements.filter(when=StepJudgementFrequencyChoices.ENTER)
        ]
        [evaluate_judgement(j, turn) for j in judgements_to_make]
    return turn


@shared_task
@observe(capture_input=False, capture_output=False)
def run_offline_judgements(turn_pk):
    turn = Turn.objects.get(pk=turn_pk)
    logger.info(f"Running offline judgements for {turn}")
    judgements_to_make = turn.step.stepjudgements.filter(
        when=StepJudgementFrequencyChoices.OFFLINE_STEP
    ).values("judgement")
    notes = [evaluate_judgement(j, turn) for j in judgements_to_make]
    logger.info(notes)
    langfuse_context.update_current_observation(session_id=turn.uuid)
    langfuse_context.flush()


def add_turns(turn, n_turns: int) -> Turn:
    if not turn.conversation.is_synthetic:
        logger.warning("Adding turns to a non-synthetic conversation.")
        turn.conversation.is_synthetic = True
        turn.conversation.save()

    for i in range(n_turns):
        turn = respond(turn)
        # refetch the object to ensure all the tree information
        # is refreshed and doesn't case a problem when trying to
        # add subsequent children
        turn = Turn.objects.get(pk=turn.pk)
        logger.info(f"Added turn: {turn.pk}, dpt:{turn.depth}, step: {turn.step}")

    return turn


@shared_task
def add_turns_task(turn_pk: int, n_turns: int):
    """
    Celery task to add N additional turns to a synthetic conversation.
    """
    turn = get_object_or_404(Turn, pk=turn_pk)
    add_turns(turn, n_turns)
    turn.conversation.synthetic_turns_scheduled = (
        turn.conversation.synthetic_turns_scheduled - n_turns
    )
    turn.conversation.save()


def start_conversation(
    step: Step,
    therapist: Optional[CustomUser] = None,
    client: Optional[CustomUser] = None,
    client_step: Optional[Step] = None,
) -> Turn:
    """
    Create a new conversation between a therapist and a (real or synthetic) client, starting from specific Intervention Steps.
    """

    # it's a synthetic conversation if we use an intervention for the client
    synth = bool(client_step)
    conversation = Conversation.objects.create(is_synthetic=synth)
    if not therapist:
        therapist, new_ = CustomUser.objects.get_or_create(
            username="Linda", role=RoleChoices.THERAPIST
        )

    if not client:
        client = silly_user()

    turn = Turn.add_root(
        conversation=conversation,
        speaker=client,
        text="/start",
        text_source=TurnTextSourceTypes.OPENING,
    )
    turn = turn.add_child(
        conversation=turn.conversation, speaker=therapist, text=step.opening_line, step=step
    )

    return turn


def continue_conversation(from_turn, speaker_interventions, n_turns) -> Turn:
    """
    Generates additional turns using the selected interventions for each speaker.
    speaker_interventions is a dictionary of {speaker_username: intervention}
    """

    logger.info(f"Continuing conversation from turn {from_turn.pk}/{from_turn.uuid[:5]}")

    # TODO: maybe update pick_speaker_for_next_response to use this logic instead
    all_speakers = [CustomUser.objects.get(username=k) for k in speaker_interventions.keys()]
    all_speakers = [s for s in all_speakers if s != from_turn.speaker] + [from_turn.speaker]
    speakers = cycle(all_speakers)
    interventions = cycle(speaker_interventions.values())

    for i, speak, inter in zip(range(n_turns), speakers, interventions):
        from_turn = respond(
            from_turn, as_speaker=speak, with_intervention_step=inter.steps.all().first()
        )

    return from_turn


@shared_task
def continue_conversation_task(from_turn_id, speaker_interventions, n_turns):
    """
    Task to call continue_conversation
    speaker_interventions is a dictionary of {speaker_username: intervention_pk}
    """

    from_turn = Turn.objects.get(pk=from_turn_id)
    speaker_interventions = {
        k: Intervention.objects.get(pk=v) for k, v in speaker_interventions.items()
    }

    newleaf = continue_conversation(from_turn, speaker_interventions, n_turns)
    logger.info("Resetting number of scheduled turns")
    newleaf.conversation.synthetic_turns_scheduled = 0
    newleaf.conversation.save()
    return True
