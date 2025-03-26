import logging
import pprint
import traceback
from collections import OrderedDict
from itertools import cycle
from typing import List, Optional

from celery import shared_task
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from langfuse.decorators import langfuse_context, observe

from llmtools.llm_calling import chatter
from mindframe.helpers import get_ordered_queryset, make_data_variable
from mindframe.models import LLM, Conversation, CustomUser, Judgement, Note, Step, Transition, Turn
from mindframe.settings import (
    DEFAULT_CONVERSATION_MODEL_NAME,
    DEFAULT_JUDGEMENT_MODEL_NAME,
    InterventionTypes,
    RoleChoices,
    StepJudgementFrequencyChoices,
    TurnTypes,
    mfuuid,
)
from mindframe.silly import silly_user
from mindframe.tree import conversation_history, is_interrupted, iter_conversation_path

logger = logging.getLogger(__name__)


def pick_speaker_for_next_response(turn: Turn):
    """Decide who should respond next in the conversation.

    In simple cases this should be really straightforward: the bot alternates
    with the client. However, in (future) group conversations between humans
    and multiple bots we might want additional logic here.
    """
    candidates = turn.conversation.speakers().filter(role=RoleChoices.BOT)
    if candidates.count():
        return candidates.first()
    else:
        raise Exception("No Bot speaker found to use for the response")
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
    model = judgement.model or get_model_for_turn(turn, "judgement")
    llmres = chatter(
        judgement.prompt_template,
        model=model,
        context=ctx,
    )
    nt = Note.objects.create(turn=turn, judgement=judgement, data=llmres)
    return nt


@shared_task
def evaluate_judgement_task(judgement_pk, turn_pk):
    judgement = Judgement.objects.get(pk=judgement_pk)
    turn = Turn.objects.get(pk=turn_pk)
    return evaluate_judgement(judgement, turn)


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


def judgement_applied_n_turns_ago(turn, judgement):
    """
    Returns how many turns ago the given judgement was last run in this conversation.

    - If the judgement was never run, return -1.
    - Otherwise, return the number of turns ago it was last run.
    """
    hist = conversation_history(turn)
    last_note = Note.objects.filter(turn__in=hist).filter(judgement=judgement).last()
    if last_note:
        return turn.depth - last_note.turn.depth
    else:
        return -1


@observe(capture_input=False, capture_output=False)
def respond(
    turn: Turn,
    as_speaker: Optional[CustomUser] = None,
    with_intervention_step: Optional[Step] = None,
    text: Optional[str] = None,
) -> Turn:
    """
    Respond to a particular turn in the conversation. Returns the new completed Turn object.

    If `as_speaker` is not provided, the system will try to automatically identify a speaker and Step to use.

    """

    if not as_speaker:
        # this will be a Bot
        as_speaker = pick_speaker_for_next_response(turn)

    if not with_intervention_step:
        try:
            spkr_history = conversation_history(turn).filter(speaker=as_speaker)
            speakers_prev_turn = spkr_history.filter(step__isnull=False).last()
            speakers_prev_step = speakers_prev_turn and speakers_prev_turn.step or None
            with_intervention_step = (
                speakers_prev_step or as_speaker.intervention.steps.all().first()
            )
        except Exception:
            logger.error("Chosen speaker doesn't have an intervention/step to use")
            raise

    # prepare an 'empty' turn ready for completion
    new_turn = turn.add_child(
        uuid=mfuuid(),
        conversation=turn.conversation,
        speaker=as_speaker,
        # use fixed, passed-in text if provided
        text=text or "...",
        step=with_intervention_step,
        turn_type=TurnTypes.BOT,
    )
    new_turn.save()
    logger.info(f"New turn created: {new_turn.uuid}")

    # EVALUATE INTERUPTIONS FIRST, BEFORE OTHER JUDGEMENTS
    # IF ANY INTERRUPTION JUDGMENT TRIGGERS,
    # - MARK THE CURRENT TURN AS A CHECKPOINT
    # - SWITCH TO THE TARGET STEP AND RESPOND
    possible_interruptions = with_intervention_step.intervention.interruptions.all()
    for i in possible_interruptions:
        # only do this if we're not already on the target step of the interruption
        if i.target_step == with_intervention_step:
            logger.info(
                "Skipping interruption ({i}) because we are already on the interruption's target step {with_intervention_step}."
            )
            continue

        previous_checkpoint = conversation_history(new_turn).filter(interruption=i).last()
        if previous_checkpoint and (new_turn.depth - previous_checkpoint.depth) < i.debounce_turns:
            logger.info(
                f"Skipping interruption ({i}) because it was already triggered within {i.debounce_turns}"
            )
            continue
        # if there is a judgement to evaluate, do that first, otherwise just evaluate the trigger
        # based on other judgements in context on this Turn.
        # TODO: We will probably need scoping rules for the context dictionary here.
        # E.g. how many turns back we look.
        if i.trigger_judgement:
            note = evaluate_judgement(i.trigger_judgement, new_turn)

        triggered = eval(i.trigger, {}, note.data)
        if triggered:
            logger.warning(f"Interruption {i} triggered\n{i.trigger}\n{note.data}")
            new_turn.interruption = i
            new_turn.checkpoint = True
            new_turn.save()
            return respond(new_turn, as_speaker=as_speaker, with_intervention_step=i.target_step)

    # run all the judgements to be made every Turn and ignore the Notes they produce
    judgements_to_make_with_turns_ago = [
        (i, judgement_applied_n_turns_ago(new_turn, i.judgement))
        for i in new_turn.step.stepjudgements.filter(when=StepJudgementFrequencyChoices.TURN)
    ]
    # here we filter to make sure judgements are only run when they are due
    # sometimes that is only every N turns rather than every turn
    judgements_to_make = [
        sj
        for sj, made_n_ago in judgements_to_make_with_turns_ago
        if (made_n_ago > 0 and made_n_ago > (sj.n_turns and sj.n_turns or -1))
        or (made_n_ago == -1 and new_turn.depth >= (sj.n_turns and sj.n_turns or -1))
    ]

    logger.info("Trigger offline Judgements")
    [
        evaluate_judgement_task.delay(sj.judgement.pk, new_turn.pk)
        for sj in judgements_to_make
        if sj.offline
    ]

    logger.info("Run online Judgements syncronously")
    [evaluate_judgement(sj.judgement, new_turn) for sj in judgements_to_make if not sj.offline]

    # ARE INTERRUPTIONS RESOLVED?
    # TODO: implement this
    # - check if we are in an interruption (unresolved checkpoint in the conversation history?)    # - if so, build a context dictionary using the Notes from judgements on this Turn
    # - evaluate the `resolution` for the interruption marked in the checkpoint using this context
    # - if the resolution is true, mark the checkpoint as resolved and save
    # - respond using the same speaker and step as the original checkpoint

    interrupted, checkpoint = is_interrupted(new_turn)
    if interrupted:
        logger.warning(f"We are still in an interruption: {checkpoint.interruption}")

        # run any resolution judgements prior to evaluating the resolution expression
        if checkpoint.interruption.resolution_judgement:
            note = evaluate_judgement(i.resolution_judgement, new_turn)

        # build a context dictionary using the Notes on this Turn
        # including the resolution judgement; then evaluate the resolution expression
        interruption_ctx = speaker_context(new_turn)
        try:
            resolved = eval(checkpoint.interruption.resolution, {}, interruption_ctx)
        except Exception as e:
            logger.error(f"Error evaluating resolution expression: {e}")
            resolved = False

        if resolved:  # return to where we were before
            logger.warning(
                f"The interruption is now resolved\n{checkpoint.interruption.resolution}==True\n responding with Step from checkpoint: {checkpoint.step}"
            )
            checkpoint.checkpoint_resolved = True
            checkpoint.save()

            # reset the Step to use to the step at the checkpoint when the interruption started
            new_turn.step = checkpoint.step
            new_turn.resuming_from = checkpoint
            new_turn.save()
            # we will now complete the turn as usual below

    # TRANSITIONS
    # get the possible transitions, and if there is one possible
    transitions_possible = possible_transitions(new_turn)
    new_turn = apply_step_transition_and_judgements(new_turn, transitions_possible)

    # if we didn't pass in a specific text to use as the response (e.g. in testing)
    # do the final completion, using all the new context available from Judgements
    if not text:
        new_turn = complete_the_turn(new_turn)
        logger.info(f"Finalized new turn UUID: {new_turn.uuid}")

    # ensure all the langfuse traces are identifiable by the Turn uuid
    langfuse_context.update_current_observation(
        name=f"Response in turn: {new_turn.uuid}",  # Use new turn ID
        session_id=new_turn.uuid,  # Make sure the session ID is correct
        output=new_turn.text,
    )
    langfuse_context.flush()
    
    return new_turn


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
    first_speaker: CustomUser = None,
    first_speaker_step: Optional[Step] = None,
    additional_speakers: Optional[List[CustomUser]] = list(),
) -> Turn:
    """
    Create a new conversation between a therapist and a (real or synthetic) client, starting from specific Intervention Steps.
    """

    if (not first_speaker) and (not first_speaker_step):
        raise ValueError("You must provide either a first_speaker or a first_speaker_step")

    if not first_speaker:
        first_speaker = first_speaker_step.intervention.get_bot_speaker()
    # it's a synthetic conversation if all the speakers are bots
    try:
        if all(
            [
                i.role == RoleChoices.BOT
                for i in [
                    first_speaker,
                ]
                + additional_speakers
            ]
        ):
            synth = True
    except Exception as e:
        logger.debug(f"Error checking if all speakers are bots: {e}")
        synth = False

    conversation = Conversation.objects.create(is_synthetic=synth)

    turn = Turn.add_root(conversation=conversation, speaker=first_speaker, turn_type=TurnTypes.JOIN)
    for i in additional_speakers:
        turn = turn.add_child(conversation=conversation, speaker=i, turn_type=TurnTypes.JOIN)

    if first_speaker_step:
        # if the step does't hard-code an opening line then we generate something
        if first_speaker_step.opening_line:
            turn = turn.add_child(
                conversation=conversation,
                speaker=first_speaker,
                text=first_speaker_step.opening_line,
                turn_type=TurnTypes.OPENING,
            )
        else:
            turn = complete_the_turn(turn)

    return turn


def continue_conversation(from_turn, speaker_interventions, n_turns) -> Turn:
    """
    Generates additional turns using the selected interventions for each speaker.
    speaker_interventions is a dictionary of {speaker_username: intervention}
    """

    logger.info(f"Continuing the conversation from turn {from_turn.pk}/{from_turn.uuid[:5]}")

    # TODO: maybe update pick_speaker_for_next_response to use this logic instead
    all_speakers = [CustomUser.objects.get(username=k) for k in speaker_interventions.keys()]
    all_speakers = [s for s in all_speakers if s != from_turn.speaker] + [from_turn.speaker]
    speakers = cycle(all_speakers)
    interventions = cycle(speaker_interventions.values())

    for i, speak, inter in zip(range(n_turns), speakers, interventions):
        logger.info(f"ADDING TURN: {i}, {speak}, {inter}")
        from_turn = respond(
            from_turn, as_speaker=speak, with_intervention_step=inter.steps.all().first()
        )

    return from_turn


@shared_task
def continue_conversation_task(from_turn_id, speakers_steps, n_turns):
    """
    Task to call continue_conversation
    speaker_interventions is a dictionary of {speaker_username: intervention_pk}
    """

    from_turn = Turn.objects.get(pk=from_turn_id)

    speakers = [CustomUser.objects.get(pk=i[0]) for i in speakers_steps]
    steps = [Step.objects.get(pk=i[1]) for i in speakers_steps]

    for sp, st, i in zip(cycle(speakers), cycle(steps), range(n_turns)):
        logger.info(f"ADDING TURN: {i}, {sp}, {st}")
        from_turn = respond(from_turn, as_speaker=sp, with_intervention_step=st)
        from_turn.conversation.synthetic_turns_scheduled += -1
        from_turn.conversation.save()

    return True


def begin_conversation(intervention, conversation, room_id):
    """
    Initialise a conversation with a Bot user and an opening line
    from the first step of 'intervention'.
    Returns the new opening bot turn.
    """
    bot_speaker = intervention.get_bot_speaker()

    first_step = intervention.steps.first()
    opener_text = first_step.opening_line if first_step else "Hello! (No opening line set.)"

    bot_turn = Turn.add_root(
        conversation=conversation,
        speaker=bot_speaker,
        text=opener_text,
        turn_type=TurnTypes.OPENING,
        step=first_step,
    )

    messages = [
        f"Creating a new conversation using {intervention}.",
        first_step.opening_line,
    ]
    send_telegram_message(room_id, messages)
    return bot_turn, messages
